#!/usr/bin/env python3
"""Beat grids for the clips and songs that have no sidecar (docs/NEXT_BODY_THEN_MIND.md, step 2).

The beat tracker is Essentia's RhythmExtractor2013, method "multifeature" (essentia-tensorflow
2.1b6.dev1389), run on the clip at 44.1 kHz mono. The three danced songs keep their sidecar
grids and do not pass through here. Writes CACHE/mind/beats/<key>.json:
  {"beats": [seconds...], "bpm": float, "confidence": float, "fallback": bool}
A clip where the tracker returns fewer than 8 beats gets a fixed 120 bpm grid and
"fallback": true; the count of such clips is reported by `summary`.

  python beats.py deam|emotify|merp [--workers N]      (resumable)
  python beats.py summary
"""
from __future__ import annotations

import argparse
import json
import sys
from multiprocessing import Pool

import numpy as np

import common
import extract

OUT = common.CACHE / "mind" / "beats"
MIN_BEATS = 8
FALLBACK_BPM = 120.0


def track(path):
    import essentia.standard as es
    audio = extract.load_audio(path, 44100)
    bpm, ticks, confidence, _, _ = es.RhythmExtractor2013(method="multifeature")(audio)
    ticks = [float(t) for t in ticks]
    fallback = len(ticks) < MIN_BEATS
    if fallback:
        step = 60.0 / FALLBACK_BPM
        ticks = [round(i * step, 6) for i in range(int(len(audio) / 44100 / step) + 1)]
    return {"beats": ticks, "bpm": float(bpm), "confidence": float(confidence), "fallback": fallback}


def _one(item):
    key, path = item
    target = OUT / f"{key}.json"
    if not target.exists():
        common.write_json(target, track(path))
    return key


def clips(which):
    if which == "deam":
        return common.deam_clips()
    if which == "emotify":
        return common.emotify_clips()
    import merp_features
    return [(f"merp_{s}", merp_features.MERP / "audio" / f"{s}.wav") for s, _ in merp_features.merp_songs()]


def summary():
    files = sorted(OUT.glob("*.json"))
    data = [json.loads(p.read_text()) for p in files]
    fallback = [p.stem for p, d in zip(files, data) if d["fallback"]]
    print(f"{len(files)} grids, {len(fallback)} fallback; bpm median {np.median([d['bpm'] for d in data]):.1f}")
    return fallback


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("which", choices=("deam", "emotify", "merp", "summary"))
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.which == "summary":
        summary()
        sys.exit(0)
    OUT.mkdir(parents=True, exist_ok=True)
    work = clips(args.which)
    with Pool(args.workers) as pool:
        for i, key in enumerate(pool.imap_unordered(_one, work), 1):
            if i % 100 == 0:
                print(i, key, flush=True)
