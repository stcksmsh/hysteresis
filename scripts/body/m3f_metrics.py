"""WO13B extra record (overseer, pending ruling on bar (e)): per episode, for every grid point (and any other run directory given), from the saved evaluation rollout:
  e         hf_share.py (work order 13A) on the 50 Hz joint trajectory;
  acc_p99   99th percentile of the hand acceleration magnitude, m/s2: hand = point 5 of the rig's forward kinematics (m3f_report.fk_points), 50 Hz, central second difference;
  fast      share of time the hand speed exceeds 1 m/s, speed = |p[i+1] - p[i-1]| x 50 / 2 (central difference).
Writes DIR/metrics.json for each directory (argmax and sampled rollouts) and prints the table.  Usage: m3f_metrics.py [DIR ...]   (default: every grid point).
"""
import json
import sys
from pathlib import Path

import numpy as np

import hf_share as H
import m3f_report as R

D = Path("/secondary/hyst-data/body/m3f")


def episode_metrics(q100):
    q = np.asarray(q100).reshape(q100.shape[0], -1, 5)[:, ::2]
    out = {"e": [], "acc_p99": [], "fast": []}
    for e in q:
        h = R.fk_points(e)[:, 5]
        acc = np.linalg.norm(h[2:] - 2 * h[1:-1] + h[:-2], axis=1) * 50.0 ** 2
        spd = np.linalg.norm(h[2:] - h[:-2], axis=1) * 50.0 / 2.0
        out["e"].append(H.hf_share(e, 50.0))
        out["acc_p99"].append(float(np.percentile(acc, 99)))
        out["fast"].append(float((spd > 1.0).mean()))
    return out


def main():
    dirs = [Path(a) for a in sys.argv[1:]] or sorted(p.parent for p in (D / "grid").glob("*/result.json"))
    for d in dirs:
        res = {m: episode_metrics(np.load(d / "rollouts" / f"trained_{m}_4.npz")["q"]) for m in ("argmax", "sample")}
        (d / "metrics.json").write_text(json.dumps(res, indent=1))
        a = res["argmax"]
        print(f"{d.name:14s} argmax: e {np.mean(a['e']):.5f}  acc_p99 {np.mean(a['acc_p99']):7.2f} m/s2  fast {np.mean(a['fast']):.4f}")


if __name__ == "__main__":
    main()
