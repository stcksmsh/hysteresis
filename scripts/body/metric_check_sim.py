"""WO46: whole-sequence realised q50 vs WO43's windowed q50 of the same sequence (docs/METRIC_RULES.md section 2). Brain env.   metric_check_sim.py [N]
For N seeded finished FineDance/Phantom/Motorica sequences and every kept window: rows 1000w..1000w+1001 of the whole-sequence q50 against controls/q50 (window recipe). Reports the
std of the joint difference (deg; yaw and roll are re-referenced per window, so an offset is expected), the lamp z and lamp speed differences per sequence -> metric/sim_check.json. Differences come from the window re-referencing of yaw/roll and the start state."""
import json
import sys
from pathlib import Path

import numpy as np

B = Path("/secondary/hyst-data/body")


def main(n=12):
    rng = np.random.default_rng(46109)
    cand = [(ds, p) for ds in ("finedance", "phantom", "motorica", "aioz") for p in sorted((B / "metric/q50" / ds).glob("*.npz")) if (B / "controls/q50" / ds / p.name).exists()]
    out = {}
    for i in rng.choice(len(cand), min(n, len(cand)), replace=False):
        ds, p = cand[i]
        a, b = np.load(p), np.load(B / "controls/q50" / ds / p.name)
        d, dl = [], []
        for k, w in enumerate(b["win"]):
            s = slice(1000 * int(w), 1000 * int(w) + 1001)
            if s.stop > len(a["q50"]):
                continue
            diff = a["q50"][s].astype(float) - b["q50"][k].astype(float)
            d.append(diff.std(0))                                                       # offset-free: the window run re-references yaw and roll to the window start
            la, lb = a["lamp"][s].astype(float), b["lamp"][k]
            sp = lambda x: np.linalg.norm(np.gradient(x, axis=0) * 50, axis=1)         # noqa: E731
            dl.append([np.abs(la[:, 2] - lb[:, 2]).mean(), np.abs(sp(la) - sp(lb)).mean()])
        if d:
            out[f"{ds}/{p.name}"] = dict(windows=len(d), joint_diff_std_deg=np.mean(d, 0).round(3).tolist(), lamp_z_abs_m=float(np.mean(dl, 0)[0]), lamp_speed_abs_m_s=float(np.mean(dl, 0)[1]))
            print(f"{ds}/{p.name}", out[f"{ds}/{p.name}"], flush=True)
    (B / "metric/sim_check.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 12)
