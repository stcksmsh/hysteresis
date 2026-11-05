"""K5 trainer (work order 9, docs/BRAIN_SPEC.md 7.19 / 7.20 point 1). M3e unchanged (m3e.Trainer is driven, never edited): try 1's architecture, lambda 0.03, lr 1e-3, the 7.19 B
mechanisms, trained on REAL windows. Provisional servo model (Feetech STS3215 12 V assumed). One arm.

    k5_train.py --out DIR [--k5 /secondary/hyst-data/body/k5] [--max-rounds N]      resume-safe: DIR/ckpt.pkl is read if present

Data: the WO8 files. A window = 120 blocks (60 s) of a song's lanes `y` (8 numbers per 0.5 s block), `phi_end`, `omega`; y gets M3d's arcsinh on arousal and surprisal, then M3e's causal running
z-score (past 60 blocks = 30 s, restarted at the window start exactly as a toy episode), so the window is an M3e episode with real state (WindowToy below subclasses m3e.ToyE and only replaces
the data). One ROUND = 16 windows (8 in observer group A, 8 in B) = one M3e epoch; the 15,624 training windows of windows.json are taken once, in a fixed seeded order (SEED), 976 full rounds
and one round of 8 windows (4 + 4). The Gumbel/tau schedule: tau_r = 0.2^(r / (R - 1)) over the R = 977 rounds (M3e's per-epoch schedule stretched over the pass). Descriptor statistics and E0 come
from one calibration pass of the untrained policy on 16 seeded training windows (as M3e/M3d calibrate on training episodes).

EARLY STOPPING RULE (fixed before any run): every VAL_EVERY = 200 rounds (3,200 windows) and at the end of the pass, score the current policy on the validation windows (the 217 songs of the
72 validation artists, one window each, starting at 50 % of the song, moved back to fit) in ARGMAX mode with the WO7 observer procedure (a fresh external and internal observer trained on
4 rollouts of 16 seeded training windows, 600 steps, seed 999); the validation figure is the mean external (a) gap. best.pkl = the policy with the highest figure. Stop when two validations in
a row fail to beat the best (strictly higher). The policy that K5 scores is best.pkl. A pass that completes without stopping ends with the final validation. Held-out artists are never read here.
Checkpoint (ckpt.pkl, atomic) every CKPT_EVERY = 25 rounds (400 windows) and after every validation; the validation history and the best figure are in it.
"""
import argparse
import json
import math
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3d_jax as J
import m3e
import m3e_jax as M

K5 = Path("/secondary/hyst-data/body/k5")
SEED = 20261106
ROUND = 16
VAL_EVERY, CKPT_EVERY, PATIENCE = 200, 25, 2
LAM, LR = 0.03, 1e-3
NB = m3d.NB
N_OBS_WINDOWS = 16
EVAL_BATCH = 64


# ---------------------------------------------------------------------------------------------------------------- windows
_LANES = {}


def lanes(k5, split, sid):
    key = (str(k5), split, sid)
    if key not in _LANES:
        z = np.load(Path(k5) / "lanes" / split / f"{sid}.npz")
        _LANES[key] = (z["y"].astype(float), z["phi_end"].astype(float), z["omega"].astype(float))
    return _LANES[key]


class WindowToy(m3e.ToyE):
    """An M3e toy whose episodes are real 60 s windows. y (E, 120, 8) raw lanes (arcsinh applied here), phi, omega (E, 120)."""

    def __init__(self, y, phi, omega):
        self.n_train, self.n_tune = len(y), 0
        self.y = m3d.transform_state(y)
        self.phi, self.omega = np.asarray(phi, float), np.asarray(omega, float)
        self.yz = m3e.running_z(self.y)
        self.sets = {}


def build_toy(k5, split, wins):
    """wins [(song id, start block)] -> WindowToy."""
    ys, ps, os_ = [], [], []
    for sid, b in wins:
        y, phi, om = lanes(k5, split, sid)
        ys.append(y[b:b + NB]), ps.append(phi[b:b + NB]), os_.append(om[b:b + NB])
        assert len(ys[-1]) == NB, (sid, b, len(y))
    return WindowToy(np.stack(ys), np.stack(ps), np.stack(os_))


def combine(a, b):
    """Observer-training windows a followed by evaluation windows b -> one toy with sets train / eval."""
    t = WindowToy.__new__(WindowToy)
    t.y, t.yz = np.concatenate([a.y, b.y]), np.concatenate([a.yz, b.yz])
    t.phi, t.omega = np.concatenate([a.phi, b.phi]), np.concatenate([a.omega, b.omega])
    t.n_train, t.n_tune = len(a.y), 0
    t.sets = {"train": slice(0, len(a.y)), "eval": slice(len(a.y), len(a.y) + len(b.y))}
    return t


def mid_window(nb, frac=0.5):
    return min(int(frac * nb), nb - NB)


def val_windows(k5, splits):
    out = []
    for sid in splits["val"]["ids"]:
        nb = len(lanes(k5, "val", sid)[0])
        out.append((sid, mid_window(nb)))
    return out


def train_order(windows, seed=SEED):
    """windows.json 'train' list -> the fixed seeded order of the single pass."""
    return [tuple(windows[i]) for i in np.random.default_rng(seed).permutation(len(windows))]


def obs_windows(order, n=N_OBS_WINDOWS, seed=7):
    """n training windows from distinct songs, seeded (observer training and calibration sets)."""
    pick, seen = [], set()
    for i in np.random.default_rng(seed).permutation(len(order)):
        if order[i][0] not in seen:
            seen.add(order[i][0]), pick.append(order[i])
        if len(pick) == n:
            break
    return pick


def should_stop(vals, patience=PATIENCE):
    """vals: validation figures in order. True when the last `patience` fail to beat the best before them (strictly higher)."""
    if len(vals) <= patience:
        return False
    best = max(vals[:-patience])
    return all(v <= best for v in vals[-patience:])


# ---------------------------------------------------------------------------------------------------------------- scoring on windows (WO7 observer procedure)
def rollout_batched(fns, C, P, toy, sl, mode, key, seed, batch=None, cb=8):
    """m3e.rollout over the windows toy.sets[...] slice `sl` in batches of `batch` (the last one padded by repeating its final window, then trimmed). Same start poses for every
    window of the set (seeded by `seed`), Gumbel noise folded per batch. -> dict of arrays (E, NB, ...)."""
    batch = batch or EVAL_BATCH
    ids = np.arange(*sl.indices(len(toy.y)))
    poses = m3d.start_poses(len(ids), seed)
    outs = []
    for i0 in range(0, len(ids), batch):
        sub = ids[i0:i0 + batch]
        n = len(sub)
        sub = np.concatenate([sub, np.repeat(sub[-1:], batch - n)]) if n < batch else sub
        pp = np.concatenate([poses[i0:i0 + n], np.repeat(poses[i0 + n - 1:i0 + n], batch - n, 0)]) if n < batch else poses[i0:i0 + n]
        inps = toy.inputs(sub, jax.random.fold_in(key, i0))
        carry = jax.vmap(lambda q: M.init_carry(q, C))(jnp.asarray(pp))
        chunks = []
        for c0 in range(0, NB, cb):
            carry, o = fns["hard"][mode](P, carry, m3d.take(inps, c0, c0 + cb))
            chunks.append(o)
        outs.append({k: np.concatenate([np.asarray(o[k]) for o in chunks], 1)[:n] for k in chunks[0]})
    return {k: np.concatenate([o[k] for o in outs]) for k in outs[0]}


def score_modes(fns, C, P, stats, combo, modes=("argmax",), rolldir=None, name="policy", log=print):
    """m3e.score_policy on window toys: 4 rollouts of the observer-training windows (Gumbel keys 100..103, start seed 100), one of the evaluation windows (key 7, seed 4242), fresh
    external and internal observers, m3e.score_rollouts. Rollouts are saved before scoring and reused. -> {mode: score dict}."""
    res = {}
    yz_tr = combo.yz[combo.sets["train"]]
    for mode in modes:
        rolls = []
        for k, (sl, key, seed) in enumerate([(combo.sets["train"], 100 + k, 100) for k in range(4)] + [(combo.sets["eval"], 7, 4242)]):
            f = None if rolldir is None else Path(rolldir) / f"{name}_{mode}_{k}.npz"
            if f is not None and f.exists():
                d = np.load(f)
                rolls.append({x: d[x] for x in d.files})
                continue
            r = rollout_batched(fns, C, P, combo, sl, mode, jax.random.PRNGKey(key), seed)
            if f is not None:
                np.savez(f, **r)
            rolls.append(r)
        Oe, Oi = m3e.fresh_observers(rolls[:4], yz_tr, stats)
        res[mode] = m3e.score_rollouts(rolls[4], Oe, Oi, stats, combo, "eval")
        s = res[mode]
        log(f"score {name} {mode}: ext a {s['ext']['a_gap_mean']:.3f} {np.round(s['ext']['a_ci'], 3).tolist()} | int a {s['int']['a_gap_mean']:.3f} | b {s['b_rms_nonroll']:.1f} | programs {s['programs_used']}")
    return res


# ---------------------------------------------------------------------------------------------------------------- the run
class K5Run:
    def __init__(self, out, k5=K5, lam=LAM, lr=LR, round_windows=ROUND, log=print, windows=None):
        self.out, self.k5, self.log, self.rw = Path(out), Path(k5), log, round_windows
        self.out.mkdir(parents=True, exist_ok=True)
        self.splits = json.loads((self.k5 / "splits.json").read_text())
        self.order = train_order(windows if windows is not None else json.loads((self.k5 / "windows.json").read_text())["train"])
        self.R = math.ceil(len(self.order) / self.rw)
        self.C = M.load_cb()
        calib = build_toy(self.k5, "train", obs_windows(self.order, round_windows))
        self.tr = m3e.Trainer(calib, self.C, lam, lr, self.R, 8, dopamine=True, log=log)
        self.set_groups(calib)
        self.extra = {"val": [], "best": None, "bad": 0, "stopped": False}
        self._calib, self._val = calib, None
        self._obs = None

    def set_groups(self, toy):
        n = len(toy.y)
        self.tr.toy, self.tr.groups = toy, {"A": np.arange(0, n // 2), "B": np.arange(n // 2, n)}

    @property
    def ckpt(self):
        return self.out / "ckpt.pkl"

    def load_or_calibrate(self):
        if self.ckpt.exists():
            d = pickle.loads(self.ckpt.read_bytes())
            self.tr.load(d["trainer"])
            for st in (self.tr.st, self.tr.vst):                       # Trainer.load turns the Adam step count into a JAX array; as a Python int (what a fresh run has) b1 ** t rounds identically
                st["t"] = int(st["t"])
            self.extra = d["extra"]
            self.log(f"resumed at round {self.tr.epoch} of {self.R}")
        else:
            self.set_groups(self._calib)
            self.tr.calibrate()

    def save(self):
        tmp = self.out / "ckpt.pkl.tmp"
        tmp.write_bytes(pickle.dumps({"trainer": self.tr.state(), "extra": self.extra}))
        tmp.replace(self.ckpt)
        (self.out / "progress.json").write_text(json.dumps({"round": self.tr.epoch, "of": self.R, "windows_done": min(self.tr.epoch * self.rw, len(self.order)), "val": self.extra["val"],
                                                          "hist": self.tr.hist[-1] if self.tr.hist else None}))

    def one_round(self):
        r = self.tr.epoch
        wins = self.order[r * self.rw:(r + 1) * self.rw]
        self.set_groups(build_toy(self.k5, "train", wins))
        self.tr.run_epoch()

    def validate(self):
        if self._val is None:
            self._val = build_toy(self.k5, "val", val_windows(self.k5, self.splits))
            self._obs = build_toy(self.k5, "train", obs_windows(self.order))
        combo = combine(self._obs, self._val)
        res = score_modes(self.tr.fns, self.C, self.tr.P, self.tr.stats, combo, ("argmax",), None, f"val{self.tr.epoch}", self.log)["argmax"]
        v = res["ext"]["a_gap_mean"]
        self.extra["val"].append({"round": self.tr.epoch, "ext_a": v, "int_a": res["int"]["a_gap_mean"], "b": res["b_rms_nonroll"]})
        if self.extra["best"] is None or v > self.extra["best"]:
            self.extra["best"], self.extra["bad"] = v, 0
            (self.out / "best.pkl.tmp").write_bytes(pickle.dumps({"P": jax.tree_util.tree_map(np.asarray, self.tr.P), "stats": self.tr.stats, "round": self.tr.epoch, "val": v}))
            (self.out / "best.pkl.tmp").replace(self.out / "best.pkl")
        else:
            self.extra["bad"] += 1
        self.extra["stopped"] = should_stop([x["ext_a"] for x in self.extra["val"]])
        self.log(f"validation at round {self.tr.epoch}: ext a {v:.4f}, best {self.extra['best']:.4f}, bad {self.extra['bad']}, stop {self.extra['stopped']}")

    def run(self, max_rounds=None):
        self.load_or_calibrate()
        t0 = time.time()
        while self.tr.epoch < self.R and not self.extra["stopped"] and (max_rounds is None or self.tr.epoch < max_rounds):
            self.one_round()
            r = self.tr.epoch
            if r % VAL_EVERY == 0 or r == self.R:
                self.validate()
            if r % CKPT_EVERY == 0 or r == self.R or self.extra["stopped"]:
                self.save()
        self.save()
        self.log(f"stopped at round {self.tr.epoch} of {self.R} ({'early stop' if self.extra['stopped'] else 'pass complete' if self.tr.epoch >= self.R else 'max rounds'}), {time.time() - t0:.0f} s this run")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k5", default=str(K5))
    ap.add_argument("--max-rounds", type=int)
    a = ap.parse_args()
    t0 = time.time()
    K5Run(a.out, a.k5, log=lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)).run(a.max_rounds)


if __name__ == "__main__":
    sys.exit(main())
