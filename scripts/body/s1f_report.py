"""WO25 report: rising (iii+D) vs falling (iii+Df), seeds 6 and 7, rule outcome of BRAIN_SPEC 7.39.2 / rules section 13.
Metrics are s1d_report's (KEYS, load). Writes report.json + report.txt in the root."""
import json
import os
import sys

import numpy as np

from s1d_report import KEYS, load

ARMS = ["iii+D", "iii+Df"]


def decide(runs, seeds):
    """runs[f'{arm}_s{seed}'] -> dict with D, mmd_between. Returns the rule outcome and the numbers it used."""
    fall_D = {s: runs[f"iii+Df_s{s}"]["D"] for s in seeds}
    mmd_f = {s: runs[f"iii+Df_s{s}"]["mmd_between"] for s in seeds}
    mmd_r = {s: runs[f"iii+D_s{s}"]["mmd_between"] for s in seeds}
    both_D = all(d >= 0.7 for d in fall_D.values())
    mean_f, mean_r = float(np.mean(list(mmd_f.values()))), float(np.mean(list(mmd_r.values())))
    mean_ok = mean_f >= mean_r
    per_seed_ok = {s: mmd_f[s] >= mmd_r[s] for s in seeds}
    outcome = "falling" if (both_D and mean_ok) else "rising"
    per_seed_outcome = "falling" if (both_D and all(per_seed_ok.values())) else "rising"
    return {"outcome": outcome, "per_seed_reading_outcome": per_seed_outcome, "readings_agree": outcome == per_seed_outcome,
            "falling_D": fall_D, "falling_D_ge_0.7_both": both_D,
            "mmd_falling": mmd_f, "mmd_rising": mmd_r, "mmd_falling_mean": mean_f, "mmd_rising_mean": mean_r,
            "mean_mmd_ok": mean_ok, "per_seed_mmd_ok": per_seed_ok}


def report(root, seeds=(6, 7)):
    out = {"runs": {}, "trajectory": {}}
    for s in seeds:
        for arm in ARMS:
            r = load(root, arm, s)
            out["runs"][f"{arm}_s{s}"] = {k: r["held"].get(k) for k in KEYS}
            out["trajectory"][f"{arm}_s{s}"] = r.get("d_traj", [])
    out["rule"] = decide(out["runs"], seeds)
    json.dump(out, open(os.path.join(root, "report.json"), "w"), indent=1)
    L = ["WO25 report (rules section 13). Thread count: 6 (cores 6-11). 1000 epochs. Seeds " + ",".join(map(str, seeds)) + "."]
    L.append(f"{'run':11s} {'JS':>6s} {'half':>6s} {'ratio':>6s} {'D':>6s} {'D CI':>15s} {'cells':>6s} {'H bits':>6s} {'2AFC':>6s} {'MMD':>8s}")
    for k, v in out["runs"].items():
        ci = v["D_ci"]
        L.append(f"{k:11s} {v['js_between']:6.3f} {v['js_half']:6.3f} {v['js_ratio']:6.2f} {v['D']:6.3f} [{ci[0]:6.3f},{ci[1]:6.3f}] {v['occupied_cells']:6.1f} {v['cell_entropy_bits']:6.2f} "
                 f"{(v['twoafc'] or {}).get('acc', float('nan')):6.3f} {v['mmd_between']:8.4f}")
    r = out["rule"]
    L += ["", "Rule (BRAIN_SPEC 7.39.2): falling if held-out D >= 0.7 on both seeds AND falling MMD >= rising mean MMD.",
          f"falling D per seed: {r['falling_D']} -> both >= 0.7: {r['falling_D_ge_0.7_both']}",
          f"MMD rising  per seed {r['mmd_rising']}  mean {r['mmd_rising_mean']:.5f}",
          f"MMD falling per seed {r['mmd_falling']}  mean {r['mmd_falling_mean']:.5f}",
          f"mean reading (default): MMD ok = {r['mean_mmd_ok']}; per-seed reading: {r['per_seed_mmd_ok']}",
          f"OUTCOME (mean reading): {r['outcome']}",
          ("Per-seed and mean readings agree." if r["readings_agree"] else f"Per-seed and mean readings DISAGREE (per-seed gives {r['per_seed_reading_outcome']}); the planner rules.")]
    for k, tr in out["trajectory"].items():
        L += ["", f"{k} trajectory (epoch: D_est / mu_D, every 10th):", " ".join(f"{t['epoch']}:{t['d_est']:.3f}/{t['mu_D']:.3f}" for t in tr)]
    open(os.path.join(root, "report.txt"), "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/body/s1f", (6, 7))
