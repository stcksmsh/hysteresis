#!/usr/bin/env python3
"""The mind spike: a seeded leaky reservoir over the stage-1 ear vector, with rehearsal.

Spec: docs/MIND.md section 3.4-3.6 and docs/NEXT_BODY_THEN_MIND.md, step 2, "What to build".
Not built: the oscillator pulse (3.2), audioic (3.3), the core's own expectation readout, any
trained core. Nothing in the core is trained: weights come from the seed.

Flow, per song (all steps are 0.5 s):
  ear vector (2,665)  --PCA 64 (fit on training folds)--> input u(n)
  pass 1 (rehearsal): core from rest on u only                      -> states, kept
  pass 2 (dancer):    core from rest on u and rho * [mind(n + L)]    L = 1, 4, 16 bars
  mind state = PCA 64 of the 512 unit states (fit on training pass-1 states)
  rehearsal input = the stored pass-1 mind state at n + L, PCA 8 (one PCA, three lags: 24 inputs)

Constants and where they come from:
  UNITS 512, DENSITY 0.1, TAU 0.5-60 s log-uniform, SR grid, start 0.9  docs/MIND.md 3.4
  LAG_BARS (1, 4, 16), BEATS_PER_BAR 4, REHEARSAL_PCA 8, EAR_PCA 64      docs/MIND.md 3.5, step-2 note
  LEAK a = 1 - exp(-hop / tau), INPUT_SCALE 1, N(0, 1/d_in) input weights, tanh,
  SEED_CORE, SEED_SHUFFLE, unit-variance scaling of the PCA inputs       builder's choices (handoff)
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import common
import lifts

SEED_CORE = 20261016
SEED_SHUFFLE = 20261017
UNITS = 512
DENSITY = 0.1
TAU_MIN, TAU_MAX = 0.5, 60.0
SR_GRID = (0.7, 0.8, 0.9, 0.95, 0.99)
SR_START = 0.9
EAR_PCA = 64
STATE_PCA = 64
REHEARSAL_PCA = 8
LAG_BARS = (1, 4, 16)
BEATS_PER_BAR = 4
INPUT_SCALE = 1.0
CHUNK = 256


@dataclass
class Clip:
    """One song or clip on the 0.5 s grid: ear vectors x (T, D), beat times, and its labels."""
    key: str
    ds: str                      # deam | emotify | merp | song
    x: np.ndarray
    beats: np.ndarray
    y: np.ndarray | None = None  # (T, 2) valence, arousal at the 0.5 s steps, NaN where unlabelled
    rows: np.ndarray | None = None   # step indices that are scored (the 2 s evaluation grid)
    profile: np.ndarray | None = None  # (9,) Emotify GEMS shares
    extra: dict = field(default_factory=dict)


# ------------------------------------------------------------------ projections

class Projector:
    """Optional per-feature standardising, then PCA scores, optionally scaled to unit variance."""

    def __init__(self, mean, scale, components, out_scale):
        self.mean, self.scale, self.components, self.out_scale = mean, scale, components, out_scale

    def __call__(self, x):
        z = (np.asarray(x, dtype=np.float32) - self.mean) / self.scale
        return ((z @ self.components.T) / self.out_scale).astype(np.float32)


def fit_projector(arrays, k, standardise=True, whiten=True):
    """PCA of the rows of `arrays` (list of (T, D)). Covariance accumulated in chunks."""
    dim = arrays[0].shape[1]
    n, total, total2 = 0, np.zeros(dim), np.zeros(dim)
    for a in arrays:
        a = np.asarray(a, dtype=np.float64)
        n += len(a)
        total += a.sum(axis=0)
        total2 += (a ** 2).sum(axis=0)
    mean = total / n
    std = np.sqrt(np.maximum(total2 / n - mean ** 2, 0.0)) if standardise else np.ones(dim)
    std[std < 1e-8] = 1.0
    mean32, std32 = mean.astype(np.float32), std.astype(np.float32)
    cov = np.zeros((dim, dim))
    for a in arrays:
        z = (np.asarray(a, dtype=np.float32) - mean32) / std32
        cov += (z.T @ z).astype(np.float64)
    cov /= max(n - 1, 1)
    values, vectors = np.linalg.eigh(cov)
    order = np.argsort(values)[::-1][:k]
    components = vectors[:, order].T.astype(np.float32)
    out_scale = np.sqrt(np.maximum(values[order], 1e-12)).astype(np.float32) if whiten else np.ones(len(order), np.float32)
    return Projector(mean32, std32, components, out_scale)


# ---------------------------------------------------------------------- beats

def beat_time(position, beats):
    """Inverse of lifts.beat_position: time in seconds of fractional beat index `position`."""
    beats = np.asarray(beats, dtype=np.float64)
    p = np.asarray(position, dtype=np.float64)
    out = np.interp(p, np.arange(len(beats)), beats)
    first, last = beats[1] - beats[0], beats[-1] - beats[-2]
    out = np.where(p < 0, beats[0] + p * first, out)
    return np.where(p > len(beats) - 1, beats[-1] + (p - (len(beats) - 1)) * last, out)


def rehearsal_index(steps, beats, lag_bars=LAG_BARS, hop=common.HOP_SECONDS):
    """(len(lag_bars), steps) step index of "n + L bars" on the beat grid; -1 where that step
    lies after the end of the song (nothing is remembered there)."""
    times = np.arange(steps) * hop
    position = lifts.beat_position(times, beats)
    out = np.empty((len(lag_bars), steps), dtype=np.int64)
    for i, bars in enumerate(lag_bars):
        target = np.rint(beat_time(position + BEATS_PER_BAR * bars, beats) / hop).astype(np.int64)
        out[i] = np.where(target < steps, np.maximum(target, 0), -1)
    return out


def rehearsal_input(scores, index):
    """(steps, 8) stored scores and (lags, steps) indices -> (steps, 8 * lags); zeros where the index is -1."""
    parts = [np.where((idx >= 0)[:, None], scores[np.maximum(idx, 0)], 0.0) for idx in index]
    return np.concatenate(parts, axis=1).astype(np.float32)


# ----------------------------------------------------------------------- core

class Core:
    """512 leaky tanh units at the 0.5 s step; nothing is trained."""

    def __init__(self, in_ear, in_rehearsal, spectral_radius, seed=SEED_CORE, units=UNITS, density=DENSITY,
                 tau_range=(TAU_MIN, TAU_MAX), hop=common.HOP_SECONDS):
        rng = np.random.default_rng(seed)
        tau = np.exp(rng.uniform(np.log(tau_range[0]), np.log(tau_range[1]), units))
        w = rng.standard_normal((units, units)) * (rng.random((units, units)) < density)
        radius = np.abs(np.linalg.eigvals(w)).max()
        self.w = (w * (spectral_radius / radius)).astype(np.float32)
        self.w_ear = (rng.standard_normal((units, in_ear)) * INPUT_SCALE / np.sqrt(in_ear)).astype(np.float32)
        self.w_reh = (rng.standard_normal((units, in_rehearsal)) * INPUT_SCALE / np.sqrt(in_rehearsal)).astype(np.float32)
        self.leak = (1.0 - np.exp(-hop / tau)).astype(np.float32)
        self.tau, self.units = tau, units

    def run(self, ear, rehearsal=None, rho=0.0):
        """ear (B, T, in_ear), rehearsal (B, T, in_rehearsal) or None -> states (B, T, units) from rest."""
        batch, steps, _ = ear.shape
        drive = ear @ self.w_ear.T
        if rehearsal is not None and rho != 0.0:
            drive = drive + np.float32(rho) * (rehearsal @ self.w_reh.T)
        x = np.zeros((batch, self.units), np.float32)
        out = np.empty((batch, steps, self.units), np.float32)
        for t in range(steps):
            x = (1.0 - self.leak) * x + self.leak * np.tanh(x @ self.w.T + drive[:, t])
            out[:, t] = x
        return out


# ---------------------------------------------------------------------- model

def _padded(arrays):
    steps = max(len(a) for a in arrays)
    out = np.zeros((len(arrays), steps, arrays[0].shape[1]), np.float32)
    for i, a in enumerate(arrays):
        out[i, :len(a)] = a
    return out


class MindModel:
    """Ear projector + core + state projector + rehearsal projector, fitted on training clips only."""

    def __init__(self, ear_projector, spectral_radius, seed=SEED_CORE, units=UNITS,
                 state_k=STATE_PCA, rehearsal_k=REHEARSAL_PCA):
        self.ear = ear_projector
        self.spectral_radius = spectral_radius
        self.state_k, self.rehearsal_k = state_k, rehearsal_k
        self.core = Core(len(ear_projector.out_scale), rehearsal_k * len(LAG_BARS), spectral_radius, seed, units)
        self.state = None
        self.rehearsal = None

    def _pass1(self, ears):
        """Pass 1 in chunks of similar length. -> list of (T, 512) states."""
        states = [None] * len(ears)
        for chunk in _chunks([len(e) for e in ears]):
            batch = self.core.run(_padded([ears[i] for i in chunk]))
            for row, i in enumerate(chunk):
                states[i] = batch[row, :len(ears[i])]
        return states

    def fit_projectors(self, clips):
        """State PCA 64 on the training clips' pass-1 states, rehearsal PCA 8 on its scores."""
        ears = [self.ear(c.x) for c in clips]
        states = self._pass1(ears)
        self.state = fit_projector(states, self.state_k, standardise=False, whiten=False)
        self.rehearsal = fit_projector([self.state(s) for s in states], self.rehearsal_k, standardise=False, whiten=True)
        return self

    def run(self, clips, rho=1.0, orders=None):
        """-> {key: {"rehearsal": (T, 64) pass-1 mind state, "mind": (T, 64) pass-2 mind state at rho}}.
        `orders` {key: permutation} runs a clip's steps in that order (the shuffle test); the
        returned arrays are in the permuted order."""
        keys = [c.key for c in clips]
        ears = []
        for c in clips:
            e = self.ear(c.x)
            ears.append(e[orders[c.key]] if orders and c.key in orders else e)
        s1 = self._pass1(ears)
        scores1 = [self.state(s) for s in s1]
        reh = [rehearsal_input(self.rehearsal(sc), rehearsal_index(len(sc), c.beats)) for sc, c in zip(scores1, clips)]
        out = {}
        s2 = [None] * len(clips)
        for chunk in _chunks([len(e) for e in ears]):
            batch = self.core.run(_padded([ears[i] for i in chunk]), _padded([reh[i] for i in chunk]), rho)
            for row, i in enumerate(chunk):
                s2[i] = self.state(batch[row, :len(ears[i])])
        for k, a, b in zip(keys, scores1, s2):
            out[k] = {"rehearsal": a, "mind": b}
        return out


def _chunks(lengths, size=CHUNK):
    order = np.argsort(lengths, kind="stable")
    return [order[i:i + size] for i in range(0, len(order), size)]


# ---------------------------------------------------------------------- output

def mind_state_field(mind, rehearsal, rho, seed, beats, readouts, provenance, hop=common.HOP_SECONDS):
    """Additive `mindState` sidecar field (docs/MIND.md section 5, minus `pulse` and `ic`, and
    without the core's own expectation error). `mind` (T, 64) is the pass-2 mind state. `perBeat`
    is the mean of the steps whose centres fall in each beat, as `emotionEncoding.perBeat`.
    The input sidecar is not touched by this function."""
    centres = np.arange(len(mind)) * hop
    edges = list(beats) + [centres[-1] + hop] if len(beats) else []
    per_beat = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = np.flatnonzero((centres >= lo) & (centres < hi))
        if not len(sel):
            sel = [int(np.argmin(np.abs(centres - (lo + hi) / 2)))]
        per_beat.append(mind[sel].mean(axis=0))
    return {
        "version": 1,
        "seed": int(seed),
        "rho": float(rho),
        "hopSeconds": hop,
        "steps": np.round(mind, 4).tolist(),
        "perBeat": np.round(np.array(per_beat), 4).tolist(),
        "readouts": readouts,
        "provenance": dict(provenance, note="pulse, ic and ownError are not built in this stage"),
    }
