"""MERP labels for the mind spike (docs/NEXT_BODY_THEN_MIND.md, step 2, "MERP as fetched").

The authors' filtered file keeps 3,482 trials (277 raters) but stores them at 2 Hz and
skips the first 12-17 s of each song. This module takes each kept trial's RAW 10 Hz series
(which starts at 0 s), rescales and smooths it the way the authors did, and averages the
trials of a song.

The authors' steps (github.com/dorienh/MERP, processing/pruning.py): rescale each rater's
values to [-1, 1] with that rater's own min and max over all their trials, then Savitzky-
Golay smoothing (window 15, order 2, mode "nearest") clipped to [-1, 1], then every 5th
sample to match the 2 Hz audio features. Which variant of these steps reproduces the
filtered file best is chosen by the data (`match_variants`): rescale per trial, per
rater, or not at all; smoothing before or after taking every 5th sample.

Time convention (not stated by the authors, assumed here): sample i of a 10 Hz series is the
rating at t = i / 10 s of the song.
"""
from __future__ import annotations

import itertools
from collections import defaultdict

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy.signal import savgol_filter

import common

RATE = 10
DECIMATION = 5
SG_WINDOW, SG_ORDER = 15, 2
# "none" is not one of the authors' described steps; it is here because it reproduces their filtered
# file far better than either rescale does (see the handoff), so the choice is left to the data.
VARIANTS = tuple(itertools.product(("none", "trial", "rater"), ("before", "after")))


def read_trials(name):
    """Trials of annotations_{raw,filtered}.parquet: [{rater, song, arousal, valence}]."""
    import pyarrow.parquet as pq
    table = pq.read_table(common.DATA / "merp" / "annotations" / f"annotations_{name}.parquet").to_pylist()
    return [{"rater": r["rater_id"], "song": r["song_id"],
             "arousal": np.asarray(r["arousal"], dtype=np.float64), "valence": np.asarray(r["valence"], dtype=np.float64)}
            for r in table]


def smooth(x):
    return np.clip(savgol_filter(x, SG_WINDOW, SG_ORDER, mode="nearest"), -1.0, 1.0)


def rescale(x, lo, hi):
    """Map [lo, hi] to [-1, 1]; a flat series maps to 0."""
    return np.zeros_like(x) if hi <= lo else (x - lo) / (hi - lo) * 2.0 - 1.0


def best_offset(candidate, target, step=DECIMATION):
    """Offset o minimising the mean squared error of candidate[o::step][:len(target)] to target.
    -> (offset, mse) or None when the candidate is too short."""
    length = len(target)
    span = step * (length - 1) + 1
    if len(candidate) < span:
        return None
    windows = sliding_window_view(candidate, span)[:, ::step]
    err = ((windows - target) ** 2).mean(axis=1)
    o = int(err.argmin())
    return o, float(err[o])


def _trial_score(raw, filt):
    """Match of one raw trial to one filtered trial: summed best MSE over both axes (per-trial
    rescale, smoothing first). Lower is better; inf when the raw trial is too short."""
    total = 0.0
    for axis in ("arousal", "valence"):
        x = raw[axis]
        found = best_offset(smooth(rescale(x, x.min(), x.max())), filt[axis])
        if found is None:
            return float("inf")
        total += found[1]
    return total


def resolve_kept(raw_trials, filtered_trials):
    """One raw trial per filtered (kept) trial. Where a rater has several raw trials of a song,
    the one that matches the filtered series best. -> [(raw, filtered)], n_duplicates_resolved."""
    by_key = defaultdict(list)
    for t in raw_trials:
        by_key[(t["rater"], t["song"])].append(t)
    pairs, duplicates = [], 0
    for filt in filtered_trials:
        candidates = by_key.get((filt["rater"], filt["song"]), [])
        if not candidates:
            raise ValueError(f"kept trial {filt['rater']}/{filt['song']} has no raw trial")
        if len(candidates) > 1:
            duplicates += 1
            candidates = [min(candidates, key=lambda c: _trial_score(c, filt))]
        pairs.append((candidates[0], filt))
    return pairs, duplicates


def _limits(pairs):
    """Per rater min and max over their kept raw trials, per axis."""
    lim = {}
    for raw, _ in pairs:
        for axis in ("arousal", "valence"):
            lo, hi = lim.get((raw["rater"], axis), (np.inf, -np.inf))
            lim[(raw["rater"], axis)] = (min(lo, raw[axis].min()), max(hi, raw[axis].max()))
    return lim


def _bounds(variant, raw, axis, limits):
    """The (lo, hi) the rescale step maps to [-1, 1]; (-1, 1) leaves a series unchanged."""
    if variant[0] == "none":
        return -1.0, 1.0
    if variant[0] == "rater":
        return limits[(raw["rater"], axis)]
    return raw[axis].min(), raw[axis].max()


def process_trial(raw, axis, variant, limits):
    """10 Hz series of one axis under `variant` = (rescale, smoothing); smoothing "after" is a
    property of the 2 Hz comparison only, so the 10 Hz series is smoothed in both cases."""
    return smooth(rescale(raw[axis], *_bounds(variant, raw, axis, limits)))


def match_variants(pairs):
    """How well each variant reproduces the filtered file on the overlap.
    -> {variant: {"rmse": mean over trials of the RMSE, "rmseMedian", "fractionUnder0.01", "trials"}}."""
    limits = _limits(pairs)
    out = {}
    for variant in VARIANTS:
        errors = []
        for raw, filt in pairs:
            mse = 0.0
            for axis in ("arousal", "valence"):
                scaled = rescale(raw[axis], *_bounds(variant, raw, axis, limits))
                if variant[1] == "before":
                    found = best_offset(smooth(scaled), filt[axis])
                    if found is None:
                        mse = np.nan
                        break
                    mse += found[1] / 2
                else:
                    length = len(filt[axis])
                    best = np.inf
                    for o in range(len(scaled) - DECIMATION * (length - 1)):
                        best = min(best, float(((smooth(scaled[o::DECIMATION][:length]) - filt[axis]) ** 2).mean()))
                    mse += best / 2
            errors.append(np.sqrt(mse))
        errors = np.array(errors)
        errors = errors[np.isfinite(errors)]
        out[variant] = {"rmse": float(errors.mean()), "rmseMedian": float(np.median(errors)),
                        "fractionUnder0.01": float((errors < 0.01).mean()), "trials": int(len(errors))}
    return out


def choose_variant(report):
    return min(report, key=lambda v: (report[v]["rmse"], v))


def step_means(series, n_steps):
    """0.5 s step means of a 10 Hz series: step k covers t in [0.5 k - 0.25, 0.5 k + 0.25),
    sample i being t = i / 10 s. NaN where no sample falls in the step."""
    out = np.full(n_steps, np.nan)
    for k in range(n_steps):
        lo, hi = max(0, int(np.ceil(5 * k - 2.5 - 1e-9))), int(np.ceil(5 * k + 2.5 - 1e-9))
        chunk = series[lo:hi]
        chunk = chunk[np.isfinite(chunk)]
        if len(chunk):
            out[k] = chunk.mean()
    return out


def song_labels(pairs, variant, durations):
    """Per-song mean over the kept trials. -> {song: {"arousal10", "valence10" (10 Hz, length
    ceil(10 duration)), "arousal", "valence" (0.5 s step means, int(duration/0.5)+1 steps), "trials"}}."""
    limits = _limits(pairs)
    grouped = defaultdict(list)
    for raw, _ in pairs:
        grouped[raw["song"]].append(raw)
    out = {}
    for song, trials in grouped.items():
        if song not in durations:
            continue
        n10 = int(np.ceil(durations[song] * RATE))
        n_steps = int(durations[song] / common.HOP_SECONDS) + 1
        entry = {"trials": len(trials)}
        for axis in ("arousal", "valence"):
            stack = np.full((len(trials), n10), np.nan)
            for i, raw in enumerate(trials):
                x = process_trial(raw, axis, variant, limits)[:n10]
                stack[i, :len(x)] = x
            with np.errstate(all="ignore"):
                mean10 = np.nanmean(stack, axis=0)
            entry[axis + "10"] = mean10
            entry[axis] = step_means(mean10, n_steps)
        out[song] = entry
    return out


def load_merp_labels(durations):
    """Everything from disk: -> (labels per song, variant report, chosen variant, n duplicates)."""
    raw, filtered = read_trials("raw"), read_trials("filtered")
    pairs, duplicates = resolve_kept(raw, filtered)
    report = match_variants(pairs)
    variant = choose_variant(report)
    return song_labels(pairs, variant, durations), report, variant, duplicates
