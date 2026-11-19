"""WO32D step A fix (docs/RETARGET_RULES.md (k)): the command limiter with braking for the joint range and no wind-up at the range clamp.

The round-1 limiter (motornet.limiter_out, and the same lines inline in motornet.simulate_goals, dialstudy.simulate, arm_sim.limit_target) steers the held target by a speed
profile sqrt(2 A |goal - target|) that knows the goal but not the range edge, then clamps the position to the range (`tgt = clip(tgt + tv*DT, lo_t, hi_t)`) and leaves the velocity
state `tv` unchanged. When the goal turns round while the target is still moving fast, the target runs past the goal into the edge, stops dead at the clamp (a velocity step of
up to LIM_V in one frame: 5.8x the acceleration limit measured as the gate does) and keeps a stale `tv` ("wind-up") that holds it there for several frames.
Fix, both in `step`: (1) the speed toward each edge is capped to the speed from which acceleration A can still stop before the edge (discrete stopping distance
v^2/(2A) + v DT/2 <= EDGE_FRACTION x distance); (2) after the clamp the velocity state is the step actually taken. Round-1 files are not edited: v2f and round 1 stay as they were.
"""
import numpy as np

import dialstudy as D
import motornet as M

DT = M.DT
EDGE_FRACTION = 0.9                      # the edge brake is sized for 90 % of the distance left: the discrete stopping bound alone is marginal and left a 1.06x residue


def step(tgt, tv, goal):
    """one 100 Hz step of the limiter: held target (5,), its velocity (5,), commanded goal (5,) -> new target, new velocity"""
    lo_t, hi_t = D.LO + D.CLIP_MARGIN, D.HI - D.CLIP_MARGIN
    e = np.clip(goal, lo_t, hi_t) - tgt
    v = np.sign(e) * np.minimum(D.LIM_V, np.sqrt(2 * D.LIM_A * np.abs(e) + 1e-12))
    v = np.where(np.abs(v) * DT > np.abs(e), e / DT, v)
    h = D.LIM_A * DT
    with np.errstate(invalid="ignore"):
        up = np.where(np.isfinite(hi_t), (-h + np.sqrt(h * h + 8 * D.LIM_A * EDGE_FRACTION * np.maximum(hi_t - tgt, 0))) / 2, np.inf)
        dn = np.where(np.isfinite(lo_t), -(-h + np.sqrt(h * h + 8 * D.LIM_A * EDGE_FRACTION * np.maximum(tgt - lo_t, 0))) / 2, -np.inf)
    v = np.clip(v, dn, up)
    tv = np.clip(tv + np.clip(v - tv, -h, h), -D.LIM_V, D.LIM_V)
    new = np.clip(tgt + tv * DT, lo_t, hi_t)
    return new, (new - tgt) / DT


def limiter_out(S):
    """the fixed limiter alone (no physics) on command rows S (n, 5) deg at 100 Hz -> limited target rows (same contract as motornet.limiter_out)"""
    tgt, tv = S[0].copy(), np.zeros(5)
    out = np.empty_like(S)
    for i, g in enumerate(S):
        tgt, tv = step(tgt, tv, g)
        out[i] = tgt
    return out


def simulate_goals(G, kp_scale=1.0, zeta=1.5):
    """motornet.simulate_goals with the fixed limiter (same model hook, servo, hard stops, 5 x 2 ms substeps, contact counting); G rows at 100 Hz -> q50, contact substeps"""
    import mujoco
    m = D.make_model(kp_scale, zeta)
    d = mujoco.MjData(m)
    q0 = G[0]
    d.qpos[:] = np.radians(q0)
    d.ctrl[:] = np.radians(q0)
    mujoco.mj_forward(m, d)
    tgt, tv = q0.copy(), np.zeros(5)
    lo_r, hi_r = np.radians(D.LO), np.radians(D.HI)
    nw = round(M.WARM_S / DT)
    rows, contacts = [], 0
    for i, g in enumerate(G):
        tgt, tv = step(tgt, tv, g)
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
