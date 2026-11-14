"""Shared pieces of the emotion stage-1 encoder check (docs/EMOTION.md).

Paths, labelled-clip manifests, song-level folds, window maths, the ridge
readout and the bootstrap. Nothing here reads a model; everything is
deterministic given the seeds below.
"""
from __future__ import annotations

import csv
import json
import os
import pathlib

import numpy as np

DATA = pathlib.Path(os.environ.get("HYST_EMOTION_DATA", "/secondary/hyst-data/emotion"))
CACHE = pathlib.Path(os.environ.get("HYST_EMOTION_CACHE", "/secondary/hyst-data/emotion/cache"))

SEED_FOLDS = 20261012
SEED_BOOTSTRAP = 20261013
SEED_INNER = 20261014
N_FOLDS = 5
N_BOOT = 2000

WINDOW_SECONDS = 4.0   # docs/EMOTION.md: windows about 3-5 s
HOP_SECONDS = 0.5      # cache grid
EVAL_STEP = 2.0        # check-1 evaluation grid (see handoff: CLAP cost)
DEAM_FIRST_LABEL = 15.0
DEAM_MAX_ID = 2000     # 1..2000 = 2013/2014 label release; 2001..2058 = 2015 full songs, excluded

GEMS = ("amazement", "solemnity", "tenderness", "nostalgia", "calmness",
        "power", "joyful_activation", "tension", "sadness")


# ---------------------------------------------------------------- manifests

def deam_clips():
    """DEAM excerpts of the 2013/2014 label release: [(key, path)]."""
    root = DATA / "deam" / "audio" / "MEMD_audio"
    out = []
    for path in sorted(root.glob("*.mp3"), key=lambda p: int(p.stem)):
        sid = int(path.stem)
        if sid <= DEAM_MAX_ID:
            out.append((f"deam_{sid}", path))
    return out


def emotify_clips():
    """Emotify clips. Track ids 1..400 run classical, rock, electronic, pop;
    each genre directory numbers its files 1..100 (assumed order, see SOURCES.md)."""
    genres = ("classical", "rock", "electronic", "pop")
    out = []
    for tid in range(1, 401):
        genre = genres[(tid - 1) // 100]
        out.append((f"emotify_{tid}", DATA / "emotify" / "audio" / genre / f"{(tid - 1) % 100 + 1}.mp3"))
    return out


def all_clips():
    return deam_clips() + emotify_clips()


def deam_dynamic(kind):
    """{song_id: (times_s, values)} for 'valence' or 'arousal' (2 Hz, from 15 s)."""
    path = DATA / "deam" / "annotations" / "annotations" / "annotations averaged per song" \
        / "dynamic (per second annotations)" / f"{kind}.csv"
    out = {}
    with open(path, newline="") as handle:
        reader = csv.reader(handle)
        header = [h.strip() for h in next(reader)]
        times = np.array([int(h[len("sample_"):-2]) / 1000.0 for h in header[1:]])
        for row in reader:
            values = np.array([float(v) if v.strip() else np.nan for v in row[1:]])
            out[int(row[0])] = (times, values)
    return out


def emotify_profiles():
    """{track_id: (genre, 9-vector fraction of raters who felt each GEMS item, n_raters)}."""
    rows = {}
    with open(DATA / "emotify" / "_dl" / "data.csv", newline="") as handle:
        for record in csv.DictReader(handle):
            record = {k.strip(): v.strip() for k, v in record.items()}
            tid = int(record["track id"])
            genre, acc, count = rows.get(tid, (record["genre"], np.zeros(len(GEMS)), 0))
            acc = acc + np.array([float(record[g]) for g in GEMS])
            rows[tid] = (genre, acc, count + 1)
    return {tid: (g, acc / n, n) for tid, (g, acc, n) in rows.items()}


# -------------------------------------------------------------------- folds

def assign_folds(keys, groups=None, seed=SEED_FOLDS, n_folds=N_FOLDS):
    """Fold index per key, by song. `groups` (e.g. genre) are balanced across folds.
    Deterministic: the same keys and seed always give the same folds."""
    keys = list(keys)
    groups = groups or {k: "" for k in keys}
    rng = np.random.default_rng(seed)
    fold = {}
    for group in sorted(set(groups.values())):
        members = sorted(k for k in keys if groups[k] == group)
        order = rng.permutation(len(members))
        for rank, index in enumerate(order):
            fold[members[index]] = rank % n_folds
    return fold


# ------------------------------------------------------------ window maths

def eval_centres(duration, first):
    """Window centres on the 2 s evaluation grid whose full 4 s window fits."""
    half = WINDOW_SECONDS / 2
    out, c = [], first
    while c + half <= duration + 1e-6:
        out.append(round(c, 6))
        c += EVAL_STEP
    return out


def pool_frames(frames, rate, centres, window=WINDOW_SECONDS):
    """Mean of `frames` (n, d) at `rate` Hz over [c-w/2, c+w/2] for each centre."""
    csum = np.vstack([np.zeros((1, frames.shape[1])), np.cumsum(frames, axis=0, dtype=np.float64)])
    out = np.empty((len(centres), frames.shape[1]), dtype=np.float32)
    for i, c in enumerate(centres):
        lo = max(0, int(round((c - window / 2) * rate)))
        hi = min(len(frames), int(round((c + window / 2) * rate)))
        hi = max(hi, lo + 1)
        out[i] = (csum[hi] - csum[lo]) / (hi - lo)
    return out


def step_centres(duration, hop=HOP_SECONDS):
    """Cache-grid window centres: 0, hop, 2 hop, ... up to the clip end."""
    return [round(k * hop, 6) for k in range(int(duration / hop) + 1)]


# ------------------------------------------------------------------- ridge

class Standardizer:
    def fit(self, x):
        self.mean = x.mean(axis=0)
        self.scale = x.std(axis=0)
        self.scale[self.scale < 1e-8] = 1.0
        return self

    def __call__(self, x):
        return ((x - self.mean) / self.scale).astype(np.float64)


ALPHAS = tuple(10.0 ** p for p in range(-1, 6))


def _gram(x, y):
    return x.T @ x, x.T @ y


def ridge_fit(x, y, alpha):
    """Closed-form ridge with an unpenalised intercept (x is standardised)."""
    xm, ym = x.mean(axis=0), y.mean(axis=0)
    xc, yc = x - xm, y - ym
    w = np.linalg.solve(xc.T @ xc + alpha * np.eye(x.shape[1]), xc.T @ yc)
    return w, ym - xm @ w


def ridge_predict(model, x):
    return x @ model[0] + model[1]


def choose_alpha(x, y, groups, seed=SEED_INNER, inner=3, alphas=ALPHAS, return_cost=False):
    """Alpha by inner group-k-fold on the training songs only (never the test fold)."""
    uniq = np.array(sorted(set(groups)))
    rng = np.random.default_rng(seed)
    which = dict(zip(rng.permutation(uniq), np.arange(len(uniq)) % inner))
    inner_fold = np.array([which[g] for g in groups])
    cost = np.zeros(len(alphas))
    for k in range(inner):
        tr, va = inner_fold != k, inner_fold == k
        std = Standardizer().fit(x[tr])
        xt, xv = std(x[tr]), std(x[va])
        xm, ym = xt.mean(axis=0), y[tr].mean(axis=0)
        xc, yc = xt - xm, y[tr] - ym
        gram, xty = xc.T @ xc, xc.T @ yc
        for i, a in enumerate(alphas):
            w = np.linalg.solve(gram + a * np.eye(gram.shape[0]), xty)
            pred = xv @ w + (ym - xm @ w)
            cost[i] += float(np.sum((pred - y[va]) ** 2))
    best = int(np.argmin(cost))
    return (alphas[best], float(cost[best])) if return_cost else alphas[best]


# --------------------------------------------------------------- bootstrap

def bootstrap_indices(n, n_boot=N_BOOT, seed=SEED_BOOTSTRAP):
    rng = np.random.default_rng(seed)
    return rng.integers(0, n, size=(n_boot, n))


def interval(samples, level=0.95):
    lo, hi = np.percentile(samples, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def write_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1))
