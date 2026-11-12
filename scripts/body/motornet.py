"""WO29A motor-network toy test: one fixed recurrent rate network, steered only by gains -> spinal spring-damper -> v2f arm. Rules: docs/MOTORNET_RULES.md.

Body env (/secondary/hyst-env/body). Disposable; no learning. Library only: motornet_run.py drives it.
"""
import numpy as np

import dialstudy as D
import make_arm as MA
import m3f_report as R

# ------------------------------------------------------------------------------------------------ network constants (rules (a))
N, TAU, DT_NET, DT = 200, 0.075, 0.005, 0.01          # units, s, integration step (200 Hz), control step (100 Hz)
RHO = 1.05                                            # spectral radius of the recurrent matrix (exact: W is rescaled to it)
NCTRL, SUBSET = 4, 80                                 # control units, neurons per unit's subset (40 %)
C_LO, C_HI = 0.5, 2.0                                 # control-unit range (log-uniform draw)
SEED_NET = 29001                                      # W, Win, masks, Wout drawn from independent streams SEED_NET + 0..3
WARM_S, SHOW_S = 10.0, 12.0
BPM_SILENT = 100.0
CENTRE = D.POST[0]                                    # round-1 neutral centre pose
CAL_FRAC = 1.0                                        # +-2 sd of an output maps to +-CAL_FRAC * round-1 neutral amplitude
SPINAL_F, SPINAL_ZETA = 3.0, 0.7


def build_net():
    g = lambda k: np.random.default_rng(SEED_NET + k)
    W = g(0).standard_normal((N, N)) / np.sqrt(N)
    W *= RHO / np.abs(np.linalg.eigvals(W)).max()
    Win = g(1).standard_normal((N, 3))
    r = g(2)
    mask = np.zeros((NCTRL, N))
    for k in range(NCTRL):
        mask[k, r.choice(N, SUBSET, replace=False)] = 1.0
    Wout = g(3).standard_normal((5, N)) / np.sqrt(N)
    return dict(W=W, Win=Win, mask=mask, Wout=Wout)


NET = build_net()


def gains(c):
    """control-unit values c (NCTRL,) -> per-neuron gain g_i = prod_k c_k ** m_ki"""
    return np.exp(np.log(np.asarray(c, float)) @ NET["mask"])


def silent_input(t):
    ph = 2 * np.pi * t * BPM_SILENT / 60.0
    return np.array([np.cos(ph), np.sin(ph), 0.0])


def run_net(c, u_fn, n_steps):
    """-> y (n_steps+1, 5) raw readout and r (n_steps+1, N) rates at the 100 Hz control rate; network time 0 = start of warm-up, x = 0."""
    g = gains(c)
    x = np.zeros(N)
    W, Win, Wout = NET["W"], NET["Win"], NET["Wout"]
    sub = round(DT / DT_NET)
    Y, Rt = np.empty((n_steps + 1, 5)), np.empty((n_steps + 1, N))
    for i in range(n_steps + 1):
        r = np.tanh(g * x)
        Y[i], Rt[i] = Wout @ r, r
        u = Win @ u_fn(i * DT)
        for _ in range(sub):
            x = x + DT_NET / TAU * (-x + W @ np.tanh(g * x) + u)
    return Y, Rt


_CAL = None


def calibration():
    """the one fit: at c = 1, silent run, mean and sd of each raw output over the shown 12 s -> (mean, sd)"""
    global _CAL
    if _CAL is None:
        n = round((WARM_S + SHOW_S) / DT)
        Y, _ = run_net(np.ones(NCTRL), silent_input, n)
        y = Y[round(WARM_S / DT):]
        _CAL = (y.mean(0), y.std(0))
    return _CAL


def to_targets(Y):
    m, s = calibration()
    return CENTRE + CAL_FRAC * D.AMP * (Y - m) / (2 * s)


def spinal(G):
    """per-joint second-order spring-damper (3 Hz, zeta 0.7) following the target rows G (n, 5) deg at 100 Hz; 1 ms semi-implicit steps; starts at rest on G[0]"""
    wn = 2 * np.pi * SPINAL_F
    th, om = G[0].copy(), np.zeros(5)
    out = np.empty_like(G)
    h, sub = 0.001, 10
    for i, tg in enumerate(G):
        out[i] = th
        for _ in range(sub):
            om = om + h * (wn * wn * (tg - th) - 2 * SPINAL_ZETA * wn * om)
            th = th + h * om
    return out


def simulate_goals(G, kp_scale=1.0, zeta=1.5):
    """G (WARM+SHOW+1 rows, 5) deg goals at 100 Hz -> q50 (601, 5) realised at 50 Hz over the shown 12 s; contacts counted from 1.5 s before it.
    Same loop as dialstudy.simulate (limiter, 0.5 deg inside the range, hard stops, 5 x 2 ms substeps); the sim runs through the warm-up."""
    import mujoco
    m = D.make_model(kp_scale, zeta)
    d = mujoco.MjData(m)
    q0 = G[0]
    d.qpos[:] = np.radians(q0)
    d.ctrl[:] = np.radians(q0)
    mujoco.mj_forward(m, d)
    tgt, tv = q0.copy(), np.zeros(5)
    lo_t, hi_t = D.LO + D.CLIP_MARGIN, D.HI - D.CLIP_MARGIN
    lo_r, hi_r = np.radians(D.LO), np.radians(D.HI)
    nw = round(WARM_S / DT)
    rows, contacts = [], 0
    for i, g in enumerate(G):
        goal = np.clip(g, lo_t, hi_t)
        e = goal - tgt
        v_des = np.sign(e) * np.minimum(D.LIM_V, np.sqrt(2 * D.LIM_A * np.abs(e) + 1e-12))
        v_des = np.where(np.abs(v_des) * DT > np.abs(e), e / DT, v_des)
        tv = np.clip(tv + np.clip(v_des - tv, -D.LIM_A * DT, D.LIM_A * DT), -D.LIM_V, D.LIM_V)
        tgt = np.clip(tgt + tv * DT, lo_t, hi_t)
        d.ctrl[:] = np.radians(tgt)
        for _ in range(5):
            mujoco.mj_step(m, d)
            qc = np.clip(d.qpos, lo_r, hi_r)
            d.qvel[:] = np.where(qc != d.qpos, 0.0, d.qvel)
            d.qpos[:] = qc
            if i >= nw - round(D.PRE_S / DT):
                contacts += int(d.ncon > 0)
        if i >= nw and (i - nw) % 2 == 0:
            rows.append(np.degrees(d.qpos))
    return np.array(rows), contacts


# ------------------------------------------------------------------------------------------------ gates
MIN_EXTENT_M, MIN_SPEED, STRETCH_S = 0.05, 0.01, 3.0


def motion_values(q50):
    h = R.fk_points(q50)[:, 5]
    ext = float((np.percentile(h, 95, axis=0) - np.percentile(h, 5, axis=0)).max())
    sp = np.linalg.norm(np.diff(h, axis=0), axis=1) * D.HZ
    n = round(STRETCH_S * D.HZ)
    cs = np.concatenate([[0], np.cumsum(sp)])
    win = (cs[n:] - cs[:-n]) / n
    return dict(extent_m=ext, min_stretch_speed=float(win.min()) if len(win) else 0.0)


THR = dict(hf_share=0.01, reversals_max=6.0)          # round 1's thresholds (all-neutral values were below the floors); read from its manifest


def run_setting(c, u_fn=silent_input, effector="lamp"):
    """-> q50, r50 (601, N) float32, gate dict {passed, parts, values}. Effector is visual only; the sim is the same."""
    n = round((WARM_S + SHOW_S) / DT)
    Y, Rt = run_net(c, u_fn, n)
    G = spinal(to_targets(Y))
    q50, contacts = simulate_goals(G)
    nw = round(WARM_S / DT)
    r50 = Rt[nw::2][:601].astype(np.float32)
    g = D.gate_values(q50, contacts)
    mv = motion_values(q50)
    ok, parts = D.judge(g, THR)
    parts["motion"] = mv["extent_m"] >= MIN_EXTENT_M and mv["min_stretch_speed"] >= MIN_SPEED
    return q50, r50, dict(passed=bool(ok and parts["motion"]), parts=parts, values={**g, **mv}, thresholds=THR)
