"""Stage 1 summary: summary.json with every measure per arm and seed, the collapse precondition first, then the verdict (docs/STAGE1_RULES.md sections 8 and 10)."""
import json
import os
import sys

import numpy as np

KEYS = ["js_between", "js_half", "js_ratio", "D", "D_common_probe", "occupied_cells", "occupied_cells_half", "cell_entropy_bits", "cell_entropy_bits_half",
        "distinct_postures", "mmd_between", "mmd_half", "peak_hand_speed"]
RUNS = [("0", 0.0), ("i", 0.0), ("ii", 0.0), ("iii", 0.0), ("iv", 0.05), ("iv", 0.5)]


def load(root, arm, lam, seed):
    p = os.path.join(root, f"run_{arm}" + (f"_{lam}" if arm == "iv" else "") + f"_s{seed}", "result.json")
    return json.load(open(p))


def row(r):
    h = r["held"]
    o = {k: h.get(k) for k in KEYS}
    o["twoafc"] = h.get("twoafc"); o["D_ci"] = h.get("D_ci"); o["val_js"] = r["val"]["js_between"]; o["val_D"] = r["val"]["D"]
    o["untrained"] = r["untrained"]
    return o


def summarise(root, epochs=1000, seeds=(0, 1)):
    runs = {}
    for seed in seeds:
        for arm, lam in RUNS:
            nm = arm + (f"({lam})" if arm == "iv" else "")
            runs[f"{nm}_s{seed}"] = row(load(root, arm, lam, seed))
    out = {"epochs": epochs, "runs": runs}
    # collapse precondition: both seeds, JS and occupied cells <= 1/3 of the seed's untrained policy
    col = {}
    for arm in ("0", "i"):
        per = []
        for s in seeds:
            r = runs[f"{arm}_s{s}"]; u = r["untrained"]
            per.append({"seed": s, "js_ratio_to_untrained": r["js_between"] / u["js_between"], "cells_ratio_to_untrained": r["occupied_cells"] / u["occupied_cells"],
                        "collapsed": bool(r["js_between"] <= u["js_between"] / 3 and r["occupied_cells"] <= u["occupied_cells"] / 3)})
        col[arm] = {"per_seed": per, "collapsed": all(p["collapsed"] for p in per)}
    ref = "i" if col["i"]["collapsed"] else ("0" if col["0"]["collapsed"] else None)
    out["collapse_precondition"] = {**col, "reference": ref}
    if ref is None:
        out["verdict"] = "NO VERDICT: neither arm 0 nor arm i collapsed (7.35.2: stop and report)"
    else:
        refjs = float(np.mean([runs[f"{ref}_s{s}"]["js_between"] for s in seeds]))
        sel = {}
        for s in seeds:    # lambda for iv chosen per seed on the validation split: JS if D >= 0.7 else D
            cand = {l: runs[f"iv({l})_s{s}"] for l in (0.05, 0.5)}
            sel[s] = max(cand, key=lambda l: cand[l]["val_js"] if cand[l]["val_D"] >= 0.7 else -1 + cand[l]["val_D"])

        def arm_ok(arm, k, dmin=None):
            res = []
            for s in seeds:
                r = runs[f"iv({sel[s]})_s{s}" if arm == "iv" else f"{arm}_s{s}"]
                res.append(r["js_between"] >= k * refjs and (dmin is None or r["D"] >= dmin))
            return all(res)
        order = [a for a in ("i", "ii", "iii", "iv") if a != ref and not (ref == "0" and False)]
        out["verdict_detail"] = {"reference_arm": ref, "reference_js_mean": refjs, "lambda_chosen_per_seed": {str(s): sel[s] for s in seeds},
                                 "iv_js_over_ref": {str(s): runs[f"iv({sel[s]})_s{s}"]["js_between"] / refjs for s in seeds},
                                 "iv_D": {str(s): runs[f"iv({sel[s]})_s{s}"]["D"] for s in seeds},
                                 "smallest_arm_reaching_2x": next((a for a in order if arm_ok(a, 2)), None)}
        out["verdict"] = "PASS" if arm_ok("iv", 3, 0.7) else "FAIL"
    json.dump(out, open(os.path.join(root, "summary.json"), "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("collapse_precondition", "verdict")}, indent=1))
    return out


if __name__ == "__main__":
    summarise(sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/body/s1")
