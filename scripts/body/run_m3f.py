"""M3f runner (design: m3f.py docstring and docs/NIGHT_LOG_body-m3f.md).

    run_m3f.py --out DIR --lam L [--lr 1e-3 --epochs 40 --eval tune|held --seed 0] [--body v1|v2] [--w-jerk W] [--w-switch W]
               [--no-obs-lp] [--no-phase-lp] [--no-xfade] [--no-pen]

Movement changes 2-4 are ON by default (switches), 1 (jerk) is on when --w-jerk > 0, the body is v2 and the body penalties are on; each is turned off alone with its flag (ablations).
DIR/ckpt.pkl after every epoch (resumes), DIR/rollouts/ (saved before scoring), DIR/result.json at the end. Provisional servo model (Feetech STS3215 12 V assumed).
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import m3e
import m3e_jax as M
import m3f


def build(a, toy, C, log):
    cfg = {"body": a.body, "obs_lp": not a.no_obs_lp, "phase_lp": not a.no_phase_lp, "xfade": not a.no_xfade}
    if a.hard_clip:
        cfg["clip"] = True                                        # only added when asked, so earlier runs' cfg (and their checkpoints) are unchanged
    opts = {"internal": True, "pen": a.body != "v1" and not a.no_pen, "jerk": a.w_jerk > 0, "sw": a.w_switch > 0 and cfg["xfade"], "pen2": a.body != "v1" and a.floor_acc_hinges}
    tr = m3f.Trainer(toy, C, cfg, a.lam, a.lr, a.epochs, a.chunk_blocks, seed=a.seed, dopamine=True, log=log, opts=opts, w_jerk=a.w_jerk, w_sw=a.w_switch)
    return cfg, tr


def add_args(ap):
    ap.add_argument("--toy", default="/secondary/hyst-data/body/m3d/toy.npz")
    ap.add_argument("--lam", type=float, default=0.03)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--chunk-blocks", type=int, default=8)
    ap.add_argument("--eval", choices=["tune", "held"], default="tune")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--body", choices=["v1", "v2", "v2f"], default="v2f")
    ap.add_argument("--w-jerk", type=float, default=0.0)
    ap.add_argument("--w-switch", type=float, default=0.0)
    ap.add_argument("--no-obs-lp", action="store_true")
    ap.add_argument("--no-phase-lp", action="store_true")
    ap.add_argument("--no-xfade", action="store_true")
    ap.add_argument("--no-pen", action="store_true")
    ap.add_argument("--floor-acc-hinges", action="store_true", help="BRAIN_SPEC 7.27 point 1: floor-margin and hand-acceleration hinges, weight 1 each (m3f.W_FLOOR, W_ACC)")
    ap.add_argument("--hard-clip", action="store_true", help="BRAIN_SPEC 7.27 point 2: targets of every ranged joint clipped CLIP_MARGIN_DEG inside the range (new body only)")
    ap.add_argument("--max-epochs-now", type=int, default=0, help="stop after this many epochs of this call (0 = all; for timing)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    add_args(ap)
    a = ap.parse_args()
    out = Path(a.out)
    (out / "rollouts").mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    toy = m3f.ToyF(a.toy)
    C = M.load_cb()
    cfg, tr = build(a, toy, C, log)
    log(f"cfg {cfg} opts {tr.opts} weights {tr.w} lam {a.lam} seed {a.seed}")
    ck = out / "ckpt.pkl"
    if ck.exists():
        tr.load(pickle.loads(ck.read_bytes()))
        log(f"resumed at epoch {tr.epoch}")
    else:
        tr.calibrate()
    done = 0
    while tr.epoch < a.epochs:
        tr.run_epoch()
        tmp = out / "ckpt.pkl.tmp"
        tmp.write_bytes(pickle.dumps(tr.state()))
        tmp.replace(ck)
        (out / "progress.json").write_text(json.dumps({"epoch": tr.epoch, "hist": tr.hist[-1]}))
        done += 1
        if a.max_epochs_now and done >= a.max_epochs_now:
            log("stopped early (timing run)")
            return 0
    res, keep = m3f.score_policy(tr.fns, cfg, C, tr.P, toy, tr.stats, a.eval, a.chunk_blocks, rolldir=str(out / "rollouts"), name="trained", log=log)
    summary = {"args": vars(a), "cfg": cfg, "opts": tr.opts, "eval_set": a.eval, "hist": tr.hist, "e0": tr.e0, "nrm": tr.nrm, "raw0_old_body": tr.raw0, "raw_this_body": tr.raw_new, "result": res, "input_group_norms": m3e.input_group_norms(tr.P)}
    (out / "result.json").write_text(json.dumps(summary, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
