#!/usr/bin/env python3
"""Dry run for check3.py: counts, fitting time and rendering time. Computes no check 3 statistic (no Spearman, no
shuffle, no bootstrap, no lane-label correlation, no dial) and reads no dial file.

  python check3_dry.py   fold 0, stage-1 source: segment counts per set, mood fit, k choice, map fit, render of
                         the held-out decoded bodies and of 1,000 training bodies, with times
"""
from __future__ import annotations

import time

import numpy as np

import check3
import common
import decoder
import mood
import render


def main():
    render.build()
    t = time.time()
    clips, folds, world = check3.load_corpus()
    print(f"loaded in {time.time() - t:.0f} s: DEAM {len(world.deam)}, Emotify {len(world.emotify)}, MERP {len(world.merp)}, songs {len(world.songs)}")
    by = {}
    for i, s in check3.segment_table(clips):
        c = clips[i]
        key = (c.ds, folds[c.key])
        by[key] = by.get(key, 0) + 1
    for ds in ("deam", "emotify", "merp", "song"):
        print(f"segments {ds}: " + ", ".join(f"fold {f}: {n}" for (d, f), n in sorted(by.items()) if d == ds))
    total = sum(by.values())
    print(f"segments total {total}; by fold " + str({f: sum(n for (d, g), n in by.items() if g == f) for f in range(6)}))
    cfg = check3.Config(core=False)
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    train, test = check3.split(clips, folds, 0)
    feats = {c.key: c.x for c in clips}
    t = time.time()
    model = check3.fit_mood(train, feats, mood.SOURCE_STAGE1)
    print(f"mood model fit (fold 0, {len(train)} training clips): {time.time() - t:.0f} s")
    t = time.time()
    lanes_tr, keys_tr = check3.segment_lanes(model, feats, train)
    print(f"training segment lanes: {lanes_tr.shape} in {time.time() - t:.0f} s")
    t = time.time()
    k, scores = decoder.choose_k(lanes_tr, keys_tr, surrogate)
    print(f"k chosen {k} in {time.time() - t:.0f} s")
    t = time.time()
    fitted = decoder.fit_map(lanes_tr[:, :2 + k], surrogate)
    print(f"map fit: {time.time() - t:.0f} s")
    lanes_te, _ = check3.segment_lanes(model.with_k(k), feats, test)
    sample = fitted.bodies(lanes_te[np.random.default_rng(0).permutation(len(lanes_te))[:500]])
    out = render.render(sample)
    print(f"render of {len(sample)} held-out decoded bodies x 3 seeds: {out['seconds']:.1f} s ({out['seconds'] / len(sample) * 1000:.1f} ms per segment)")
    print(f"rendered ok: {int(out['ok'].sum())} of {len(sample)}")


if __name__ == "__main__":
    main()
