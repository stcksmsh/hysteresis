"""M3e runner (design: m3e.py docstring and docs/NIGHT_LOG_body-m3e.md).

    run_m3e.py --out DIR --lam L [--lr 1e-3 --epochs 40 --chunk-blocks 8 --eval tune|held --toy toy.npz --no-dopamine]

DIR/ckpt.pkl after every epoch (resumes), DIR/rollouts/ (saved before scoring), DIR/result.json at the end (both modes; the pass/fail is the argmax mode).
Provisional servo model (Feetech STS3215 12 V assumed).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3e
import m3e_jax as M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--toy", default="/secondary/hyst-data/body/m3d/toy.npz")
    ap.add_argument("--lam", type=float, required=True)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--chunk-blocks", type=int, default=8)
    ap.add_argument("--eval", choices=["tune", "held"], default="tune")
    ap.add_argument("--seed", type=int, default=0, help="Trainer seed (WO11: 1 = the second seed); 0 reproduces try 1")
    ap.add_argument("--no-dopamine", action="store_true")
    ap.add_argument("--ablate", choices=["none", "a1_closed_loop", "a2_gating", "a3_internal"], default="none", help="WO9 report-only ablations; none = try 1")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "rollouts").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    toy = m3e.ToyE(a.toy)
    C = M.load_cb()
    if a.ablate == "a1_closed_loop":
        C = {**C, "loop_gate": jnp.asarray(0.0)}
    tr = m3e.Trainer(toy, C, a.lam, a.lr, a.epochs, a.chunk_blocks, seed=a.seed, dopamine=not a.no_dopamine, log=log, gate=a.ablate != "a2_gating", internal=a.ablate != "a3_internal")
    ck = out / "ckpt.pkl"
    if ck.exists():
        tr.load(pickle.loads(ck.read_bytes()))
        log(f"resumed at epoch {tr.epoch}")
    else:
        tr.calibrate()
    while tr.epoch < a.epochs:
        tr.run_epoch()
        tmp = out / "ckpt.pkl.tmp"
        tmp.write_bytes(pickle.dumps(tr.state()))
        tmp.replace(ck)
        (out / "progress.json").write_text(json.dumps({"epoch": tr.epoch, "hist": tr.hist[-1]}))
    res, keep = m3e.score_policy(tr.fns, C, tr.P, toy, tr.stats, a.eval, a.chunk_blocks, rolldir=str(out / "rollouts"), name="trained", log=log)
    summary = {"args": vars(a), "eval_set": a.eval, "hist": tr.hist, "e0": tr.e0, "result": res, "input_group_norms": m3e.input_group_norms(tr.P)}
    if not a.no_dopamine:
        sigma = float(np.sqrt(tr.sd.var))
        delta, summ = m3e.dopamine_lane(tr.V, sigma, keep["argmax"][2], keep["argmax"][0], tr.stats, toy, a.eval)
        np.save(out / "dopamine_lane.npy", delta)
        summary["dopamine"] = summ
        log(f"dopamine: {summ}")
    log(f"input group norms: {summary['input_group_norms']}")
    (out / "result.json").write_text(json.dumps(summary, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
