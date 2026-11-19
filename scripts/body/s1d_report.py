"""WO24 report (report-only, no pass claim): report.json + report.txt in the root."""
import json
import os
import sys

ARMS = ["ii", "iii", "iii+D"]
KEYS = ["js_between", "js_half", "js_ratio", "D", "D_ci", "occupied_cells", "cell_entropy_bits", "twoafc", "mmd_between", "mmd_half"]


def load(root, arm, seed):
    return json.load(open(os.path.join(root, f"run_{arm.replace('+', '')}_s{seed}", "result.json")))


def report(root, seeds=(4, 5)):
    out = {"runs": {}, "iii+D_trajectory": {}, "statements": {}}
    lines = []
    for s in seeds:
        for arm in ARMS:
            r = load(root, arm, s)
            h = r["held"]
            out["runs"][f"{arm}_s{s}"] = {k: h.get(k) for k in KEYS}
            if arm == "iii+D":
                out["iii+D_trajectory"][f"s{s}"] = r.get("d_traj", [])
        d = out["runs"][f"iii+D_s{s}"]
        ii, iii = out["runs"][f"ii_s{s}"], out["runs"][f"iii_s{s}"]
        out["statements"][f"s{s}"] = (
            f"seed {s}: iii+D held-out D = {d['D']:.3f} (CI {d['D_ci'][0]:.3f}..{d['D_ci'][1]:.3f}), "
            f"{'reaches' if d['D'] >= 0.7 else 'does not reach'} 0.7; occupied cells iii+D {d['occupied_cells']:.1f} vs ii {ii['occupied_cells']:.1f} vs iii {iii['occupied_cells']:.1f}")
    json.dump(out, open(os.path.join(root, "report.json"), "w"), indent=1)
    lines.append("WO24 report (report-only, no pass claim). Thread count: 6 (cores 6-11). 1000 epochs.")
    lines.append(f"{'run':10s} {'JS':>6s} {'half':>6s} {'ratio':>6s} {'D':>6s} {'D CI':>15s} {'cells':>6s} {'H bits':>6s} {'2AFC':>6s} {'MMD':>8s}")
    for k, v in out["runs"].items():
        ci = v["D_ci"]
        lines.append(f"{k:10s} {v['js_between']:6.3f} {v['js_half']:6.3f} {v['js_ratio']:6.2f} {v['D']:6.3f} [{ci[0]:6.3f},{ci[1]:6.3f}] {v['occupied_cells']:6.1f} {v['cell_entropy_bits']:6.2f} "
                     f"{(v['twoafc'] or {}).get('acc', float('nan')):6.3f} {v['mmd_between']:8.4f}")
    lines += [""] + list(out["statements"].values()) + [""]
    for s, tr in out["iii+D_trajectory"].items():
        lines.append(f"iii+D {s} trajectory (epoch: D_est / mu_D, every 10th):")
        lines.append(" ".join(f"{t['epoch']}:{t['d_est']:.3f}/{t['mu_D']:.3f}" for t in tr))
    open(os.path.join(root, "report.txt"), "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    report(sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/body/s1d", (4, 5))
