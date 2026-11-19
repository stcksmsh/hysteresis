"""Render body vectors with the real body generator (crates/hyst-previz/examples/body_render.rs).

`render(bodies)` returns, per body, the mean over the three fixed seeds of the 37 descriptors of the
clips `body.rs` makes (each on the existing stretch ladder), or ok=False when any of the three is still
infeasible after the ladder. Nothing is approximated here; the surrogate lives in decoder.py.
"""
from __future__ import annotations

import json
import os
import pathlib
import subprocess
import tempfile

import numpy as np

SEEDS = (20261028, 20261029, 20261030)
REPO = pathlib.Path(__file__).resolve().parents[2]
BINARY = pathlib.Path(os.environ.get("HYST_BODY_RENDER", REPO / "target" / "release" / "examples" / "body_render"))
DESCRIPTORS = 37
DIMENSIONS = 15


def build():
    """cargo build of the render binary (a no-op when it is current)."""
    subprocess.run(["cargo", "build", "--release", "-p", "hyst-previz", "--example", "body_render"],
                   cwd=REPO, check=True, capture_output=True)


def render(bodies, seeds=SEEDS, binary=None):
    """bodies (n, 15) in 0..1 -> dict(ok (n,) bool, desc (n, 37) float64 with NaN where not ok,
    stretch (n, len(seeds)) float64 with NaN where not ok, seconds float)."""
    bodies = np.asarray(bodies, dtype=np.float64)
    if bodies.ndim != 2 or bodies.shape[1] != DIMENSIONS or ((bodies < 0) | (bodies > 1)).any():
        raise ValueError("bodies must be (n, 15) with values in 0..1")
    if not len(bodies):
        return {"ok": np.zeros(0, bool), "desc": np.zeros((0, DESCRIPTORS)), "stretch": np.zeros((0, len(seeds))), "seconds": 0.0}
    binary = pathlib.Path(binary or BINARY)
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = pathlib.Path(tmp) / "in.json", pathlib.Path(tmp) / "out.json"
        src.write_text(json.dumps({"seeds": list(seeds), "bodies": bodies.tolist()}))
        subprocess.run([str(binary), str(src), str(dst)], check=True, capture_output=True)
        out = json.loads(dst.read_text())
    ok = np.array(out["ok"], dtype=bool)
    desc = np.full((len(bodies), DESCRIPTORS), np.nan)
    stretch = np.full((len(bodies), len(seeds)), np.nan)
    for i in np.flatnonzero(ok):
        desc[i], stretch[i] = out["desc"][i], out["stretch"][i]
    return {"ok": ok, "desc": desc, "stretch": stretch, "seconds": float(out["seconds"])}
