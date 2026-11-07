"""End-stop report for the pass2 check (BRAIN_SPEC 7.28 / 7.29; report only, no bar uses it). Provisional servo model.

An end-stop event = a ranged joint (shoulder, elbow, wrist bend; make_arm RANGE_DEG) at its range limit (|q - limit| <= EPS_DEG) at a sample where it was not at that limit at the previous
sample (the hard clip of WO14A puts a clipped joint exactly on the limit). Hand = last forward-kinematics point (m3f_report.fk_points). Hand acceleration and jerk are the norms of the
second and third np.gradient of the hand position at the trajectory's rate. For each trajectory (one episode / window) and rate (50 Hz = every second sample; 100 Hz = all):
    events, and mean / p99 of |acc| and |jerk| over the samples within +-HALF_S of any event, against the same over the whole trajectory.
50 Hz: pooled over trajectories (all event samples together, all samples together). 100 Hz: both pooled and per trajectory (mean over trajectories that have events of the ratio window/overall).
"""
import numpy as np

import make_arm as MA
import m3f_report as R

EPS_DEG = 1e-3
HALF_S = 0.05
JOINTS = {"shoulder": 1, "elbow": 2, "wrist_bend": 3}


def events(q):
    """q (T, 5) deg -> {joint name: sample indices of end-stop events}."""
    out = {}
    for name, j in JOINTS.items():
        lo, hi = MA.RANGE_DEG[j]
        at = (q[:, j] <= lo + EPS_DEG) | (q[:, j] >= hi - EPS_DEG)
        out[name] = np.flatnonzero(at[1:] & ~at[:-1]) + 1
    return out


def hand_acc_jerk(q, hz):
    """q (T, 5) deg at hz -> (|acc| (T,), |jerk| (T,)) of the hand, m/s2 and m/s3."""
    h = R.fk_points(q)[:, 5]
    v = np.gradient(h, axis=0) * hz
    a = np.gradient(v, axis=0) * hz
    j = np.gradient(a, axis=0) * hz
    return np.linalg.norm(a, axis=1), np.linalg.norm(j, axis=1)


def one(q, hz):
    """q (T, 5) deg at 100 Hz -> dict for this trajectory at hz (50 or 100): n events per joint, mask of samples near an event, |acc|, |jerk|."""
    step = 100 // hz
    qs = q[::step]
    ev = {k: np.unique(v // step) for k, v in events(q).items()}
    near = np.zeros(len(qs), bool)
    w = int(round(HALF_S * hz))
    for v in ev.values():
        for i in v:
            near[max(0, i - w):i + w + 1] = True
    a, j = hand_acc_jerk(qs, float(hz))
    return {"n": {k: int(len(v)) for k, v in ev.items()}, "near": near, "acc": a, "jerk": j}


def _stats(x):
    return {"mean": float(x.mean()), "p99": float(np.percentile(x, 99))} if len(x) else None


def report(q, hz_list=(50, 100)):
    """q (E, NB, 50, 5) deg at 100 Hz -> {hz: {...}}. Events counted per trajectory (E trajectories) and per minute of trajectory."""
    q = np.asarray(q, float).reshape(len(q), -1, 5)
    out = {}
    for hz in hz_list:
        rs = [one(e, hz) for e in q]
        n = {k: [r["n"][k] for r in rs] for k in JOINTS}
        near = np.concatenate([r["near"] for r in rs])
        acc, jerk = np.concatenate([r["acc"] for r in rs]), np.concatenate([r["jerk"] for r in rs])
        d = {"n_trajectories": len(rs), "events_total": {k: int(sum(v)) for k, v in n.items()}, "events_per_trajectory_mean": {k: float(np.mean(v)) for k, v in n.items()},
             "trajectories_with_events": int(sum(1 for r in rs if near_any(r))), "seconds_near": float(near.sum() / hz),
             "pooled": {"acc_near": _stats(acc[near]), "acc_all": _stats(acc), "jerk_near": _stats(jerk[near]), "jerk_all": _stats(jerk)}}
        if hz == 100:
            rows = [(r["acc"][r["near"]].mean() / r["acc"].mean(), r["jerk"][r["near"]].mean() / r["jerk"].mean()) for r in rs if near_any(r)]
            d["per_trajectory"] = {"acc_ratio_mean": float(np.mean([a for a, _ in rows])) if rows else None, "jerk_ratio_mean": float(np.mean([b for _, b in rows])) if rows else None,
                                   "n": len(rows)}
        out[str(hz)] = d
    return out


def near_any(r):
    return bool(r["near"].any())
