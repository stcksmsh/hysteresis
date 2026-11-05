"""M3d, the differentiable body in JAX (docs/BRAIN_SPEC.md 7.16 point 2): spinal generators with the L3 phase coupling, the M0 arm in MJX, the
body-study descriptors (roll excluded). Float64 throughout (x64): the descriptors' third differences amplify float32 rounding. Provisional servo model
(Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25). Ports: cpg.CPG (+ the kappa term of tm3c.CPGK), arm_sim.ArmSim.step,
bdesc.descriptors (itself a port of Rust body.rs). Two deliberate differences from the numpy side, both for differentiability: sqrt(x + 1e-12) where a sqrt of a
possibly-zero value is differentiated, and the observer reads the true joint positions (the numpy ArmSim's proprioception quantises them to the encoder step).
"""
import math

import jax

jax.config.update("jax_enable_x64", True)
import jax.numpy as jnp  # noqa: E402
import mujoco  # noqa: E402
import numpy as np  # noqa: E402
from mujoco import mjx  # noqa: E402

import arm_sim as A  # noqa: E402
import bdesc  # noqa: E402
import cpg  # noqa: E402
import make_arm as MA  # noqa: E402

DT = 0.01
SUB = A.SUBSTEPS
BLOCK = 50                                           # control steps per 0.5 s
N_DESC = bdesc.N_DESC
MODEL = mujoco.MjModel.from_xml_string(MA.final_xml())
MODEL.opt.iterations = 1                              # one Newton iteration: MJX differentiates a single solver iteration, not its while_loop (limits at +-110 deg are active only at the clip)
MX = mjx.put_model(MODEL)
V, ACC = jnp.array(cpg.V), jnp.array(cpg.A)
CLO, CHI, BEND = jnp.array(cpg.LO), jnp.array(cpg.HI), jnp.array(cpg.BEND)
SLO, SHI = jnp.array(A.LO), jnp.array(A.HI)         # servo target range (inf for the continuous joints)
LIM_V, LIM_A = jnp.array(A.LIM_V), jnp.array(A.LIM_A)
AXES = np.array(MA.AXES, float)
LINKS = np.array(MA.LINKS, float)
KAPPA_MAX = 2 * math.pi


# ---------------------------------------------------------------------------------------------------------------- spinal generators
def cpg_init(centre):
    z = jnp.zeros(5)
    return {"phase": z, "freq": jnp.full(5, 0.5), "lag": z, "amp": z, "centre": jnp.asarray(centre, float)}


def to_command(u):
    """u (4, 5) in [0, 1] -> goal dict (babble.to_command)."""
    centre = CLO + u[2] * (CHI - CLO)
    a_max = jnp.where(BEND, CHI - jnp.abs(centre), cpg.AMP_CAP_CONTINUOUS)
    return {"freq": cpg.F_MIN + u[0] * (cpg.F_MAX - cpg.F_MIN), "amp": u[1] * a_max, "centre": centre, "lag": u[3] * cpg.LAG_MAX}


def _slew(cur, goal, rate):
    return cur + jnp.clip(goal - cur, -rate * DT, rate * DT)


def cpg_step(s, goal, phi, kappa):
    """One control period -> (new state, target (5,) deg). phase += dt*kappa*sin(phi - phase) first (tm3c.CPGK); kappa = 0 adds exactly 0.0 (== cpg.CPG)."""
    phase = s["phase"] + DT * kappa * jnp.sin(phi - s["phase"])
    freq, lag = _slew(s["freq"], goal["freq"], 2.0), _slew(s["lag"], goal["lag"], 0.25)
    centre, amp_raw = _slew(s["centre"], goal["centre"], 0.1 * V), _slew(s["amp"], goal["amp"], 0.1 * V)
    amp = jnp.maximum(jnp.where(BEND, jnp.minimum(amp_raw, CHI - jnp.abs(centre)), amp_raw), 0.0)
    w = 2 * math.pi * (1 + cpg.COUPLING)
    am = jnp.maximum(amp, 1e-9)
    f = jnp.minimum(freq, jnp.minimum(0.8 * V / am / w, jnp.sqrt(cpg.ACC_SHARE * ACC / am) / w))
    lead = phase[:-1] - 2 * math.pi * lag[1:]
    pull = jnp.concatenate([jnp.zeros(1), jnp.sin(lead - phase[1:])])
    phase = phase + DT * 2 * math.pi * f * (1 + cpg.COUPLING * pull)
    return {"phase": phase, "freq": freq, "lag": lag, "amp": amp_raw, "centre": centre}, centre + amp * jnp.cos(phase)


# ---------------------------------------------------------------------------------------------------------------- arm
def arm_init(q_deg):
    d = mjx.make_data(MODEL)
    q = jnp.radians(jnp.asarray(q_deg, float))
    return d.replace(qpos=q, ctrl=q), jnp.asarray(q_deg, float), jnp.zeros(5)


def arm_step(d, tgt, tv, target_deg):
    """One 10 ms control step (arm_sim.ArmSim.step) -> (d, tgt, tv, power W)."""
    goal = jnp.clip(target_deg, SLO, SHI)
    e = goal - tgt
    v_des = jnp.sign(e) * jnp.minimum(LIM_V, jnp.sqrt(2 * LIM_A * jnp.abs(e) + 1e-12))
    v_des = jnp.where(jnp.abs(v_des) * DT > jnp.abs(e), e / DT, v_des)
    tv = jnp.clip(tv + jnp.clip(v_des - tv, -LIM_A * DT, LIM_A * DT), -LIM_V, LIM_V)
    tgt = jnp.clip(tgt + tv * DT, SLO, SHI)
    d = d.replace(ctrl=jnp.radians(tgt))

    def sub(c, _):
        dd, p = c
        dd = mjx.step(MX, dd)
        return (dd, p + jnp.abs(dd.actuator_force * dd.qvel).sum()), None
    (d, p), _ = jax.lax.scan(sub, (d, 0.0), None, length=SUB)
    return d, tgt, tv, p / SUB


# ---------------------------------------------------------------------------------------------------------------- descriptors (31, roll excluded)
FPS = bdesc.FPS


def _rot(axis, deg):
    K = jnp.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    th = jnp.radians(deg)[:, None, None]
    return jnp.eye(3) + jnp.sin(th) * K + (1 - jnp.cos(th)) * (K @ K)


def hand_points(q):
    B = jnp.broadcast_to(jnp.eye(3), (q.shape[0], 3, 3))
    p = jnp.zeros((q.shape[0], 3))
    for j in range(5):
        B = B @ _rot(AXES[j], q[:, j])
        p = p + B @ LINKS[j]
    return p


def _p90(v):
    return jnp.sort(v)[int(math.floor((len(v) - 1) * 0.9 + 0.5))]


def _norm(v):
    sd = v.std()
    return jnp.where(sd > 1e-12, (v - v.mean()) / jnp.where(sd > 1e-12, sd, 1.0), 0.0)


def _best_lag(a, b):
    a, b = _norm(a), _norm(b)
    m = int(0.5 * FPS)
    cs = []
    for l in range(-m, m + 1):
        i0, i1 = max(0, -l), min(len(a), len(b) - l)
        cs.append(jnp.dot(a[i0:i1], b[i0 + l:i1 + l]) / (i1 - i0))
    c = jnp.stack(cs)
    return (2 * m - jnp.argmax(c[::-1]) - m) / FPS          # ties go to the last lag, as Rust's max_by; the lag itself carries no gradient


def descriptors(q, max_lag_s=1.0):
    """(T, 5) deg at 60 fps -> (31,) (bdesc.descriptors)."""
    out, speeds = [], []
    for j in range(4):
        s = q[:, j]
        d1 = jnp.abs(jnp.diff(s)) * FPS
        d2 = jnp.abs(s[2:] - 2 * s[1:-1] + s[:-2]) * FPS ** 2
        d3 = jnp.abs(s[3:] - 3 * s[2:-1] + 3 * s[1:-2] - s[:-3]) * FPS ** 3
        for d in (d1, d2, d3):
            out += [d.mean(), _p90(d)]
        speeds.append(d1)
    h = hand_points(q)
    out.append(h[:, 2].mean())
    out.append(jnp.mean(jnp.sqrt(h[:, 0] ** 2 + h[:, 1] ** 2 + (h[:, 2] - bdesc.SHOULDER_Z) ** 2 + 1e-12)) / bdesc.REACH_M)
    out.append(jnp.mean(jnp.abs(q[:, 2]) + jnp.abs(q[:, 3])))
    out += [_best_lag(speeds[a], speeds[b]) for a, b in ((0, 1), (1, 2), (2, 3))]
    hs = jnp.sqrt((jnp.diff(h, axis=0) ** 2).sum(1) + 1e-18) * FPS
    m = hs.mean()
    var = ((hs - m) ** 2).sum()
    per = []
    for l in range(int(0.3 * FPS), int(max_lag_s * FPS) + 1):
        per.append(jnp.where(var < 1e-12, 0.0, ((hs[:len(hs) - l] - m) * (hs[l:] - m)).sum() / jnp.where(var < 1e-12, 1.0, var)))
    out.append(jnp.max(jnp.stack(per)))
    return jnp.stack(out)


_T = np.arange(121) / FPS * 100.0
_I0 = np.minimum(_T.astype(int), 199)
_W = jnp.array((_T - _I0)[:, None])


def window_frames(pos100):
    """(201, 5) positions at 100 Hz covering 2.00 s -> (121, 5) at 60 fps (bdesc.window_frames)."""
    return pos100[_I0] * (1 - _W) + pos100[_I0 + 1] * _W


# ---------------------------------------------------------------------------------------------------------------- policy pieces
K_PROG = 8
MOD = 0.2
D_IN = 16
D_OUT = K_PROG + 20 + 5


def init_policy(key, hidden=64):
    k1, k2, k3 = jax.random.split(key, 3)
    import babble
    u0 = np.clip(np.stack([babble.ou_commands(np.random.default_rng(1234 + i), 1)[0] for i in range(K_PROG)]), 0.02, 0.98)       # the 8 programs of T-M3
    b2 = jnp.zeros(D_OUT).at[28:].set(-3.0)                       # kappa starts near 0 (sigmoid(-3) = 0.047) but not dead
    return {"w1": jax.random.normal(k1, (D_IN, hidden)) / math.sqrt(D_IN), "b1": jnp.zeros(hidden),
            "w2": 0.1 * jax.random.normal(k2, (hidden, D_OUT)) / math.sqrt(hidden), "b2": b2,
            "theta": jnp.asarray(np.log(u0 / (1 - u0)).reshape(K_PROG, 20))}


def motor_cortex(P, x):
    h = jnp.tanh(x @ P["w1"] + P["b1"])
    o = h @ P["w2"] + P["b2"]
    kappa = P["kappa_fix"] if "kappa_fix" in P else KAPPA_MAX * jax.nn.sigmoid(o[K_PROG + 20:])     # "kappa_fix" (5,) rad/s: report-only control override (WO7)
    return o[:K_PROG], o[K_PROG:K_PROG + 20], kappa


def gumbel_softmax(logits, g, tau, hard=False):
    """Soft sample softmax((logits + g) / tau); hard=True is the straight-through one-hot of the same sample (forward one-hot, soft gradient)."""
    soft = jax.nn.softmax((logits + g) / tau)
    if not hard:
        return soft
    one = jax.nn.one_hot(jnp.argmax(logits + g), logits.shape[-1])
    return one + soft - jax.lax.stop_gradient(soft)


def program_weights(logits, g, tau, mode):
    """mode 'train': soft Gumbel-softmax at temperature tau; 'sample': hard one-hot of the Gumbel-max sample; 'argmax': hard one-hot of the logits."""
    if mode == "train":
        return gumbel_softmax(logits, g, tau)
    if mode == "sample":
        return jax.nn.one_hot(jnp.argmax(logits + g), K_PROG)
    return jax.nn.one_hot(jnp.argmax(logits), K_PROG)


def observer_apply(O, x):
    for i, (W_, b_) in enumerate(O):
        x = x @ W_ + b_
        if i < len(O) - 1:
            x = jnp.tanh(x)
    return x


def init_observer(key, hidden=64, n_out=8):
    sizes = [N_DESC, hidden, hidden, n_out]
    ks = jax.random.split(key, len(sizes) - 1)
    return [(jax.random.normal(k, (a, b)) / math.sqrt(a), jnp.zeros(b)) for k, a, b in zip(ks, sizes[:-1], sizes[1:])]


# ---------------------------------------------------------------------------------------------------------------- rollout
def block_fn(P, mode, tau, carry, inp):
    """One 0.5 s block of one episode. carry: dict(d, tgt, tv, cs, buf (200, 5) deg). inp: dict(x (16), phi0, om0, g (8)).
    -> carry, out dict(window frames' descriptors raw (31), logits, pi, kappa, ms (5) mean square joint speed deg^2/s^2, energy J)."""
    logits, amod, kappa = motor_cortex(P, inp["x"])
    pi = program_weights(logits, inp["g"], tau, mode)
    u = jnp.clip(pi @ jax.nn.sigmoid(P["theta"]) + MOD * jnp.tanh(amod), 0, 1).reshape(4, 5)
    goal = to_command(u)

    @jax.checkpoint
    def step(c, k):
        d, tgt, tv, cs = c
        cs, t = cpg_step(cs, goal, inp["phi0"] + inp["om0"] * DT * (k + 1), kappa)
        d, tgt, tv, p = arm_step(d, tgt, tv, t)
        return (d, tgt, tv, cs), (jnp.degrees(d.qpos), jnp.degrees(d.qvel), p)

    (d, tgt, tv, cs), (q, qd, p) = jax.lax.scan(step, (carry["d"], carry["tgt"], carry["tv"], carry["cs"]), jnp.arange(BLOCK))
    full = jnp.concatenate([carry["buf"], q])
    desc = descriptors(window_frames(full[-201:]))
    out = {"desc": desc, "logits": logits, "pi": pi, "kappa": kappa, "ms": (qd ** 2).mean(0), "energy": p.sum() * DT}
    return {"d": d, "tgt": tgt, "tv": tv, "cs": cs, "buf": full[-200:]}, out


def init_carry(q0):
    d, tgt, tv = arm_init(q0)
    return {"d": d, "tgt": tgt, "tv": tv, "cs": cpg_init(q0), "buf": jnp.broadcast_to(jnp.asarray(q0, float), (200, 5))}


def chunk(P, mode, tau, carry, inps):
    """E episodes, nb blocks. carry batched over E; inps leaves (E, nb, ...). -> carry, outs leaves (E, nb, ...)."""
    def one(c, i):
        return jax.lax.scan(lambda cc, ii: block_fn(P, mode, tau, cc, ii), c, i)
    c, o = jax.vmap(one)(carry, inps)
    return c, jax.tree_util.tree_map(lambda x: x, o)


def adam_init(P):
    z = jax.tree_util.tree_map(jnp.zeros_like, P)
    return {"m": z, "v": z, "t": 0}


def adam_step(P, g, st, lr, clip=1.0, wd=0.0, b1=0.9, b2=0.999):
    leaves = jax.tree_util.tree_leaves(g)
    gn = jnp.sqrt(sum((x ** 2).sum() for x in leaves))
    sc = jnp.minimum(1.0, clip / (gn + 1e-12))
    g = jax.tree_util.tree_map(lambda x: x * sc, g)
    t = st["t"] + 1
    m = jax.tree_util.tree_map(lambda a, b: b1 * a + (1 - b1) * b, st["m"], g)
    v = jax.tree_util.tree_map(lambda a, b: b2 * a + (1 - b2) * b * b, st["v"], g)
    P = jax.tree_util.tree_map(lambda p, mm, vv: p - lr * ((mm / (1 - b1 ** t)) / (jnp.sqrt(vv / (1 - b2 ** t)) + 1e-8) + wd * p), P, m, v)
    return P, {"m": m, "v": v, "t": t}, gn
