"""WO11 report: seed-2 paired (a)_try1 - (a)_ablation, then the BRAIN_SPEC 7.21 point 1 rule across both seeds, the dopamine fact (7.21 point 2), and the try 1 seed spread.
Seed 1 = Trainer seed 0 (WO8/WO9: m3e/try1, m3e/ablations/*); seed 2 = Trainer seed 1 (m3e/seed2/*). Writes seed2/summary.json.
Rule: credited for a decoding (ext or int, argmax) only if the paired interval is above 0 in BOTH seeds. Dopamine lowers decoding for a decoding only if the paired
interval try1 - A2 is below 0 (upper end < 0) in both seeds, argmax."""
import json
from pathlib import Path

import m3d_controls as K

D = Path("/secondary/hyst-data/body/m3e")
NAMES = ["a1_closed_loop", "a2_gating", "a3_internal"]
DEC = ("ext", "int")


def load(root, name):
    return json.loads((root / name / "result.json").read_text())["result"]


def paired(base, r):
    return {m: {d: K.paired_difference(base[m][d]["a_gaps"], r[m][d]["a_gaps"]) for d in DEC} for m in r}


def main():
    s1, s2 = D, D / "seed2"
    b1, b2 = load(s1, "try1"), load(s2, "try1")
    out = {"try1_scores": {}, "try1_spread": {}, "ablations": {}}
    for tag, b in (("seed1", b1), ("seed2", b2)):
        out["try1_scores"][tag] = {m: {d: {"a": b[m][d]["a_gap_mean"], "ci": b[m][d]["a_ci"]} for d in DEC} | {"b": b[m]["b_rms_nonroll"], "c_mi": b[m]["c_mi"], "c_p": b[m]["c_p"]} for m in b}
    out["try1_spread"] = {m: {d: {"seed1_minus_seed2": b1[m][d]["a_gap_mean"] - b2[m][d]["a_gap_mean"],
                                  "paired_per_episode": K.paired_difference(b1[m][d]["a_gaps"], b2[m][d]["a_gaps"])} for d in DEC} for m in b1}
    for n in NAMES:
        r1, r2 = load(s1 / "ablations", n), load(s2, n)
        p1, p2 = paired(b1, r1), paired(b2, r2)
        row = {"seed2_scores": {m: {"ext_a": r2[m]["ext"]["a_gap_mean"], "ext_ci": r2[m]["ext"]["a_ci"], "int_a": r2[m]["int"]["a_gap_mean"], "int_ci": r2[m]["int"]["a_ci"], "b": r2[m]["b_rms_nonroll"],
                                    "c_mi": r2[m]["c_mi"], "c_p": r2[m]["c_p"]} for m in r2},
               "paired_seed1": {m: {d: {k: v for k, v in p1[m][d].items() if k != "per_episode"} for d in DEC} for m in p1},
               "paired_seed2": {m: {d: {k: v for k, v in p2[m][d].items() if k != "per_episode"} for d in DEC} for m in p2}}
        row["verdict"] = {d: ("credited" if p1["argmax"][d]["ci"][0] > 0 and p2["argmax"][d]["ci"][0] > 0 else "present") for d in DEC}
        row["lowers_decoding_both_seeds"] = {d: bool(p1["argmax"][d]["ci"][1] < 0 and p2["argmax"][d]["ci"][1] < 0) for d in DEC}
        out["ablations"][n] = row
    (s2 / "summary.json").write_text(json.dumps(out, indent=1))
    rd = lambda x: [round(x["mean"], 3), [round(c, 3) for c in x["ci"]]]
    for m in ("argmax", "sample"):
        print("try1 spread", m, {d: round(out["try1_spread"][m][d]["seed1_minus_seed2"], 3) for d in DEC})
    for n, row in out["ablations"].items():
        print(n, row["verdict"], "lowers", row["lowers_decoding_both_seeds"])
        for m in ("argmax", "sample"):
            print("  ", m, "seed2 paired", {d: rd(row["paired_seed2"][m][d]) for d in DEC}, "seed1 paired", {d: rd(row["paired_seed1"][m][d]) for d in DEC})


if __name__ == "__main__":
    main()
