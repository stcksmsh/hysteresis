"""Stage 3 loss (docs/STAGE3_RULES_TRAIN.md section 2): per chunk of 8 blocks,
    dec_ext + dec_int (both streams, Lipschitz observers, D-scaled per stream) + 0.5 InfoNCE + sum_k mu_k g_k (seven limit hinges) + W_SWITCH x tv."""
import math

import jax
import jax.numpy as jnp
import numpy as np

import m3d_jax as J
import m3f_jax as F
import s3_obs as O

W_NCE, TEMP, W_SWITCH = 0.5, 0.1, 0.01
HAND_V, JOLT, ACC, FLOOR = 1.2, 9.0, 4.8, 0.05
N_G = 7
G_NAMES = ["energy", "jerk", "hand_v", "jolt", "acc", "floor", "lim"]
MOT_IN, MUS_IN, EMB = 120, 34, 32


def init_enc(key):
    k = jax.random.split(key, 4)
    d = lambda kk, a, b: jax.random.normal(kk, (a, b)) / math.sqrt(a)
    return {"mot": {"W1": d(k[0], MOT_IN, 64), "b1": jnp.zeros(64), "W2": d(k[1], 64, EMB), "b2": jnp.zeros(EMB)},
            "mus": {"W1": d(k[2], MUS_IN, 32), "b1": jnp.zeros(32), "W2": d(k[3], 32, EMB), "b2": jnp.zeros(EMB)}}


def embed(e, x):
    h = jnp.tanh(x @ e["W1"] + e["b1"]) @ e["W2"] + e["b2"]
    return h / (jnp.linalg.norm(h, axis=-1, keepdims=True) + 1e-8)


def info_nce(a, b, temp=TEMP):
    """a, b (B, D) L2-normalised, positives on the diagonal; symmetric."""
    s = a @ b.T / temp
    lab = jnp.arange(a.shape[0])
    return 0.5 * (-jnp.mean(jax.nn.log_softmax(s, 1)[lab, lab]) - jnp.mean(jax.nn.log_softmax(s.T, 1)[lab, lab]))


def hand_inputs(q):
    """q (E, nb, 50, 5) deg -> (E, nb * 5 * 3) metres: the hand position at 10 Hz (every 10th control step) over the chunk."""
    E, nb = q.shape[:2]
    sub = q.reshape(E, nb * 50, 5)[:, 9::10]
    return jax.vmap(J.hand_points)(sub).reshape(E, -1)


def music_inputs(tgt):
    """tgt (E, nb, 17) -> (E, 34): mean and sd over the chunk's blocks."""
    return jnp.concatenate([tgt.mean(1), tgt.std(1)], -1)


def limit_g(o, valid, thr):
    n = jnp.maximum(valid.sum(), 1.0)
    mean = lambda x: (x * valid).sum() / n
    return jnp.stack([mean(jax.nn.relu(o["energy"] / thr["energy"] - 1.0)), mean(jax.nn.relu(o["jerk"] / thr["jerk"] - 1.0)), mean(o["hand_v"]) / HAND_V, mean(o["jolt"]) / JOLT,
                      mean(o["acc"]) / ACC, mean(o["floor"]) / FLOOR, mean(o["lim"])])


def make_fns(C, cfg):
    chunk = F.make_chunk(cfg)

    def loss_fn(Q, Oe, Oi, carry, inps, tgt, valid, tau, mu, dw, dmu, dsd, imu, isd, thr, c0, nce_on):
        Oe, Oi = jax.lax.stop_gradient(Oe), jax.lax.stop_gradient(Oi)
        buf = carry["buf"]
        carry, o = chunk(C, Q["P"], "train", tau, carry, inps)
        n = jnp.maximum(valid.sum(), 1.0)
        mean = lambda x: (x * valid).sum() / n
        xe = O.ext_features_chunk(buf, o["q"], c0)
        xi = jnp.clip((o["idesc"] - imu) / isd, -8, 8)
        pe, pi_ = O.lip_apply(Oe, xe), O.lip_apply(Oi, xi)
        se, si = (pe - tgt) ** 2, (pi_ - tgt) ** 2
        stream = lambda s: ((1.0 + dw[0]) * mean(s[..., :4].mean(-1))) + ((1.0 + dw[1]) * mean(s[..., 4:].mean(-1)))
        dec_e, dec_i = stream(se), stream(si)
        nce = info_nce(embed(Q["enc"]["mus"], music_inputs(tgt)), embed(Q["enc"]["mot"], hand_inputs(o["q"]))) * nce_on
        g = limit_g(o, valid, thr)
        loss = dec_e + dec_i + W_NCE * nce + (mu * g).sum() + W_SWITCH * mean(o["tv"])
        aux = {"dec_e": dec_e, "dec_i": dec_i, "nce": nce, "g": g, "de": se.mean(-1), "xin": o["xin"], "desc": o["desc"], "idesc": o["idesc"], "q": o["q"], "ms": o["ms"], "pi": o["pi"],
               "kappa": o["kappa"], "tv": mean(o["tv"]), "fast_e": mean(se[..., :4].mean(-1)), "slow_e": mean(se[..., 4:].mean(-1))}
        return loss, (carry, aux)

    hard = {m: jax.jit(lambda P, carry, inps, m=m: chunk(C, P, m, 0.0, carry, inps)) for m in ("argmax", "sample")}
    return {"loss": jax.jit(jax.value_and_grad(loss_fn, has_aux=True)), "hard": hard}
