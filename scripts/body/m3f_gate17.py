"""WO17 gate (BRAIN_SPEC 7.32.5): per seed, 7.30.3 (m3f_gate.gate: toy bar (a) ext/int, (b), (c), (e'1) <= 6.001, (e'2) <= 0.01101, floor-margin breach episodes <= 2 of 16) PLUS the 7.31.2 parking gate:
no ranged joint (shoulder, elbow, wrist bend) on a stop (|q| within 0.05 deg of 110) for more than 10 % of the time (pooled over the 16 held-out episodes), and no single stop-hold longer than 5 s.
Report-only: share of time on a stop per joint, longest stop-hold, longest hold of ANY pose (hand speed < 2 cm/s, FK hand point at 50 Hz), clip-boundary holds (>= 2 s within 1 deg of 109.5 and under half
on the stop, as WO16b), program counts and top share, trained - kappa0 paired (argmax and sampled, from controls), end stops (m3f_endstop.json). Reads RUNDIR/try1/{result.json,rollouts,controls,endstop.json};
writes RUNDIR/gate17.json.
    m3f_gate17.py RUNDIR [RUNDIR ...]
"""
import json
import sys
from pathlib import Path

import numpy as np

import m3f_gate as G
import m3f_park_diag as D
import m3f_report as R

STOP_SHARE_MAX, STOP_HOLD_MAX_S, HAND_STILL_MPS = 0.10, 5.0, 0.02


def longest_run(mask):
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def parking(q):
    """q (E, T, 5) deg at 100 Hz."""
    E, T, _ = q.shape
    out = {"share_on_stop": {}, "longest_stop_hold_s": {}}
    for j, nm in D.JOINTS.items():
        on = np.abs(np.abs(q[..., j]) - D.STOP) < D.TOL_DEG
        out["share_on_stop"][nm] = float(on.mean())
        out["longest_stop_hold_s"][nm] = float(max(longest_run(on[e]) for e in range(E)) / 100.0)
    out["longest_stop_hold_s_any_joint"] = max(out["longest_stop_hold_s"].values())
    # longest hold of any pose: hand speed < 2 cm/s (FK hand at 50 Hz)
    best = 0
    per_ep = []
    for e in range(E):
        hand = R.fk_points(q[e, ::2])[:, 5]
        v = np.linalg.norm(np.diff(hand, axis=0), axis=1) * 50.0
        r = longest_run(v < HAND_STILL_MPS) / 50.0
        per_ep.append(r)
        best = max(best, r)
    out["longest_any_pose_hold_s"] = float(best)
    out["any_pose_hold_s_per_episode_max_mean"] = [float(np.mean(per_ep)), float(max(per_ep))]
    return out


def gate17(rundir):
    rd = Path(rundir)
    g = G.gate(rundir)
    t1 = rd / "try1"
    res = json.loads((t1 / "result.json").read_text())["result"]
    q = np.load(t1 / "rollouts" / "trained_argmax_4.npz")["q"]
    q = q.reshape(q.shape[0], -1, 5)
    pk = parking(q)
    parts = dict(g["parts"])
    parts["parking_share_on_stop"] = bool(all(v <= STOP_SHARE_MAX for v in pk["share_on_stop"].values()))
    parts["parking_longest_stop_hold"] = bool(pk["longest_stop_hold_s_any_joint"] <= STOP_HOLD_MAX_S)
    out = {"pass": all(parts.values()), "parts": parts, "gate_7_30_3": g, "parking": pk}
    # clip-boundary holds (report only)
    bh = D.find_holds(q, D.BOUNDARY, D.BOUNDARY_TOL)
    kept = []
    for h in bh:
        on = np.abs(np.abs(q[h["episode"], h["start"]:h["end"], h["joint"]]) - D.STOP) < D.TOL_DEG
        if on.mean() < 0.5:
            kept.append({"episode": h["episode"], "joint": h["name"], "start_s": h["start"] / 100.0, "end_s": h["end"] / 100.0})
    out["clip_boundary_holds"] = {"n": len(kept), "total_s": float(sum(k["end_s"] - k["start_s"] for k in kept)), "per_joint_s": {nm: float(sum(k["end_s"] - k["start_s"] for k in kept if k["joint"] == nm)) for nm in D.JOINTS.values()}}
    stop_holds = D.find_holds(q)
    out["stop_holds_ge_2s"] = {"n": len(stop_holds), "total_s": float(sum((h["end"] - h["start"]) / 100.0 for h in stop_holds))}
    for m in ("argmax", "sample"):
        cnt = np.asarray(res[m]["program_counts"], float)
        out[f"programs_{m}"] = {"counts": cnt.tolist(), "top_share": float(cnt.max() / cnt.sum()), "used": res[m]["programs_used"]}
    cs = t1 / "controls" / "summary.json"
    if cs.exists():
        c = json.loads(cs.read_text())
        pk0 = c["paired"]["ii_trained_kappa0"]
        out["trained_minus_kappa0"] = {m: {k: {"mean": pk0[m][k]["mean"], "ci": pk0[m][k]["ci"]} for k in ("ext", "int")} for m in ("argmax", "sample")}
    es = t1 / "endstop.json"
    if es.exists():
        e = json.loads(es.read_text())["trained"]
        out["end_stops"] = {m: {k: v for k, v in e[m].items() if k != "per_episode"} for m in e}
    (rd / "gate17.json").write_text(json.dumps(out, indent=1))
    return out


def main():
    for d in sys.argv[1:]:
        o = gate17(d)
        print(d, "PASS" if o["pass"] else "FAIL", {k: v for k, v in o["parts"].items() if not v} or "all components pass",
              "| on stop", {k: round(v, 3) for k, v in o["parking"]["share_on_stop"].items()}, "longest stop-hold %.2f s" % o["parking"]["longest_stop_hold_s_any_joint"],
              "longest any-pose hold %.1f s" % o["parking"]["longest_any_pose_hold_s"])


if __name__ == "__main__":
    main()
