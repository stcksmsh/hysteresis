"""M3e (docs/BRAIN_SPEC.md 7.19 part B): the M3d toy rerun with a closed loop, a dopamine-scaled selection rate, causal normalisation and a self-observer.
Provisional servo model (Feetech STS3215 12 V assumed). Design stated in docs/NIGHT_LOG_body-m3e.md before the first run; summary:

Toy, bar, statistics (m3d.time_shuffled_gap, mi_with_shuffles, boot_ci) and mode rules as M3d, except: every pass/fail is in ARGMAX mode (sampled reported only).
Closed loop: m3e_jax.py (25 extra cortex inputs, zero-initialised). Block = 0.5 s; the cortex decides once per block, from the end-of-previous-block proprioception.
Causal normalisation: the toy brain state y (after arcsinh of arousal and total surprisal) is z-scored with running statistics over the past 60 blocks (30 s, the
block itself included for the target; the input for block b uses the z-score of block b-1 and the change from b-2). Fewer than 8 blocks in the window: z = 0 and the
block is not scored. VALID_FROM = EVAL_FROM = 8 blocks (4 s). Clipped to +-5.
Self-observer: observer_int (37 -> 64 -> 64 -> 8) on the quantised delayed proprioception descriptors (m3e_jax.block_fn idesc), cross-fitted exactly like the
external one (31 -> 64 -> 64 -> 8 on the visible descriptors, no roll). Loss = dec_ext + dec_int + LAMBDA x (mean block energy / E0) (energy is a cost: M3d's sign).
Dopamine: critic V(x_in) = tanh(x_in W1 + b1) W2 + b2 (41 -> 32 -> 1) predicts R_b = -mean over blocks b..b+3 (2 s) of the external decoding loss of the (soft,
training) rollout. delta_b = R_b - V_b (blocks with a full window inside the chunk, all four blocks scored). sigma_delta^2: running mean of delta^2 (decay 0.9 per chunk).
Selection rate multiplier m = 0.5 + clip(mean|delta| over the chunk / sigma_delta, 0, 2), applied to the Adam step of the program-logit path: cortex output weights
w2[:, :8] and bias b2[:8]. Every other parameter keeps the base rate; a chunk with no scoreable window has m = 1. The critic has its own Adam (lr 1e-3).
"""
import math
import time

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3d_jax as J
import m3e_jax as M

VALID_FROM = 8
EVAL_FROM = 8
ZWIN, ZMIN, CLIP_Z = 60, 8, 5.0
CRIT_H = 4
NB = m3d.NB
NON_ROLL = m3d.NON_ROLL


# ---------------------------------------------------------------------------------------------------------------- causal data
def running_z(y, win=ZWIN, minn=ZMIN, clip=CLIP_Z):
    """y (E, T, k) -> z (E, T, k): block b standardised by the mean and SD of blocks max(0, b-win+1)..b (causal); 0 where the window holds fewer than `minn` blocks."""
    z = np.zeros_like(y, dtype=float)
    for b in range(minn - 1, y.shape[1]):
        w = y[:, max(0, b - win + 1):b + 1]
        z[:, b] = (y[:, b] - w.mean(1)) / (w.std(1) + 1e-8)
    return np.clip(z, -clip, clip)


class ToyE(m3d.Toy):
    """M3d's toy with causal normalisation of the targets and of the cortex's state input."""

    def __init__(self, path):
        super().__init__(path)
        self.yz = running_z(self.y)

    def inputs(self, idx, key):
        zr = self.yz[idx]
        sh = lambda a: np.concatenate([np.zeros_like(a[:, :1]), a[:, :-1]], 1)
        prev = sh(zr)
        x = np.concatenate([prev, prev - sh(prev)], -1)
        shp = lambda a: sh(a)
        return {"x": jnp.asarray(x), "phi0": jnp.asarray(shp(self.phi[idx])), "om0": jnp.asarray(shp(self.omega[idx])),
                "g": jax.random.gumbel(key, (x.shape[0], NB, J.K_PROG))}


def valid_mask(c0, nb, E):
    return jnp.asarray(np.broadcast_to((np.arange(c0, c0 + nb) >= VALID_FROM).astype(float), (E, nb)).copy())


def init_observer(key, n_in, hidden=64, n_out=8):
    sizes = [n_in, hidden, hidden, n_out]
    ks = jax.random.split(key, 3)
    return [(jax.random.normal(k, (a, b)) / math.sqrt(a), jnp.zeros(b)) for k, a, b in zip(ks, sizes[:-1], sizes[1:])]


# ---------------------------------------------------------------------------------------------------------------- dopamine
def init_critic(key, hidden=32):
    k1, k2 = jax.random.split(key)
    return {"w1": jax.random.normal(k1, (M.D_IN, hidden)) / math.sqrt(M.D_IN), "b1": jnp.zeros(hidden), "w2": 0.1 * jax.random.normal(k2, (hidden, 1)) / math.sqrt(hidden), "b2": jnp.zeros(1)}


def critic_apply(V, x):
    return (jnp.tanh(x @ V["w1"] + V["b1"]) @ V["w2"] + V["b2"])[..., 0]


def realised_legibility(dec, c0, crit_h=CRIT_H):
    """dec (E, nb) external decoding loss of a chunk starting at global block c0 -> R (E, nb-crit_h+1) = -mean of the next crit_h blocks, mask (nb-crit_h+1,) of windows
    whose blocks are all scored."""
    nb = dec.shape[1]
    n = nb - crit_h + 1
    R = -np.stack([dec[:, b:b + crit_h].mean(1) for b in range(n)], 1)
    mask = np.array([c0 + b >= VALID_FROM for b in range(n)])
    return R, mask


class RunningSD:
    def __init__(self, decay=0.9):
        self.decay, self.var = decay, None

    def update(self, d2):
        self.var = d2 if self.var is None else self.decay * self.var + (1 - self.decay) * d2
        return math.sqrt(self.var) + 1e-8


def rate_multiplier(delta, sigma):
    """0.5 + clip(mean|delta| / sigma, 0, 2)."""
    return 0.5 + float(np.clip(np.abs(delta).mean() / sigma, 0.0, 2.0))


def logit_mult(P, m):
    """Per-parameter learning-rate multipliers: m on the program-logit path (w2[:, :8], b2[:8]), 1 elsewhere."""
    one = jax.tree_util.tree_map(jnp.ones_like, P)
    one["w2"] = one["w2"].at[:, :J.K_PROG].set(m)
    one["b2"] = one["b2"].at[:J.K_PROG].set(m)
    return one


def adam_step_mult(P, g, st, lr, mult, clip=1.0, b1=0.9, b2=0.999):
    """J.adam_step with a per-element learning-rate multiplier tree."""
    gn = jnp.sqrt(sum((x ** 2).sum() for x in jax.tree_util.tree_leaves(g)))
    sc = jnp.minimum(1.0, clip / (gn + 1e-12))
    g = jax.tree_util.tree_map(lambda x: x * sc, g)
    t = st["t"] + 1
    m = jax.tree_util.tree_map(lambda a, b: b1 * a + (1 - b1) * b, st["m"], g)
    v = jax.tree_util.tree_map(lambda a, b: b2 * a + (1 - b2) * b * b, st["v"], g)
    P = jax.tree_util.tree_map(lambda p, mm, vv, k: p - lr * k * ((mm / (1 - b1 ** t)) / (jnp.sqrt(vv / (1 - b2 ** t)) + 1e-8)), P, m, v, mult)
    return P, {"m": m, "v": v, "t": t}, gn


# ---------------------------------------------------------------------------------------------------------------- jitted pieces
def make_fns(C):
    def loss_fn(P, Oe, Oi, carry, inps, yz, valid, tau, lam, e0, dmu, dsd, imu, isd):
        Oe, Oi = jax.lax.stop_gradient(Oe), jax.lax.stop_gradient(Oi)
        carry, o = M.chunk(C, P, "train", tau, carry, inps)
        dec = lambda O, d, mu, sd: ((jax.vmap(jax.vmap(lambda x: J.observer_apply(O, x)))(jnp.clip((d - mu) / sd, -8, 8)) - yz) ** 2).mean(-1)
        de, di = dec(Oe, o["desc"], dmu, dsd), dec(Oi, o["idesc"], imu, isd)
        n = jnp.maximum(valid.sum(), 1.0)
        Le, Li = (de * valid).sum() / n, (di * valid).sum() / n
        en = (o["energy"] * valid).sum() / n / e0
        return Le + Li + lam * en, (carry, {"dec_e": Le, "dec_i": Li, "en": en, "de": de, "xin": o["xin"], "desc": o["desc"], "idesc": o["idesc"], "ms": o["ms"], "pi": o["pi"], "kappa": o["kappa"]})

    hard = {m: jax.jit(lambda P, carry, inps, m=m: M.chunk(C, P, m, 0.0, carry, inps)) for m in ("argmax", "sample")}
    return {"loss": jax.jit(jax.value_and_grad(loss_fn, has_aux=True)), "hard": hard}


@jax.jit
def _critic_step(V, st, x, r, w):
    def loss(V):
        return (((critic_apply(V, x) - r) ** 2) * w).sum() / jnp.maximum(w.sum(), 1.0)
    l, g = jax.value_and_grad(loss)(V)
    V, st, _ = J.adam_step(V, g, st, 1e-3)
    return V, st, l


def rollout(fns, C, P, toy, idx, mode, key, chunk_blocks, seed_start):
    """Full episodes, no gradient, hard choices. -> dict of numpy arrays (E, NB, ...)."""
    n = len(range(*idx.indices(len(toy.y)))) if isinstance(idx, slice) else len(idx)
    inps = toy.inputs(idx, key)
    carry = jax.vmap(lambda q: M.init_carry(q, C))(jnp.asarray(m3d.start_poses(n, seed_start)))
    outs = []
    for c0 in range(0, NB, chunk_blocks):
        carry, o = fns["hard"][mode](P, carry, m3d.take(inps, c0, c0 + chunk_blocks))
        outs.append(o)
    return {k: np.concatenate([np.asarray(o[k]) for o in outs], 1) for k in outs[0]}


# ---------------------------------------------------------------------------------------------------------------- scoring (WO7 observer procedure, external and internal)
def fresh_observers(rolls, yz, stats):
    """The WO7 procedure: fresh observers (init key 0, 64 hidden), 600 Adam steps, seed 999, on the training-episode rollouts of the fixed policy (4 rollouts) and the
    causal targets. rolls: list of rollout dicts. -> external O, internal O."""
    xe = np.concatenate([m3d.std_desc(r["desc"], stats["dmu"], stats["dsd"])[:, VALID_FROM:].reshape(-1, J.N_DESC) for r in rolls])
    xi = np.concatenate([m3d.std_desc(r["idesc"], stats["imu"], stats["isd"])[:, VALID_FROM:].reshape(-1, M.N_IDESC) for r in rolls])
    y = np.concatenate([yz[:, VALID_FROM:].reshape(-1, 8) for _ in rolls])
    Oe, _ = m3d.train_observer(init_observer(jax.random.PRNGKey(0), J.N_DESC), xe, y, 600, seed=999)
    Oi, _ = m3d.train_observer(init_observer(jax.random.PRNGKey(0), M.N_IDESC), xi, y, 600, seed=999)
    return Oe, Oi


def decode_stats(r, O, mu, sd, key, yz, which):
    """Predictions of one decoder on a rollout -> per-episode (a) gaps, matched loss."""
    pred = np.asarray(jax.vmap(jax.vmap(lambda x: J.observer_apply(O, x)))(jnp.asarray(m3d.std_desc(r[key], mu, sd))))
    gaps, matched = m3d.time_shuffled_gap(pred, yz, start=EVAL_FROM)
    lo, hi = m3d.boot_ci(gaps)
    return {"a_gap_mean": float(gaps.mean()), "a_ci": [lo, hi], "a_pass": bool(lo > 0), "a_gaps": gaps.tolist(), "matched_loss": float(matched.mean())}, pred


def score_rollouts(held, Oe, Oi, stats, toy, which):
    """One mode: held-out rollout `held` scored by both observers, plus (b) and (c). -> dict."""
    idx = toy.sets[which]
    yz = toy.yz[idx]
    ybins, _ = m3d.state_bins(toy.y[idx])
    ext, _ = decode_stats(held, Oe, stats["dmu"], stats["dsd"], "desc", yz, which)
    itn, _ = decode_stats(held, Oi, stats["imu"], stats["isd"], "idesc", yz, which)
    ms = held["ms"]
    prog = held["pi"].argmax(-1)
    mi, p, null_mean = m3d.mi_with_shuffles(prog[:, 1:], ybins[:, :-1])
    cnt = np.bincount(prog.ravel(), minlength=J.K_PROG)
    b = float(np.sqrt(ms[..., NON_ROLL].mean()))
    return {"ext": ext, "int": itn, "b_rms_nonroll": b, "b_per_joint": np.sqrt(ms.mean((0, 1))).tolist(), "b_pass": bool(b >= 10.0),
            "c_mi": mi, "c_p": p, "c_null_mean": null_mean, "c_pass": bool(p < 0.01), "program_counts": cnt.tolist(), "programs_used": int((cnt > 0).sum()),
            "kappa_mean": held["kappa"].mean((0, 1)).tolist(), "energy_per_block": float(held["energy"].mean())}


def score_policy(fns, C, P, toy, stats, which, chunk_blocks, rolldir=None, name="policy", log=print):
    """Both modes. Rollouts (4 training + 1 evaluation set per mode) are saved to rolldir BEFORE scoring and reused if present. -> {mode: score dict}, {mode: (Oe, Oi, held)}."""
    import os
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
            r = rollout(fns, C, P, toy, idx, mode, jax.random.PRNGKey(key), chunk_blocks, seed)
            if f:
                np.savez(f, **r)
            rolls.append(r)
        Oe, Oi = fresh_observers(rolls[:4], yz_tr, stats)
        res[mode] = score_rollouts(rolls[4], Oe, Oi, stats, toy, which)
        keep[mode] = (Oe, Oi, rolls[4])
        s = res[mode]
        log(f"score {name} {which} {mode}: ext a {s['ext']['a_gap_mean']:.3f} {np.round(s['ext']['a_ci'], 3).tolist()} | int a {s['int']['a_gap_mean']:.3f} {np.round(s['int']['a_ci'], 3).tolist()} | "
            f"b {s['b_rms_nonroll']:.1f} | c MI {s['c_mi']:.4f} p {s['c_p']:.4f} | programs {s['programs_used']}")
    return res, keep


# ---------------------------------------------------------------------------------------------------------------- training
class Trainer:
    def __init__(self, toy, C, lam, lr, epochs, chunk_blocks=8, seed=0, dopamine=True, log=print):
        self.toy, self.C, self.lam, self.lr, self.epochs, self.cb, self.log, self.dopamine = toy, C, lam, lr, epochs, chunk_blocks, log, dopamine
        self.fns = make_fns(C)
        key = jax.random.PRNGKey(seed)
        self.key, k1, k2, k3, k4, k5, k6 = jax.random.split(key, 7)
        self.P = M.init_policy(k1)
        self.obs = {"A": (init_observer(k2, J.N_DESC), init_observer(k4, M.N_IDESC)), "B": (init_observer(k3, J.N_DESC), init_observer(k5, M.N_IDESC))}
        self.st = J.adam_init(self.P)
        self.V = init_critic(k6)
        self.vst = J.adam_init(self.V)
        self.sd = RunningSD()
        n = toy.n_train
        self.groups = {"A": np.arange(0, n // 2), "B": np.arange(n // 2, n)}
        self.data = {"A": [], "B": []}
        self.stats, self.e0, self.epoch, self.hist = None, None, 0, []

    def _collect(self, g, desc, idesc):
        yz = self.toy.yz[self.groups[g]][:, VALID_FROM:].reshape(-1, 8)
        xe = m3d.std_desc(desc, self.stats["dmu"], self.stats["dsd"])[:, VALID_FROM:].reshape(-1, J.N_DESC)
        xi = m3d.std_desc(idesc, self.stats["imu"], self.stats["isd"])[:, VALID_FROM:].reshape(-1, M.N_IDESC)
        return xe, xi, yz

    def _roll(self, idx, key, mode="argmax", seed=100):
        return rollout(self.fns, self.C, self.P, self.toy, idx, mode, key, self.cb, seed)

    def calibrate(self):
        rs = {g: self._roll(idx, jax.random.PRNGKey(11)) for g, idx in self.groups.items()}
        cat = lambda k, n: np.concatenate([rs[g][k][:, VALID_FROM:].reshape(-1, n) for g in rs])
        d, i = cat("desc", J.N_DESC), cat("idesc", M.N_IDESC)
        self.stats = {"dmu": d.mean(0), "dsd": d.std(0) + 1e-9, "imu": i.mean(0), "isd": i.std(0) + 1e-9}
        self.e0 = float(np.mean([rs[g]["energy"][:, VALID_FROM:].mean() for g in rs]))
        for g in "AB":
            self.data[g].append(self._collect(g, rs[g]["desc"], rs[g]["idesc"]))
        self._refresh(400)
        self.log(f"calibration: E0 {self.e0:.5f} J/block, untrained RMS speed {np.sqrt(np.concatenate([rs[g]['ms'] for g in rs]).mean()):.1f}")

    def _refresh(self, steps):
        for scored, source in (("A", "B"), ("B", "A")):
            xe = np.concatenate([d[0] for d in self.data[source]])
            xi = np.concatenate([d[1] for d in self.data[source]])
            y = np.concatenate([d[2] for d in self.data[source]])
            oe, le = m3d.train_observer(self.obs[scored][0], xe, y, steps, seed=self.epoch)
            oi, li = m3d.train_observer(self.obs[scored][1], xi, y, steps, seed=self.epoch + 1000)
            self.obs[scored] = (oe, oi)
            self.log(f"  observers for group {scored} (trained on {source}, {len(xe)} blocks): ext {le:.3f} int {li:.3f}")

    def tau(self):
        return 1.0 * 0.2 ** (self.epoch / max(self.epochs - 1, 1))

    def run_epoch(self):
        t0 = time.time()
        tau = self.tau()
        S = self.stats
        acc = {"dec_e": [], "dec_i": [], "en": [], "rms": [], "mult": [], "absd": [], "clip": [], "kap": [], "vloss": []}
        for g in "AB":
            idx = self.groups[g]
            E = len(idx)
            self.key, kk = jax.random.split(self.key)
            inps = self.toy.inputs(idx, kk)
            yz = jnp.asarray(self.toy.yz[idx])
            carry = jax.vmap(lambda q: M.init_carry(q, self.C))(jnp.asarray(m3d.start_poses(E, 100)))
            ds, ids = [], []
            for c0 in range(0, NB, self.cb):
                sl = lambda a: a[:, c0:c0 + self.cb]
                (l, (carry, aux)), grad = self.fns["loss"](self.P, self.obs[g][0], self.obs[g][1], carry, m3d.take(inps, c0, c0 + self.cb), sl(yz), valid_mask(c0, self.cb, E), tau, self.lam,
                                                           self.e0, S["dmu"], S["dsd"], S["imu"], S["isd"])
                mult = 1.0
                if self.dopamine:
                    R, mask = realised_legibility(np.asarray(aux["de"]), c0)
                    if mask.any():
                        x = aux["xin"][:, :R.shape[1]]
                        Vp = np.asarray(critic_apply(self.V, x))
                        delta = (R - Vp)[:, mask]
                        sigma = self.sd.update(float((delta ** 2).mean()))
                        mult = rate_multiplier(delta, sigma)
                        acc["absd"].append(float(np.abs(delta).mean()))
                        acc["clip"].append(float((np.abs(delta) / sigma >= 2.0).mean()))
                        w = jnp.asarray(np.broadcast_to(mask, R.shape).astype(float))
                        self.V, self.vst, vl = _critic_step(self.V, self.vst, x, jnp.asarray(R), w)
                        acc["vloss"].append(float(vl))
                acc["mult"].append(mult)
                self.P, self.st, gn = adam_step_mult(self.P, grad, self.st, self.lr, logit_mult(self.P, mult))
                ds.append(np.asarray(aux["desc"]))
                ids.append(np.asarray(aux["idesc"]))
                if c0 >= VALID_FROM:
                    acc["dec_e"].append(float(aux["dec_e"]))
                    acc["dec_i"].append(float(aux["dec_i"]))
                    acc["en"].append(float(aux["en"]))
                acc["rms"].append(float(np.sqrt(np.asarray(aux["ms"])[..., NON_ROLL].mean())))
                acc["kap"].append(np.asarray(aux["kappa"]).mean())
            self.data[g] = (self.data[g] + [self._collect(g, np.concatenate(ds, 1), np.concatenate(ids, 1))])[-4:]
        self._refresh(200)
        mean = lambda k: float(np.mean(acc[k])) if acc[k] else None
        rec = {"epoch": self.epoch, "tau": tau, "dec_e": mean("dec_e"), "dec_i": mean("dec_i"), "energy_rel": mean("en"), "rms_speed": mean("rms"), "kappa_mean": mean("kap"),
               "rate_mult": mean("mult"), "abs_delta": mean("absd"), "clip_share": mean("clip"), "critic_loss": mean("vloss"), "sigma_delta": math.sqrt(self.sd.var) if self.sd.var else None, "secs": time.time() - t0}
        self.hist.append(rec)
        self.log("epoch " + str({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}))
        self.epoch += 1
        return rec

    def state(self):
        t = lambda x: jax.tree_util.tree_map(np.asarray, x)
        return {"P": t(self.P), "obs": {g: [t(o) for o in os_] for g, os_ in self.obs.items()}, "stats": self.stats, "e0": self.e0, "epoch": self.epoch, "hist": self.hist, "data": self.data,
                "key": np.asarray(self.key), "st": t(self.st), "V": t(self.V), "vst": t(self.vst), "sd_var": self.sd.var}

    def load(self, s):
        to = lambda t: jax.tree_util.tree_map(jnp.asarray, t)
        self.P, self.st, self.V, self.vst = to(s["P"]), to(s["st"]), to(s["V"]), to(s["vst"])
        self.obs = {g: tuple([tuple(l) for l in to(o)] for o in os_) for g, os_ in s["obs"].items()}
        self.stats, self.e0, self.epoch, self.hist, self.data, self.key, self.sd.var = s["stats"], s["e0"], s["epoch"], s["hist"], s["data"], jnp.asarray(s["key"]), s["sd_var"]


# ---------------------------------------------------------------------------------------------------------------- dopamine lane and reports
def dopamine_lane(V, sigma, held, Oe, stats, toy, which):
    """Per-block delta on the evaluation episodes of a rollout (argmax): R from the final external observer's decoding loss, V from the critic. -> delta (E, NB-3), summary."""
    yz = toy.yz[toy.sets[which]]
    pred = np.asarray(jax.vmap(jax.vmap(lambda x: J.observer_apply(Oe, x)))(jnp.asarray(m3d.std_desc(held["desc"], stats["dmu"], stats["dsd"]))))
    R, mask = realised_legibility(((pred - yz) ** 2).mean(-1), 0)
    delta = R - np.asarray(critic_apply(V, jnp.asarray(held["xin"][:, :R.shape[1]])))
    d = delta[:, mask]
    return delta, {"mean_abs_delta": float(np.abs(d).mean()), "sigma_delta_training": sigma, "share_clipped": float((np.abs(d) / sigma >= 2.0).mean()), "share_below_half_sigma": float((np.abs(d) / sigma < 0.5).mean())}


def input_group_norms(P):
    w = np.asarray(P["w1"])
    return {"state (16)": float(np.linalg.norm(w[:16])), "proprio (10)": float(np.linalg.norm(w[16:26])), "cerebellum pose (5)": float(np.linalg.norm(w[26:31])), "cerebellum error (10)": float(np.linalg.norm(w[31:41]))}
