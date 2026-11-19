"""WO9 Part 2 report (docs/NIGHT_LOG_body-m3e.md): paired (a)_try1 - (a)_ablation on the 16 held-out episodes, external and internal, argmax and sampled; credited =
external argmax interval above 0. Reads /secondary/hyst-data/body/m3e/{try1,ablations/*}/result.json; writes ablations/summary.json."""
import json
from pathlib import Path

import m3d_controls as K

D = Path("/secondary/hyst-data/body/m3e")
NAMES = ["a1_closed_loop", "a2_gating", "a3_internal"]


def main():
    base = json.loads((D / "try1/result.json").read_text())["result"]
    out = {"try1": {m: {d: base[m][d]["a_gap_mean"] for d in ("ext", "int")} for m in base}, "ablations": {}}
    for n in NAMES:
        p = D / "ablations" / n / "result.json"
        if not p.exists():
            continue
        r = json.loads(p.read_text())["result"]
        row = {"scores": {m: {"ext_a": r[m]["ext"]["a_gap_mean"], "ext_ci": r[m]["ext"]["a_ci"], "int_a": r[m]["int"]["a_gap_mean"], "int_ci": r[m]["int"]["a_ci"], "b": r[m]["b_rms_nonroll"],
                              "c_mi": r[m]["c_mi"], "c_p": r[m]["c_p"], "programs_used": r[m]["programs_used"], "kappa_mean": r[m]["kappa_mean"]} for m in r},
               "paired": {m: {d: K.paired_difference(base[m][d]["a_gaps"], r[m][d]["a_gaps"]) for d in ("ext", "int")} for m in r}}
        row["credited"] = bool(row["paired"]["argmax"]["ext"]["ci"][0] > 0)
        out["ablations"][n] = row
    (D / "ablations" / "summary.json").write_text(json.dumps(out, indent=1))
    for n, row in out["ablations"].items():
        print(n, "credited" if row["credited"] else "not credited", {m: {d: [round(row["paired"][m][d]["mean"], 3), [round(x, 3) for x in row["paired"][m][d]["ci"]]] for d in ("ext", "int")} for m in row["paired"]})


if __name__ == "__main__":
    main()
