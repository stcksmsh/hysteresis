"""WO24 chain: arms ii, iii, iii+D x seeds 4,5 (rules section 12), resume-safe, then the report.
    python -u s1d_chain.py [--epochs 1000] [--root /secondary/hyst-data/body/s1d] [--seeds 4,5]"""
import argparse
import os
import time

import s1d_report
import s1_toy as S

RUNS = ["ii", "iii", "iii+D"]


def run_dir(root, arm, seed):
    return os.path.join(root, f"run_{arm.replace('+', '')}_s{seed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=1000)
    ap.add_argument("--root", default="/secondary/hyst-data/body/s1d")
    ap.add_argument("--seeds", default="4,5")
    a = ap.parse_args()
    seeds = tuple(int(x) for x in a.seeds.split(","))
    data = S.build_data()
    t0 = time.time()
    for seed in seeds:
        for arm in RUNS:
            d = run_dir(a.root, arm, seed)
            if os.path.exists(os.path.join(d, "result.json")):
                print("skip", d, flush=True)
                continue
            print(f"=== {d} start {time.time() - t0:.0f}s", flush=True)
            S.run(arm, seed, a.epochs, 0.0, d, data)
    s1d_report.report(a.root, seeds)
    print("done", time.time() - t0, flush=True)
