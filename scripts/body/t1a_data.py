"""WO38 T1a data (rules docs/T1A_RULES.md section 1): kept 20 s windows of the T0 npz files -> t1a/windows_<split>.npz and t1a/scale.json. Brain env (numpy).
    t1a_data.py build      all three splits
"""
import json
import sys
from pathlib import Path

import numpy as np

T0 = Path("/secondary/hyst-data/body/t0")
OUT = Path("/secondary/hyst-data/body/t1a")
COPIES = ("V1", "V2", "V1m", "V2m")
WIN_ROWS, CH = 2000, 50                                                   # 20 s and 0.5 s at 100 Hz


def kept_windows(z):
    """npz (T0 layout) -> (N, 2000, 5) float32 gesture of its kept windows and their window indices; chunks never cross a window edge"""
    keep = np.flatnonzero(z["win_pass"])
    g = np.asarray(z["gesture"], np.float32)
    return (np.stack([g[i * WIN_ROWS:(i + 1) * WIN_ROWS] for i in keep]) if len(keep) else np.zeros((0, WIN_ROWS, 5), np.float32)), keep


def to_chunks(w):
    """(N, 2000, 5) -> (N, 40, 50, 5)"""
    return w.reshape(len(w), WIN_ROWS // CH, CH, w.shape[-1])


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    acc = {s: dict(g=[], w=[], src=[], copy=[], dancer=[], win=[]) for s in ("train", "validation", "test")}
    dancers = {}
    for ds, src in (("finedance", 0), ("aioz", 1)):
        for p in sorted((T0 / "seq" / ds).glob("*.npz")):
            z = np.load(p)
            g, keep = kept_windows(z)
            if not len(g):
                continue
            key, copy = p.stem.split("__")
            a = acc[str(z["split"])]
            a["g"].append(g)
            n = len(g)
            a["w"] += [float(z["weight"])] * n
            a["src"] += [src] * n
            a["copy"] += [COPIES.index(copy)] * n
            a["dancer"] += [dancers.setdefault(key, len(dancers))] * n
            a["win"] += keep.tolist()
    names = np.array(sorted(dancers, key=dancers.get))
    sd = np.concatenate(acc["train"]["g"]).reshape(-1, 5).std(0)
    (OUT / "scale.json").write_text(json.dumps(dict(sd=sd.tolist(), joints=["base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll"], n_train_rows=int(sum(len(x) for x in acc["train"]["g"]) * WIN_ROWS))))
    counts = {}
    for s, a in acc.items():
        g = np.concatenate(a["g"])
        np.savez(OUT / f"windows_{s}.npz", g=g, w=np.array(a["w"], np.float32), src=np.array(a["src"], np.int8), copy=np.array(a["copy"], np.int8), dancer=np.array(a["dancer"], np.int32),
                 win=np.array(a["win"], np.int32), dancers=names)
        src = np.array(a["src"])
        counts[s] = dict(windows=len(g), chunks=len(g) * WIN_ROWS // CH, finedance_chunks=int((src == 0).sum()) * 40, aioz_chunks=int((src == 1).sum()) * 40)
    (OUT / "counts.json").write_text(json.dumps(counts, indent=1))
    print(json.dumps(counts), "sd", sd.round(2).tolist())


def load(split):
    """-> dict(g (N,2000,5) in degrees, w, src, copy, dancer, win) of one split"""
    z = np.load(OUT / f"windows_{split}.npz")
    return {k: z[k] for k in z.files if k != "dancers"}


def scale():
    return np.array(json.loads((OUT / "scale.json").read_text())["sd"], np.float32)


if __name__ == "__main__":
    build()
