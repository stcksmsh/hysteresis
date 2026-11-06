"""WO13B grid selection (BRAIN_SPEC 7.24 rule with 7.25's (e') in place of (e)): among the grid points that pass the toy bar (external (a), (b), (c), argmax, tune episodes) AND
(e'1) mean over episodes of hand-acceleration p99 <= 1.25 x the mean of v47's three per-song values (6.001 m/s2) AND (e'2) mean over episodes of the share of time with hand speed
> 1 m/s <= 1.25 x the mean of v47's three values (0.01101), take the highest external (a) (argmax mean gap, rounded to 3 decimals); ties go to the smaller weights (jerk first, then
switch). (e'), (e) and the table contact are recomputed here from each point's saved evaluation rollout (m3f_report.eprime_rollout), so every point is measured the same way.
Limits are read from docs/hf_v47_eprime_reference.json.     m3f_select.py     writes /secondary/hyst-data/body/m3f/selection.json
"""
import json
from pathlib import Path

import numpy as np

import m3f_report as R

D = Path("/secondary/hyst-data/body/m3f")
REF = Path(__file__).resolve().parents[2] / "docs" / "hf_v47_eprime_reference.json"


def main():
    ref = json.loads(REF.read_text())
    songs = [v for v in ref.values() if isinstance(v, dict) and "acc_p99" in v]
    lim_acc, lim_gt1 = 1.25 * float(np.mean([s["acc_p99"] for s in songs])), 1.25 * float(np.mean([s["gt1"] for s in songs]))
    rows = []
    for p in sorted((D / "grid").glob("*/result.json")):
        j = json.loads(p.read_text())
        r = j["result"]["argmax"]
        ep = R.eprime_rollout(np.load(p.parent / "rollouts" / "trained_argmax_4.npz")["q"])
        row = {"name": p.parent.name, "w_jerk": j["args"]["w_jerk"], "w_switch": j["args"]["w_switch"], "ext_a": r["ext"]["a_gap_mean"], "ext_ci": r["ext"]["a_ci"], "ext_pass": r["ext"]["a_pass"],
               "int_a": r["int"]["a_gap_mean"], "b": r["b_rms_nonroll"], "b_pass": r["b_pass"], "c_mi": r["c_mi"], "c_p": r["c_p"], "c_pass": r["c_pass"], "programs_used": r["programs_used"],
               "e": ep["e_mean"], "eprime1_acc_p99": ep["acc_p99_mean"], "eprime2_fast": ep["fast_mean"], "contact_share": ep["contact_mean"],
               "eprime1_pass": ep["acc_p99_mean"] <= lim_acc, "eprime2_pass": ep["fast_mean"] <= lim_gt1, "bar": bool(r["ext"]["a_pass"] and r["b_pass"] and r["c_pass"])}
        row["eligible"] = row["bar"] and row["eprime1_pass"] and row["eprime2_pass"]
        rows.append(row)
    ok = sorted([r for r in rows if r["eligible"]], key=lambda r: (-round(r["ext_a"], 3), r["w_jerk"], r["w_switch"]))
    out = {"limit_eprime1": lim_acc, "limit_eprime2": lim_gt1, "rows": rows, "selected": ok[0]["name"] if ok else None,
           "selected_weights": {"w_jerk": ok[0]["w_jerk"], "w_switch": ok[0]["w_switch"]} if ok else None}
    (D / "selection.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(f"{r['name']:14s} ext a {r['ext_a']:.3f} {np.round(r['ext_ci'], 3).tolist()} b {r['b']:.1f} c p {r['c_p']:.3f} bar {r['bar']} | e'1 {r['eprime1_acc_p99']:.3f} (<= {lim_acc:.3f}: {r['eprime1_pass']}) "
              f"e'2 {r['eprime2_fast']:.5f} (<= {lim_gt1:.5f}: {r['eprime2_pass']}) | e {r['e']:.5f} contact {r['contact_share']:.4f} | eligible {r['eligible']}")
    print("selected:", out["selected"], out["selected_weights"])


if __name__ == "__main__":
    main()
