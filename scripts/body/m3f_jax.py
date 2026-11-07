"""M3f block (docs/BRAIN_SPEC.md 7.24): m3e_jax.block_fn with the new body and the four movement changes, each behind its own switch in `cfg`. Provisional servo model
(Feetech STS3215 12 V assumed). m3d_jax.py, m3e_jax.py, make_arm.py are unchanged. With every switch off and body "v1" the computation is m3e_jax.block_fn's, op for op
(tests: test_m3f.Identity).

cfg (static, hashable via `key(cfg)`):
  body      "v1" (M0, no table: the M3e body) or "v2" (make_arm_v2: table plane z = 0 with contact, self-collision).
  obs_lp    movement 2: the observers' descriptors are computed on joint trajectories low-passed at 10 Hz (2nd-order Butterworth, causal, run over the whole 250-sample buffer and
            the last 2.01 s used), and the jerk descriptors are removed from both observers' inputs. External: the 8 jerk (3rd difference mean and p90) entries of joints 0-3
            (indices 4,5,10,11,16,17,22,23) -> 23 inputs. Internal: the same 8 and the roll's 2 jerk entries (31+4, 31+5) -> 27 inputs.
  phase_lp  movement 3: the L3 phase that drives the CPG coupling is the unit vector exp(i phi) low-passed with tau 0.2 s (state in the carry), its angle advanced by atan(om tau)
            (the steady-state lag of a first-order low-pass on a rotating vector), and kappa is multiplied by the block's L3 order parameter R = |(mean cos, mean sin)| of the
            previous block (input "R"; kappa stays learned).
  xfade     movement 4: the generator settings u (4, 5) move linearly from their value at the block start to the new program's over 0.75 s (75 control steps; a block is 50, so
            the ramp is cut at the next block, which starts from the value reached). Also outputs the program total variation per block (the switch cost).
New per-block outputs: q (50, 5) deg per control step, jerk (mean squared 3rd difference, deg^2/s^6, all five joints), hand_v / jolt (mean hinge of the 50 Hz hand speed over 1.2 m/s
and of its change rate over 9 m/s2, the check-csv limits), lim (mean over steps and the three bends of relu(|q| - 100 deg) / 10 deg), tv (0.5 x L1 change of the program weights).
"""
import math

import jax
import jax.numpy as jnp
import mujoco
import numpy as np
from mujoco import mjx
from scipy.signal import butter, lfilter_zi

import arm_sim as A
import m3d_jax as J
import m3e_jax as M
import make_arm_v2 as V2

HAND_MPS, JOLT_MPS2 = 1.2, 9.0                       # body.rs
LIM_DEG = 100.0                                      # 10 deg inside the +-110 deg ranges
XFADE_STEPS = 75                                     # 0.75 s
PHASE_TAU = 0.2
LP_B, LP_A = butter(2, 10.0, fs=100.0)               # 10 Hz at the 100 Hz control rate
LP_ZI = lfilter_zi(LP_B, LP_A)
JERK_E = [4, 5, 10, 11, 16, 17, 22, 23]
JERK_I = JERK_E + [35, 36]
KEEP_E = np.array([i for i in range(J.N_DESC) if i not in JERK_E])
KEEP_I = np.array([i for i in range(M.N_IDESC) if i not in JERK_I])
BENDS = [1, 2, 3]
DEFAULT = dict(body="v1", obs_lp=False, phase_lp=False, xfade=False)


def key(cfg):
    return tuple(sorted(cfg.items()))


def n_desc(cfg):
    return len(KEEP_E) if cfg["obs_lp"] else J.N_DESC


def n_idesc(cfg):
    return len(KEEP_I) if cfg["obs_lp"] else M.N_IDESC


# ---------------------------------------------------------------------------------------------------------------- the two bodies
def _model_v2(iterations=1, condim=3):
    m = mujoco.MjModel.from_xml_string(V2.xml_v2(condim=condim))
    m.opt.iterations = iterations                      # one Newton iteration, as the M3d body (MJX differentiates one solver iteration, not the while_loop)
    return m


MODELS = {"v2": _model_v2(), "v2f": _model_v2(condim=1)}              # v2f: frictionless contacts (cheaper constraint solve)
MX = {k: mjx.put_model(m) for k, m in MODELS.items()}


def arm_init(cfg, q_deg):
    if cfg["body"] == "v1":
        return J.arm_init(q_deg)
    d = mjx.make_data(MODELS[cfg["body"]])
    q = jnp.radians(jnp.asarray(q_deg, float))
    return d.replace(qpos=q, ctrl=q), jnp.asarray(q_deg, float), jnp.zeros(5)


def arm_step(cfg, d, tgt, tv, target_deg):
    """J.arm_step on the chosen body (v1: J.arm_step itself)."""
    if cfg["body"] == "v1":
        return J.arm_step(d, tgt, tv, target_deg)
    goal = jnp.clip(target_deg, J.SLO, J.SHI)
    e = goal - tgt
    v_des = jnp.sign(e) * jnp.minimum(J.LIM_V, jnp.sqrt(2 * J.LIM_A * jnp.abs(e) + 1e-12))
    v_des = jnp.where(jnp.abs(v_des) * J.DT > jnp.abs(e), e / J.DT, v_des)
    tv = jnp.clip(tv + jnp.clip(v_des - tv, -J.LIM_A * J.DT, J.LIM_A * J.DT), -J.LIM_V, J.LIM_V)
    tgt = jnp.clip(tgt + tv * J.DT, J.SLO, J.SHI)
    d = d.replace(ctrl=jnp.radians(tgt))

    def sub(c, _):
        dd, p = c
        dd = mjx.step(MX[cfg["body"]], dd)
        return (dd, p + jnp.abs(dd.actuator_force * dd.qvel).sum()), None
    (d, p), _ = jax.lax.scan(sub, (d, 0.0), None, length=J.SUB)
    return d, tgt, tv, p / J.SUB


# ---------------------------------------------------------------------------------------------------------------- pieces
def lowpass(x):
    """(T, 5) -> (T, 5): the 10 Hz Butterworth (direct form II transposed), started at steady state for x[0]."""
    b, a = jnp.asarray(LP_B), jnp.asarray(LP_A)
    zi = jnp.asarray(LP_ZI)[:, None] * x[0][None]

    def step(z, xt):
        y = b[0] * xt + z[0]
        z0 = b[1] * xt - a[1] * y + z[1]
        z1 = b[2] * xt - a[2] * y
        return jnp.stack([z0, z1]), y
    return jax.lax.scan(step, zi, x)[1]


def phase_filter(z, z_has, raw, om0):
    """Movement 3: low-pass the unit vector of the raw L3 phase (tau 0.2 s), return (z, phase) with the angle advanced by atan(om tau)."""
    e = jnp.stack([jnp.cos(raw), jnp.sin(raw)])
    z = jnp.where(z_has > 0, z, e)
    z = z + (1.0 - math.exp(-J.DT / PHASE_TAU)) * (e - z)
    return z, jnp.arctan2(z[1], z[0]) + jnp.arctan(om0 * PHASE_TAU)


def xfade_u(u_start, u, k):
    """Movement 4: generator settings at control step k (0-based) of a block, 0.75 s linear ramp from u_start to u."""
    return u_start + jnp.minimum((k + 1) / XFADE_STEPS, 1.0) * (u - u_start)


def penalties(full):
    """full (>= 53, 5) deg at 100 Hz, the last 50 rows are the block -> dict jerk (mean squared 3rd difference, deg^2/s^6), hand_v and jolt (mean hinge over the check-csv limits on the
    50 Hz hand trajectory), lim (mean relu(|q| - 100 deg)/10 deg over the three bends and the 50 steps)."""
    j3 = jnp.diff(full[-53:], n=3, axis=0) * 100.0 ** 3
    hp = J.hand_points(full[-51:])[::2]                                     # 26 points at 50 Hz, the last sample of the previous block first
    hv = jnp.sqrt(((hp[1:] - hp[:-1]) ** 2).sum(-1) + 1e-18) * 50.0
    hj = jnp.abs(hv[1:] - hv[:-1]) * 50.0
    return {"jerk": (j3 ** 2).mean(), "hand_v": jax.nn.relu(hv - HAND_MPS).mean(), "jolt": jax.nn.relu(hj - JOLT_MPS2).mean(),
            "lim": (jax.nn.relu(jnp.abs(full[-50:, BENDS]) - LIM_DEG) / (110.0 - LIM_DEG)).mean()}


def init_policy(key_, cfg, hidden=64):
    return M.init_policy(key_, hidden)


def init_carry(cfg, q0, C):
    c = M.init_carry(q0, C)
    d, tgt, tv = arm_init(cfg, q0)
    return {**c, "d": d, "tgt": tgt, "tv": tv, "u_eff": jnp.zeros((4, 5)), "u_has": jnp.asarray(0.0), "pi_prev": jnp.zeros(J.K_PROG), "pi_has": jnp.asarray(0.0),
            "z": jnp.zeros(2), "z_has": jnp.asarray(0.0)}


def make_block_fn(cfg):
    def block_fn(C, P, mode, tau, carry, inp):
        if "cb_reset" in inp:
            carry = {**carry, "cb": {**carry["cb"], "h": carry["cb"]["h"] * (1.0 - inp["cb_reset"])}}
        xin = jnp.concatenate([inp["x"], carry["feat"] * C.get("loop_gate", 1.0)])
        logits, amod, kappa = J.motor_cortex(P, xin)
        pi = J.program_weights(logits, inp["g"], tau, mode)
        u = jnp.clip(pi @ jax.nn.sigmoid(P["theta"]) + J.MOD * jnp.tanh(amod), 0, 1).reshape(4, 5)
        if cfg["phase_lp"]:
            kappa = kappa * inp["R"]
        u_start = jnp.where(carry["u_has"] > 0, carry["u_eff"], u)
        goal0 = J.to_command(u)

        @jax.checkpoint
        def step(c, k):
            d, tgt, tv, cs, cbs, snap, obs_prev, pred1, lv1, z, z_has = c
            raw = inp["phi0"] + inp["om0"] * J.DT * (k + 1)
            if cfg["phase_lp"]:
                z, phi = phase_filter(z, z_has, raw, inp["om0"])
                z_has = jnp.asarray(1.0)
            else:
                phi = raw
            if cfg["xfade"]:
                ue = xfade_u(u_start, u, k)
                goal = J.to_command(ue)
            else:
                ue, goal = u, goal0
            cs, t = J.cpg_step(cs, goal, phi, kappa)
            obs = snap
            cbs, mean, lv = M.cb_step(C, cbs, jax.lax.stop_gradient(obs), jax.lax.stop_gradient(t))
            err = (obs - obs_prev) / C["dsd"][0] - pred1
            e10 = err[:10]
            nll = (0.5 * (lv1[:10] + e10 ** 2 / jnp.exp(lv1[:10]) + math.log(2 * math.pi))).mean()
            d, tgt, tv, p = arm_step(cfg, d, tgt, tv, t)
            new_snap = M.snap_of(d)
            pose = obs[:5] + mean[2, :5] * C["dsd"][2, :5]
            return (d, tgt, tv, cs, cbs, new_snap, obs, mean[0], lv[0], z, z_has), (jnp.degrees(d.qpos), jnp.degrees(d.qvel), p, obs, pose, err, (e10 ** 2).mean(), nll, ue)

        cin = (carry["d"], carry["tgt"], carry["tv"], carry["cs"], carry["cb"], carry["snap"], carry["obs_prev"], carry["pred1"], carry["lv1"], carry["z"], carry["z_has"])
        (d, tgt, tv, cs, cbs, snap, obs_prev, pred1, lv1, z, z_has), (q, qd, p, obs, pose, err, cb_sq, cb_nll, ues) = jax.lax.scan(step, cin, jnp.arange(J.BLOCK))
        full = jnp.concatenate([carry["buf"], q])
        pfull = jnp.concatenate([carry["pbuf"], obs[:, :5]])
        if cfg["obs_lp"]:
            fq, fp = lowpass(full), lowpass(pfull)
        else:
            fq, fp = full, pfull
        frames = J.window_frames(fp[-201:])
        desc = J.descriptors(J.window_frames(fq[-201:]))
        idesc = jnp.concatenate([J.descriptors(frames), M.roll_feats(frames[:, 4])])
        if cfg["obs_lp"]:
            desc, idesc = desc[KEEP_E], idesc[KEEP_I]
        prop = (obs[-1, :10] - C["omu"][:10]) / C["osd"][:10]
        pose_s = jax.lax.stop_gradient((pose[-1] - C["omu"][:5]) / C["osd"][:5])
        feat = jnp.clip(jnp.concatenate([prop, pose_s, jax.lax.stop_gradient(err[-1, :10])]), -8, 8)
        # penalties and cost terms (computed always; the loss decides which to use)
        pen = penalties(full)
        tv_pi = 0.5 * jnp.abs(pi - carry["pi_prev"]).sum() * carry["pi_has"]
        out = {"desc": desc, "idesc": idesc, "logits": logits, "pi": pi, "kappa": kappa, "ms": (qd ** 2).mean(0), "energy": p.sum() * J.DT, "xin": xin, "feat": feat,
               "cb_sq": cb_sq.mean(), "cb_nll": cb_nll.mean(), "q": q, **pen, "tv": tv_pi}
        new = {"d": d, "tgt": tgt, "tv": tv, "cs": cs, "buf": full[-200:], "cb": cbs, "snap": snap, "pbuf": pfull[-200:], "obs_prev": obs_prev, "pred1": pred1, "lv1": lv1, "feat": feat,
               "u_eff": ues[-1], "u_has": jnp.asarray(1.0), "pi_prev": pi, "pi_has": jnp.asarray(1.0), "z": z, "z_has": z_has}
        return new, out
    return block_fn


def make_chunk(cfg):
    bf = make_block_fn(cfg)

    def chunk(C, P, mode, tau, carry, inps):
        def one(c, i):
            return jax.lax.scan(lambda cc, ii: bf(C, P, mode, tau, cc, ii), c, i)
        return jax.vmap(one)(carry, inps)
    return chunk
