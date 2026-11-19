"""Mood lanes of the `mindState` interface (docs/NEXT_DECODER_THEN_BRAIN.md, D1).

Three kinds of lane, all read from an encoding on the 0.5 s step grid:
  mood.energy  a ridge direction fitted on arousal labels (DEAM 2013/14 and the MERP songs)
  mood.power   a ridge direction fitted on Emotify's GEMS "power" ratings, per clip
  mood.rest    PCA of the encoding after both anchor directions are projected out
Each lane is smoothed causally (tau 8 s, no delay; smoothing.py) and scaled to 0..1 by constants fitted
once on the training clips and stored in the model (and in the sidecar field), never per song.
Nothing here looks at a test clip: `fit` receives training arrays only.
"""
from __future__ import annotations

import numpy as np

import common
import smoothing

TAU_SECONDS = 8.0
LAG_SECONDS = 0.0
K_MAX = 16
SCALE_PERCENTILES = (1.0, 99.0)
SOURCE_STAGE1 = "stage1-smooth8"
SOURCE_BASELINE49 = "baseline49-smooth8"
SOURCE_CORE2B = "core-2b-smooth8"


class MoodModel:
    """Fitted lanes. `k` of the K_MAX rest components are used."""

    FIELDS = ("mean", "scale", "w_energy", "w_power", "b_energy", "b_power", "basis", "rest_mean",
              "components", "lane_scale")

    def __init__(self, source, columns, k=K_MAX, **arrays):
        self.source, self.columns, self.k = source, int(columns), int(k)
        for name in self.FIELDS:
            setattr(self, name, np.asarray(arrays[name], dtype=np.float64))

    def with_k(self, k):
        if not 0 <= k <= self.components.shape[0]:
            raise ValueError(f"k must be in 0..{self.components.shape[0]}")
        return MoodModel(self.source, self.columns, k, **{f: getattr(self, f) for f in self.FIELDS})

    def raw(self, x):
        """(T, d) encoding -> (T, 2 + k) unsmoothed, unscaled lanes: energy, power, rest..."""
        z = (np.asarray(x[:, :self.columns], dtype=np.float64) - self.mean) / self.scale
        perp = z - (z @ self.basis.T) @ self.basis
        rest = (perp - self.rest_mean) @ self.components[:self.k].T
        return np.column_stack([z @ self.w_energy + self.b_energy, z @ self.w_power + self.b_power, rest])

    def smoothed(self, x):
        return smoothing.smooth_delay(self.raw(x), TAU_SECONDS, LAG_SECONDS)

    def scaled(self, smoothed):
        lo, hi = self.lane_scale[:2 + self.k, 0], self.lane_scale[:2 + self.k, 1]
        return np.clip((smoothed - lo) / (hi - lo), 0.0, 1.0)

    def lanes(self, x):
        """(T, d) encoding of one song -> (T, 2 + k) lanes in 0..1 (energy, power, rest...)."""
        return self.scaled(self.smoothed(x))

    def save(self, path):
        np.savez_compressed(path, source=self.source, columns=self.columns, k=self.k,
                            **{f: getattr(self, f) for f in self.FIELDS})

    @classmethod
    def load(cls, path):
        with np.load(path) as z:
            return cls(str(z["source"]), int(z["columns"]), int(z["k"]), **{f: z[f] for f in cls.FIELDS})


def _stats(steps, columns):
    n, total, total2 = 0, 0.0, 0.0
    for a in steps:
        a = np.asarray(a[:, :columns], dtype=np.float64)
        n += len(a)
        total, total2 = total + a.sum(axis=0), total2 + (a ** 2).sum(axis=0)
    mean = total / n
    scale = np.sqrt(np.maximum(total2 / n - mean ** 2, 0.0))
    scale[scale < 1e-8] = 1.0
    return mean, scale


def _ridge_direction(z, y, groups):
    """Ridge of y on z as (direction, intercept) acting on z itself (alpha by inner folds on the training clips)."""
    alpha = common.choose_alpha(z, y, groups)
    std = common.Standardizer().fit(z)
    w, b = common.ridge_fit(std(z), y, alpha)
    return w[:, 0] / std.scale, float(b[0] - (std.mean / std.scale) @ w[:, 0])


def lane_range(lanes):
    """(lanes, 2) lo and hi: the 1st and 99th percentile of each training lane; a lane that never varies gets width 1."""
    lo, hi = np.percentile(lanes, SCALE_PERCENTILES, axis=0)
    return np.column_stack([lo, np.where(hi > lo, hi, lo + 1.0)])


def fit(steps, arousal, power, source=SOURCE_STAGE1, columns=None, k=K_MAX):
    """Fit the lanes on training data only.
    steps    list of (T, d) encodings of the training clips (energy/power scaling and PCA use every step)
    arousal  (X, y, groups): encoding rows with their arousal labels, grouped by clip
    power    (X, y): clip-mean encodings with their Emotify power rating
    """
    columns = steps[0].shape[1] if columns is None else columns
    mean, scale = _stats(steps, columns)
    z_of = lambda a: (np.asarray(a[:, :columns], dtype=np.float64) - mean) / scale
    xa, ya, ga = arousal
    xp, yp = power
    w_e, b_e = _ridge_direction(z_of(xa), np.asarray(ya, dtype=np.float64)[:, None], ga)
    w_p, b_p = _ridge_direction(z_of(xp), np.asarray(yp, dtype=np.float64)[:, None], np.arange(len(xp)))
    u1 = w_e / np.linalg.norm(w_e)
    v = w_p - (w_p @ u1) * u1
    u2 = v / np.linalg.norm(v)
    basis = np.stack([u1, u2])

    cov, n, total = np.zeros((columns, columns)), 0, np.zeros(columns)
    for a in steps:
        z = z_of(a)
        p = z - (z @ basis.T) @ basis
        total += p.sum(axis=0)
        n += len(p)
    rest_mean = total / n
    for a in steps:
        z = z_of(a)
        p = (z - (z @ basis.T) @ basis - rest_mean).astype(np.float32)
        cov += (p.T @ p).astype(np.float64)
    values, vectors = np.linalg.eigh(cov / max(n - 1, 1))
    components = vectors[:, np.argsort(values)[::-1][:K_MAX]].T

    model = MoodModel(source, columns, K_MAX, mean=mean, scale=scale, w_energy=w_e, w_power=w_p,
                      b_energy=b_e, b_power=b_p, basis=basis, rest_mean=rest_mean, components=components,
                      lane_scale=np.tile([0.0, 1.0], (2 + K_MAX, 1)))
    lanes = np.concatenate([model.smoothed(a) for a in steps])
    model.lane_scale = lane_range(lanes)
    return model.with_k(min(k, len(components)))
