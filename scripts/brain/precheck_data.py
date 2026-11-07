"""Data side of the DEAM / MERP within-song arousal pre-check (BRAIN_SPEC 4.6, reported only). Reads DEAM and MERP audio and labels as
scripts/emotion/check1b.py does (common.deam_clips, common.deam_dynamic, merp_features, merp_labels; beats from the stage-1 mind cache).

Per clip, per 0.5 s step: brain = the magnitudes of the 4 x 256 complex modes at the end of each 100 ms bin, averaged over the step (1,024
values); fast = the 44 standardised fast features averaged over the step; y = the arousal label of that step (NaN where there is none).
Clips without a cached beat grid get phase (1, 0) throughout. `run` returns check_b3.precheck's result.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "emotion"))
import b2  # noqa: E402
import core  # noqa: E402
import fast_features  # noqa: E402


def clip_features(model, audio_path, beats, mean, std, n_steps):
    """-> brain (n_steps, 1024), fast (n_steps, 44)."""
    feats = fast_features.fast_features(b2.decode(audio_path))
    x = b2.build_inputs(feats, beats, mean, std) if beats is not None else np.concatenate(
        [np.clip((feats - mean) / np.maximum(std, 1e-8), -core.CLIP, core.CLIP), np.tile([1.0, 0.0], (len(feats), 1))], 1).astype(np.float32)
    run = b2.run_core(model, x)
    mags = np.concatenate([np.hypot(s[:, :core.N], s[:, core.N:]) for s in run["states"]], 1)
    fast = x[:len(mags) * b2.STRIDE, :core.FEAT].reshape(len(mags), b2.STRIDE, core.FEAT).mean(1)
    pool = lambda a, per: np.vstack([a[i * per:(i + 1) * per].mean(0) for i in range(min(n_steps, len(a) // per))]) if len(a) >= per else a[:0]
    out = []
    for a, per in ((mags, 5), (fast, 5)):
        p = pool(a, per)
        full = np.full((n_steps, a.shape[1]), np.nan)
        full[:len(p)] = p
        out.append(full)
    return out[0], out[1]


def run(model, stats, core2b_path, precheck_fn, limit=None):
    import common
    import merp_features
    import merp_labels
    mean, std = stats
    clips = []
    dyn = common.deam_dynamic("arousal")
    for key, path in common.deam_clips()[:limit]:
        sid = int(key.split("_")[1])
        if sid not in dyn or not path.exists():
            continue
        times, values = dyn[sid]
        times = times[:len(values)]
        times, values = times[np.isfinite(values)], values[np.isfinite(values)]
        if not len(times):
            continue
        n_steps = int(round(times[-1] / common.HOP_SECONDS)) + 1
        y = np.full(n_steps, np.nan)
        y[np.round(times / common.HOP_SECONDS).astype(int)] = values
        beat_file = common.CACHE / "mind" / "beats" / f"{key}.json"
        beats = np.asarray(json.loads(beat_file.read_text())["beats"]) if beat_file.exists() else None
        brain, fast = clip_features(model, path, beats, mean, std, n_steps)
        clips.append({"key": key, "dataset": "deam", "brain": brain, "fast": fast, "y": y})
    songs = merp_features.merp_songs()
    labels = merp_labels.load_merp_labels(dict(songs))[0]
    for song, duration in songs[:limit]:
        path = merp_features.MERP / "audio" / f"{song}.wav"
        y = np.asarray(labels[song]["arousal"], dtype=np.float64)
        beat_file = common.CACHE / "mind" / "beats" / f"merp_{song}.json"
        beats = np.asarray(json.loads(beat_file.read_text())["beats"]) if beat_file.exists() else None
        brain, fast = clip_features(model, path, beats, mean, std, len(y))
        clips.append({"key": f"merp_{song}", "dataset": "merp", "brain": brain, "fast": fast, "y": y})
    folds = common.assign_folds([c["key"] for c in clips])
    core2b = None
    if core2b_path:
        z = np.load(core2b_path)
        core2b = {k: z[k] for k in z.files}
    return precheck_fn(clips, folds, core2b)
