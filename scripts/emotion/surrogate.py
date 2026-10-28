#!/usr/bin/env python3
"""Fit the surrogate of the decoder (decoder.py): body vector -> 37 descriptors, learned on rendered bodies.

  python surrogate.py render   write 20,000 uniform body vectors (fixed seed) for body_render and run it
  python surrogate.py fit      fit on the first 16,000 that rendered, report R^2 on the other 4,000 (held out)

Uniform bodies are drawn independently of any song; the surrogate only steers the decoder's fit, check 3
scores real renders. Output under /secondary/hyst-data/emotion/check3/ (outside git).
"""
from __future__ import annotations

import json
import sys

import numpy as np

import common
import decoder
import render

DIR = common.DATA / "check3"
SEED_BODIES = 20261028
N_BODIES = 20000
N_TRAIN = 16000


def make_bodies():
    return np.random.default_rng(SEED_BODIES).random((N_BODIES, render.DIMENSIONS))


def run_render():
    DIR.mkdir(parents=True, exist_ok=True)
    bodies = make_bodies()
    out = render.render(bodies)
    np.savez_compressed(DIR / "surrogate_renders.npz", bodies=bodies, **out)
    print(f"{len(bodies)} bodies, {out['ok'].sum()} feasible, {out['seconds']:.0f} s")


def fit():
    z = np.load(DIR / "surrogate_renders.npz")
    ok = z["ok"]
    bodies, desc = z["bodies"][ok], z["desc"][ok]
    train, held = slice(0, N_TRAIN), slice(N_TRAIN, None)
    train, held = slice(0, N_TRAIN), slice(N_TRAIN, None)
    s = decoder.Surrogate().fit(bodies[train], desc[train])
    r2 = s.r2(bodies[held], desc[held])
    s.save(DIR / "surrogate.pt")
    report = {"bodies": int(len(ok)), "feasible": int(ok.sum()), "train": int(len(bodies[train])),
              "heldOut": int(len(bodies[held])), "r2PerDescriptor": r2.round(4).tolist(),
              "r2Mean": float(r2.mean()), "r2Min": float(r2.min()), "r2Median": float(np.median(r2))}
    common.write_json(DIR / "surrogate_report.json", report)
    print(json.dumps({k: v for k, v in report.items() if k != "r2PerDescriptor"}))


if __name__ == "__main__":
    {"render": run_render, "fit": fit}[sys.argv[1]]()
