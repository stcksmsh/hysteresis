"""WO25 chain: arms iii+D (rising), iii+Df (falling) x seeds 6,7 (rules section 13), resume-safe, then the report.
    python -u s1f_chain.py [--epochs 1000] [--root /secondary/hyst-data/body/s1f] [--seeds 6,7]"""
import argparse
import os
import time

import s1f_report
import s1_toy as S

RUNS = ["iii+D", "iii+Df"]


def run_dir(root, arm, seed):
    return os.path.join(root, f"run_{arm.replace('+', '')}_s{seed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=1000)
    ap.add_argument("--root", default="/secondary/hyst-data/body/s1f")
    ap.add_argument("--seeds", default="6,7")
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
    s1f_report.report(a.root, seeds)
    print("done", time.time() - t0, flush=True)
