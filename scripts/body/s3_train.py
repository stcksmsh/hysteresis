"""Stage 3 trainer (work order 26B, docs/STAGE3_RULES_TRAIN.md, BRAIN_SPEC 7.39.4 + 7.40). The pass2 body and K5 machinery (k5p2_train.K5P2Run: windows, order, validation, best.pkl, checkpoint, pause/stop/mains,
compute box) driven by a new trainer: two-stream Lipschitz decoding with a D hinge per stream, InfoNCE on tempo/RMS-matched batches, seven limit hinges with dual multipliers. One arm.

    s3_train.py --out DIR [--k5 /secondary/hyst-data/body/k5] [--s3 /secondary/hyst-data/body/s3] [--max-rounds N] [--timed]      resume-safe
    --timed: the overseer's timed round only (2 rounds + 1 validation + the D estimate, then the projection); never the run.
"""
import argparse
import json
import math
import os
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import k5p2_train as P2
import m3d
import m3d_jax as J
import m3e
import m3e_jax as M
import m3f
import m3f_jax as F

import s3_data as D
import s3_loss as L
import s3_obs as O

VALID_FROM = m3e.VALID_FROM
NB = m3d.NB
N_SLOW_IN = D.N_SLOW
ETA_D, D_TARGET, N_D_WINDOWS = 0.16, 0.7, 16
MU_STEP = 0.02


def init_policy3(key, cfg):
    """The pass2 policy with N_SLOW_IN zero rows inserted into the cortex's first weights after the 16 state rows (so it equals the pass2 initial policy at the start)."""
    P = F.init_policy(key, cfg)
    w1 = P["w1"]
    return {**P, "w1": jnp.concatenate([w1[:16], jnp.zeros((N_SLOW_IN, w1.shape[1])), w1[16:]])}


def init_critic3(key, d_in, hidden=32):
    k1, k2 = jax.random.split(key)
    return {"w1": jax.random.normal(k1, (d_in, hidden)) / math.sqrt(d_in), "b1": jnp.zeros(hidden), "w2": 0.1 * jax.random.normal(k2, (hidden, 1)) / math.sqrt(hidden), "b2": jnp.zeros(1)}


def d_update(mu, d):
    """Rules section 2 point 3: mu <- max(0, mu + 0.16 max(0, 0.7 - D)). Rising only."""
    return max(0.0, mu + ETA_D * max(0.0, D_TARGET - d))


class Trainer3(m3e.Trainer):
    def __init__(self, toy, C, cfg, thr, lr, epochs, chunk_blocks=8, seed=0, log=print):
        self.cfg, self.thr = cfg, {k: float(thr[k]) for k in ("energy", "jerk")}
        self.toy, self.C, self.lam, self.lr, self.epochs, self.cb, self.log, self.dopamine, self.gate = toy, C, None, lr, epochs, chunk_blocks, log, True, True
        self.fns = L.make_fns(C, cfg)
        self.key, k1, k2, k3, k4, k5, k6, k7 = jax.random.split(jax.random.PRNGKey(seed), 8)
        self.P = init_policy3(k1, cfg)
        self.enc = L.init_enc(k7)
        self.obs = {"A": (O.init_obs(k2, O.N_EXT), O.init_obs(k4, F.n_idesc(cfg))), "B": (O.init_obs(k3, O.N_EXT), O.init_obs(k5, F.n_idesc(cfg)))}
        self.st = J.adam_init({"P": self.P, "enc": self.enc})
        self.V = init_critic3(k6, 16 + N_SLOW_IN + M.N_CB)
        self.vst = J.adam_init(self.V)
        self.sd = m3e.RunningSD()
        n = toy.n_train
        self.groups = {"A": np.arange(0, n // 2), "B": np.arange(n // 2, n)}
        self.data = {"A": [], "B": []}
        self.stats, self.e0, self.epoch, self.hist = None, None, 0, []
        self.mu = np.ones(L.N_G)                 # limit-hinge multipliers
        self.muD = np.zeros(2)                   # D multipliers: fast, slow
        self.Dest = [None, None]
        self.dtoy = None                         # the fixed validation windows of the D estimate (set by the run)

    # ------------------------------------------------------------------------------------------------ rollouts and observers
    def _roll(self, idx, key, mode="argmax", seed=100):
        return m3f.rollout(self.fns, self.cfg, self.C, self.P, self.toy, idx, mode, key, self.cb, seed)

    def _collect(self, g, r):
        S = self.stats
        xe = O.ext_features(r["q"])[:, VALID_FROM:].reshape(-1, O.N_EXT)
        xi = m3d.std_desc(r["idesc"], S["imu"], S["isd"])[:, VALID_FROM:].reshape(-1, F.n_idesc(self.cfg))
        y = self.toy.tgt[self.groups[g]][:, VALID_FROM:].reshape(-1, D.N_TGT)
        return xe, xi, y

    def _refresh(self, steps):
        for scored, source in (("A", "B"), ("B", "A")):
            xe, xi, y = (np.concatenate([d[i] for d in self.data[source]]) for i in range(3))
            oe, le = O.train_obs(self.obs[scored][0], xe, y, steps, seed=self.epoch)
            oi, li = O.train_obs(self.obs[scored][1], xi, y, steps, seed=self.epoch + 1000)
            self.obs[scored] = (oe, oi)
            self.log(f"  observers for group {scored} (trained on {source}, {len(xe)} blocks): ext {le:.3f} int {li:.3f}")

    def calibrate(self):
        rs = {g: self._roll(idx, jax.random.PRNGKey(11)) for g, idx in self.groups.items()}
        cat = lambda k, n: np.concatenate([rs[g][k][:, VALID_FROM:].reshape(-1, n) for g in rs])
        d, i = cat("desc", F.n_desc(self.cfg)), cat("idesc", F.n_idesc(self.cfg))
        self.stats = {"dmu": d.mean(0), "dsd": d.std(0) + 1e-9, "imu": i.mean(0), "isd": i.std(0) + 1e-9}      # dmu/dsd: pass2's descriptors, used by the K5 validation observers
        self.e0 = float(np.mean([rs[g]["energy"][:, VALID_FROM:].mean() for g in rs]))
        for g in "AB":
            self.data[g].append(self._collect(g, rs[g]))
        self._refresh(400)
        self.log(f"calibration: E0 {self.e0:.5f} J/block, untrained RMS speed {np.sqrt(np.concatenate([rs[g]['ms'] for g in rs]).mean()):.1f}; thresholds {self.thr}")

    def update_D(self):
        """Rules section 2 point 3: D per stream on the fixed validation windows (argmax rollout, group-A and group-B external observers), then the rising multipliers."""
        n = len(self.dtoy.y)
        r = m3f.rollout(self.fns, self.cfg, self.C, self.P, self.dtoy, np.arange(n), "argmax", jax.random.PRNGKey(4242), self.cb, 4242)
        xe = jnp.asarray(O.ext_features(r["q"]))
        ds = []
        for g in "AB":
            pred = np.asarray(O.lip_apply(self.obs[g][0], xe))
            ds.append([O.shifted_D(pred, self.dtoy.tgt, np.arange(D.N_FAST)), O.shifted_D(pred, self.dtoy.tgt, np.arange(D.N_FAST, D.N_TGT))])
        self.Dest = np.mean(ds, 0).tolist()
        self.muD = np.array([d_update(m, d) for m, d in zip(self.muD, self.Dest)])

    # ------------------------------------------------------------------------------------------------ a round
    def run_epoch(self):
        t0 = time.time()
        tau = self.tau()
        S = self.stats
        thr = {k: jnp.asarray(v) for k, v in self.thr.items()}
        acc = {k: [] for k in ("dec_e", "dec_i", "nce", "fast", "slow", "rms", "mult", "absd", "clip", "kap", "vloss", "tv")}
        gs = []
        for g in "AB":
            idx = self.groups[g]
            E = len(idx)
            self.key, kk = jax.random.split(self.key)
            inps = self.toy.inputs(idx, kk)
            tgt = jnp.asarray(self.toy.tgt[idx])
            carry = jax.vmap(lambda q: F.init_carry(self.cfg, q, self.C))(jnp.asarray(m3d.start_poses(E, 100)))
            qs, ids = [], []
            for c0 in range(0, NB, self.cb):
                Q = {"P": self.P, "enc": self.enc}
                (l, (carry, aux)), grad = self.fns["loss"](Q, self.obs[g][0], self.obs[g][1], carry, m3d.take(inps, c0, c0 + self.cb), tgt[:, c0:c0 + self.cb], m3e.valid_mask(c0, self.cb, E), tau,
                                                           jnp.asarray(self.mu), jnp.asarray(self.muD), S["dmu"], S["dsd"], S["imu"], S["isd"], thr, float(c0), float(c0 >= VALID_FROM))
                mult = 1.0
                if self.dopamine:
                    Rr, mask = m3e.realised_legibility(np.asarray(aux["de"]), c0)
                    if mask.any():
                        x = aux["xin"][:, :Rr.shape[1]]
                        delta = (Rr - np.asarray(m3e.critic_apply(self.V, x)))[:, mask]
                        sigma = self.sd.update(float((delta ** 2).mean()))
                        mult = m3e.rate_multiplier(delta, sigma)
                        acc["absd"].append(float(np.abs(delta).mean()))
                        acc["clip"].append(float((np.abs(delta) / sigma >= 2.0).mean()))
                        wt = jnp.asarray(np.broadcast_to(mask, Rr.shape).astype(float))
                        self.V, self.vst, vl = m3e._critic_step(self.V, self.vst, x, jnp.asarray(Rr), wt)
                        acc["vloss"].append(float(vl))
                acc["mult"].append(mult)
                mt = {"P": m3e.logit_mult(self.P, mult), "enc": jax.tree_util.tree_map(jnp.ones_like, self.enc)}
                Q, self.st, gn = m3e.adam_step_mult(Q, grad, self.st, self.lr, mt)
                self.P, self.enc = Q["P"], Q["enc"]
                gv = np.asarray(aux["g"])
                self.mu = np.maximum(0.0, self.mu + MU_STEP * gv)
                qs.append(np.asarray(aux["q"]))
                ids.append(np.asarray(aux["idesc"]))
                if c0 >= VALID_FROM:
                    gs.append(gv)
                    for k, v in (("dec_e", aux["dec_e"]), ("dec_i", aux["dec_i"]), ("nce", aux["nce"]), ("fast", aux["fast_e"]), ("slow", aux["slow_e"]), ("tv", aux["tv"])):
                        acc[k].append(float(v))
                acc["rms"].append(float(np.sqrt(np.asarray(aux["ms"])[..., m3d.NON_ROLL].mean())))
                acc["kap"].append(np.asarray(aux["kappa"]).mean())
            self.data[g] = (self.data[g] + [self._collect(g, {"q": np.concatenate(qs, 1), "idesc": np.concatenate(ids, 1)})])[-4:]
        self._refresh(200)
        self.update_D()
        mean = lambda k: float(np.mean(acc[k])) if acc[k] else None
        rec = {"epoch": self.epoch, "tau": tau, "dec_e": mean("dec_e"), "dec_i": mean("dec_i"), "fast_mse": mean("fast"), "slow_mse": mean("slow"), "nce": mean("nce"), "tv": mean("tv"),
               "g": dict(zip(L.G_NAMES, np.mean(gs, 0).tolist())) if gs else None, "mu": dict(zip(L.G_NAMES, self.mu.tolist())), "muD": {"fast": float(self.muD[0]), "slow": float(self.muD[1])},
               "D_fast": self.Dest[0], "D_slow": self.Dest[1], "rms_speed": mean("rms"), "kappa_mean": mean("kap"), "rate_mult": mean("mult"), "abs_delta": mean("absd"),
               "critic_loss": mean("vloss"), "secs": time.time() - t0}
        self.hist.append(rec)
        self.log("epoch " + json.dumps({k: (round(v, 4) if isinstance(v, float) else (({a: round(b, 4) for a, b in v.items()}) if isinstance(v, dict) else v)) for k, v in rec.items()}))
        self.epoch += 1
        return rec

    def state(self):
        s = m3e.Trainer.state(self)
        s["enc"], s["mu"], s["muD"], s["Dest"] = jax.tree_util.tree_map(np.asarray, self.enc), self.mu, self.muD, self.Dest
        return s

    def load(self, s):
        m3e.Trainer.load(self, s)
        self.enc = jax.tree_util.tree_map(jnp.asarray, s["enc"])
        self.mu, self.muD, self.Dest = s["mu"], s["muD"], s["Dest"]


class Stage3Run(P2.K5P2Run):
    def __init__(self, out, k5=T.K5, s3=D.S3, lr=T.LR, batch=8, log=print, windows=None, cfg=None, tempo=None, thr=None):
        self.cfg = cfg or P2.CFG
        self.out, self.k5, self.s3, self.log, self.rw, self.batch = Path(out), Path(k5), Path(s3), log, 2 * batch, batch
        self.out.mkdir(parents=True, exist_ok=True)
        self.splits = json.loads((self.k5 / "splits.json").read_text())
        wl = [tuple(w) for w in (windows if windows is not None else json.loads((self.k5 / "windows.json").read_text())["train"])]
        self.order = T.train_order(wl)
        self.R = -(-len(self.order) // self.rw)
        self.C = M.load_cb()
        tempo, thr = (tempo, thr) if tempo is not None else D.load_inputs(self.s3)
        self.matched = D.Matched(tempo, wl, batch)
        f = self.out / "corpus_sd.json"
        if f.exists():
            self.floor_sd = np.array(json.loads(f.read_text()))
        else:
            self.floor_sd = 0.1 * D.corpus_sd(self.k5, wl)
            f.write_text(json.dumps(self.floor_sd.tolist()))
        calib = D.build_toy3(self.k5, self.s3, "train", T.obs_windows(self.order, self.rw), self.floor_sd)
        self.tr = Trainer3(calib, self.C, self.cfg, thr, lr, self.R, 8, log=log)
        self.tr.dtoy = D.build_toy3(self.k5, self.s3, "val", T.val_windows(self.k5, self.splits)[:N_D_WINDOWS], self.floor_sd)
        self.set_groups(calib)
        self.extra = {"val": [], "best": None, "bad": 0, "stopped": False}
        self._calib, self._val, self._obs = calib, None, None

    def one_round(self):
        r = self.tr.epoch
        self.set_groups(D.build_toy3(self.k5, self.s3, "train", self.matched.round_windows(self.order, r), self.floor_sd))
        self.tr.run_epoch()

    def validate(self):
        if self._val is None:
            self._val = D.build_toy3(self.k5, self.s3, "val", T.val_windows(self.k5, self.splits), self.floor_sd)
            self._obs = D.build_toy3(self.k5, self.s3, "train", T.obs_windows(self.order), self.floor_sd)
        combo = D.combine3(self._obs, self._val)
        res = P2.score_modes(self.tr.fns, self.cfg, self.C, self.tr.P, self.tr.stats, combo, ("argmax",), None, f"val{self.tr.epoch}", self.log)["argmax"]
        v = res["ext"]["a_gap_mean"]
        self.extra["val"].append({"round": self.tr.epoch, "ext_a": v, "int_a": res["int"]["a_gap_mean"], "b": res["b_rms_nonroll"], "spent_h": self.clock.spent / 3600})
        if self.extra["best"] is None or v > self.extra["best"]:
            self.extra["best"], self.extra["bad"] = v, 0
            with open(self.out / "best.pkl.tmp", "wb") as f:
                f.write(pickle.dumps({"P": jax.tree_util.tree_map(np.asarray, self.tr.P), "stats": self.tr.stats, "round": self.tr.epoch, "val": v, "cfg": self.cfg,
                                      "s3": {"enc": jax.tree_util.tree_map(np.asarray, self.tr.enc), "slow_inputs": True, "floor_sd": self.floor_sd.tolist()}}))
                f.flush()
                os.fsync(f.fileno())
            os.replace(self.out / "best.pkl.tmp", self.out / "best.pkl")
        else:
            self.extra["bad"] += 1
        self.extra["stopped"] = T.should_stop([x["ext_a"] for x in self.extra["val"]])
        self.log(f"validation at round {self.tr.epoch}: ext a {v:.4f}, best {self.extra['best']:.4f}, bad {self.extra['bad']}, stop {self.extra['stopped']}, compute {self.clock.spent / 3600:.2f} h")


def timed(run, rounds=2):
    """The timed round (overseer's word only): `rounds` real rounds, then one validation; projection against the 30 h box."""
    run.load_or_calibrate()
    run.clock = T.Clock(run.extra.get("spent_s", 0.0))
    secs = []
    for _ in range(rounds):
        t0 = time.time()
        run.one_round()
        secs.append(time.time() - t0)
        run.save()
    t0 = time.time()
    run.validate()
    val_s = time.time() - t0
    round_s = float(np.mean(secs[1:] or secs))
    n_val = run.R // T.VAL_EVERY + 1
    hours = (run.R * round_s + n_val * val_s) / 3600
    out = {"round_secs": secs, "round_s_used": round_s, "validation_s": val_s, "R": run.R, "validations": n_val, "projected_h": hours, "box_h": T.BOX_H, "within_box": hours <= T.BOX_H,
           "threads": os.environ.get("OMP_NUM_THREADS"), "note": "round 0 includes JIT compile; round_s_used is the mean of the later rounds"}
    (run.out / "timed_round.json").write_text(json.dumps(out, indent=1))
    run.log("timed round: " + json.dumps(out))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--k5", default=str(T.K5))
    ap.add_argument("--s3", default=str(D.S3))
    ap.add_argument("--max-rounds", type=int)
    ap.add_argument("--timed", action="store_true", help="the timed round only")
    ap.add_argument("--limit-windows", type=int, help="test only")
    ap.add_argument("--batch", type=int, default=8, help="test only: windows per group")
    a = ap.parse_args()
    for f in ("tempo_rms.json", "thresholds.json", "slow/norm.json"):
        if not (Path(a.s3) / f).exists():
            raise SystemExit(f"missing {Path(a.s3) / f}: work order 26A's deliverables are not there yet (rules section 4)")
    T.install_signals()
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    T.wait_mains(log)
    w = None if a.limit_windows is None else json.loads((Path(a.k5) / "windows.json").read_text())["train"][:a.limit_windows]
    run = Stage3Run(a.out, a.k5, a.s3, batch=a.batch, log=log, windows=w)
    if a.timed:
        timed(run)
        return 0
    run.run(a.max_rounds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
