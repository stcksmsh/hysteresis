"""M3d runner (see m3d.py for the stated design).

    run_m3d.py --out DIR --lam L [--lr 1e-3 --epochs 40 --chunk-blocks 8 --eval tune|held --toy toy.npz]

Writes DIR/log.txt lines to stdout, DIR/ckpt.pkl after every epoch (resumes from it), DIR/result.json at the end. Provisional servo model (Feetech STS3215 12 V assumed).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import m3d
import m3d_jax as J


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--toy", default="/secondary/hyst-data/body/m3d/toy.npz")
    ap.add_argument("--lam", type=float, required=True)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--chunk-blocks", type=int, default=8)
    ap.add_argument("--obs-hidden", type=int, default=64)
    ap.add_argument("--eval", choices=["tune", "held"], default="tune")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    toy = m3d.Toy(a.toy)
    tr = m3d.Trainer(toy, a.lam, a.lr, a.epochs, a.chunk_blocks, a.obs_hidden, log=log)
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
    O = tr.final_observer()
    res = {"args": vars(a), "eval_set": a.eval, "hist": tr.hist, "e0": tr.e0, "result": m3d.evaluate(tr.fns, tr.P, O, tr.stats, toy, a.eval, a.chunk_blocks, log=log)}
    (out / "result.json").write_text(json.dumps(res, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
