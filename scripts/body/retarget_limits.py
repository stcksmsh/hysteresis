"""WO32C report-only: per-joint speed/acceleration ratios of the 145 gated candidates (both variants), limiter cut, servo overshoot, per-genre medians, "limits" pass counts at
tolerances 1.05, 1.25, 1.5. Re-runs the same sims as `retarget_run.py clips` (same stream, same code path); changes no rule, gate, scale or clip, renders nothing.
Output /secondary/hyst-data/body/retarget_look/limits_breakdown.json. Run (body env): python -u retarget_limits.py [N_CANDIDATES=145]
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget_run as RR  # noqa: E402

JN = RR.JN
TOLS = (1.05, 1.25, 1.5)
HZ = 50


def ratios(q50, LIM_V, LIM_A):
    """per joint max speed / limit and max acceleration / limit of 50 Hz rows, as dialstudy.gate_values computes them"""
    v = np.diff(q50, axis=0) * HZ
    a = (q50[2:] - 2 * q50[1:-1] + q50[:-2]) * HZ * HZ
    return np.abs(v).max(0) / LIM_V, np.abs(a).max(0) / LIM_A


def one(c, var):
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    D, M = RR.patch_gates()
    v = RR.human(c["seq"])[0 if var == "V1" else 1]
    i0 = round(c["start_s"] * RT.FPS)
    G0 = RT.to_100hz(RT.to_commands(RT.referenced(v, i0), var), c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
    G, gshare = P.guard(G0)
    q50, contacts = M.simulate_goals(G)
    gates = RR.gates_v2p(q50, contacts, gshare)
    lim = M.limiter_out(G)[round(RR.PRE_S * 100):]                      # limiter output, 100 Hz, the shown 20 s
    tgt = G0[round(RR.PRE_S * 100):]
    sp_r, ac_r = ratios(q50, D.LIM_V, D.LIM_A)
    v_l = np.abs(np.diff(lim, axis=0) * 100).max(0) / D.LIM_V
    a_l = np.abs(lim[2:] - 2 * lim[1:-1] + lim[:-2]).max(0) * 100 * 100 / D.LIM_A
    p = lambda a: np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)
    cut = 1 - p(lim) / np.maximum(p(tgt), 1e-9)
    t_sp = np.abs(np.diff(tgt, axis=0) * 100).max(0) / D.LIM_V           # the retargeted command itself (before the limiter)
    t_ac = np.abs(tgt[2:] - 2 * tgt[1:-1] + tgt[:-2]).max(0) * 100 * 100 / D.LIM_A
    return dict(
        speed_ratio=sp_r.tolist(), accel_ratio=ac_r.tolist(),
        worst_speed=float(sp_r.max()), worst_speed_joint=JN[int(sp_r.argmax())], worst_accel=float(ac_r.max()), worst_accel_joint=JN[int(ac_r.argmax())],
        limiter_cut=dict(zip(JN, cut.tolist())),
        limiter_out_speed_ratio=v_l.tolist(), limiter_out_accel_ratio=a_l.tolist(),
        overshoot_speed=(sp_r - v_l).tolist(), overshoot_accel=(ac_r - a_l).tolist(),
        command_speed_ratio=t_sp.tolist(), command_accel_ratio=t_ac.tolist(),
        gate_values={k: gates["values"][k] for k in ("speed_ratio", "accel_ratio", "contact_substeps", "endstop_samples", "floor_m", "hf_share", "reversals_max", "guard_share")},
        other_gates_pass=bool(all(x for k, x in gates["parts"].items() if k != "limits")), limits_pass=bool(gates["parts"]["limits"]), all_pass=bool(gates["passed"]))


def main(n):
    cat = RR.catalogue()
    order = [str(g) for g in np.random.default_rng(RR.SEED).permutation(sorted({v[0] for v in cat.values()}))]
    rows = []
    for k in range(n):
        c = RR.pick(k, order, cat)
        r = {var: one(c, var) for var in ("V1", "V2")}
        rows.append(dict(cand=c, **r))
        print(k, c["genre"], {v: (round(r[v]["worst_speed"], 2), round(r[v]["worst_accel"], 2)) for v in r}, flush=True)
    med = lambda x: float(np.median(x)) if len(x) else None
    out = dict(note="report only; nothing adopted. Ratios as dialstudy.gate_values (50 Hz realised rows, diff*50 / LIM_V; second difference*2500 / LIM_A). Limiter output = motornet.limiter_out at 100 Hz on the guarded command. Overshoot = realised ratio - limiter-output ratio. Cut share = 1 - (limiter-output p5-p95 / command p5-p95).",
               limits=dict(speed_deg_s=[v for v, _ in __import__("make_arm").LIMITS], accel_deg_s2=[a for _, a in __import__("make_arm").LIMITS]), joints=list(JN), candidates=n)
    by = {}
    for var in ("V1", "V2"):
        d = {}
        d["limits_pass_at_tolerance"] = {str(t): int(sum(1 for r in rows if r[var]["worst_speed"] <= t and r[var]["worst_accel"] <= t)) for t in TOLS}
        d["all_gates_pass_at_tolerance_other_gates_unchanged"] = {str(t): int(sum(1 for r in rows if r[var]["other_gates_pass"] and r[var]["worst_speed"] <= t and r[var]["worst_accel"] <= t)) for t in TOLS}
        d["both_variants_all_gates_pass_at_tolerance"] = None
        d["failing_joint_count_speed"] = {j: int(sum(1 for r in rows if r[var]["worst_speed"] > 1.05 and r[var]["worst_speed_joint"] == j)) for j in JN}
        d["failing_joint_count_accel"] = {j: int(sum(1 for r in rows if r[var]["worst_accel"] > 1.05 and r[var]["worst_accel_joint"] == j)) for j in JN}
        d["per_joint_median"] = {j: dict(speed_ratio=med([r[var]["speed_ratio"][i] for r in rows]), accel_ratio=med([r[var]["accel_ratio"][i] for r in rows]),
                                         limiter_cut=med([r[var]["limiter_cut"][j] for r in rows]), limiter_cut_max=float(max(r[var]["limiter_cut"][j] for r in rows)),
                                         overshoot_speed=med([r[var]["overshoot_speed"][i] for r in rows]), overshoot_accel=med([r[var]["overshoot_accel"][i] for r in rows]),
                                         command_speed_ratio=med([r[var]["command_speed_ratio"][i] for r in rows]), command_accel_ratio=med([r[var]["command_accel_ratio"][i] for r in rows]))
                                 for i, j in enumerate(JN)}
        g = defaultdict(list)
        for r in rows:
            g[r["cand"]["genre"]].append(r)
        d["per_genre"] = {k: dict(n=len(v), median_worst_speed=med([x[var]["worst_speed"] for x in v]), median_worst_accel=med([x[var]["worst_accel"] for x in v]),
                                  limits_pass_1_05=int(sum(1 for x in v if x[var]["limits_pass"])), all_gates_pass=int(sum(1 for x in v if x[var]["all_pass"]))) for k, v in sorted(g.items())}
        by[var] = d
    for t in TOLS:
        by.setdefault("both_variants_all_gates_pass_at_tolerance", {})[str(t)] = int(sum(
            1 for r in rows if all(r[v]["other_gates_pass"] and r[v]["worst_speed"] <= t and r[v]["worst_accel"] <= t for v in ("V1", "V2"))))
    for v in ("V1", "V2"):
        by[v].pop("both_variants_all_gates_pass_at_tolerance")
    out["summary"] = by
    out["per_candidate"] = rows
    Path("/secondary/hyst-data/body/retarget_look/limits_breakdown.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(by, indent=1)[:6000])


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 145)
