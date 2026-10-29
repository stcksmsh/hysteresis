"""B3 corpus step 8: fast features (44 columns, 100 Hz) for every file of a list, plus training-side statistics.

usage: corpus_features.py FINAL_LIST_CSV [WORKERS]   (columns: id, split; audio is audio/<id:06d>.mp3)
Writes features/<id:06d>.npy (float32, frames x 44), skips files already done.
Statistics: per-column mean and SD (float64, population SD) over every frame of the TRAIN split only,
written to feature_stats.npz and feature_stats.json (with sha256 of the npz, the track count, the frame count).
"""
import hashlib
import json
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fast_features as ff  # noqa: E402

C = "/secondary/hyst-data/brain/corpus/"


def work(i):
    out = f"{C}features/{i:06d}.npy"
    if os.path.exists(out):
        return i, "have"
    x = ff.fast_features(ff.load_mono(f"{C}audio/{i:06d}.mp3"))
    np.save(out + ".tmp.npy", x.astype(np.float32))
    os.replace(out + ".tmp.npy", out)
    return i, "new"


def stats(train_ids):
    n, s, q = 0, np.zeros(ff.N_COLUMNS), np.zeros(ff.N_COLUMNS)
    for i in train_ids:
        x = np.load(f"{C}features/{i:06d}.npy").astype(np.float64)
        n += len(x)
        s += x.sum(0)
        q += (x * x).sum(0)
    mean = s / n
    sd = np.sqrt(np.maximum(q / n - mean ** 2, 0.0))
    return n, mean, sd


def main():
    import csv
    rows = list(csv.DictReader(open(sys.argv[1])))
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 16
    os.makedirs(C + "features", exist_ok=True)
    ids = [int(r["id"]) for r in rows]
    with Pool(workers) as p:
        for k, (i, how) in enumerate(p.imap_unordered(work, ids, chunksize=2)):
            if k % 100 == 99:
                print(f"features {k + 1}/{len(ids)}", flush=True)
    train = [int(r["id"]) for r in rows if r["split"] == "train"]
    n, mean, sd = stats(train)
    np.savez(C + "feature_stats.npz", mean=mean, sd=sd)
    h = hashlib.sha256(open(C + "feature_stats.npz", "rb").read()).hexdigest()
    json.dump({"columns": ff.COLUMNS, "train_tracks": len(train), "train_frames": int(n), "sd_min": float(sd.min()),
               "sha256_npz": h, "mean": mean.tolist(), "sd": sd.tolist()}, open(C + "feature_stats.json", "w"), indent=1)
    print(f"stats on {len(train)} train tracks, {n} frames, sha256 {h}, min SD {sd.min():.3g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
