"""WO22 verdict (BRAIN_SPEC 7.37.1, docs/STAGE1_RULES.md section 11). Reads run_*/result.json of seeds 2 and 3; prints and saves verdict.json/.txt.
    python s1r_verdict.py [--root /secondary/hyst-data/body/s1r] [--old /secondary/hyst-data/body/s1]"""
import argparse
import json
import os

import numpy as np

ARMS = [("0", "0", 0.0), ("i", "i", 0.0), ("ii", "ii", 0.0), ("iii", "iii", 0.0), ("iv(0.05)", "iv", 0.05), ("iv(0.5)", "iv", 0.5)]
SEEDS = (2, 3)


def load_runs(root, seeds):
    out = {}
    for name, arm, lam in ARMS:
        for s in seeds:
            p = os.path.join(root, f"run_{arm}" + (f"_{lam}" if arm == "iv" else "") + f"_s{s}", "result.json")
            if os.path.exists(p):
                out[(name, s)] = json.load(open(p))
    return out


def verdict(runs, seeds=SEEDS):
    """runs[(arm_name, seed)] = result.json dict. Pure function of the data."""
    res = {"precondition": {}}
    for a in ("0", "i"):
        ratios = {s: runs[(a, s)]["held"]["js_between"] / runs[(a, s)]["held"]["js_half"] for s in seeds}
        res["precondition"][a] = {"js_ratio": ratios, "met": all(r <= 1.5 for r in ratios.values())}
    ref = "i" if res["precondition"]["i"]["met"] else ("0" if res["precondition"]["0"]["met"] else None)
    res["reference_arm"] = ref
    if ref is None:
        res["verdict"] = "no verdict (collapse precondition not met: neither arm 0 nor arm i has JS ratio <= 1.5 on both seeds)"
        return res
    refjs = float(np.mean([runs[(ref, s)]["held"]["js_between"] for s in seeds]))
    res["reference_js"] = refjs
    arms = {}
    for name in ("ii", "iii", "iv(0.05)", "iv(0.5)"):
        js = {s: runs[(name, s)]["held"]["js_between"] for s in seeds}
        D = {s: runs[(name, s)]["held"]["D"] for s in seeds}
        f = float(np.mean(list(js.values()))) / refjs
        dok = all(d >= 0.7 for d in D.values())
        arms[name] = {"js": js, "D": D, "factor": f, "D_ok_all_seeds": dok, "reaches_2x": bool(f >= 2 and dok), "reaches_3x": bool(f >= 3 and dok)}
    res["arms"] = arms
    iv = [arms["iv(0.05)"], arms["iv(0.5)"]]

    def reach(k):
        return {"ii": arms["ii"][k], "iii": arms["iii"][k], "iv": any(x[k] for x in iv)}
    r2 = reach("reaches_2x")
    res["smallest_arm_2x"] = next((a for a in ("ii", "iii", "iv") if r2[a]), None)
    res["iv_reaches_3x"] = reach("reaches_3x")["iv"]
    res["verdict"] = f"reference arm {ref}; smallest arm reaching >=2x with D>=0.7: {res['smallest_arm_2x']}; iv reaches >=3x: {res['iv_reaches_3x']}"
    return res


def table(runs, seeds):
    L = [f"{'arm':9s} seed {'JS':>7s} {'JSratio':>7s} {'D':>6s} {'cells':>7s} {'entropy':>7s} {'2AFC':>6s} {'MMD':>7s}"]
    for name, _, _ in ARMS:
        for s in seeds:
            r = runs.get((name, s))
            if r is None:
                continue
            h = r["held"]
            L.append(f"{name:9s} {s:4d} {h['js_between']:7.3f} {h['js_between'] / h['js_half']:7.2f} {h['D']:6.3f} {h['occupied_cells']:7.1f} "
                     f"{h['cell_entropy_bits']:7.2f} {h['twoafc']['acc']:6.3f} {h['mmd_between']:7.4f}")
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/secondary/hyst-data/body/s1r")
    ap.add_argument("--old", default="/secondary/hyst-data/body/s1")
    a = ap.parse_args()
    runs = load_runs(a.root, SEEDS)
    res = verdict(runs)
    txt = ["WO22 Stage 1 rerun, seeds 2 and 3 (7.37.1)", ""]
    for arm, p in res["precondition"].items():
        txt.append(f"precondition arm {arm}: JS ratios {p['js_ratio']} -> {'met' if p['met'] else 'not met'}")
    txt.append(f"VERDICT: {res['verdict']}")
    if "arms" in res:
        for n, x in res["arms"].items():
            txt.append(f"  {n}: mean JS / ref = {x['factor']:.2f}, D per seed {x['D']}, 2x {x['reaches_2x']}, 3x {x['reaches_3x']}")
    txt += ["", table(runs, SEEDS), "", "Seeds 0/1 (WO20): informational only (7.37.1)", table(load_runs(a.old, (0, 1)), (0, 1))]
    out = "\n".join(txt)
    print(out)
    json.dump(res, open(os.path.join(a.root, "verdict.json"), "w"), indent=1, default=str)
    open(os.path.join(a.root, "verdict.txt"), "w").write(out + "\n")
