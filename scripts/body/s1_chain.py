"""Stage 1 chain (work order 20): the 12 runs as one unit, resume-safe (a run with result.json is skipped), then summary.
    python -u s1_chain.py [--epochs 1000] [--root /secondary/hyst-data/body/s1]"""
import argparse
import os
import time

import s1_summary
import s1_toy as S

RUNS = [("0", 0.0), ("i", 0.0), ("ii", 0.0), ("iii", 0.0), ("iv", 0.05), ("iv", 0.5)]


def run_dir(root, arm, lam, seed):
    return os.path.join(root, f"run_{arm}" + (f"_{lam}" if arm == "iv" else "") + f"_s{seed}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=1000)
    ap.add_argument("--root", default="/secondary/hyst-data/body/s1")
    a = ap.parse_args()
    data = S.build_data()
    t0 = time.time()
    for seed in (0, 1):
        for arm, lam in RUNS:
            d = run_dir(a.root, arm, lam, seed)
            if os.path.exists(os.path.join(d, "result.json")):
                print("skip", d, flush=True)
                continue
            print(f"=== {d} start {time.time() - t0:.0f}s", flush=True)
            S.run(arm, seed, a.epochs, lam, d, data)
    s1_summary.summarise(a.root, a.epochs)
    print("done", time.time() - t0, flush=True)
