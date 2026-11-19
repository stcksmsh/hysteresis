"""Stage 1 toy (work order 20). Definitions: docs/STAGE1_RULES.md. TOY ONLY: a 2-link planar arm, synthetic songs.

    cd scripts/body && /secondary/hyst-env/body/bin/python -u s1_toy.py --arm iv --seed 0 --epochs 1000 --lam 0.5 --out /secondary/hyst-data/body/s1/run_iv_0.5_s0
    python s1_toy.py --smoke          # one epoch per arm, prints seconds per epoch and the projection
"""
import argparse
import json
import os
import pickle
import time

import jax
import jax.numpy as jnp
import numpy as np
from scipy.optimize import minimize

DT, T, SECS = 0.05, 800, 40.0
L1 = L2 = 0.30
QMAX = np.array([2.0, 2.4], np.float32)
LAG = 0.35
K_WIN, T_FROM, G_OUT = 30, 60, 4.0
SHIFT_MIN = 160
WIN_C, SUB_C = 160, 4                   # contrastive window (8 s), motion subsample
V_MAX, J_MAX, Q_MARGIN = 1.2, 400.0, 0.15
GRID_N, GRID_LIM = 24, 0.6
ARMS = ["0", "i", "ii", "iii", "iv"]
LEVEL = {"0": 0, "i": 0, "ii": 1, "iii": 2, "iv": 3, "iii+D": 2, "iii+Df": 2}   # cumulative level; arm 0 = arm i with pass2 soft costs instead of hinges
D_TARGET, ETA_D, D_SONGS = 0.7, 0.16, 16                       # WO24 (rules section 12): D hinge target, dual step per epoch, held-in songs
TAU_Z = 5.0                                              # arm i z-score time constant (s), 1/8 of the song (BRAIN_SPEC 7.35)
LAM_SOFT, W_JERK_SOFT = 0.03, 0.03                       # pass2: LAM, W_JERK
SOFT_FLOORS = {"hand_v": 0.02, "jolt": 0.2, "lim": 0.005, "jerk": 1.0, "en": 1e-6}   # m3f.FLOORS


# ----------------------------------------------------------------------------- songs
def _ou(rng, n, tau, sd):
    a = np.exp(-DT / tau)
    x = np.zeros(n)
    e = rng.standard_normal(n) * sd * np.sqrt(1 - a * a)
    x[0] = rng.standard_normal() * sd
    for i in range(1, n):
        x[i] = a * x[i - 1] + e[i]
    return x


def make_song(seed):
    rng = np.random.default_rng(seed)
    bpm = rng.uniform(90, 130)
    off = rng.uniform(0, 1)
    logg = rng.normal(0, 0.3)
    z0 = rng.standard_normal(2)
    z = np.stack([z0[k] + _ou(rng, T, 10.0, 0.15) for k in range(2)], 1)         # (T, 2)
    t = np.arange(T) * DT
    phi = off + bpm / 60.0 * t
    beat = np.floor(phi).astype(int)
    onset = np.concatenate([[False], beat[1:] > beat[:-1]])
    accent = (beat % 4 == 0)
    imp = onset.astype(float)
    a = np.exp(-DT / 0.1)
    p = np.zeros(T)
    for i in range(T):
        p[i] = (a * p[i - 1] if i else 0.0) + imp[i]
    e = np.exp(logg) * (1 + 0.4 * np.tanh(z[:, 0])) * p * np.exp(0.3 * z[:, 1] * accent)
    s = z + 0.3 * rng.standard_normal((T, 2))
    c, sn = np.cos(2 * np.pi * phi), np.sin(2 * np.pi * phi)
    feats = np.stack([c, sn, e, s[:, 0], s[:, 1]], 1).astype(np.float32)
    tgt = np.stack([c, sn, np.cos(2 * np.pi * phi / 4), np.sin(2 * np.pi * phi / 4), z[:, 0], z[:, 1],
                    np.full(T, (bpm - 110) / 20), np.full(T, logg)], 1).astype(np.float32)
    return feats, tgt, bpm, logg


def make_corpus(seeds):
    out = [make_song(s) for s in seeds]
    return {"feats": np.stack([o[0] for o in out]), "tgt": np.stack([o[1] for o in out]),
            "bpm": np.array([o[2] for o in out]), "logg": np.array([o[3] for o in out])}


TRAIN_SEEDS, VAL_SEEDS, HELD_SEEDS = [1000 + i for i in range(64)], [2000 + i for i in range(16)], [3000 + i for i in range(32)]


def corpus_stats(train_tgt):
    flat = train_tgt.reshape(-1, 8)
    return flat.mean(0), flat.std(0)


def causal_z(tgt, floor_sd, tau_s=TAU_Z):
    """(S,T,8) -> causal EMA z-score within each song, bias corrected, sd floored at floor_sd (8,)."""
    a = np.exp(-DT / tau_s)
    S, n, D = tgt.shape
    out = np.zeros_like(tgt)
    m = np.zeros((S, D)); v = np.zeros((S, D)); w = 0.0
    for i in range(n):
        m = a * m + (1 - a) * tgt[:, i]
        v = a * v + (1 - a) * tgt[:, i] ** 2
        w = a * w + (1 - a)
        mu = m / w
        sd = np.sqrt(np.maximum(v / w - mu ** 2, 0))
        out[:, i] = (tgt[:, i] - mu) / np.maximum(sd, floor_sd)
    return out


def make_targets(corpus, arm_i, stats):
    mu, sd = stats
    if arm_i:
        return causal_z(corpus["tgt"], 0.1 * sd).astype(np.float32)
    z = causal_z(corpus["tgt"], 0.1 * sd)
    std = (corpus["tgt"] - mu) / sd
    z[:, :, 4:] = std[:, :, 4:]
    return z.astype(np.float32)


# ----------------------------------------------------------------------------- arm
def fk(q):
    a1, a12 = q[..., 0], q[..., 0] + q[..., 1]
    return jnp.stack([L1 * jnp.cos(a1) + L2 * jnp.cos(a12), L1 * jnp.sin(a1) + L2 * jnp.sin(a12)], -1)


def rollout(pol, feats):
    """feats (S,T,5) -> q (S,T,2). Deterministic."""
    S = feats.shape[0]
    qmax = jnp.asarray(QMAX)

    def step(carry, x):
        h, q = carry
        zr = jax.nn.sigmoid(x @ pol["Wz"] + h @ pol["Uz"] + pol["bz"])
        r = jax.nn.sigmoid(x @ pol["Wr"] + h @ pol["Ur"] + pol["br"])
        n = jnp.tanh(x @ pol["Wn"] + (r * h) @ pol["Un"] + pol["bn"])
        h = (1 - zr) * n + zr * h
        a = h @ pol["Wo"] + pol["bo"]
        qs = 0.95 * qmax * jnp.tanh(a)
        q = q + LAG * (qs - q)
        return (h, q), q

    h0 = jnp.zeros((S, pol["Uz"].shape[0])); q0 = jnp.zeros((S, 2))
    _, qs = jax.lax.scan(step, (h0, q0), jnp.swapaxes(feats, 0, 1))
    return jnp.swapaxes(qs, 0, 1)


# ----------------------------------------------------------------------------- nets
def _dense(key, i, o, scale=1.0):
    return jax.random.normal(key, (i, o)) * scale / np.sqrt(i)


def init_params(seed):
    ks = iter(jax.random.split(jax.random.PRNGKey(seed), 32))
    H = 32
    pol = {}
    for g in "zrn":
        pol["W" + g] = _dense(next(ks), 5, H); pol["U" + g] = _dense(next(ks), H, H); pol["b" + g] = jnp.zeros(H)
    pol["Wo"] = _dense(next(ks), H, 2); pol["bo"] = jnp.zeros(2)
    obs = {"W1": _dense(next(ks), 2 * K_WIN, 64), "b1": jnp.zeros(64), "W2": _dense(next(ks), 64, 64), "b2": jnp.zeros(64),
           "W3": _dense(next(ks), 64, 8), "b3": jnp.zeros(8)}
    mus = {"W1": _dense(next(ks), 5, 32), "b1": jnp.zeros(32), "W2": _dense(next(ks), 32, 32), "b2": jnp.zeros(32)}
    mot = {"W1": _dense(next(ks), 2 * (WIN_C // SUB_C), 64), "b1": jnp.zeros(64), "W2": _dense(next(ks), 64, 32), "b2": jnp.zeros(32)}
    return {"pol": pol, "obs": obs, "mus": mus, "mot": mot}


def windows(hand):
    """hand (S,T,2) -> (S,T,2K) causal windows, zero padded; newest first."""
    pad = jnp.concatenate([jnp.zeros((hand.shape[0], K_WIN - 1, 2)), hand], 1)
    idx = jnp.arange(hand.shape[1])[:, None] + (K_WIN - 1) - jnp.arange(K_WIN)[None, :]
    return pad[:, idx].reshape(hand.shape[0], hand.shape[1], 2 * K_WIN)


def spec_norm(W):
    return W / jnp.maximum(1.0, jnp.linalg.norm(W, 2))


def observer(obs, w, lip):
    f = spec_norm if lip else (lambda x: x)
    h = jnp.tanh(w @ f(obs["W1"]) + obs["b1"])
    h = jnp.tanh(h @ f(obs["W2"]) + obs["b2"])
    return G_OUT * (h @ f(obs["W3"]) + obs["b3"])


def music_emb(mus, x):
    h = jnp.tanh(x @ mus["W1"] + mus["b1"])
    e = h @ mus["W2"] + mus["b2"]
    return e / (jnp.linalg.norm(e, axis=-1, keepdims=True) + 1e-8)


def motion_emb(mot, x):
    h = jnp.tanh(x @ mot["W1"] + mot["b1"])
    e = h @ mot["W2"] + mot["b2"]
    return e / (jnp.linalg.norm(e, axis=-1, keepdims=True) + 1e-8)


def info_nce(a, b, temp=0.1):
    """a, b (B,D) normalised; symmetric InfoNCE, matching pairs on the diagonal."""
    s = a @ b.T / temp
    lab = jnp.arange(a.shape[0])
    la = -jnp.mean(jax.nn.log_softmax(s, 1)[lab, lab])
    lb = -jnp.mean(jax.nn.log_softmax(s.T, 1)[lab, lab])
    return 0.5 * (la + lb)


def posture_embedding(hand):
    """(S,T,2) -> (S,64) soft histogram, rows sum to 1."""
    cell = 2 * GRID_LIM / 8
    cen = (jnp.arange(8) + 0.5) * cell - GRID_LIM
    gx = jnp.exp(-0.5 * ((hand[..., 0:1] - cen) / cell) ** 2)       # (S,T,8)
    gy = jnp.exp(-0.5 * ((hand[..., 1:2] - cen) / cell) ** 2)
    gx = gx / (gx.sum(-1, keepdims=True) + 1e-8); gy = gy / (gy.sum(-1, keepdims=True) + 1e-8)
    h = jnp.einsum("stx,sty->sxy", gx, gy).reshape(hand.shape[0], 64) / hand.shape[1]
    return h


def logdet_K(emb, ell=0.05):
    d2 = jnp.sum((emb[:, None] - emb[None]) ** 2, -1)
    K = jnp.exp(-d2 / (2 * ell ** 2)) + 1e-3 * jnp.eye(emb.shape[0])
    return jnp.linalg.slogdet(K)[1]


def hinges(q, hand):
    """-> (S,3) violation means: speed, jerk envelope, joint-limit margin."""
    v = (hand[:, 2:] - hand[:, :-2]) / (2 * DT)
    g1 = jnp.mean(jax.nn.relu(jnp.linalg.norm(v, axis=-1) / V_MAX - 1), 1)
    j = (hand[:, 3:] - 3 * hand[:, 2:-1] + 3 * hand[:, 1:-2] - hand[:, :-3]) / DT ** 3
    j2 = j[..., 0] ** 2 + j[..., 1] ** 2
    jr = jnp.sqrt(jax.lax.reduce_window(j2, 0.0, jax.lax.add, (1, 5), (1, 1), "VALID") / 5)
    g2 = jnp.mean(jax.nn.relu(jr / J_MAX - 1), 1)
    qm = jnp.asarray(QMAX)
    g3 = jnp.mean(jnp.sum(jax.nn.relu((jnp.abs(q) - (qm - Q_MARGIN)) / Q_MARGIN), -1), 1)
    return jnp.stack([g1, g2, g3], 1)


# ----------------------------------------------------------------------------- loss
def soft_terms(q, hand, g):
    """pass2-style terms on a batch (mean): energy proxy (mean squared joint velocity, rad^2/s^2), hand-speed hinge, jolt (jerk-envelope hinge), limit proximity, joint jerk (mean squared 3rd difference, deg^2/s^6)."""
    qd = jnp.diff(q, axis=1) / DT
    j3 = jnp.diff(q, n=3, axis=1) / DT ** 3 * (180 / np.pi)
    return jnp.stack([jnp.mean(qd ** 2), g[0], g[1], g[2], jnp.mean(j3 ** 2)])


def loss_fn(params, mu, feats, tgt, starts, arm, lam, nrm=None, dw=None):
    """feats (B,T,5), tgt (B,T,8), starts (B,) contrastive window starts. -> loss, aux dict."""
    q = rollout(params["pol"], feats)
    hand = fk(q)
    lip = arm >= 2        # arm = LEVEL
    pred = observer(params["obs"], windows(hand), lip)
    dec = jnp.mean((pred[:, T_FROM:] - tgt[:, T_FROM:]) ** 2)
    g = jnp.mean(hinges(q, hand), 0)
    if nrm is not None:           # arm 0: pass2 soft costs, normalised by the untrained policy's values; no hinges, no multipliers
        st = soft_terms(q, hand, g) / nrm
        total = (dec if dw is None else dw * dec) + LAM_SOFT * jnp.sum(st[:4]) + W_JERK_SOFT * st[4]
    else:
        total = (dec if dw is None else dw * dec) + jnp.sum(mu * g)
    aux = {"dec": dec, "g": g, "nce": jnp.zeros(()), "logdet": jnp.zeros(())}
    if arm >= 1:
        sl = lambda x, s, n: jax.lax.dynamic_slice_in_dim(x, s, n, 0)
        mus_in = jax.vmap(lambda f, s: jnp.mean(sl(f, s, WIN_C), 0))(feats, starts)
        mot_in = jax.vmap(lambda h, s: sl(h, s, WIN_C)[::SUB_C].reshape(-1))(hand, starts)
        nce = info_nce(music_emb(params["mus"], mus_in), motion_emb(params["mot"], mot_in))
        total = total + 0.5 * nce
        aux["nce"] = nce
    if arm >= 3:
        ld = logdet_K(posture_embedding(hand))
        total = total - lam * ld
        aux["logdet"] = ld
    return total, aux


# ----------------------------------------------------------------------------- adam, batches
def adam_init(p):
    return {"m": jax.tree_util.tree_map(jnp.zeros_like, p), "v": jax.tree_util.tree_map(jnp.zeros_like, p), "t": 0}


def adam_step(p, g, st, lr=3e-3, clip=1.0, b1=0.9, b2=0.999):
    gn = jnp.sqrt(sum(jnp.sum(x ** 2) for x in jax.tree_util.tree_leaves(g)))
    sc = jnp.minimum(1.0, clip / (gn + 1e-12))
    g = jax.tree_util.tree_map(lambda x: x * sc, g)
    t = st["t"] + 1
    m = jax.tree_util.tree_map(lambda a, b: b1 * a + (1 - b1) * b, st["m"], g)
    v = jax.tree_util.tree_map(lambda a, b: b2 * a + (1 - b2) * b * b, st["v"], g)
    p = jax.tree_util.tree_map(lambda x, a, b: x - lr * (a / (1 - b1 ** t)) / (jnp.sqrt(b / (1 - b2 ** t)) + 1e-8), p, m, v)
    return p, {"m": m, "v": v, "t": t}


def d_hinge_update(mu_d, d_est, eta=ETA_D, target=D_TARGET, falling=False):
    """Rules section 12: g_D = max(0, target - D_est); mu_D <- max(0, mu_D + eta * g_D). -> (mu_D, g_D).
    falling=True (section 13, arm iii+Df): g_D = target - D_est (signed), so mu_D falls while D_est > target; never below 0."""
    g = (target - d_est) if falling else max(0.0, target - d_est)
    return max(0.0, mu_d + eta * g), g


def d_est(params, feats, tgt, lip=True):
    """D exactly as the evaluation (shifted_gap_D, fixed shift seed 0) on a fixed held-in subset (rules section 12)."""
    _, hand = rollout_np(params, feats)
    return shifted_gap_D(observe_np(params, hand, lip), tgt, boot=False)[0]


def nearest_batch(bpm, logg, anchor, B=8):
    d = np.sqrt(((bpm - bpm[anchor]) / 10) ** 2 + ((logg - logg[anchor]) / 0.3) ** 2)
    return np.argsort(d)[:B]       # includes the anchor itself (distance 0)


def soft_norm(params, tr, n=16):
    """pass2 style: each soft term divided by its value for the UNTRAINED policy (first n train songs), floored (SOFT_FLOORS, copied from m3f.FLOORS)."""
    f = jnp.asarray(tr["feats"][:n])
    q = rollout(params["pol"], f); hand = fk(q)
    v = np.asarray(soft_terms(q, hand, jnp.mean(hinges(q, hand), 0)))
    fl = np.array([SOFT_FLOORS[k] for k in ("en", "hand_v", "jolt", "lim", "jerk")])
    return jnp.asarray(np.maximum(v, fl))


def train(arm, seed, epochs, lam=0.0, data=None, log=print, params=None):
    """arm in ARMS. data = dict(train corpus, tgt) -> returns params, history."""
    ai = LEVEL[arm]
    tr = data["train"]; tgt = data["tgt_train"]
    params = init_params(seed) if params is None else params
    st = adam_init(params)
    mu = jnp.ones(3)
    mu_d, dw = 0.0, 1.0
    use_d = arm in ("iii+D", "iii+Df")
    rng = np.random.default_rng(10_000 + seed)
    nrm = soft_norm(params, tr) if arm == "0" else None
    if nrm is not None:
        log(f"soft-cost normalisation (untrained policy): {np.round(np.asarray(nrm), 5).tolist()}")
    gradf = jax.jit(jax.value_and_grad(lambda p, m, f, t, s, l, w: loss_fn(p, m, f, t, s, ai, l, nrm, w if use_d else None), has_aux=True))
    hist = []
    for ep in range(epochs):
        t0 = time.time(); acc = []
        for _ in range(8):
            idx = nearest_batch(tr["bpm"], tr["logg"], int(rng.integers(0, len(tr["bpm"]))))
            starts = jnp.asarray(rng.integers(0, T - WIN_C + 1, len(idx)))
            (l, aux), g = gradf(params, mu, jnp.asarray(tr["feats"][idx]), jnp.asarray(tgt[idx]), starts, lam, dw)
            params, st = adam_step(params, g, st)
            mu = jnp.maximum(0.0, mu + 0.02 * aux["g"])
            acc.append([float(l), float(aux["dec"]), float(aux["nce"]), float(aux["logdet"])] + [float(x) for x in aux["g"]])
        a = np.mean(acc, 0)
        dinfo = {}
        if use_d:
            de = d_est(params, tr["feats"][:D_SONGS], tgt[:D_SONGS])
            mu_d, gd = d_hinge_update(mu_d, de, ETA_D, falling=arm == "iii+Df")
            dw = 1.0 + mu_d
            dinfo = {"d_est": de, "g_D": gd, "mu_D": mu_d}
        hist.append({"epoch": ep, "loss": a[0], "dec": a[1], "nce": a[2], "logdet": a[3], "g": a[4:].tolist(), "mu": [float(x) for x in mu], "sec": time.time() - t0, **dinfo})
        if ep % 10 == 0 or ep == epochs - 1:
            log(f"{arm} s{seed} ep{ep} loss {a[0]:.4f} dec {a[1]:.4f} nce {a[2]:.3f} logdet {a[3]:.2f} g {np.round(a[4:], 4).tolist()} mu {np.round(np.array(mu), 3).tolist()} {('D_est %.3f mu_D %.3f ' % (de, mu_d)) if use_d else ''}{hist[-1]['sec']:.1f}s")
    return params, hist


# ----------------------------------------------------------------------------- evaluation
def rollout_np(params, feats):
    q = jax.jit(rollout)(params["pol"], jnp.asarray(feats))
    return np.asarray(q), np.asarray(fk(q))


def observe_np(params, hand, lip):
    return np.asarray(jax.jit(lambda o, h: observer(o, windows(h), lip))(params["obs"], jnp.asarray(hand)))


def hist2d(hand, n=GRID_N, lim=GRID_LIM):
    """(T,2) -> normalised histogram (n*n,)."""
    c = np.floor((np.clip(hand, -lim + 1e-9, lim - 1e-9) + lim) / (2 * lim / n)).astype(int)
    h = np.bincount(c[:, 0] * n + c[:, 1], minlength=n * n).astype(float)
    return h / h.sum()


def js_div(p, q):
    m = 0.5 * (p + q)
    def kl(a, b):
        k = a > 0
        return np.sum(a[k] * np.log2(a[k] / b[k]))
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def between_song_js(hand):
    H = np.stack([hist2d(h) for h in hand])
    pairs = [js_div(H[i], H[j]) for i in range(len(H)) for j in range(i + 1, len(H))]
    half = [js_div(hist2d(h[:T // 2]), hist2d(h[T // 2:])) for h in hand]
    return float(np.median(pairs)), float(np.median(half))


def mmd_between(hand, bw=0.1, sub=4):
    """RBF-kernel MMD^2 between whole-song hand-position samples (every `sub`-th step); median over song pairs and the half-song control (secondary column)."""
    def k(a, b):
        return np.exp(-((a[:, None] - b[None]) ** 2).sum(-1) / (2 * bw ** 2))
    def mmd(a, b):
        return k(a, a).mean() + k(b, b).mean() - 2 * k(a, b).mean()
    X = hand[:, ::sub]
    pairs = [mmd(X[i], X[j]) for i in range(len(X)) for j in range(i + 1, len(X))]
    half = [mmd(x[:len(x) // 2], x[len(x) // 2:]) for x in X]
    return float(np.median(pairs)), float(np.median(half))


def occupied_cells(hand):
    """Occupied cells on the 24 x 24 grid (any dwell), mean over songs; compare only at equal durations. Also the mean entropy (bits) of the cell distribution."""
    H = [hist2d(h) for h in hand]
    return float(np.mean([(x > 0).sum() for x in H])), float(np.mean([-(x[x > 0] * np.log2(x[x > 0])).sum() for x in H]))


def distinct_postures(hand):
    return float(np.mean([(hist2d(h) >= 0.005).sum() for h in hand]))


def shifted_gap_D(pred, tgt, n_shifts=20, seed=0, boot=True):
    """D = 1 - L_matched / L_shifted over songs (rules section 3); also per-song gaps for a bootstrap."""
    rng = np.random.default_rng(seed)
    S = len(pred)
    lm = np.array([np.mean((pred[s, T_FROM:] - tgt[s, T_FROM:]) ** 2) for s in range(S)])
    ls = np.zeros(S)
    for s in range(S):
        v = []
        for _ in range(n_shifts):
            k = int(rng.integers(SHIFT_MIN, T - SHIFT_MIN + 1))
            v.append(np.mean((pred[s, T_FROM:] - np.roll(tgt[s], k, 0)[T_FROM:]) ** 2))
        ls[s] = np.mean(v)
    D = 1 - lm.mean() / ls.mean()
    if not boot:
        return float(D), None
    boot = [1 - lm[i].mean() / ls[i].mean() for i in (rng.integers(0, S, S) for _ in range(1000))]
    return float(D), [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]


def ridge_probe_D(train_hand, train_tgt, hand, tgt, alpha=1.0):
    """Common probe (secondary): ridge from the hand window to the arm ii-iv target, fit on train; D on held-out."""
    w = lambda h: np.asarray(windows(jnp.asarray(h)))[:, T_FROM::5].reshape(-1, 2 * K_WIN)
    X = w(train_hand); Y = train_tgt[:, T_FROM::5].reshape(-1, 8)
    Xm = np.hstack([X, np.ones((len(X), 1))])
    W = np.linalg.solve(Xm.T @ Xm + alpha * np.eye(Xm.shape[1]), Xm.T @ Y)
    pred = np.stack([np.hstack([np.asarray(windows(jnp.asarray(hand[s:s + 1])))[0], np.ones((T, 1))]) @ W for s in range(len(hand))])
    return shifted_gap_D(pred, tgt)[0]


def clip_features(q, hand):
    """q (T,2), hand (T,2) -> list of feature vectors for five 8 s clips."""
    feats = []
    n = T // 5
    for c in range(5):
        sl = slice(c * n, (c + 1) * n)
        qs = q[sl]; w = np.diff(qs, axis=0) / DT
        feats.append(np.concatenate([hist2d(hand[sl], 12), qs.mean(0), qs.std(0), np.abs(w).mean(0), np.abs(w).std(0)]))
    return feats


def logreg(X, y, C=1.0):
    mu, sd = X.mean(0), X.std(0) + 1e-8
    Xs = (X - mu) / sd
    d = Xs.shape[1]

    def f(wb):
        w, b = wb[:d], wb[d]
        z = Xs @ w + b
        l = np.sum(np.logaddexp(0, z) - y * z) * C + 0.5 * w @ w
        p = 1 / (1 + np.exp(-z))
        gw = C * Xs.T @ (p - y) + w
        return l, np.concatenate([gw, [C * np.sum(p - y)]])
    r = minimize(f, np.zeros(d + 1), jac=True, method="L-BFGS-B")
    return lambda Z: ((Z - mu) / sd) @ r.x[:d] + r.x[d]


def two_afc(q, hand, bpm, n_boot=10_000, seed=0):
    rng = np.random.default_rng(seed)
    F = [clip_features(q[s], hand[s]) for s in range(len(q))]
    accs, accs_sh = [], []
    for i in range(len(q)):
        for j in range(i + 1, len(q)):
            if abs(bpm[i] - bpm[j]) > 5:
                continue
            X = np.array([F[i][0], F[i][1], F[j][0], F[j][1]]); y = np.array([0, 0, 1, 1.0])
            Xt = np.array([F[i][3], F[i][4], F[j][3], F[j][4]]); yt = np.array([0, 0, 1, 1.0])
            f = logreg(X, y)
            accs.append(np.mean((f(Xt) > 0) == yt))
            f2 = logreg(X, rng.permutation(y))
            accs_sh.append(np.mean((f2(Xt) > 0) == yt))
    a = np.array(accs)
    if len(a) == 0:
        return {"n_pairs": 0}
    bs = a[rng.integers(0, len(a), (n_boot, len(a)))].mean(1)
    return {"n_pairs": len(a), "acc": float(a.mean()), "ci": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "shuffled": float(np.mean(accs_sh))}


def evaluate(params, arm, data, which="held"):
    """-> measures dict on the 'held' or 'val' split (rules section 7)."""
    lip = LEVEL[arm] >= 2
    c = data[which]
    q, hand = rollout_np(params, c["feats"])
    pred = observe_np(params, hand, lip)
    js, js_half = between_song_js(hand)
    D, ci = shifted_gap_D(pred, data["tgt_" + which])
    mm, mm_half = mmd_between(hand)
    res = {"mmd_between": mm, "mmd_half": mm_half, "js_between": js, "js_half": js_half, "js_ratio": js / max(js_half, 1e-12), "D": D, "D_ci": ci,
           "occupied_cells": occupied_cells(hand)[0], "cell_entropy_bits": occupied_cells(hand)[1],
           "occupied_cells_half": occupied_cells(np.concatenate([hand[:, :T // 2], hand[:, T // 2:]]))[0], "cell_entropy_bits_half": occupied_cells(np.concatenate([hand[:, :T // 2], hand[:, T // 2:]]))[1],
           "distinct_postures": distinct_postures(hand), "peak_hand_speed": float(np.mean([np.linalg.norm(np.diff(h, axis=0), axis=1).max() / DT for h in hand])),
           "mean_dec_loss": float(np.mean((pred[:, T_FROM:] - data["tgt_" + which][:, T_FROM:]) ** 2))}
    if which == "held":
        res["twoafc"] = two_afc(q, hand, c["bpm"])
        _, trh = rollout_np(params, data["train"]["feats"])
        res["D_common_probe"] = ridge_probe_D(trh, data["tgt_ii_train"], hand, data["tgt_ii_held"])
    return res


def untrained_reference(seed, data, which="held"):
    """Between-song JS and distinct postures of the untrained (initial) policy for this seed: the collapse precondition's denominators."""
    _, hand = rollout_np(init_params(seed), data[which]["feats"])
    return {"js_between": between_song_js(hand)[0], "distinct_postures": distinct_postures(hand), "occupied_cells": occupied_cells(hand)[0], "cell_entropy_bits": occupied_cells(hand)[1]}


def build_data():
    tr, va, he = make_corpus(TRAIN_SEEDS), make_corpus(VAL_SEEDS), make_corpus(HELD_SEEDS)
    st = corpus_stats(tr["tgt"])
    d = {"train": tr, "val": va, "held": he, "stats": st}
    for nm, c in (("train", tr), ("val", va), ("held", he)):
        d["tgt_i_" + nm] = make_targets(c, True, st)
        d["tgt_ii_" + nm] = make_targets(c, False, st)
    return d


def arm_data(d, arm):
    k = "tgt_i_" if arm in ("0", "i") else "tgt_ii_"
    out = dict(d)
    for nm in ("train", "val", "held"):
        out["tgt_" + nm] = d[k + nm]
    out["tgt_train"] = d[k + "train"]
    return out


def run(arm, seed, epochs, lam, out, data=None):
    os.makedirs(out, exist_ok=True)
    d = arm_data(data or build_data(), arm)
    lf = open(os.path.join(out, "log.txt"), "a")
    def log(s):
        print(s, flush=True); lf.write(s + "\n"); lf.flush()
    params, hist = train(arm, seed, epochs, lam, d, log)
    pickle.dump(jax.tree_util.tree_map(np.asarray, params), open(os.path.join(out, "params.pkl"), "wb"))
    res = {"arm": arm, "seed": seed, "lam": lam, "epochs": epochs, "val": evaluate(params, arm, d, "val"), "held": evaluate(params, arm, d, "held"), "untrained": untrained_reference(seed, d), "hist_tail": hist[-5:],
           "d_traj": [{k: h[k] for k in ("epoch", "d_est", "g_D", "mu_D")} for h in hist if "d_est" in h and h["epoch"] % 10 == 0],
           "sec_per_epoch": float(np.mean([h["sec"] for h in hist[1:]] or [hist[0]["sec"]]))}
    json.dump(res, open(os.path.join(out, "result.json"), "w"), indent=1)
    log(json.dumps({k: res["held"][k] for k in ("js_between", "js_half", "D", "occupied_cells")}))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=ARMS + ["iii+D", "iii+Df"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--epochs", type=int, default=1000)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--out")
    ap.add_argument("--smoke", action="store_true")
    a = ap.parse_args()
    if a.smoke:
        data = build_data(); secs = {}
        for arm in ARMS:
            r = run(arm, 0, 2, 0.5 if arm == "iv" else 0.0, f"/secondary/hyst-data/body/s1/smoke_{arm}", data)
            secs[arm] = r["sec_per_epoch"]
        print("sec/epoch", secs)
        per_run = {k: v * 1000 for k, v in secs.items()}
        total = 2 * (per_run["0"] + per_run["i"] + per_run["ii"] + per_run["iii"] + 2 * per_run["iv"])
        print(f"projection 1000 epochs x 12 runs, serial at this thread count: {total / 3600:.1f} h")
    else:
        run(a.arm, a.seed, a.epochs, a.lam, a.out)
