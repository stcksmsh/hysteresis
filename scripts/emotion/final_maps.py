#!/usr/bin/env python3
"""Fit the final mood model and decoder map of each encoding exactly as check3r2.py does for the user's
songs (the sixth set: fitted on all five folds' clips, never on the user's songs) and save them for
mindstate.py and bodytrack.py (docs/NEXT_DECODER_THEN_BRAIN.md, D3).

Usage: python final_maps.py OUT_DIR [--check DIR]

Writes OUT_DIR/{stage1,baseline49}.model.npz (mood.MoodModel) and OUT_DIR/{stage1,baseline49}.map.npz
(bodytrack.save_map) and OUT_DIR/reproduction.json. Nothing is chosen here: the settings are check3r2's
(bounded map, round 2). With --check DIR (check3r2's output directory) it compares the bodies and lanes
it gets for the sixth set with the ones check3r2 saved in segments_5.npz and reports the largest
absolute difference per encoding; it does not stop on a difference.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

import numpy as np

import bodytrack
import check1b as c1
import check3 as c3
import common
import decoder
import mood

ENCODINGS = {"stage1": ("decoder", mood.SOURCE_STAGE1, None),
             "baseline49": ("baseline49", mood.SOURCE_BASELINE49, c3.BASELINE_COLUMNS)}


def fit_final(clips, folds, surrogate, cfg, log=print):
    """-> {encoding: prep} where prep is c3.prepare's result for the sixth set (model, k, map, lanes)."""
    train, test = c3.split(clips, folds, c3.SIXTH)
    stage1 = {c.key: c.x for c in clips}
    out = {}
    for name, (_, source, columns) in ENCODINGS.items():
        out[name] = c3.prepare(train, test, stage1, source, columns, surrogate, cfg)
        log(f"{name}: k {out[name]['k']}, bounds {json.dumps(out[name]['links']['bounds'])}, met {out[name]['links']['met']}")
    return out


def compare(final, check_dir):
    """Largest absolute difference of the sixth-set bodies and lanes against check3r2's saved ones."""
    saved = np.load(pathlib.Path(check_dir) / f"segments_{c3.SIXTH}.npz")
    report = {}
    for name, (saved_name, _, _) in ENCODINGS.items():
        prep = final[name]
        bodies = prep["map"].bodies(prep["lanes_te"])
        old_lanes, old_bodies = saved[f"{saved_name}/lanes"], saved[f"{saved_name}/bodies"]
        report[name] = {"segments": int(len(old_bodies)), "keysEqual": bool((saved[f"{saved_name}/keys"] == np.array(prep["keys_te"])).all()),
                        "lanesMaxAbsDiff": float(np.abs(prep["lanes_te"] - old_lanes).max()) if old_lanes.shape == prep["lanes_te"].shape else None,
                        "bodiesMaxAbsDiff": float(np.abs(bodies - old_bodies).max()) if old_bodies.shape == bodies.shape else None}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("out")
    parser.add_argument("--check")
    args = parser.parse_args(argv)
    cfg = c3.Config(core=False, bound=True)
    clips, folds, _ = c3.load_corpus()
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    final = fit_final(clips, folds, surrogate, cfg, log=lambda s: print(s, flush=True))
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, prep in final.items():
        prep["model"].save(out / f"{name}.model.npz")
        bodytrack.save_map(out / f"{name}.map.npz", prep["map"], f"{ENCODINGS[name][1]}-final")
    report = compare(final, args.check) if args.check else {}
    common.write_json(out / "reproduction.json", report)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main(sys.argv[1:])
