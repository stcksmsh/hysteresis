"""WO30B motor-network toy round 2: two populations (slow tau 300 ms, fast tau 75 ms). Rules: docs/MOTORNET2_RULES.md. Body env.

Library: network, calibration, simulation and gates (the spinal layer, servo, limiter and sim are round 1's, imported from motornet.py unchanged).
Disposable; no learning. Drivers: motornet2_fit.py (silent fit), motornet2_run.py (sampling, clips).
"""
import numpy as np

import dialstudy as D
import motornet as M

NS, NF = 100, 100
N = NS + NF
SLOW, FAST = slice(0, NS), slice(NS, N)
TAU = np.r_[np.full(NS, 0.3), np.full(NF, 0.075)]
DT_NET, DT = M.DT_NET, M.DT
RHO = 1.05                      # spectral radius of each population's within-population block
NCTRL, SUBSET = 4, 80
C_LO, C_HI = M.C_LO, M.C_HI
SEED_NET, SEED_PROJ = 30001, 30002
WARM_S, SHOW_S = 10.0, 30.0
BPM_SILENT = 100.0
CAL_FRAC = 0.6
NIN = 8                         # cos, sin, L4 x4, energy, arousal
L4_DIM = 4
# the body constants are round 1's (motornet.py); only the clip length differs and the reversal-rate divisor follows it
D.CLIP_S = SHOW_S
INPUT_S = np.array([1.0, 1.0])  # (slow, fast); set by motornet2_fit.py, value in docs/MOTORNET2_RULES.md


def build_net():
    g = lambda k: np.random.default_rng(SEED_NET + k)
    W = g(0).standard_normal((N, N)) / np.sqrt(N)
    rho_block = []
    for p in (SLOW, FAST):
        blk = W[p, p]
        rho_block.append(float(np.abs(np.linalg.eigvals(blk)).max()))
        W[p, :] *= RHO / rho_block[-1]                      # one factor per population: all its rows, both blocks
    Win = g(1).standard_normal((N, NIN))
    Win[FAST, 2:2 + L4_DIM] = 0.0                           # L4 goes to the slow population only
    r = g(2)
    mask = np.zeros((NCTRL, N))
    for k in range(NCTRL):
        mask[k, r.choice(N, SUBSET, replace=False)] = 1.0
    r3 = g(3)
    Wout = np.zeros((5, N))
    Wout[0:2, SLOW] = r3.standard_normal((2, NS)) / np.sqrt(NS)     # base yaw, shoulder: slow only
    Wout[2:5, FAST] = r3.standard_normal((3, NF)) / np.sqrt(NF)     # elbow, wrist bend, wrist roll: fast only
    Pl4 = np.random.default_rng(SEED_PROJ).standard_normal((512, L4_DIM))
    full_rho = float(np.abs(np.linalg.eigvals(W)).max())
    return dict(W=W, Win=Win, mask=mask, Wout=Wout, Pl4=Pl4, block_rho_raw=rho_block, full_rho=full_rho)


NET = build_net()


def win_scaled():
    return NET["Win"] * np.r_[np.full(NS, INPUT_S[0]), np.full(NF, INPUT_S[1])][:, None]


def gains(c):
    return np.exp(np.log(np.asarray(c, float)) @ NET["mask"])


def silent_input(t):
    ph = 2 * np.pi * t * BPM_SILENT / 60.0
    u = np.zeros(NIN)
    u[0], u[1] = np.cos(ph), np.sin(ph)
    return u


def run_net(c, u_fn, n_steps):
    """-> y (n+1, 5) raw readout, r (n+1, N) rates at 100 Hz; network time 0 = start of warm-up, x = 0."""
    g = gains(c)
    x = np.zeros(N)
    W, Win, Wout = NET["W"], win_scaled(), NET["Wout"]
    sub = round(DT / DT_NET)
    k = DT_NET / TAU
    Y, Rt = np.empty((n_steps + 1, 5)), np.empty((n_steps + 1, N))
    for i in range(n_steps + 1):
        r = np.tanh(g * x)
        Y[i], Rt[i] = Wout @ r, r
        u = Win @ u_fn(i * DT)
        for _ in range(sub):
            x = x + k * (-x + W @ np.tanh(g * x) + u)
    return Y, Rt


_CAL = None


def calibration():
    """gain 1, silent, 10 s warm-up + SHOW_S shown: mean and sd of each raw output over the shown part"""
    global _CAL
    if _CAL is None:
        Y, _ = run_net(np.ones(NCTRL), silent_input, round((WARM_S + SHOW_S) / DT))
        y = Y[round(WARM_S / DT):]
        _CAL = (y.mean(0), y.std(0))
    return _CAL


def to_targets(Y):
    m, s = calibration()
    return M.CENTRE + CAL_FRAC * D.AMP * (Y - m) / (2 * s)


def participation_ratio(r):
    lam = np.clip(np.linalg.eigvalsh(np.cov(np.asarray(r, float).T)), 0, None)
    return float((lam.sum() ** 2) / (lam ** 2).sum()) if (lam ** 2).sum() > 0 else 0.0


def gate(q, contacts):
    """-> (passed, parts, values, thresholds); round 1's gates on a SHOW_S clip"""
    g = D.gate_values(q, contacts)
    ok, parts = D.judge(g, M.THR)
    mv = M.motion_values(q)
    parts["motion"] = mv["extent_m"] >= M.MIN_EXTENT_M and mv["min_stretch_speed"] >= M.MIN_SPEED
    return bool(ok and parts["motion"]), parts, {**g, **mv}


def finish(Y, Rt):
    """raw readout + rates -> q50 (1501, 5), r50 (1501, N), gate dict"""
    G = M.spinal(to_targets(Y))
    q50, contacts = M.simulate_goals(G)
    nw = round(WARM_S / DT)
    ok, parts, vals = gate(q50, contacts)
    return q50, Rt[nw::2][:len(q50)].astype(np.float32), dict(passed=ok, parts=parts, values=vals, thresholds=M.THR)


def run_setting(c, u_fn=silent_input):
    Y, Rt = run_net(c, u_fn, round((WARM_S + SHOW_S) / DT))
    return finish(Y, Rt)


def pr_per_population(r50):
    return dict(slow=participation_ratio(r50[:, SLOW]), fast=participation_ratio(r50[:, FAST]))


def p595(a):
    return np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)


# ------------------------------------------------------------------------------------------------ inputs
BLOCK_S = 0.5


def music_input(beat_y, l4p, energy, arousal, start_s, warm_s=WARM_S):
    """beat_y (blocks, 8) round-1 lanes (cols 2, 3 = l3_cos, l3_sin; 0.5 s blocks); l4p (n10, 4), energy (n10,), arousal (n10,) already standardised and
    clipped, all at 10 Hz bins (centre (k + 0.5) 0.1 s). -> u_fn(t), network time t = 0 is song time start_s - warm_s."""
    tb = (np.arange(len(beat_y)) + 0.5) * BLOCK_S
    ta = (np.arange(len(arousal)) + 0.5) * 0.1
    te = (np.arange(len(energy)) + 0.5) * 0.1

    def u(t):
        s = start_s - warm_s + t
        v = np.zeros(NIN)
        v[0], v[1] = np.interp(s, tb, beat_y[:, 2]), np.interp(s, tb, beat_y[:, 3])
        v[2:2 + L4_DIM] = [np.interp(s, ta, l4p[:, j]) for j in range(L4_DIM)]
        v[6] = np.interp(s, te, energy)
        v[7] = np.interp(s, ta, arousal)
        return v
    return u
