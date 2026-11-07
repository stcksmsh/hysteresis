"""M3f reports from saved rollouts: bar component (e) and check-csv-style breaches. Provisional servo model (Feetech STS3215 12 V assumed).

(e) (BRAIN_SPEC 7.24 + the overseer's defaults): joint velocity by central difference of the 50 Hz joint trajectory (the toy's 100 Hz trajectory sampled at every second step), Welch
spectrum (4 s Hann segments, 50 % overlap, mean removed), share = power above 3 Hz / power above 0 Hz, summed over the four non-roll joints; one value per episode. `hf_share_q50`
is this file's own implementation; scripts/body/hf_share.py (work order 13A) is the reference once it is merged (test_m3f.HfShare compares them).
Breaches use the check-csv thresholds on the 50 Hz trajectory: points 1-4 clear z = 0 by 0.05 m, the hand by 0.05 + 0.06 m; hand speed 1.2 m/s; hand jolt 9 m/s2 (|change of
hand speed| x 50); joint position range (+-110 deg on the bends); per-joint speed and acceleration limits (body.rs LIMITS).
"""
import numpy as np
from scipy.signal import welch

import bdesc
import make_arm as MA

HZ = 50
FLOOR_M, DISC_M, HAND_MPS, JOLT_MPS2 = 0.05, 0.06, 1.2, 9.0


def hf_share_q50(q50, f_cut=3.0):
    """q50 (T, 5) deg at 50 Hz -> share of joint-velocity power above f_cut over power above 0 (non-roll joints summed)."""
    v = (q50[2:, :4] - q50[:-2, :4]) * HZ / 2.0
    f, p = welch(v, fs=HZ, window="hann", nperseg=4 * HZ, noverlap=2 * HZ, detrend="constant", axis=0)
    p = p.sum(1)
    return float(p[f > f_cut].sum() / p[f > 0].sum())


def hf_share_rollout(q):
    """q (E, NB, 50, 5) deg at 100 Hz -> {per_episode, mean}."""
    q = np.asarray(q).reshape(q.shape[0], -1, 5)[:, ::2]
    per = [hf_share_q50(e) for e in q]
    return {"per_episode": per, "mean": float(np.mean(per))}


def fk_points(q):
    """q (T, 5) deg -> (T, 6, 3): origin and the point after each joint's link (ensemble.rs forward_kinematics, origin 0, yaw 0)."""
    T = len(q)
    B = np.broadcast_to(np.eye(3), (T, 3, 3)).copy()
    p = np.zeros((T, 3))
    pts = [p.copy()]
    for j in range(5):
        B = B @ bdesc._rot(MA.AXES[j], q[:, j])
        p = p + B @ np.asarray(MA.LINKS[j], float)
        pts.append(p.copy())
    return np.stack(pts, 1)


TABLE_R_LINK, TABLE_R_BALL = 0.01, DISC_M


def hand_metrics(q50, plane=None):
    """BRAIN_SPEC 7.25 (e'): q50 (T, 5) deg at 50 Hz -> hand acceleration p99 (m/s2), share of time hand speed > 1 m/s, and the share of time the arm touches the table.
    Hand = last point of the rig's forward kinematics (same as arm_sim.fk); velocity and acceleration by np.gradient (x 50, x 50), norms. Contact (geometric, from the realised joint
    angles): a link capsule (r 0.01) or the ball (r 0.06) overlaps the plane z = 0: min z of the link end points p1..p4 minus 0.01, or p5 z minus 0.06, below 0."""
    P = fk_points(q50)
    h = P[:, 5]
    v = np.gradient(h, axis=0) * HZ
    a = np.gradient(v, axis=0) * HZ
    if plane is None:
        touch = np.minimum(P[:, 1:5, 2].min(1) - TABLE_R_LINK, P[:, 5, 2] - TABLE_R_BALL) < 0
    else:                                                          # raised plane: in contact = a surface within 1 mm above the plane or below it
        touch = np.minimum(P[:, 1:5, 2].min(1) - TABLE_R_LINK - plane, P[:, 5, 2] - TABLE_R_BALL - plane) < 0.001
    return {"acc_p99": float(np.percentile(np.linalg.norm(a, axis=1), 99)), "fast": float((np.linalg.norm(v, axis=1) > 1.0).mean()), "contact": float(touch.mean())}


def eprime_rollout(q, plane=None):
    """q (E, NB, 50, 5) deg at 100 Hz -> per episode and mean of (e'1) acc_p99, (e'2) fast share, contact share (+ seconds), and (e) from hf_share.py."""
    import hf_share
    q = np.asarray(q).reshape(q.shape[0], -1, 5)[:, ::2]
    rows = [hand_metrics(e, plane) for e in q]
    out = {k: [r[k] for r in rows] for k in ("acc_p99", "fast", "contact")}
    out["contact_s"] = [c * len(q[0]) / HZ for c in out["contact"]]
    out["e"] = [hf_share.hf_share(e, float(HZ)) for e in q]
    out.update({k + "_mean": float(np.mean(v)) for k, v in list(out.items())})
    return out


def near_limit(q, deg=2.0):
    """q (E, NB, 50, 5) deg at 100 Hz -> per ranged joint (shoulder, elbow, wrist_bend): share of time within `deg` of either limit (mean over episodes), the share beyond the limit itself, and
    the largest excess beyond it (deg)."""
    q = np.asarray(q).reshape(q.shape[0], -1, 5)
    out = {}
    for j, name in ((1, "shoulder"), (2, "elbow"), (3, "wrist_bend")):
        lo, hi = MA.RANGE_DEG[j]
        x = q[:, :, j]
        out[name] = {"within": float(((x < lo + deg) | (x > hi - deg)).mean()), "beyond": float(((x < lo) | (x > hi)).mean()), "max_excess_deg": float(max((lo - x).max(), (x - hi).max(), 0.0)),
                     "within_per_episode": ((x < lo + deg) | (x > hi - deg)).mean(1).tolist()}
    return out


def breaches(q):
    """q (E, NB, 50, 5) deg at 100 Hz -> per type: share of rows breaching (mean over episodes), episodes with any breach, worst excess."""
    q = np.asarray(q).reshape(q.shape[0], -1, 5)[:, ::2]
    rng = [(-110.0, 110.0) if r else (-1e9, 1e9) for r in MA.RANGE_DEG]
    out = {k: {"rows": [], "worst": 0.0} for k in ("floor_m", "hand_speed", "hand_jolt", "joint_range_deg", "joint_speed", "joint_accel")}
    for e in q:
        P = fk_points(e)
        floor = np.minimum((P[:, 1:5, 2] - FLOOR_M).min(1), P[:, 5, 2] - FLOOR_M - DISC_M)
        hs = np.linalg.norm(np.diff(P[:, 5], axis=0), axis=1) * HZ
        hj = np.abs(np.diff(hs)) * HZ
        over = np.maximum.reduce([np.maximum(e[:, j] - rng[j][1], rng[j][0] - e[:, j]) for j in range(5)])
        sp = np.abs(np.diff(e, axis=0)) * HZ - np.array([v for v, _ in MA.LIMITS])
        ac = np.abs(e[2:] - 2 * e[1:-1] + e[:-2]) * HZ * HZ - np.array([a for _, a in MA.LIMITS])
        for k, bad, worst in (("floor_m", floor < 0, -floor.min()), ("hand_speed", hs > HAND_MPS, hs.max() - HAND_MPS), ("hand_jolt", hj > JOLT_MPS2, hj.max() - JOLT_MPS2),
                              ("joint_range_deg", over > 0, over.max()), ("joint_speed", (sp > 0).any(1), sp.max()), ("joint_accel", (ac > 0).any(1), ac.max())):
            out[k]["rows"].append(float(bad.mean()))
            out[k]["worst"] = max(out[k]["worst"], float(worst))
    return {k: {"row_share_mean": float(np.mean(v["rows"])), "episodes_with_breach": int(sum(r > 0 for r in v["rows"])), "episodes": len(v["rows"]), "worst_excess": v["worst"]} for k, v in out.items()}
