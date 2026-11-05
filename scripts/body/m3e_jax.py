"""M3e, the closed-loop block of M3d (docs/BRAIN_SPEC.md 7.19 part B1). Builds on m3d_jax.py (unchanged); new behaviour lives here. Provisional servo model
(Feetech STS3215 12 V assumed).

Per control step (100 Hz) the loop now also carries a bus-servo proprioception snapshot (what ArmSim returns: position quantised to the encoder step, velocity, load,
of the PREVIOUS step = 10 ms delay) and the frozen K1 round-2 cerebellum (GRU 256, ported from cerebellum.py; run continuously, state in the carry; its inputs are
stop-gradient: it is a frozen sensor, no gradient is propagated through it). At the end of each 0.5 s block the motor cortex's NEXT input gets 25 numbers:
  prop (10)  quantised delayed joint positions and velocities of all five joints (roll included), standardised with the cerebellum's training statistics;
  pose (5)   the cerebellum's predicted pose 100 ms ahead (absolute position, same standardisation);
  err  (10)  its prediction error: realised proprioception change over the last step minus its +10 ms prediction made one step earlier, in units of the training
             SD of that change (positions and velocities).
All clipped to +-8. The 25 new input weights of the cortex start at zero (the closed loop is off until learned).
Position quantisation passes the gradient straight through (round() has none): q + stop_gradient(round(q / step) * step - q).
Internal descriptors (self-observer input): the 31 body-study descriptors of the quantised delayed positions plus the roll joint's 6 numbers (mean and p90 of the
absolute 1st, 2nd and 3rd differences) = 37.
"""
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import arm_sim as A
import m3d_jax as J

CB_NPZ = Path("/secondary/hyst-data/body/m3e/cb_r2.npz")
N_CB = 25
D_IN = J.D_IN + N_CB                  # 41
N_IDESC = J.N_DESC + 6                # 37
QUANT = A.QUANT_DEG
EFF = 10
HID = 256


def load_cb(path=CB_NPZ):
    z = np.load(path)
    return {k: jnp.asarray(z[k]) for k in z.files}


def cb_init(t0):
    """Cerebellum state: hidden (256), ring of the last 10 raw targets, most recent first (before any step, all equal to t0 as cerebellum.features pads)."""
    return {"h": jnp.zeros(HID), "ring": jnp.broadcast_to(jnp.asarray(t0, float), (EFF, 5))}


def cb_step(C, s, obs, t):
    """One step of the ported cerebellum. obs (15) raw, t (5) raw servo target. -> new state, mean (3, 15) and logvar (3, 15) (standardised change units)."""
    o = (obs - C["omu"]) / C["osd"]
    tt = (t - C["tmu"]) / C["tsd"]
    eff = ((s["ring"] - C["tmu"]) / C["tsd"]).reshape(-1)               # tgt_{k-1}, tgt_{k-2}, ... tgt_{k-10}
    x = jnp.concatenate([o, tt, eff])
    a = jnp.tanh(C["inp_weight"] @ x + C["inp_bias"])
    gi = C["rnn_weight_ih_l0"] @ a + C["rnn_bias_ih_l0"]
    gh = C["rnn_weight_hh_l0"] @ s["h"] + C["rnn_bias_hh_l0"]
    r = jax.nn.sigmoid(gi[:HID] + gh[:HID])
    z = jax.nn.sigmoid(gi[HID:2 * HID] + gh[HID:2 * HID])
    n = jnp.tanh(gi[2 * HID:] + r * gh[2 * HID:])
    h = (1 - z) * n + z * s["h"]
    out = (C["head_weight"] @ h + C["head_bias"] + C["skip_weight"] @ x + C["skip_bias"]).reshape(3, 15, 2)
    return {"h": h, "ring": jnp.concatenate([t[None], s["ring"][:-1]])}, out[..., 0], jnp.clip(out[..., 1], -8, 4)


def quantise_st(q):
    return q + jax.lax.stop_gradient(jnp.round(q / QUANT) * QUANT - q)


def snap_of(d):
    """The proprioception a bus servo reports after this step (before the one-step delay is applied by the carry)."""
    q = jnp.degrees(d.qpos)
    return jnp.concatenate([quantise_st(q), jnp.degrees(d.qvel), d.actuator_force])


def roll_feats(q):
    """(T,) roll angle at 60 fps -> mean and p90 of |d1|, |d2|, |d3| (6)."""
    s = q
    d1 = jnp.abs(jnp.diff(s)) * J.FPS
    d2 = jnp.abs(s[2:] - 2 * s[1:-1] + s[:-2]) * J.FPS ** 2
    d3 = jnp.abs(s[3:] - 3 * s[2:-1] + 3 * s[1:-2] - s[:-3]) * J.FPS ** 3
    return jnp.stack([f(d) for d in (d1, d2, d3) for f in (jnp.mean, J._p90)])


def init_policy(key, hidden=64):
    """M3d's policy with 25 zero rows appended to the cortex's input weights."""
    P = J.init_policy(key, hidden)
    return {**P, "w1": jnp.concatenate([P["w1"], jnp.zeros((N_CB, hidden))])}


def init_carry(q0, C):
    c = J.init_carry(q0)
    q0 = jnp.asarray(q0, float)
    snap = jnp.concatenate([jnp.round(q0 / QUANT) * QUANT, jnp.zeros(10)])
    return {**c, "cb": cb_init(q0), "snap": snap, "pbuf": jnp.broadcast_to(snap[:5], (200, 5)), "obs_prev": snap, "pred1": jnp.zeros(15), "feat": jnp.zeros(N_CB)}


def block_fn(C, P, mode, tau, carry, inp):
    """One 0.5 s block of one episode, closed loop. inp: x (16), phi0, om0, g (8). -> carry, out (as J.block_fn plus idesc (37), xin (41), feat (25))."""
    xin = jnp.concatenate([inp["x"], carry["feat"]])
    logits, amod, kappa = J.motor_cortex(P, xin)
    pi = J.program_weights(logits, inp["g"], tau, mode)
    u = jnp.clip(pi @ jax.nn.sigmoid(P["theta"]) + J.MOD * jnp.tanh(amod), 0, 1).reshape(4, 5)
    goal = J.to_command(u)

    @jax.checkpoint
    def step(c, k):
        d, tgt, tv, cs, cbs, snap, obs_prev, pred1 = c
        cs, t = J.cpg_step(cs, goal, inp["phi0"] + inp["om0"] * J.DT * (k + 1), kappa)
        obs = snap                                                                     # what the bus reports at this step: the previous step's state
        cbs, mean, _ = cb_step(C, cbs, jax.lax.stop_gradient(obs), jax.lax.stop_gradient(t))
        err = (obs - obs_prev) / C["dsd"][0] - pred1                                    # realised change over the last step minus the +10 ms prediction made then
        d, tgt, tv, p = J.arm_step(d, tgt, tv, t)
        new_snap = snap_of(d)
        pose = obs[:5] + mean[2, :5] * C["dsd"][2, :5]                                  # predicted position 100 ms ahead
        return (d, tgt, tv, cs, cbs, new_snap, obs, mean[0]), (jnp.degrees(d.qpos), jnp.degrees(d.qvel), p, obs, pose, err)

    cin = (carry["d"], carry["tgt"], carry["tv"], carry["cs"], carry["cb"], carry["snap"], carry["obs_prev"], carry["pred1"])
    (d, tgt, tv, cs, cbs, snap, obs_prev, pred1), (q, qd, p, obs, pose, err) = jax.lax.scan(step, cin, jnp.arange(J.BLOCK))
    full = jnp.concatenate([carry["buf"], q])
    pfull = jnp.concatenate([carry["pbuf"], obs[:, :5]])                               # quantised delayed positions, 100 Hz
    frames = J.window_frames(pfull[-201:])
    desc = J.descriptors(J.window_frames(full[-201:]))
    idesc = jnp.concatenate([J.descriptors(frames), roll_feats(frames[:, 4])])
    prop = (obs[-1, :10] - C["omu"][:10]) / C["osd"][:10]
    pose_s = jax.lax.stop_gradient((pose[-1] - C["omu"][:5]) / C["osd"][:5])
    feat = jnp.clip(jnp.concatenate([prop, pose_s, jax.lax.stop_gradient(err[-1, :10])]), -8, 8)
    out = {"desc": desc, "idesc": idesc, "logits": logits, "pi": pi, "kappa": kappa, "ms": (qd ** 2).mean(0), "energy": p.sum() * J.DT, "xin": xin, "feat": feat}
    return {"d": d, "tgt": tgt, "tv": tv, "cs": cs, "buf": full[-200:], "cb": cbs, "snap": snap, "pbuf": pfull[-200:], "obs_prev": obs_prev, "pred1": pred1, "feat": feat}, out


def chunk(C, P, mode, tau, carry, inps):
    """E episodes, nb blocks. carry batched over E; inps leaves (E, nb, ...)."""
    def one(c, i):
        return jax.lax.scan(lambda cc, ii: block_fn(C, P, mode, tau, cc, ii), c, i)
    return jax.vmap(one)(carry, inps)
