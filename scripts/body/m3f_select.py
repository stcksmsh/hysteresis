"""WO13B grid selection (BRAIN_SPEC 7.24 rule, fixed before the grid ran): among the grid points that pass the toy bar (external (a), (b), (c), argmax, tune episodes) AND (e) <= 1.25 x the
mean of v47's three per-song values, take the highest external (a) (argmax mean gap, rounded to 3 decimals); ties go to the smaller weights (jerk first, then switch).
(e) is recomputed here from each point's saved evaluation rollout with scripts/body/hf_share.py (work order 13A), the reference implementation, so every point is measured the same way.

    m3f_select.py --ref V47_A V47_B V47_C     the three per-song v47 values (from docs/hf_v47_reference.json); writes /secondary/hyst-data/body/m3f/selection.json
"""
import argparse
import json
from pathlib import Path

import numpy as np

import hf_share as H

D = Path("/secondary/hyst-data/body/m3f")


def e_of(rolldir, mode="argmax"):
    q = np.load(Path(rolldir) / f"trained_{mode}_4.npz")["q"]
    q = q.reshape(q.shape[0], -1, 5)[:, ::2]                 # 100 Hz -> 50 Hz
    per = [H.hf_share(e, 50.0) for e in q]
    return float(np.mean(per)), per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", type=float, nargs=3, required=True)
    a = ap.parse_args()
    limit = 1.25 * float(np.mean(a.ref))
    rows = []
    for p in sorted((D / "grid").glob("*/result.json")):
        j = json.loads(p.read_text())
        r = j["result"]["argmax"]
        e, per = e_of(p.parent / "rollouts")
        row = {"name": p.parent.name, "w_jerk": j["args"]["w_jerk"], "w_switch": j["args"]["w_switch"], "ext_a": r["ext"]["a_gap_mean"], "ext_ci": r["ext"]["a_ci"], "ext_pass": r["ext"]["a_pass"],
               "int_a": r["int"]["a_gap_mean"], "b": r["b_rms_nonroll"], "b_pass": r["b_pass"], "c_mi": r["c_mi"], "c_p": r["c_p"], "c_pass": r["c_pass"], "e": e, "e_pass": e <= limit,
               "bar": bool(r["ext"]["a_pass"] and r["b_pass"] and r["c_pass"]), "e_in_json": r["e"]["mean"]}
        row["eligible"] = row["bar"] and row["e_pass"]
        rows.append(row)
    ok = sorted([r for r in rows if r["eligible"]], key=lambda r: (-round(r["ext_a"], 3), r["w_jerk"], r["w_switch"]))
    out = {"v47_per_song": a.ref, "limit_e": limit, "rows": rows, "selected": ok[0]["name"] if ok else None,
           "selected_weights": {"w_jerk": ok[0]["w_jerk"], "w_switch": ok[0]["w_switch"]} if ok else None}
    (D / "selection.json").write_text(json.dumps(out, indent=1))
    for r in rows:
        print(f"{r['name']:14s} ext a {r['ext_a']:.3f} {np.round(r['ext_ci'], 3).tolist()} b {r['b']:.1f} c p {r['c_p']:.3f} bar {r['bar']} | e {r['e']:.4f} (<= {limit:.4f}: {r['e_pass']}) | eligible {r['eligible']}")
    print("selected:", out["selected"], out["selected_weights"])


if __name__ == "__main__":
    main()
