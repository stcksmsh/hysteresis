"""M3d (docs/BRAIN_SPEC.md 7.16 point 2): learning to move by gradient. TOY ONLY. Provisional servo model (Feetech STS3215 12 V assumed).

Everything below is stated before the first run.

Pipeline (m3d_jax.py): toy brain state y_{b-1} (the last finished 0.5 s block, globally standardised, plus its change) -> motor cortex (MLP 16 -> 64 -> 33) ->
Gumbel-softmax mixture over the 8 programs of T-M3 + bounded modulation (+-0.2 of each command range) + coupling kappa (5 values, KAPPA_MAX 2 pi rad/s x
sigmoid, bias -3) -> spinal generators with the L3 phase coupling (phi_L3 extrapolated causally from the last block's measured phase and rate) -> MJX physics of
the M0 arm -> 31 descriptors of the last 2 s (roll excluded) -> observer MLP 31 -> 64 -> 64 -> 8.

Targets: the 8 brain-state numbers per 0.5 s block, with arcsinh applied to arousal and total surprisal first (heavy tails: up to 4e4 on the toy), then z-scored
within each episode (over its 120 blocks), clipped to +-5. The mean predictor scores 1.0.
Loss = observer MSE on the block's target + LAMBDA x (mean block energy / E0), E0 = the mean block energy of the untrained policy. Blocks before 2 s of movement exist are not scored.
Observer cross-fitted: 16 training episodes in two groups A, B of 8. The observer that scores group A was trained on group B's data and vice versa; frozen
(stop_gradient, and not in the optimiser) while it scores; both refreshed after each epoch (200 Adam steps, lr 1e-3, weight decay 1e-3, batch 256, from the last 4 epochs of data).
The policy gets one Adam step (lr LR, global gradient clip 1) per chunk; the chunk is CHUNK_BLOCKS blocks = the backward horizon (default 8 blocks = 4 s), carry
stop-gradient at the chunk edge, descriptor windows that start before the chunk read the earlier positions as constants.
Temperature schedule: tau_e = 1.0 x (0.2)^(e / (EPOCHS - 1)) over the epochs (1.0 -> 0.2), soft samples while training; evaluation uses hard one-hot choices
(argmax of the logits, and the Gumbel-max sample, both reported).

Evaluation on held-out episodes (new seeds), observer trained on all training data (600 Adam steps), blocks from 4 s on:
  (a) per episode, mean of [observer loss with targets circularly shifted by s blocks] - [loss with the matched targets], s >= 8 blocks (4 s), 20 seeded shifts averaged;
      95 % bootstrap interval of the mean over episodes (10,000 resamples); pass if the lower bound > 0.
  (b) RMS joint speed over the four non-roll joints >= 10 deg/s.
  (c) MI (nats) between the program (hard) and the state bin at decision time (quartile of arousal pooled over the held-out blocks x 4 bins of the L3 phase atan2(sin, cos)
      of the previous block), against 1,000 circular shifts (>= 4 s) of each episode's state-bin sequence; p = (1 + #{null >= obs}) / 1001; pass if p < 0.01.
"""
import math
import time

import jax
import jax.numpy as jnp
import numpy as np

import m3d_jax as J

NB = 120                 # blocks per episode (60 s)
VALID_FROM = 4           # first scored block (2 s of movement exist)
EVAL_FROM = 8            # evaluation scores blocks from 4 s on
CLIP_Z = 5.0
OBS_LR, OBS_WD, OBS_BATCH = 1e-3, 1e-3, 256
NON_ROLL = [0, 1, 2, 3]


# ---------------------------------------------------------------------------------------------------------------- data
def zscore_within(y, clip=CLIP_Z):
    """y (E, blocks, 8): per episode and number, mean 0 and SD 1 over its blocks, clipped."""
    z = (y - y.mean(1, keepdims=True)) / (y.std(1, keepdims=True) + 1e-8)
    return np.clip(z, -clip, clip)


def transform_state(y):
    y = np.array(y, float)
    y[..., :2] = np.arcsinh(y[..., :2])
    return y


class Toy:
    def __init__(self, path):
        d = np.load(path)
        self.n_train, self.n_tune = int(d["n_train"]), int(d["n_tune"])
        self.y = transform_state(d["y"])
        self.phi, self.omega = d["phi"].astype(float), d["omega"].astype(float)
        self.seeds = d["seeds"]
        tr = self.y[:self.n_train]
        self.mu, self.sd = tr.mean((0, 1)), tr.std((0, 1)) + 1e-8
        self.yz = zscore_within(self.y)
        self.sets = {"train": slice(0, self.n_train), "tune": slice(self.n_train, self.n_train + self.n_tune), "held": slice(self.n_train + self.n_tune, None)}

    def inputs(self, idx, key):
        """Per-block inputs for the episodes `idx` (list/slice): x (E, NB, 16), phi0, om0 (E, NB), g (E, NB, 8) Gumbel noise."""
        ys = (self.y[idx] - self.mu) / self.sd
        prev = np.concatenate([np.zeros_like(ys[:, :1]), ys[:, :-1]], 1)
        prev2 = np.concatenate([np.zeros_like(ys[:, :1]), prev[:, :-1]], 1)
        x = np.concatenate([prev, prev - prev2], -1)
        shift = lambda a: np.concatenate([np.zeros_like(a[:, :1]), a[:, :-1]], 1)
        return {"x": jnp.asarray(x), "phi0": jnp.asarray(shift(self.phi[idx])), "om0": jnp.asarray(shift(self.omega[idx])),
                "g": jax.random.gumbel(key, (x.shape[0], NB, J.K_PROG))}


def start_poses(n, seed):
    return np.array([0.0, -55.0, 35.0, 5.0, 0.0]) + np.random.default_rng(seed).uniform(-10, 10, (n, 5))


def take(tree, a, b):
    return jax.tree_util.tree_map(lambda x: x[:, a:b], tree)


# ---------------------------------------------------------------------------------------------------------------- jitted pieces
def make_fns(chunk_blocks):
    def run(P, mode, tau, carry, inps):
        return J.chunk(P, mode, tau, carry, inps)

    def loss_fn(P, O, carry, inps, yz, valid, tau, lam, e0, dmu, dsd):
        O = jax.lax.stop_gradient(O)
        carry, o = J.chunk(P, "train", tau, carry, inps)
        xd = jnp.clip((o["desc"] - dmu) / dsd, -8, 8)
        pred = jax.vmap(jax.vmap(lambda x: J.observer_apply(O, x)))(xd)
        dec = ((pred - yz) ** 2).mean(-1)
        n = jnp.maximum(valid.sum(), 1.0)
        L = (dec * valid).sum() / n
        en = (o["energy"] * valid).sum() / n / e0
        return L + lam * en, (carry, {"dec": L, "en": en, "desc": o["desc"], "ms": o["ms"], "pi": o["pi"], "kappa": o["kappa"], "energy": o["energy"]})

    return {"raw": loss_fn, "loss": jax.jit(jax.value_and_grad(loss_fn, has_aux=True)), "hard": {m: jax.jit(lambda P, carry, inps, m=m: J.chunk(P, m, 0.0, carry, inps)) for m in ("argmax", "sample")},
            "soft": jax.jit(lambda P, tau, carry, inps: J.chunk(P, "train", tau, carry, inps))}


@jax.jit
def _obs_step(O, st, x, y):
    def loss(O):
        return ((jax.vmap(lambda a: J.observer_apply(O, a))(x) - y) ** 2).mean()
    l, g = jax.value_and_grad(loss)(O)
    O, st, _ = J.adam_step(O, g, st, OBS_LR, clip=10.0, wd=OBS_WD)
    return O, st, l


def train_observer(O, x, y, steps, seed=0):
    """O params (warm start), x (n, 31) standardised descriptors, y (n, 8). -> O, final batch loss."""
    st = J.adam_init(O)
    rng = np.random.default_rng(seed)
    x, y = jnp.asarray(x), jnp.asarray(y)
    l = None
    for _ in range(steps):
        i = rng.integers(0, len(x), OBS_BATCH)
        O, st, l = _obs_step(O, st, x[i], y[i])
    return O, float(l)


def valid_mask(c0, nb, E):
    return jnp.asarray(np.broadcast_to((np.arange(c0, c0 + nb) >= VALID_FROM).astype(float), (E, nb)).copy())


def std_desc(desc, dmu, dsd):
    return np.clip((np.asarray(desc) - dmu) / dsd, -8, 8)


# ---------------------------------------------------------------------------------------------------------------- rollouts
def rollout_hard(fns, P, toy, idx, mode, key, chunk_blocks, seed_start):
    """Full episodes, no gradient, hard program choices. -> dict of numpy arrays (E, NB, ...): desc, pi, logits, kappa, ms, energy."""
    n = len(range(*idx.indices(len(toy.y)))) if isinstance(idx, slice) else len(idx)
    inps = toy.inputs(idx, key)
    carry = jax.vmap(J.init_carry)(jnp.asarray(start_poses(n, seed_start)))
    outs = []
    for c0 in range(0, NB, chunk_blocks):
        carry, o = fns["hard"][mode](P, carry, take(inps, c0, c0 + chunk_blocks))
        outs.append(o)
    return {k: np.concatenate([np.asarray(o[k]) for o in outs], 1) for k in outs[0]}


# ---------------------------------------------------------------------------------------------------------------- statistics
def mutual_information(a, b):
    """Plug-in MI (nats) of two integer label arrays of the same length."""
    a, b = np.asarray(a).ravel(), np.asarray(b).ravel()
    ka, kb = a.max() + 1, b.max() + 1
    p = np.bincount(a * kb + b, minlength=ka * kb).reshape(ka, kb) / len(a)
    pa, pb = p.sum(1, keepdims=True), p.sum(0, keepdims=True)
    m = p > 0
    return float((p[m] * np.log(p[m] / (pa @ pb)[m])).sum())


def state_bins(y, edges=None):
    """y (E, NB, 8) raw (transformed) brain state -> bins (E, NB) in 0..15 (arousal quartile x 4 L3 phase bins), quartile edges."""
    if edges is None:
        edges = np.percentile(y[..., 0], [25, 50, 75])
    q = np.searchsorted(edges, y[..., 0])
    ph = np.minimum(((np.arctan2(y[..., 3], y[..., 2]) + math.pi) / (2 * math.pi) * 4).astype(int), 3)
    return q * 4 + ph, edges


def mi_with_shuffles(prog, bins, n_shuf=1000, seed=0, min_shift=8):
    """prog, bins (E, T) integers; circular shifts (>= min_shift blocks) of each episode's bin sequence. -> observed MI, p."""
    rng = np.random.default_rng(seed)
    E, T = prog.shape
    obs = mutual_information(prog, bins)
    null = np.empty(n_shuf)
    for s in range(n_shuf):
        sh = rng.integers(min_shift, T - min_shift + 1, E)
        null[s] = mutual_information(prog, np.stack([np.roll(bins[e], sh[e]) for e in range(E)]))
    return obs, float((1 + (null >= obs).sum()) / (n_shuf + 1)), float(null.mean())


def boot_ci(x, n=10000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.asarray(x)
    bs = x[rng.integers(0, len(x), (n, len(x)))].mean(1)
    return float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def time_shuffled_gap(pred, yz, n_shifts=20, seed=0, min_shift=8, start=EVAL_FROM):
    """pred, yz (E, NB, 8). Per episode: mean over blocks >= start of [loss against targets shifted circularly by s >= min_shift blocks] - [matched loss],
    averaged over n_shifts seeded shifts. -> (E,) gaps, matched loss per episode."""
    rng = np.random.default_rng(seed)
    E, T = pred.shape[:2]
    matched = ((pred - yz) ** 2).mean(-1)[:, start:].mean(1)
    gaps = np.empty(E)
    for e in range(E):
        g = []
        for _ in range(n_shifts):
            s = int(rng.integers(min_shift, T - min_shift + 1))
            g.append(((pred[e] - np.roll(yz[e], s, axis=0)) ** 2).mean(-1)[start:].mean() - matched[e])
        gaps[e] = np.mean(g)
    return gaps, matched


def evaluate(fns, P, O, stats, toy, which, chunk_blocks, key_seed=7, start_seed=4242, log=print):
    """The bar on the episodes `which` ('tune' or 'held') for both choice modes. -> dict."""
    idx = toy.sets[which]
    yz = toy.yz[idx]
    ybins, _ = state_bins(toy.y[idx])
    res = {}
    for mode in ("argmax", "sample"):
        r = rollout_hard(fns, P, toy, idx, mode, jax.random.PRNGKey(key_seed), chunk_blocks, start_seed)
        xd = std_desc(r["desc"], stats["dmu"], stats["dsd"])
        pred = np.asarray(jax.vmap(jax.vmap(lambda x: J.observer_apply(O, x)))(jnp.asarray(xd)))
        gaps, matched = time_shuffled_gap(pred, yz)
        lo, hi = boot_ci(gaps)
        ms = r["ms"]
        prog = r["pi"].argmax(-1)
        mi, p, null_mean = mi_with_shuffles(prog[:, 1:], ybins[:, :-1])
        cnt = np.bincount(prog.ravel(), minlength=J.K_PROG)
        res[mode] = {"a_gap_mean": float(gaps.mean()), "a_ci": [lo, hi], "a_pass": bool(lo > 0), "a_gaps": gaps.tolist(), "matched_loss": float(matched.mean()),
                     "b_rms_nonroll": float(np.sqrt(ms[..., NON_ROLL].mean())), "b_per_joint": np.sqrt(ms.mean((0, 1))).tolist(),
                     "b_pass": bool(np.sqrt(ms[..., NON_ROLL].mean()) >= 10.0),
                     "c_mi": mi, "c_p": p, "c_null_mean": null_mean, "c_pass": bool(p < 0.01), "program_counts": cnt.tolist(),
                     "programs_used": int((cnt > 0).sum()), "kappa_mean": r["kappa"].mean((0, 1)).tolist(), "energy_per_block": float(r["energy"].mean())}
        log(f"eval {which} {mode}: " + str({k: (round(v, 4) if isinstance(v, float) else v) for k, v in res[mode].items() if k not in ("b_per_joint", "kappa_mean", "a_gaps")}))
    return res


# ---------------------------------------------------------------------------------------------------------------- training
class Trainer:
    def __init__(self, toy, lam, lr, epochs, chunk_blocks=8, obs_hidden=64, seed=0, log=print):
        self.toy, self.lam, self.lr, self.epochs, self.cb, self.log = toy, lam, lr, epochs, chunk_blocks, log
        self.fns = make_fns(chunk_blocks)
        key = jax.random.PRNGKey(seed)
        self.key, k1, k2, k3 = jax.random.split(key, 4)
        self.P = J.init_policy(k1)
        self.obs = {"A": J.init_observer(k2, obs_hidden), "B": J.init_observer(k3, obs_hidden)}      # obs["A"] scores group A (trained on B)
        self.st = J.adam_init(self.P)
        n = toy.n_train
        self.groups = {"A": np.arange(0, n // 2), "B": np.arange(n // 2, n)}
        self.data = {"A": [], "B": []}                                                              # per group: list of (x std (n,31), y (n,8)), last 4 epochs
        self.stats = None
        self.e0 = None
        self.epoch = 0
        self.hist = []

    def _collect(self, g, desc):
        """desc (E, NB, 31) raw of group g -> standardised valid blocks with their targets."""
        yz = self.toy.yz[self.groups[g]]
        x = std_desc(desc, self.stats["dmu"], self.stats["dsd"])[:, VALID_FROM:].reshape(-1, J.N_DESC)
        return x, yz[:, VALID_FROM:].reshape(-1, 8)

    def calibrate(self):
        """One pass of the untrained policy (no update): descriptor standardisation, E0, the first observers."""
        descs, ens, ms = {}, [], []
        for g, idx in self.groups.items():
            r = rollout_hard(self.fns, self.P, self.toy, idx, "argmax", jax.random.PRNGKey(11), self.cb, 100)
            descs[g] = r["desc"]
            ens.append(r["energy"][:, VALID_FROM:].mean())
            ms.append(r["ms"])
        allv = np.concatenate([descs[g][:, VALID_FROM:].reshape(-1, J.N_DESC) for g in descs])
        self.stats = {"dmu": allv.mean(0), "dsd": allv.std(0) + 1e-9}
        self.e0 = float(np.mean(ens))
        for g in "AB":
            self.data[g].append(self._collect(g, descs[g]))
        self._refresh(steps=400)
        self.log(f"calibration: E0 {self.e0:.5f} J/block, untrained RMS speed {np.sqrt(np.concatenate(ms).mean()):.1f}")

    def _refresh(self, steps):
        for scored, source in (("A", "B"), ("B", "A")):
            x = np.concatenate([d[0] for d in self.data[source]])
            y = np.concatenate([d[1] for d in self.data[source]])
            self.obs[scored], l = train_observer(self.obs[scored], x, y, steps, seed=self.epoch)
            self.log(f"  observer for group {scored} (trained on {source}, {len(x)} blocks): train loss {l:.3f}")

    def tau(self):
        return 1.0 * 0.2 ** (self.epoch / max(self.epochs - 1, 1))

    def run_epoch(self):
        t0 = time.time()
        tau = self.tau()
        rec = {"epoch": self.epoch, "tau": tau}
        decs, ens, mss, pis, kaps = [], [], [], [], []
        for g in "AB":
            idx = self.groups[g]
            E = len(idx)
            self.key, kk = jax.random.split(self.key)
            inps = self.toy.inputs(idx, kk)
            yz = jnp.asarray(self.toy.yz[idx])
            carry = jax.vmap(J.init_carry)(jnp.asarray(start_poses(E, 100)))
            descs = []
            for c0 in range(0, NB, self.cb):
                (l, (carry, aux)), grad = self.fns["loss"](self.P, self.obs[g], carry, take(inps, c0, c0 + self.cb), yz[:, c0:c0 + self.cb], valid_mask(c0, self.cb, E),
                                                           tau, self.lam, self.e0, self.stats["dmu"], self.stats["dsd"])
                self.P, self.st, gn = J.adam_step(self.P, grad, self.st, self.lr)
                descs.append(np.asarray(aux["desc"]))
                if c0 >= VALID_FROM:
                    decs.append(float(aux["dec"]))
                    ens.append(float(aux["en"]))
                mss.append(float(np.sqrt(np.asarray(aux["ms"])[..., NON_ROLL].mean())))
                pis.append(np.asarray(aux["pi"]))
                kaps.append(np.asarray(aux["kappa"]))
            self.data[g] = (self.data[g] + [self._collect(g, np.concatenate(descs, 1))])[-4:]
        self._refresh(steps=200)
        pi = np.concatenate(pis, 1)
        mean_pi = pi.mean((0, 1))
        rec.update({"dec": float(np.mean(decs)), "energy_rel": float(np.mean(ens)), "rms_speed": float(np.mean(mss)), "kappa_mean": float(np.mean(kaps)),
                    "pi_mean": mean_pi.round(3).tolist(), "pi_hard_share": float((pi.max(-1)).mean()), "secs": time.time() - t0})
        self.hist.append(rec)
        self.log("epoch " + str({k: (round(v, 4) if isinstance(v, float) else v) for k, v in rec.items()}))
        self.epoch += 1
        return rec

    def final_observer(self, steps=600):
        """The observer for held-out scoring: trained on the last epochs' data of both groups."""
        x = np.concatenate([d[0] for g in "AB" for d in self.data[g]])
        y = np.concatenate([d[1] for g in "AB" for d in self.data[g]])
        O, l = train_observer(self.obs["A"], x, y, steps, seed=999)
        self.log(f"final observer: {len(x)} blocks, train loss {l:.3f}")
        return O

    def state(self):
        return {"P": jax.tree_util.tree_map(np.asarray, self.P), "obs": {g: jax.tree_util.tree_map(np.asarray, o) for g, o in self.obs.items()}, "stats": self.stats, "e0": self.e0,
                "epoch": self.epoch, "hist": self.hist, "data": self.data, "key": np.asarray(self.key), "st": jax.tree_util.tree_map(np.asarray, self.st)}

    def load(self, s):
        to = lambda t: jax.tree_util.tree_map(jnp.asarray, t)
        self.P, self.obs, self.st = to(s["P"]), {g: [tuple(l) for l in to(o)] for g, o in s["obs"].items()}, to(s["st"])
        self.stats, self.e0, self.epoch, self.hist, self.data, self.key = s["stats"], s["e0"], s["epoch"], s["hist"], s["data"], jnp.asarray(s["key"])
