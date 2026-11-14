"""WO13B extra record (overseer, pending ruling on bar (e)): per episode, for every grid point (and any other run directory given), from the saved evaluation rollout:
  e         hf_share.py (work order 13A) on the 50 Hz joint trajectory;
  acc_p99   99th percentile of the hand acceleration magnitude, m/s2 (BRAIN_SPEC 7.25 (e'1)): hand = last point of the rig's forward kinematics, 50 Hz, np.gradient twice;
  fast      share of time the hand speed exceeds 1 m/s ((e'2), np.gradient);  contact  share of time the arm touches the table (geometric, see m3f_report.hand_metrics).
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
    return R.eprime_rollout(q100)


def main():
    dirs = [Path(a) for a in sys.argv[1:]] or sorted(p.parent for p in (D / "grid").glob("*/result.json"))
    for d in dirs:
        res = {m: episode_metrics(np.load(d / "rollouts" / f"trained_{m}_4.npz")["q"]) for m in ("argmax", "sample")}
        (d / "metrics.json").write_text(json.dumps(res, indent=1))
        a = res["argmax"]
        print(f"{d.name:14s} argmax: e {a['e_mean']:.5f}  e'1 acc_p99 {a['acc_p99_mean']:7.3f} m/s2  e'2 fast {a['fast_mean']:.5f}  contact {a['contact_mean']:.4f}")


if __name__ == "__main__":
    main()
