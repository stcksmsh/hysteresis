"""K5-pass2 trainer (work order 14B, docs/BRAIN_SPEC.md 7.22-7.27). k5_train.K5Run (data, order, early stopping, checkpoints, pause/stop/mains, compute box) driving m3f.Trainer
(body v2f, movement changes 1-4, jerk and switch costs) instead of m3e.Trainer. k5_train.py, m3e*.py, m3f*.py are imported, never edited. Provisional servo model. One arm.

    k5p2_train.py --out DIR [--k5 /secondary/hyst-data/body/k5] [--max-rounds N] [--no-chain]      resume-safe

Differences from try 1 only: CFG (body v2f, obs_lp, phase_lp, xfade on), W_JERK 0.03, W_SWITCH 0.01, the windows carry the L3 order parameter R (m3f.ToyF's input), rollouts and
observers use cfg-sized carries and inputs, BOX_H 30 (7.27 point 5). The 7.27 hinges and hard clip arrive through m3f.Trainer opts / cfg when work order 14A is merged: put them in
OPTS / CFG below (nothing else changes). Seed and window order as try 1.
"""
import argparse
import json
import os
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import m3d
import m3e
import m3e_jax as M
import m3f
import m3f_jax as F

import make_arm_v2 as V2

assert V2.RAISED_PLANE_Z is not None
# = run_m3f.py build() with --body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane --w-floor 1.0 (BRAIN_SPEC 7.30.8); the values come from agent 2's code
CFG = dict(body="v2f", obs_lp=True, phase_lp=True, xfade=True, ctc=0.006, plane=V2.RAISED_PLANE_Z, smooth_u=True, clip=True)      # smooth_u = --smooth-u (WO17, 7.32)
OPTS = {"internal": True, "pen": True, "jerk": True, "sw": True, "pen2": True}      # pen2 = --floor-acc-hinges (W_FLOOR = W_ACC = 1, 7.27)
W_JERK, W_SWITCH, W_FLOOR = 0.03, 0.01, 1.0
T.BOX_H = 30.0
NB = T.NB


class WindowToyF(T.WindowToy):
    """WindowToy plus the L3 order parameter input R of the previous block (as m3f.ToyF)."""

    def _r(self):
        self.R = np.clip(np.hypot(self.y[..., 2], self.y[..., 3]), 0.0, 1.0)

    def inputs(self, idx, key):
        d = super().inputs(idx, key)
        r = self.R[idx]
        d["R"] = jnp.asarray(np.concatenate([np.zeros_like(r[:, :1]), r[:, :-1]], 1))
        return d


def build_toy(k5, split, wins):
    t = T.build_toy(k5, split, wins)
    t.__class__ = WindowToyF
    t._r()
    return t


def combine(a, b):
    t = T.combine(a, b)
    t.__class__ = WindowToyF
    t.R = np.concatenate([a.R, b.R])
    return t


def rollout_batched(fns, cfg, C, P, toy, sl, mode, key, seed, batch=None, cb=8, cache=None):
    """k5_train.rollout_batched with m3f carries (same batching, padding, cache and SIGTERM points)."""
    ids = np.arange(*sl.indices(len(toy.y)))
    batch = min(batch or T.EVAL_BATCH, len(ids))
    poses = m3d.start_poses(len(ids), seed)
    outs = []
    for i0 in range(0, len(ids), batch):
        f = None if cache is None else Path(f"{cache}_b{i0}.npz")
        if f is not None and f.exists():
            d = np.load(f)
            outs.append({k: d[k] for k in d.files})
            continue
        sub = ids[i0:i0 + batch]
        n = len(sub)
        sub = np.concatenate([sub, np.repeat(sub[-1:], batch - n)]) if n < batch else sub
        pp = np.concatenate([poses[i0:i0 + n], np.repeat(poses[i0 + n - 1:i0 + n], batch - n, 0)]) if n < batch else poses[i0:i0 + n]
        inps = toy.inputs(sub, jax.random.fold_in(key, i0))
        carry = jax.vmap(lambda q: F.init_carry(cfg, q, C))(jnp.asarray(pp))
        chunks = []
        for c0 in range(0, NB, cb):
            carry, o = fns["hard"][mode](P, carry, m3d.take(inps, c0, c0 + cb))
            chunks.append(o)
        outs.append({k: np.concatenate([np.asarray(o[k]) for o in chunks], 1)[:n] for k in chunks[0]})
        if f is not None:
            np.savez(str(f) + ".tmp.npz", **outs[-1])
            os.replace(str(f) + ".tmp.npz", f)
        T.check()
        T.wait_mains()
    return {k: np.concatenate([o[k] for o in outs]) for k in outs[0]}


def score_modes(fns, cfg, C, P, stats, combo, modes=("argmax",), rolldir=None, name="policy", log=print):
    """k5_train.score_modes on cfg (observers sized by cfg), plus (e), (e'), breaches of the evaluation windows' rollout."""
    import m3f_report as R
    res = {}
    yz_tr = combo.yz[combo.sets["train"]]
    for mode in modes:
        rolls = []
        for k, (sl, key, seed) in enumerate([(combo.sets["train"], 100 + k, 100) for k in range(4)] + [(combo.sets["eval"], 7, 4242)]):
            cache = None if rolldir is None else str(Path(rolldir) / f"{name}_{mode}_{k}")
            rolls.append(rollout_batched(fns, cfg, C, P, combo, sl, mode, jax.random.PRNGKey(key), seed, cache=cache))
        Oe, Oi = m3f.fresh_observers(cfg, rolls[:4], yz_tr, stats)
        res[mode] = m3e.score_rollouts(rolls[4], Oe, Oi, stats, combo, "eval")
        res[mode]["e"] = R.hf_share_rollout(rolls[4]["q"])
        res[mode]["eprime"] = R.eprime_rollout(rolls[4]["q"])
        res[mode]["breaches"] = R.breaches(rolls[4]["q"])
        s = res[mode]
        log(f"score {name} {mode}: ext a {s['ext']['a_gap_mean']:.3f} {np.round(s['ext']['a_ci'], 3).tolist()} | int a {s['int']['a_gap_mean']:.3f} | b {s['b_rms_nonroll']:.1f} | "
            f"programs {s['programs_used']} | e'1 {s['eprime']['acc_p99_mean']:.2f} e'2 {s['eprime']['fast_mean']:.4f}")
    return res


class K5P2Run(T.K5Run):
    def __init__(self, out, k5=T.K5, lam=T.LAM, lr=T.LR, round_windows=T.ROUND, log=print, windows=None, cfg=None, opts=None, w_jerk=W_JERK, w_sw=W_SWITCH, w_floor=W_FLOOR):
        self.cfg = cfg or CFG
        self.out, self.k5, self.log, self.rw = Path(out), Path(k5), log, round_windows
        self.out.mkdir(parents=True, exist_ok=True)
        self.splits = json.loads((self.k5 / "splits.json").read_text())
        self.order = T.train_order(windows if windows is not None else json.loads((self.k5 / "windows.json").read_text())["train"])
        self.R = -(-len(self.order) // self.rw)
        self.C = M.load_cb()
        calib = build_toy(self.k5, "train", T.obs_windows(self.order, round_windows))
        self.tr = m3f.Trainer(calib, self.C, self.cfg, lam, lr, self.R, 8, dopamine=True, log=log, opts=opts or OPTS, w_jerk=w_jerk, w_sw=w_sw, w_floor=w_floor)
        self.set_groups(calib)
        self.extra = {"val": [], "best": None, "bad": 0, "stopped": False}
        self._calib, self._val, self._obs = calib, None, None

    def one_round(self):
        r = self.tr.epoch
        self.set_groups(build_toy(self.k5, "train", self.order[r * self.rw:(r + 1) * self.rw]))
        self.tr.run_epoch()

    def validate(self):
        if self._val is None:
            self._val = build_toy(self.k5, "val", T.val_windows(self.k5, self.splits))
            self._obs = build_toy(self.k5, "train", T.obs_windows(self.order))
        combo = combine(self._obs, self._val)
        res = score_modes(self.tr.fns, self.cfg, self.C, self.tr.P, self.tr.stats, combo, ("argmax",), None, f"val{self.tr.epoch}", self.log)["argmax"]
        v = res["ext"]["a_gap_mean"]
        self.extra["val"].append({"round": self.tr.epoch, "ext_a": v, "int_a": res["int"]["a_gap_mean"], "b": res["b_rms_nonroll"], "spent_h": self.clock.spent / 3600})
        if self.extra["best"] is None or v > self.extra["best"]:
            self.extra["best"], self.extra["bad"] = v, 0
            with open(self.out / "best.pkl.tmp", "wb") as f:
                f.write(pickle.dumps({"P": jax.tree_util.tree_map(np.asarray, self.tr.P), "stats": self.tr.stats, "round": self.tr.epoch, "val": v, "cfg": self.cfg}))
                f.flush()
                os.fsync(f.fileno())
            os.replace(self.out / "best.pkl.tmp", self.out / "best.pkl")
        else:
            self.extra["bad"] += 1
        self.extra["stopped"] = T.should_stop([x["ext_a"] for x in self.extra["val"]])
        self.log(f"validation at round {self.tr.epoch}: ext a {v:.4f}, best {self.extra['best']:.4f}, bad {self.extra['bad']}, stop {self.extra['stopped']}, compute {self.clock.spent / 3600:.2f} h")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k5", default=str(T.K5))
    ap.add_argument("--max-rounds", type=int)
    ap.add_argument("--limit-windows", type=int, help="test only")
    ap.add_argument("--round-windows", type=int, default=T.ROUND, help="test only")
    a = ap.parse_args()
    T.install_signals()
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    T.wait_mains(log)
    w = None if a.limit_windows is None else json.loads((Path(a.k5) / "windows.json").read_text())["train"][:a.limit_windows]
    K5P2Run(a.out, a.k5, round_windows=a.round_windows, log=log, windows=w).run(a.max_rounds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
