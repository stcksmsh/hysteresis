#!/usr/bin/env python3
"""Check 1b of docs/MIND.md section 7 / docs/NEXT_BODY_THEN_MIND.md step 2: does a recurrent core
with a memory of having rehearsed the song follow feeling inside a song better than stage 1's
memoryless encoding?

Written and committed before any result; it has never been run on real data when committed.
The rules are those of NEXT_BODY_THEN_MIND.md, step 2 (the "Check" list, the dated notes of
b1775f8 and 72ba7bc, and the dial formats). In short:

Reference: stage 1's pick (baseline+all, 2,665 per 0.5 s step) read memorylessly by a ridge, same
folds, same rows. Core: mind.py (512 leaky units, rehearsal) with ridge readouts from the PCA-64
mind state. rho = 1 (the dancer) is scored; rho = 0 is reported beside it.
  Folds: 5 by song, seeded as check1.py (DEAM: songs; Emotify: balanced by genre; MERP: the 43
  songs longer than 50 s). Bootstrap: 2,000 resamples over songs, percentile (common.py).
  Gate 1  per held-out song, Pearson r over time of the arousal readout (song means removed),
          averaged over songs, on DEAM and on MERP each: core mean above the reference mean and
          core lower 95 % bound above the reference upper bound.
  Gate 2  pooled DEAM timing R^2 (mean of valence and arousal) and Emotify mean rank correlation of
          the core are each not below the lower 95 % bound of stage 1's pick (STAGE1_PICK).
  Gate 3  one seeded shuffle of the step order per held-out song, both passes shuffled the same
          way, readouts as trained: within-song arousal r falls to at most half, on DEAM and MERP each.
  Gate 4  per step, distance between the rho = 1 and rho = 0 mind states; statistic = mean over
          lifts of that distance averaged over the 8 beats before the lift; null = the same number
          of 8-beat windows per song drawn from windows that overlap no lift window, 1,000 draws,
          p = (1 + draws at or above) / 1,001 < 0.05, on MERP and on the three songs pooled, each.
  Gate 5  Five Years 0-30 s reads lower in arousal than 156-258 s; Presence 120-190 s reads sad
          (sadness in the top three of the nine GEMS averaged over the span, and its mean there above
          its mean over the rest of the song); the arousal readout correlates with the user's pass A
          energy (0.5 s step means, masked spans left out, no lag) better than the reference does on at
          least 2 of the 3 songs. Readouts for the three songs: fitted on all DEAM and all 43 MERP songs.
All five gates must pass.

Known lifts: lifts.py (rule of b1775f8). MERP beats: beats.py. Everything the rules leave open
and this file therefore fixes is listed in POINTS_LEFT_OPEN and in the handoff.

  python check1b.py [--out DIR] [--dial DIR]
Reads the dial files only in main(), only when it runs.
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import spearmanr

import check1
import common
import lifts
import merp_labels
import mind
from mind import Clip

SEED_PERM = 20261018
N_DRAWS = 1000
LIFT_WINDOW_BEATS = 8
STAGE1_PICK = {  # docs/DANCE_HANDOFF.md, "Final check 1: stems baseline", baseline+all: value [low, high]
    "timing": (0.617, 0.596, 0.635),
    "rho": (0.616, 0.588, 0.643),
}
FIVE_YEARS_OPENING, FIVE_YEARS_CLIMAX = (0.0, 30.0), (156.0, 258.0)
PRESENCE_SPAN = (120.0, 190.0)
INSTANT_CRUSH_MASKS = [(135.0, 171.0), (329.0, 1e9)]
INSTANT_CRUSH_TRY1_END = 329.0
SONGS = (  # key, title, dial file, sidecar stem
    ("instant-crush", "Instant Crush", "song1.m4a", "instant-crush"),
    ("five-years", "Five Years", "song2.m4a", "five-years-steady"),
    ("presence", "Presence", "song3.m4a", "presence"),
)
MUSIC_ARM = pathlib.Path(os.environ.get(
    "HYST_MUSIC_ARM", "/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm"))

POINTS_LEFT_OPEN = """
1 Library clips (DEAM, Emotify) have CLAP only every 2 s in the stage-1 cache; the core runs every 0.5 s, so
  CLAP is linearly interpolated in time between the cached centres (held at the ends). The MERP songs and the
  three songs have CLAP at every 0.5 s step. MERT of the library clips was run whole, of MERP and the songs in 30 s chunks.
2 Rows scored: the 2 s grid of check1.py (DEAM labels at 15, 17, ...; MERP and Emotify centres 2, 4, ...), for both
  methods, for training and scoring.
3 One valence/arousal readout per method, fitted on the pooled DEAM + MERP training rows (labels as released, both
  -1..1); gate 1 and 2 split the held-out predictions by dataset. Gate 2's DEAM timing R^2 is therefore not from a
  DEAM-only fit as in stage 1.
4 MERP label of step k = mean of the 10 Hz series over t in [0.5 k - 0.25, 0.5 k + 0.25), sample i at t = i / 10.
5 The rho = 0 reading refits the readout on the training clips' rho = 0 states.
6 Mind-state PCA 64 fitted on training pass-1 states; one rehearsal PCA 8 (of those scores), applied to each of the
  three lags; every PCA input scaled to unit variance; nothing remembered after the end of a song (zeros).
7 Spectral radius: chosen per outer fold by 3 inner folds over the DEAM + MERP training songs, score = mean of the DEAM
  and the MERP mean within-song arousal r; PCAs are fitted once on the whole training fold (unsupervised).
8 Gate 3: labels move with their steps (the step keeps its ear vector and its label); only the history is scrambled.
9 Gate 4: windows span 8 beats ending at the lift; steps whose centres fall in the window; MERP lifts from the mean-rater
  arousal at 10 Hz; distance = Euclidean in the PCA-64 mind state.
10 Gate 5: Instant Crush pass A is always try 1 (a + 1) / 2, also if dial2.json holds an Instant Crush pass A take.
  Dial values per step as for MERP (point 4); a step touching a mask is left out.
11 Lift rule details: see lifts.py (centred shrinking windows, adjacent-sample merge, limits on the placed lift,
  16-beat rule against the last kept lift).
12 Beat tracker for DEAM, Emotify and MERP: Essentia RhythmExtractor2013 multifeature (beats.py); fallback 120 bpm
  grid below 8 beats, counted in the output.
"""


@dataclass
class Config:
    units: int = mind.UNITS
    ear_k: int = mind.EAR_PCA
    state_k: int = mind.STATE_PCA
    rehearsal_k: int = mind.REHEARSAL_PCA
    sr_grid: tuple = mind.SR_GRID
    n_boot: int = common.N_BOOT
    n_draws: int = N_DRAWS


@dataclass
class World:
    deam: list
    emotify: list
    merp: list
    songs: list
    folds: dict
    info: dict = field(default_factory=dict)


# ----------------------------------------------------------------- data (real)

def _interp_clap(clap, steps, centre0, hop):
    pos = np.clip((np.arange(steps) * common.HOP_SECONDS - centre0) / hop, 0, len(clap) - 1)
    lo = np.floor(pos).astype(int)
    hi = np.minimum(lo + 1, len(clap) - 1)
    w = (pos - lo)[:, None].astype(np.float32)
    return clap[lo] * (1 - w) + clap[hi] * w


def library_vectors(key):
    """baseline+all of a DEAM / Emotify clip on the 0.5 s grid: stems baseline (49), MERT mean of layers
    (768), CLAP (512, interpolated), EffNet (1,280), mood (56)."""
    emb = common.CACHE / "emb"
    base = np.load(emb / "baseline_stems" / f"{key}.npy").astype(np.float32)
    mert = np.load(emb / "mert" / f"{key}.npy").astype(np.float32).mean(axis=1)
    eff = np.load(emb / "essentia_effnet" / f"{key}.npy").astype(np.float32)
    mood = np.load(emb / "essentia_mood" / f"{key}.npy").astype(np.float32)
    clap = np.load(emb / "clap" / f"{key}.npy").astype(np.float32)
    manifest = json.loads((emb / "clap" / "manifest.json").read_text())
    steps = min(len(base), len(mert), len(eff), len(mood))
    return np.concatenate([base[:steps], mert[:steps], _interp_clap(clap, steps, manifest["centre0"], manifest["hopSeconds"]),
                           eff[:steps], mood[:steps]], axis=1)


def read_beats(key):
    path = common.CACHE / "mind" / "beats" / f"{key}.json"
    return np.asarray(json.loads(path.read_text())["beats"], dtype=np.float64)


def _step(centre):
    return int(round(centre / common.HOP_SECONDS))


def load_library(durations):
    """DEAM and Emotify clips, rows and labels exactly as check1.py indexes them."""
    data = check1.build_index(durations)
    deam, cursor = [], 0
    for key, centres in data["deam_index"]:
        x = library_vectors(key)
        y = np.full((len(x), 2), np.nan)
        rows = []
        for c in centres:
            y[_step(c)] = data["y"][cursor]
            rows.append(_step(c))
            cursor += 1
        deam.append(Clip(key, "deam", x, read_beats(key), y, np.array(rows, dtype=int)))
    emotify = []
    for (key, centres), profile in zip(data["emotify_index"], data["profile"]):
        x = library_vectors(key)
        emotify.append(Clip(key, "emotify", x, read_beats(key), None, np.array([_step(c) for c in centres], dtype=int), profile))
    folds = common.assign_folds([f"deam_{s}" for s in sorted(set(data["song"]))])
    folds.update(common.assign_folds([f"emotify_{t}" for t in data["tids"]],
                                     {f"emotify_{t}": data["genre"][t] for t in data["tids"]}))
    return deam, emotify, folds


def load_merp():
    """The 43 MERP songs longer than 50 s: ear vectors from merp_features.py, labels from merp_labels.py."""
    import merp_features
    songs = merp_features.merp_songs()
    labels, report, variant, duplicates = merp_labels.load_merp_labels(dict(songs))
    clips = []
    for song, duration in songs:
        x = np.load(common.CACHE / "mind" / "merp" / f"{song}.npy").astype(np.float32)
        y = np.full((len(x), 2), np.nan)
        for j, axis in enumerate(("valence", "arousal")):
            m = min(len(x), len(labels[song][axis]))
            y[:m, j] = labels[song][axis][:m]
        rows = np.array([_step(c) for c in common.eval_centres(duration, common.EVAL_STEP)], dtype=int)
        rows = rows[(rows < len(x)) & np.isfinite(y[np.minimum(rows, len(x) - 1)]).all(axis=1)]
        clips.append(Clip(f"merp_{song}", "merp", x, read_beats(f"merp_{song}"), y, rows,
                          extra={"duration": duration, "arousal10": labels[song]["arousal10"], "trials": labels[song]["trials"]}))
    folds = common.assign_folds([c.key for c in clips])
    info = {"labelVariant": list(variant), "labelMatch": {"|".join(k): v for k, v in report.items()},
            "duplicatesResolved": duplicates}
    return clips, folds, info


def load_songs(sidecar_dir=MUSIC_ARM):
    """The three danced songs: ear vectors and beat grids from their emotion sidecars."""
    out = []
    for key, title, _, stem in SONGS:
        sidecar = json.loads((pathlib.Path(sidecar_dir) / f"{stem}.emotion.sidecar.json").read_text())
        x = np.asarray(sidecar["emotionEncoding"]["steps"], dtype=np.float32)
        out.append(Clip(key, "song", x, np.asarray(sidecar["beats"], dtype=np.float64),
                        extra={"duration": float(sidecar["duration"]), "title": title}))
    return out


def load_real():
    durations = {p.stem: len(np.load(p, mmap_mode="r")) / 20.0 for p in (common.CACHE / "frames_mix").glob("*.npy")}
    deam, emotify, folds = load_library(durations)
    merp, merp_folds, info = load_merp()
    folds.update(merp_folds)
    return World(deam, emotify, merp, load_songs(), folds, info)


# ------------------------------------------------------------------- dial files

def _dial_steps(series, n_steps, masks):
    """0.5 s step means of a 10 Hz dial series; steps touching a mask or beyond the recording are NaN."""
    out = merp_labels.step_means(np.asarray(series, dtype=np.float64), n_steps)
    for k in range(n_steps):
        lo, hi = k * common.HOP_SECONDS - 0.25, k * common.HOP_SECONDS + 0.25
        if any(lo < b and a < hi for a, b in masks):
            out[k] = np.nan
    return out


def load_dial(v2_path, try1_path):
    """-> {song key: {"energy10": (n,), "light10", "heavy10" (pass B, optional), "masks", "source"}}.
    Pass A of Five Years and Presence from dial2.json; Instant Crush pass A is try 1's arousal as (a + 1) / 2
    with its masks. Pass B (light, heavy) from dial2.json, whatever the song."""
    out = {key: {"masks": [], "source": {}} for key, *_ in SONGS}
    by_file = {file: key for key, _, file, _ in SONGS}
    v2 = json.loads(pathlib.Path(v2_path).read_text())
    for take in v2["takes"]:
        if take.get("status") != "done" or take["song"] not in by_file:
            continue
        key, samples = by_file[take["song"]], take["samples"]
        if take["pass"] == "A":
            out[key]["energy10"] = np.array([s[1] for s in samples], dtype=np.float64)
            out[key]["source"]["A"] = "dial2.json pass A"
        elif take["pass"] == "B":
            out[key]["light10"] = np.array([s[1] for s in samples], dtype=np.float64)
            out[key]["heavy10"] = np.array([s[2] for s in samples], dtype=np.float64)
    try1 = json.loads(pathlib.Path(try1_path).read_text())
    entry = max((s for s in try1["songs"] if s.get("title") == "Instant Crush" or s.get("file") == "song1.m4a"),
                key=lambda s: len(s["samples"]))
    arousal = np.array([s[2] for s in entry["samples"]], dtype=np.float64)
    out["instant-crush"]["energy10"] = (arousal + 1.0) / 2.0
    out["instant-crush"]["masks"] = list(INSTANT_CRUSH_MASKS)
    out["instant-crush"]["source"]["A"] = "dial-ic-try1.json arousal, (a + 1) / 2"
    return out


# ------------------------------------------------------------------ small tools

def within_r(pred, true):
    """Pearson r with the song means removed; NaN when either is constant."""
    p, t = pred - pred.mean(), true - true.mean()
    d = np.sqrt((p ** 2).sum() * (t ** 2).sum())
    return float((p * t).sum() / d) if d > 1e-12 else float("nan")


def boot_mean(values, n_boot):
    values = np.asarray(values, dtype=np.float64)
    idx = common.bootstrap_indices(len(values), n_boot)
    return float(values.mean()), common.interval(values[idx].mean(axis=1))


class Ridge:
    """Standardise, choose the penalty by inner 3-fold on the training songs only, fit."""

    def __init__(self, x, y, groups):
        self.std = common.Standardizer().fit(x)
        self.model = common.ridge_fit(self.std(x), y, common.choose_alpha(x, y, groups))

    def __call__(self, x):
        return common.ridge_predict(self.model, self.std(x))


def _group_ids(clips):
    return {c.key: i for i, c in enumerate(clips)}


def pooled_rows(clips, outputs, field_name):
    """(X, Y, groups) of the labelled rows. outputs[key][field_name] is the (T, k) state; None uses clip.x."""
    ids = _group_ids(clips)
    xs, ys, gs = [], [], []
    for c in clips:
        source = c.x if outputs is None else outputs[c.key][field_name]
        xs.append(source[c.rows])
        ys.append(c.y[c.rows])
        gs.append(np.full(len(c.rows), ids[c.key]))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(gs)


def clip_means(clips, outputs, field_name):
    out = []
    for c in clips:
        source = c.x if outputs is None else outputs[c.key][field_name]
        out.append(source[c.rows].mean(axis=0))
    return np.stack(out)


# ------------------------------------------------------------ spectral radius

def select_radius(train, ear, cfg):
    """Grid value with the best inner-fold within-song arousal r (DEAM and MERP each averaged, then the mean)."""
    labelled = [c for c in train if c.ds in ("deam", "merp")]
    rng = np.random.default_rng(common.SEED_INNER)
    which = dict(zip(rng.permutation([c.key for c in labelled]), np.arange(len(labelled)) % 3))
    scores = {}
    for radius in cfg.sr_grid:
        model = mind.MindModel(ear, radius, mind.SEED_CORE, cfg.units, cfg.state_k, cfg.rehearsal_k).fit_projectors(train)
        out = model.run(labelled, 1.0)
        per_ds = {"deam": [], "merp": []}
        for k in range(3):
            tr = [c for c in labelled if which[c.key] != k]
            va = [c for c in labelled if which[c.key] == k]
            x, y, g = pooled_rows(tr, out, "mind")
            readout = Ridge(x, y, g)
            for c in va:
                r = within_r(readout(out[c.key]["mind"][c.rows])[:, 1], c.y[c.rows, 1])
                if np.isfinite(r):
                    per_ds[c.ds].append(r)
        scores[radius] = float(np.mean([np.mean(v) if v else 0.0 for v in per_ds.values()]))
    best = max(cfg.sr_grid, key=lambda r: (scores[r], -r))
    return best, scores


# ------------------------------------------------------------------ one model

def fit_model(train, cfg):
    """Everything fitted on `train` clips only: ear PCA, radius, core projectors, ridge readouts."""
    ear = mind.fit_projector([c.x for c in train], cfg.ear_k)
    radius, scores = select_radius(train, ear, cfg)
    model = mind.MindModel(ear, radius, mind.SEED_CORE, cfg.units, cfg.state_k, cfg.rehearsal_k).fit_projectors(train)
    out = model.run(train, 1.0)
    lab = [c for c in train if c.ds in ("deam", "merp")]
    emo = [c for c in train if c.ds == "emotify"]
    ids = _group_ids(emo)
    emo_groups = np.array([ids[c.key] for c in emo])
    readouts = {
        "va_core": Ridge(*pooled_rows(lab, out, "mind")),
        "va_core0": Ridge(*pooled_rows(lab, out, "rehearsal")),
        "va_ref": Ridge(*pooled_rows(lab, None, None)),
        "gems_core": Ridge(clip_means(emo, out, "mind"), np.stack([c.profile for c in emo]), emo_groups),
        "gems_core0": Ridge(clip_means(emo, out, "rehearsal"), np.stack([c.profile for c in emo]), emo_groups),
        "gems_ref": Ridge(clip_means(emo, None, None), np.stack([c.profile for c in emo]), emo_groups),
    }
    return model, readouts, radius, scores


def evaluate(model, readouts, test, rho_runs=True):
    """Held-out predictions of one fitted model on `test` clips -> per-clip dict."""
    out1 = model.run(test, 1.0)
    result = {}
    for c in test:
        s1, s0 = out1[c.key]["mind"], out1[c.key]["rehearsal"]
        entry = {"mind": s1, "rehearsal": s0, "dist": np.linalg.norm(s1 - s0, axis=1)}
        if c.ds in ("deam", "merp"):
            entry["core"] = readouts["va_core"](s1[c.rows])
            entry["core0"] = readouts["va_core0"](s0[c.rows])
            entry["ref"] = readouts["va_ref"](c.x[c.rows])
        if c.ds == "emotify":
            entry["core"] = readouts["gems_core"](s1[c.rows].mean(axis=0, keepdims=True))[0]
            entry["core0"] = readouts["gems_core0"](s0[c.rows].mean(axis=0, keepdims=True))[0]
            entry["ref"] = readouts["gems_ref"](c.x[c.rows].mean(axis=0, keepdims=True))[0]
        result[c.key] = entry
    return result


def shuffled_predictions(model, readouts, test):
    """Gate 3: arousal-readout predictions at the scored rows after one seeded shuffle per song."""
    labelled = [c for c in test if c.ds in ("deam", "merp")]
    orders = {c.key: np.random.default_rng([mind.SEED_SHUFFLE, i]).permutation(len(c.x)) for i, c in enumerate(labelled)}
    out = model.run(labelled, 1.0, orders)
    pred = {}
    for c in labelled:
        inverse = np.argsort(orders[c.key])
        pred[c.key] = readouts["va_core"](out[c.key]["mind"][inverse[c.rows]])
    return pred


# ----------------------------------------------------------------------- gates

def gate1(collected, world, cfg):
    result = {}
    for ds, clips in (("deam", world.deam), ("merp", world.merp)):
        rows = []
        for c in clips:
            p = collected[c.key]
            rows.append([within_r(p[m][:, 1], c.y[c.rows, 1]) for m in ("core", "ref", "core0")]
                        + [within_r(p[m][:, 0], c.y[c.rows, 0]) for m in ("core", "ref", "core0")])
        rows = np.array(rows)
        keep = np.isfinite(rows[:, :3]).all(axis=1)
        core, ref, core0 = (boot_mean(rows[keep, i], cfg.n_boot) for i in range(3))
        valence = [boot_mean(rows[np.isfinite(rows[:, 3 + i]), 3 + i], cfg.n_boot) for i in range(3)]
        result[ds] = {"songs": int(keep.sum()), "songsDropped": int((~keep).sum()),
                      "core": core, "reference": ref, "core_rho0": core0,
                      "valence": {"core": valence[0], "reference": valence[1], "core_rho0": valence[2]},
                      "pass": bool(core[0] > ref[0] and core[1][0] > ref[1][1])}
    result["pass"] = bool(result["deam"]["pass"] and result["merp"]["pass"])
    return result


def gate2(collected, world, cfg):
    stats = []
    for c in world.deam:
        p = collected[c.key]["core"]
        row = []
        for j in range(2):
            t, q = c.y[c.rows, j], p[:, j]
            row.append([len(t), t.sum(), (t ** 2).sum(), ((t - q) ** 2).sum(), ((t - t.mean()) ** 2).sum(),
                        (((t - t.mean()) - (q - q.mean())) ** 2).sum(), 0])
        stats.append(row)
    stats = np.array(stats)
    pooled, _ = check1.r2_from_stats(stats)
    idx = common.bootstrap_indices(len(stats), cfg.n_boot)
    boot, _ = check1.r2_from_stats(stats[idx])
    timing = float(pooled.mean())
    rho = np.array([np.nan_to_num(spearmanr(collected[c.key]["core"], c.profile)[0]) for c in world.emotify])
    rho_mean, rho_ci = boot_mean(rho, cfg.n_boot)
    return {"timing": {"value": timing, "ci": common.interval(boot.mean(axis=1)), "stage1": STAGE1_PICK["timing"],
                       "valence": float(pooled[0]), "arousal": float(pooled[1]), "pass": bool(timing >= STAGE1_PICK["timing"][1])},
            "rho": {"value": rho_mean, "ci": rho_ci, "stage1": STAGE1_PICK["rho"], "pass": bool(rho_mean >= STAGE1_PICK["rho"][1])},
            "pass": bool(timing >= STAGE1_PICK["timing"][1] and rho_mean >= STAGE1_PICK["rho"][1])}


def gate2_reference(collected, world):
    """Reference's pooled timing R^2 and Emotify rho on the same folds (reported, not gated)."""
    sse = sst = 0.0
    for j in range(2):
        t = np.concatenate([c.y[c.rows, j] for c in world.deam])
        q = np.concatenate([collected[c.key]["ref"][:, j] for c in world.deam])
        sse += 1 - ((t - q) ** 2).sum() / ((t - t.mean()) ** 2).sum()
    rho = np.mean([np.nan_to_num(spearmanr(collected[c.key]["ref"], c.profile)[0]) for c in world.emotify])
    return {"timing": float(sse / 2), "rho": float(rho)}


def gate3(collected, shuffled, world, cfg):
    result = {}
    for ds, clips in (("deam", world.deam), ("merp", world.merp)):
        rows = np.array([[within_r(collected[c.key]["core"][:, 1], c.y[c.rows, 1]),
                          within_r(shuffled[c.key][:, 1], c.y[c.rows, 1])] for c in clips])
        rows = rows[np.isfinite(rows).all(axis=1)]
        before, after = rows[:, 0].mean(), rows[:, 1].mean()
        result[ds] = {"songs": int(len(rows)), "rOriginal": boot_mean(rows[:, 0], cfg.n_boot),
                      "rShuffled": boot_mean(rows[:, 1], cfg.n_boot),
                      "pass": bool(before > 0 and after <= 0.5 * before)}
    result["pass"] = bool(result["deam"]["pass"] and result["merp"]["pass"])
    return result


def lift_window_steps(lift, beats, steps):
    """Steps whose centres lie in the 8 beats before `lift`."""
    position = lifts.beat_position([lift], beats)[0]
    lo, hi = mind.beat_time(position - LIFT_WINDOW_BEATS, beats), mind.beat_time(position, beats)
    idx = np.flatnonzero((np.arange(steps) * common.HOP_SECONDS >= lo) & (np.arange(steps) * common.HOP_SECONDS < hi))
    return idx if len(idx) else np.array([min(max(int(round(hi / common.HOP_SECONDS)), 0), steps - 1)])


def gate4(song_data, cfg):
    """song_data: [(key, dist per step, beats, lift times)]. Pooled over the songs given."""
    observed, per_song, lift_counts = [], {}, {}
    for key, dist, beats, lift_times in song_data:
        lift_counts[key] = len(lift_times)
        if not lift_times:
            continue
        windows = [lift_window_steps(t, beats, len(dist)) for t in lift_times]
        observed += [float(dist[w].mean()) for w in windows]
        positions = lifts.beat_position(lift_times, beats)
        starts = np.arange(0, max(int(np.floor(lifts.beat_position([len(dist) * common.HOP_SECONDS], beats)[0])) - LIFT_WINDOW_BEATS, 0) + 1)
        free = [b for b in starts if all(abs(b - (p - LIFT_WINDOW_BEATS)) >= LIFT_WINDOW_BEATS for p in positions)]
        candidate = []
        for b in free:
            lo, hi = mind.beat_time(b, beats), mind.beat_time(b + LIFT_WINDOW_BEATS, beats)
            idx = np.flatnonzero((np.arange(len(dist)) * common.HOP_SECONDS >= lo) & (np.arange(len(dist)) * common.HOP_SECONDS < hi))
            if len(idx):
                candidate.append(float(dist[idx].mean()))
        per_song[key] = (len(lift_times), np.array(candidate))
    if not observed:
        return {"lifts": lift_counts, "windows": 0, "pass": False, "note": "no lifts"}
    rng = np.random.default_rng(SEED_PERM)
    stat = float(np.mean(observed))
    draws = np.empty(cfg.n_draws)
    for d in range(cfg.n_draws):
        chosen = []
        for n, pool in per_song.values():
            if len(pool):
                chosen += list(rng.choice(pool, size=n, replace=len(pool) < n))
        draws[d] = np.mean(chosen) if chosen else np.nan
    p = float((1 + np.nansum(draws >= stat)) / (cfg.n_draws + 1))
    return {"lifts": lift_counts, "windows": len(observed), "statistic": stat, "nullMean": float(np.nanmean(draws)),
            "nullInterval": common.interval(draws[np.isfinite(draws)]), "p": p, "pass": bool(p < 0.05)}


def dial_correlation(readout_arousal, dial_steps):
    n = min(len(readout_arousal), len(dial_steps))
    a, b = readout_arousal[:n], dial_steps[:n]
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3:
        return float("nan"), int(ok.sum())
    return float(np.corrcoef(a[ok], b[ok])[0, 1]), int(ok.sum())


def mean_over(series, span, hop=common.HOP_SECONDS):
    lo, hi = int(round(span[0] / hop)), int(round(span[1] / hop))
    return float(np.mean(series[lo:hi]))


def gate5(song_out, dial, world):
    by_key = {c.key: c for c in world.songs}
    result = {"songs": {}}
    fy = song_out["five-years"]["va_core"][:, 1]
    fy_ref = song_out["five-years"]["va_ref"][:, 1]
    opening, climax = mean_over(fy, FIVE_YEARS_OPENING), mean_over(fy, FIVE_YEARS_CLIMAX)
    result["fiveYears"] = {"opening": opening, "climax": climax, "reference": [mean_over(fy_ref, FIVE_YEARS_OPENING), mean_over(fy_ref, FIVE_YEARS_CLIMAX)],
                           "pass": bool(opening < climax)}
    g = song_out["presence"]["gems_core"]
    names = list(common.GEMS)
    span = np.array([mean_over(g[:, i], PRESENCE_SPAN) for i in range(9)])
    sad = names.index("sadness")
    lo, hi = int(round(PRESENCE_SPAN[0] / common.HOP_SECONDS)), int(round(PRESENCE_SPAN[1] / common.HOP_SECONDS))
    rest = np.delete(g[:, sad], np.arange(lo, min(hi, len(g))))
    rank = int((span > span[sad]).sum()) + 1
    result["presence"] = {"gemsInSpan": dict(zip(names, map(float, span))), "sadnessRank": rank,
                          "sadnessSpan": float(span[sad]), "sadnessRest": float(rest.mean()),
                          "pass": bool(rank <= 3 and span[sad] > rest.mean())}
    wins = 0
    for key, title, *_ in SONGS:
        steps = len(by_key[key].x)
        d = dial[key]
        if "energy10" not in d:
            result["songs"][key] = {"title": title, "note": "no pass A"}
            continue
        dial_steps = _dial_steps(d["energy10"], steps, d["masks"])
        r_core, n = dial_correlation(song_out[key]["va_core"][:, 1], dial_steps)
        r_ref, _ = dial_correlation(song_out[key]["va_ref"][:, 1], dial_steps)
        entry = {"title": title, "steps": n, "core": r_core, "reference": r_ref, "coreWins": bool(r_core > r_ref),
                 "source": d["source"].get("A")}
        if "light10" in d:
            light, heavy = _dial_steps(d["light10"], steps, d["masks"]), _dial_steps(d["heavy10"], steps, d["masks"])
            entry["passB"] = {
                "lightMinusHeavy_vs_valence": dial_correlation(song_out[key]["va_core"][:, 0], light - heavy)[0],
                "light_vs_joyful_activation": dial_correlation(song_out[key]["gems_core"][:, names.index("joyful_activation")], light)[0],
                **{f"heavy_vs_{n_}": dial_correlation(song_out[key]["gems_core"][:, names.index(n_)], heavy)[0]
                   for n_ in ("sadness", "tension", "nostalgia")}}
        wins += int(entry["coreWins"])
        result["songs"][key] = entry
    result["dial"] = {"wins": wins, "pass": bool(wins >= 2)}
    result["pass"] = bool(result["fiveYears"]["pass"] and result["presence"]["pass"] and result["dial"]["pass"])
    return result


# ------------------------------------------------------------------ the check

def curve_lifts(energy10, beats, duration, masks):
    return lifts.find_lifts(energy10, beats, duration, masks)


def run(world, dial, cfg, out_dir=None, log=print):
    """Everything. `dial` is load_dial's result. Returns the results dict (also written to out_dir)."""
    start = time.time()
    clips = world.deam + world.emotify + world.merp
    collected, shuffled, radii = {}, {}, {}
    for f in range(common.N_FOLDS):
        train = [c for c in clips if world.folds[c.key] != f]
        test = [c for c in clips if world.folds[c.key] == f]
        model, readouts, radius, scores = fit_model(train, cfg)
        collected.update(evaluate(model, readouts, test))
        shuffled.update(shuffled_predictions(model, readouts, test))
        radii[str(f)] = {"chosen": radius, "innerScores": {str(k): v for k, v in scores.items()}}
        log(f"fold {f}: spectral radius {radius} ({time.time() - start:.0f}s)")
    model, readouts, radius, scores = fit_model(clips, cfg)
    radii["all"] = {"chosen": radius, "innerScores": {str(k): v for k, v in scores.items()}}
    log(f"final model: spectral radius {radius}")
    songs = evaluate(model, readouts, world.songs)
    song_out = {}
    for c in world.songs:
        s = songs[c.key]
        song_out[c.key] = {"va_core": readouts["va_core"](s["mind"]), "va_ref": readouts["va_ref"](c.x),
                           "gems_core": readouts["gems_core"](s["mind"]), "dist": s["dist"]}

    results = {"gate1": gate1(collected, world, cfg), "gate2": gate2(collected, world, cfg),
               "gate3": gate3(collected, shuffled, world, cfg)}
    results["gate2"]["reference"] = gate2_reference(collected, world)
    merp_data, lift_report = [], {}
    for c in world.merp:
        curve = (c.extra["arousal10"] + 1.0) / 2.0
        times = curve_lifts(curve[np.isfinite(curve)], c.beats, c.extra["duration"], [])
        lift_report[c.key] = times
        merp_data.append((c.key, collected[c.key]["dist"], c.beats, times))
    song_data = []
    for c in world.songs:
        d = dial[c.key]
        times = curve_lifts(d["energy10"], c.beats, c.extra["duration"], d["masks"]) if "energy10" in d else []
        lift_report[c.key] = times
        song_data.append((c.key, song_out[c.key]["dist"], c.beats, times))
    results["gate4"] = {"merp": gate4(merp_data, cfg), "songs": gate4(song_data, cfg)}
    results["gate4"]["pass"] = bool(results["gate4"]["merp"]["pass"] and results["gate4"]["songs"]["pass"])
    results["gate5"] = gate5(song_out, dial, world)
    results["pass"] = bool(all(results[g]["pass"] for g in ("gate1", "gate2", "gate3", "gate4", "gate5")))
    results["radii"] = radii
    results["world"] = {"deam": len(world.deam), "emotify": len(world.emotify), "merp": len(world.merp), **world.info}
    results["seconds"] = round(time.time() - start, 1)
    if out_dir:
        out = pathlib.Path(out_dir)
        common.write_json(out / "results.json", results)
        common.write_json(out / "folds.json", world.folds)
        common.write_json(out / "lifts.json", {k: [round(float(t), 2) for t in v] for k, v in lift_report.items()})
    return results


def report(results, log=print):
    def ci(v):
        return f"{v[0]:.3f} [{v[1][0]:.3f}, {v[1][1]:.3f}]"
    g1 = results["gate1"]
    for ds in ("deam", "merp"):
        d = g1[ds]
        log(f"gate 1 {ds}: {d['songs']} songs ({d['songsDropped']} dropped, r undefined); within-song arousal r "
            f"core {ci(d['core'])}, reference {ci(d['reference'])}, core rho=0 {ci(d['core_rho0'])}; "
            f"valence core {ci(d['valence']['core'])}, reference {ci(d['valence']['reference'])} -> {'PASS' if d['pass'] else 'FAIL'}")
    log(f"GATE 1: {'PASS' if g1['pass'] else 'FAIL'}")
    g2 = results["gate2"]
    log(f"gate 2 timing R2 {g2['timing']['value']:.3f} [{g2['timing']['ci'][0]:.3f}, {g2['timing']['ci'][1]:.3f}] "
        f"(valence {g2['timing']['valence']:.3f}, arousal {g2['timing']['arousal']:.3f}) vs stage 1 {g2['timing']['stage1'][0]} "
        f"[{g2['timing']['stage1'][1]}, {g2['timing']['stage1'][2]}] -> {'PASS' if g2['timing']['pass'] else 'FAIL'}; "
        f"Emotify rank corr {g2['rho']['value']:.3f} [{g2['rho']['ci'][0]:.3f}, {g2['rho']['ci'][1]:.3f}] vs stage 1 "
        f"{g2['rho']['stage1'][0]} [{g2['rho']['stage1'][1]}, {g2['rho']['stage1'][2]}] -> {'PASS' if g2['rho']['pass'] else 'FAIL'}; "
        f"reference here: timing {g2['reference']['timing']:.3f}, rank corr {g2['reference']['rho']:.3f}")
    log(f"GATE 2: {'PASS' if g2['pass'] else 'FAIL'}")
    g3 = results["gate3"]
    for ds in ("deam", "merp"):
        d = g3[ds]
        log(f"gate 3 {ds}: {d['songs']} songs; r {ci(d['rOriginal'])} -> shuffled {ci(d['rShuffled'])} -> {'PASS' if d['pass'] else 'FAIL'}")
    log(f"GATE 3: {'PASS' if g3['pass'] else 'FAIL'}")
    for name in ("merp", "songs"):
        d = results["gate4"][name]
        counts = ", ".join(f"{k}: {v}" for k, v in d["lifts"].items()) if name == "songs" else \
            f"{sum(d['lifts'].values())} lifts in {sum(1 for v in d['lifts'].values() if v)} of {len(d['lifts'])} songs"
        log(f"gate 4 {name}: lifts {counts}; " + (f"statistic {d['statistic']:.4f}, null mean {d['nullMean']:.4f} "
            f"[{d['nullInterval'][0]:.4f}, {d['nullInterval'][1]:.4f}], p = {d['p']:.4f}" if "p" in d else d["note"])
            + f" -> {'PASS' if d['pass'] else 'FAIL'}")
    log(f"GATE 4: {'PASS' if results['gate4']['pass'] else 'FAIL'}")
    g5 = results["gate5"]
    log(f"gate 5 Five Years: opening {g5['fiveYears']['opening']:.3f}, climax {g5['fiveYears']['climax']:.3f} "
        f"(reference {g5['fiveYears']['reference'][0]:.3f}, {g5['fiveYears']['reference'][1]:.3f}) -> {'PASS' if g5['fiveYears']['pass'] else 'FAIL'}")
    p = g5["presence"]
    log(f"gate 5 Presence: sadness rank {p['sadnessRank']} of 9, span {p['sadnessSpan']:.3f}, rest {p['sadnessRest']:.3f} -> "
        f"{'PASS' if p['pass'] else 'FAIL'}")
    for key, e in g5["songs"].items():
        log(f"gate 5 dial {e['title']}: " + (e["note"] if "note" in e else
            f"{e['steps']} steps, r core {e['core']:.3f}, reference {e['reference']:.3f}, source {e['source']}"))
        if "passB" in e:
            log("  pass B (reported): " + ", ".join(f"{k} {v:.3f}" for k, v in e["passB"].items()))
    log(f"gate 5 dial: core ahead on {g5['dial']['wins']} of 3 -> {'PASS' if g5['dial']['pass'] else 'FAIL'}")
    log(f"GATE 5: {'PASS' if g5['pass'] else 'FAIL'}")
    log(f"OVERALL: {'PASS' if results['pass'] else 'FAIL'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(common.DATA / "check1b"))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    args = parser.parse_args(argv)
    cfg = Config()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} "
          f"core={mind.SEED_CORE} shuffle={mind.SEED_SHUFFLE} permutation={SEED_PERM}", flush=True)
    world = load_real()
    print(f"DEAM {len(world.deam)}, Emotify {len(world.emotify)}, MERP {len(world.merp)} clips; label variant {world.info['labelVariant']}", flush=True)
    dial = load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    results = run(world, dial, cfg, args.out, log=lambda s: print(s, flush=True))
    report(results)


if __name__ == "__main__":
    main()
