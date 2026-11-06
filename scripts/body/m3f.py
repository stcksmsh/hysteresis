"""M3f (docs/BRAIN_SPEC.md 7.24): the M3e toy recipe on the new body with the four movement changes (m3f_jax.py), Trainer/scoring copied from m3e.py with these differences only:
  * block function, carry and observers' input sizes come from `cfg` (m3f_jax.py);
  * loss = dec_ext + dec_int + LAMBDA x (energy + hand-speed hinge + hand-jolt hinge + limit-proximity cost) + W_JERK x jerk + W_SWITCH x switch,
    energy/E0 as before; hinge, limit and jerk each divided by their value for the UNTRAINED policy on the calibration episodes (floored, see FLOORS); the switch cost is the mean program
    total variation per scored block (already in the energy term's units: 1 = every block fully switches). The three body penalties are on only for body "v2".
  * the toy gives the L3 order parameter R (|mean cos, mean sin| of the previous block) as an input, used by movement 3 only;
  * rollouts keep the 100 Hz joint trajectory q so (e) and the check-csv-style breaches can be computed.
Everything else (toy, bar (a)-(c), statistics, tau schedule, dopamine, observers' optimiser, WO7 observer procedure, argmax pass/fail) is m3e's, imported unchanged.
Provisional servo model (Feetech STS3215 12 V assumed).
"""
import math
import os
import time

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3d_jax as J
import m3e
import m3e_jax as M
import m3f_jax as F

FLOORS = {"hand_v": 0.02, "jolt": 0.2, "lim": 0.005, "jerk": 1.0}       # the untrained values are floored at these before dividing (a zero denominator explodes)
NB = m3d.NB
VALID_FROM = m3e.VALID_FROM
NON_ROLL = m3d.NON_ROLL


class ToyF(m3e.ToyE):
    """ToyE plus the L3 order parameter input R (previous block, like phi0)."""

    def __init__(self, path):
        super().__init__(path)
        self.R = np.clip(np.hypot(self.y[..., 2], self.y[..., 3]), 0.0, 1.0)

    def inputs(self, idx, key):
        d = super().inputs(idx, key)
        r = self.R[idx]
        d["R"] = jnp.asarray(np.concatenate([np.zeros_like(r[:, :1]), r[:, :-1]], 1))
        return d


# ---------------------------------------------------------------------------------------------------------------- jitted pieces
def make_fns(C, cfg, opts):
    """opts: internal (bool), pen (bool: hand-speed, jolt, limit terms), jerk (bool), sw (bool)."""
    chunk = F.make_chunk(cfg)

    def loss_fn(P, Oe, Oi, carry, inps, yz, valid, tau, lam, e0, dmu, dsd, imu, isd, nrm, w):
        Oe, Oi = jax.lax.stop_gradient(Oe), jax.lax.stop_gradient(Oi)
        carry, o = chunk(C, P, "train", tau, carry, inps)
        dec = lambda O, d, mu, sd: ((jax.vmap(jax.vmap(lambda x: J.observer_apply(O, x)))(jnp.clip((d - mu) / sd, -8, 8)) - yz) ** 2).mean(-1)
        de, di = dec(Oe, o["desc"], dmu, dsd), dec(Oi, o["idesc"], imu, isd)
        n = jnp.maximum(valid.sum(), 1.0)
        mean = lambda x: (x * valid).sum() / n
        Le, Li = mean(de), mean(di)
        en = mean(o["energy"]) / e0
        terms = {"hand_v": mean(o["hand_v"]) / nrm["hand_v"], "jolt": mean(o["jolt"]) / nrm["jolt"], "lim": mean(o["lim"]) / nrm["lim"], "jerk": mean(o["jerk"]) / nrm["jerk"], "sw": mean(o["tv"])}
        pen = (terms["hand_v"] + terms["jolt"] + terms["lim"]) if opts["pen"] else 0.0
        loss = Le + (Li if opts["internal"] else 0.0) + lam * (en + pen) + (w["jerk"] * terms["jerk"] if opts["jerk"] else 0.0) + (w["sw"] * terms["sw"] if opts["sw"] else 0.0)
        return loss, (carry, {"dec_e": Le, "dec_i": Li, "en": en, "de": de, "xin": o["xin"], "desc": o["desc"], "idesc": o["idesc"], "ms": o["ms"], "pi": o["pi"], "kappa": o["kappa"],
                              "terms": terms, "raw": {k: mean(o[k]) for k in ("jerk", "hand_v", "jolt", "lim", "tv")}})

    hard = {m: jax.jit(lambda P, carry, inps, m=m: chunk(C, P, m, 0.0, carry, inps)) for m in ("argmax", "sample")}
    return {"loss": jax.jit(jax.value_and_grad(loss_fn, has_aux=True)), "hard": hard}


def rollout(fns, cfg, C, P, toy, idx, mode, key, chunk_blocks, seed_start):
    n = len(range(*idx.indices(len(toy.y)))) if isinstance(idx, slice) else len(idx)
    inps = toy.inputs(idx, key)
    carry = jax.vmap(lambda q: F.init_carry(cfg, q, C))(jnp.asarray(m3d.start_poses(n, seed_start)))
    outs = []
    for c0 in range(0, NB, chunk_blocks):
        carry, o = fns["hard"][mode](P, carry, m3d.take(inps, c0, c0 + chunk_blocks))
        outs.append(o)
    return {k: np.concatenate([np.asarray(o[k]) for o in outs], 1) for k in outs[0]}


def fresh_observers(cfg, rolls, yz, stats):
    """m3e.fresh_observers with the input sizes of cfg."""
    xe = np.concatenate([m3d.std_desc(r["desc"], stats["dmu"], stats["dsd"])[:, VALID_FROM:].reshape(-1, F.n_desc(cfg)) for r in rolls])
    xi = np.concatenate([m3d.std_desc(r["idesc"], stats["imu"], stats["isd"])[:, VALID_FROM:].reshape(-1, F.n_idesc(cfg)) for r in rolls])
    y = np.concatenate([yz[:, VALID_FROM:].reshape(-1, 8) for _ in rolls])
    Oe, _ = m3d.train_observer(m3e.init_observer(jax.random.PRNGKey(0), F.n_desc(cfg)), xe, y, 600, seed=999)
    Oi, _ = m3d.train_observer(m3e.init_observer(jax.random.PRNGKey(0), F.n_idesc(cfg)), xi, y, 600, seed=999)
    return Oe, Oi


def score_policy(fns, cfg, C, P, toy, stats, which, chunk_blocks, rolldir=None, name="policy", log=print):
    """m3e.score_policy for cfg, plus (e) and breaches per mode. Rollouts are saved before scoring and reused if present."""
    import m3f_report as R
    res, keep = {}, {}
    yz_tr = toy.yz[toy.sets["train"]]
    for mode in ("argmax", "sample"):
        rolls = []
        for k, (idx, key, seed) in enumerate([(toy.sets["train"], 100 + k, 100) for k in range(4)] + [(toy.sets[which], 7, 4242)]):
            f = None if rolldir is None else f"{rolldir}/{name}_{mode}_{k}.npz"
            if f and os.path.exists(f):
                d = np.load(f)
                rolls.append({x: d[x] for x in d.files})
                continue
            r = rollout(fns, cfg, C, P, toy, idx, mode, jax.random.PRNGKey(key), chunk_blocks, seed)
            if f:
                np.savez(f, **r)
            rolls.append(r)
        Oe, Oi = fresh_observers(cfg, rolls[:4], yz_tr, stats)
        res[mode] = m3e.score_rollouts(rolls[4], Oe, Oi, stats, toy, which)
        res[mode]["e"] = R.hf_share_rollout(rolls[4]["q"])
        res[mode]["eprime"] = R.eprime_rollout(rolls[4]["q"])
        res[mode]["breaches"] = R.breaches(rolls[4]["q"])
        keep[mode] = (Oe, Oi, rolls[4])
        s = res[mode]
        log(f"score {name} {which} {mode}: ext a {s['ext']['a_gap_mean']:.3f} {np.round(s['ext']['a_ci'], 3).tolist()} | int a {s['int']['a_gap_mean']:.3f} {np.round(s['int']['a_ci'], 3).tolist()} | "
            f"b {s['b_rms_nonroll']:.1f} | c MI {s['c_mi']:.4f} p {s['c_p']:.4f} | programs {s['programs_used']} | e {s['e']['mean']:.4f} | e'1 {s['eprime']['acc_p99_mean']:.2f} e'2 {s['eprime']['fast_mean']:.4f} contact {s['eprime']['contact_mean']:.4f}")
    return res, keep


# ---------------------------------------------------------------------------------------------------------------- training
class Trainer(m3e.Trainer):
    """m3e.Trainer on cfg. opts: internal, pen, jerk, sw (loss terms), w_jerk, w_sw."""

    def __init__(self, toy, C, cfg, lam, lr, epochs, chunk_blocks=8, seed=0, dopamine=True, log=print, opts=None, w_jerk=0.0, w_sw=0.0):
        opts = {"internal": True, "pen": cfg["body"] != "v1", "jerk": False, "sw": False, **(opts or {})}
        self.cfg, self.opts, self.w = cfg, opts, {"jerk": w_jerk, "sw": w_sw}
        self.toy, self.C, self.lam, self.lr, self.epochs, self.cb, self.log, self.dopamine, self.gate = toy, C, lam, lr, epochs, chunk_blocks, log, dopamine, True
        self.fns = make_fns(C, cfg, opts)
        key = jax.random.PRNGKey(seed)
        self.key, k1, k2, k3, k4, k5, k6 = jax.random.split(key, 7)
        self.P = F.init_policy(k1, cfg)
        io = m3e.init_observer
        self.obs = {"A": (io(k2, F.n_desc(cfg)), io(k4, F.n_idesc(cfg))), "B": (io(k3, F.n_desc(cfg)), io(k5, F.n_idesc(cfg)))}
        self.st = J.adam_init(self.P)
        self.V = m3e.init_critic(k6)
        self.vst = J.adam_init(self.V)
        self.sd = m3e.RunningSD()
        n = toy.n_train
        self.groups = {"A": np.arange(0, n // 2), "B": np.arange(n // 2, n)}
        self.data = {"A": [], "B": []}
        self.stats, self.e0, self.epoch, self.hist = None, None, 0, []
        self.nrm = None

    def _collect(self, g, desc, idesc):
        yz = self.toy.yz[self.groups[g]][:, VALID_FROM:].reshape(-1, 8)
        xe = m3d.std_desc(desc, self.stats["dmu"], self.stats["dsd"])[:, VALID_FROM:].reshape(-1, F.n_desc(self.cfg))
        xi = m3d.std_desc(idesc, self.stats["imu"], self.stats["isd"])[:, VALID_FROM:].reshape(-1, F.n_idesc(self.cfg))
        return xe, xi, yz

    def _roll(self, idx, key, mode="argmax", seed=100):
        return rollout(self.fns, self.cfg, self.C, self.P, self.toy, idx, mode, key, self.cb, seed)

    def calibrate(self):
        rs = {g: self._roll(idx, jax.random.PRNGKey(11)) for g, idx in self.groups.items()}
        cat = lambda k, n: np.concatenate([rs[g][k][:, VALID_FROM:].reshape(-1, n) for g in rs])
        d, i = cat("desc", F.n_desc(self.cfg)), cat("idesc", F.n_idesc(self.cfg))
        self.stats = {"dmu": d.mean(0), "dsd": d.std(0) + 1e-9, "imu": i.mean(0), "isd": i.std(0) + 1e-9}
        self.e0 = float(np.mean([rs[g]["energy"][:, VALID_FROM:].mean() for g in rs]))
        mean_raw = lambda r: {k: float(np.mean([r[g][k][:, VALID_FROM:].mean() for g in r])) for k in ("hand_v", "jolt", "lim", "jerk")}
        raw_new = mean_raw(rs)
        if self.cfg["body"] == "v1":
            raw = raw_new
        else:                                         # overseer ruling: divide by the untrained policy's value on the OLD body (same episodes, same switches), not on the contact body
            cfg1 = {**self.cfg, "body": "v1"}
            fns1 = make_fns(self.C, cfg1, self.opts)
            raw = mean_raw({g: rollout(fns1, cfg1, self.C, self.P, self.toy, idx, "argmax", jax.random.PRNGKey(11), self.cb, 100) for g, idx in self.groups.items()})
        self.nrm = {k: max(v, FLOORS[k]) for k, v in raw.items()}
        self.raw0, self.raw_new = raw, raw_new
        for g in "AB":
            self.data[g].append(self._collect(g, rs[g]["desc"], rs[g]["idesc"]))
        self._refresh(400)
        self.log(f"calibration: E0 {self.e0:.5f} J/block, untrained RMS speed {np.sqrt(np.concatenate([rs[g]['ms'] for g in rs]).mean()):.1f}; untrained penalty values old body {raw}, this body {raw_new}, divisors (old body, floored) {self.nrm}")

    def run_epoch(self):
        t0 = time.time()
        tau = self.tau()
        S = self.stats
        acc = {k: [] for k in ("dec_e", "dec_i", "en", "rms", "mult", "absd", "clip", "kap", "vloss", "hand_v", "jolt", "lim", "jerk", "tv")}
        nrm = {k: jnp.asarray(v) for k, v in self.nrm.items()}
        w = {k: jnp.asarray(v) for k, v in self.w.items()}
        for g in "AB":
            idx = self.groups[g]
            E = len(idx)
            self.key, kk = jax.random.split(self.key)
            inps = self.toy.inputs(idx, kk)
            yz = jnp.asarray(self.toy.yz[idx])
            carry = jax.vmap(lambda q: F.init_carry(self.cfg, q, self.C))(jnp.asarray(m3d.start_poses(E, 100)))
            ds, ids = [], []
            for c0 in range(0, NB, self.cb):
                (l, (carry, aux)), grad = self.fns["loss"](self.P, self.obs[g][0], self.obs[g][1], carry, m3d.take(inps, c0, c0 + self.cb), yz[:, c0:c0 + self.cb], m3e.valid_mask(c0, self.cb, E), tau,
                                                           self.lam, self.e0, S["dmu"], S["dsd"], S["imu"], S["isd"], nrm, w)
                mult = 1.0
                if self.dopamine:
                    Rr, mask = m3e.realised_legibility(np.asarray(aux["de"]), c0)
                    if mask.any():
                        x = aux["xin"][:, :Rr.shape[1]]
                        Vp = np.asarray(m3e.critic_apply(self.V, x))
                        delta = (Rr - Vp)[:, mask]
                        sigma = self.sd.update(float((delta ** 2).mean()))
                        mult = m3e.rate_multiplier(delta, sigma)
                        acc["absd"].append(float(np.abs(delta).mean()))
                        acc["clip"].append(float((np.abs(delta) / sigma >= 2.0).mean()))
                        wt = jnp.asarray(np.broadcast_to(mask, Rr.shape).astype(float))
                        self.V, self.vst, vl = m3e._critic_step(self.V, self.vst, x, jnp.asarray(Rr), wt)
                        acc["vloss"].append(float(vl))
                acc["mult"].append(mult)
                self.P, self.st, gn = m3e.adam_step_mult(self.P, grad, self.st, self.lr, m3e.logit_mult(self.P, mult))
                ds.append(np.asarray(aux["desc"]))
                ids.append(np.asarray(aux["idesc"]))
                if c0 >= VALID_FROM:
                    for k in ("dec_e", "dec_i", "en"):
                        acc[k].append(float(aux[k]))
                    for k in ("hand_v", "jolt", "lim", "jerk", "tv"):
                        acc[k].append(float(aux["raw"][k]))
                acc["rms"].append(float(np.sqrt(np.asarray(aux["ms"])[..., NON_ROLL].mean())))
                acc["kap"].append(np.asarray(aux["kappa"]).mean())
            self.data[g] = (self.data[g] + [self._collect(g, np.concatenate(ds, 1), np.concatenate(ids, 1))])[-4:]
        self._refresh(200)
        mean = lambda k: float(np.mean(acc[k])) if acc[k] else None
        rec = {"epoch": self.epoch, "tau": tau, "dec_e": mean("dec_e"), "dec_i": mean("dec_i"), "energy_rel": mean("en"), "rms_speed": mean("rms"), "kappa_mean": mean("kap"),
               "rate_mult": mean("mult"), "abs_delta": mean("absd"), "clip_share": mean("clip"), "critic_loss": mean("vloss"), "sigma_delta": math.sqrt(self.sd.var) if self.sd.var else None,
               "hand_v": mean("hand_v"), "jolt": mean("jolt"), "lim": mean("lim"), "jerk": mean("jerk"), "tv": mean("tv"), "secs": time.time() - t0}
        self.hist.append(rec)
        self.log("epoch " + str({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}))
        self.epoch += 1
        return rec

    def state(self):
        s = super().state()
        s["nrm"], s["raw0"], s["raw_new"] = self.nrm, self.raw0, self.raw_new
        return s

    def load(self, s):
        super().load(s)
        self.nrm, self.raw0, self.raw_new = s["nrm"], s["raw0"], s["raw_new"]
