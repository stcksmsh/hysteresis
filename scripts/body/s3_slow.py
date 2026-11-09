"""Stage 3 slow-stream lanes (work order 26A; docs/STAGE3_RULES_DATA_EVAL.md section 1). Brain env (/secondary/hyst-env/brain). Imports k5_data, edits nothing.

    s3_slow.py raw   [--threads 6]    s3/raw_l4/<split>/<id>.npy  (nb, 512) float32: per 0.5 s block the mean of Re and Im of the L4 state (256 modes). Check, train, val; resume-safe.
    s3_slow.py fit                    PCA on the train songs only -> s3/slow/norm.json (components, mean, variances, column mean/sd)
    s3_slow.py build                  s3/slow/<split>/<id>.npz  with `slow` (nb, 13): 8 L4 PCs, 8 s surprisal integral, logpow_L1..L4; z-scored by the train-corpus mean/sd
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))                 # b2, braindump, train_b7, core (as k5_data.py)
K5 = Path("/secondary/hyst-data/body/k5")
S3 = Path("/secondary/hyst-data/body/s3")
BLOCK, CHUNK = 50, 6000
NPC = 8
INT_SAMPLES = 80                                              # 8 s of the 10 Hz lane
COLS = [f"l4_pc{i + 1}" for i in range(NPC)] + ["surp_int8", "logpow_L1", "logpow_L2", "logpow_L3", "logpow_L4"]


def surprisal_integral(total10, nb):
    """total10: the 10 Hz total-surprisal lane s10[:, 4] (NaN = absent). -> (nb,) causal sums over the last 80 samples ending at sample 5 b + 4 (NaN as 0)."""
    s = np.nan_to_num(np.asarray(total10, np.float64), nan=0.0)
    c = np.concatenate([[0.0], np.cumsum(s)])
    end = 5 * np.arange(nb) + 4 + 1                           # exclusive end index into s
    end = np.minimum(end, len(s))
    start = np.maximum(end - INT_SAMPLES, 0)
    return c[end] - c[start]


def l4_blocks(model, x):
    """x (T, 46) core input -> (nb, 512) float32: block mean of Re and Im of the L4 state (the same run as k5_data.song_lanes)."""
    import torch
    T = len(x)
    nb = T // BLOCK
    st = model.init_state(1)
    parts = []
    with torch.no_grad():
        for a in range(0, T, CHUNK):
            out, st = model(torch.from_numpy(x[a:a + CHUNK])[None], st)
            h = out[3]["h"][0]
            n = len(h) // BLOCK
            if n:
                hb = h[:n * BLOCK].reshape(n, BLOCK, -1)
                parts.append(torch.cat([hb.real.mean(1), hb.imag.mean(1)], 1).numpy())
    return np.concatenate(parts, 0)[:nb].astype(np.float32)


def cmd_raw(threads, out=None, limit=None):
    import torch
    import b2
    import braindump as bd
    import train_b7
    import k5_data as K
    torch.set_num_threads(threads)
    sp = json.loads((K5 / "splits.json").read_text())
    model, meta = train_b7.load_model7(bd.CKPT)
    mean, std = bd.stats()
    t0, done = time.time(), 0.0
    for split in ("check", "train", "val"):
        d = (out or S3) / "raw_l4" / split
        d.mkdir(parents=True, exist_ok=True)
        for sid in sp[split]["ids"][:limit]:
            p = d / f"{sid}.npy"
            if p.exists():
                continue
            feats = np.load(K.CORPUS / "features" / f"{sid}.npy").astype(np.float32)
            x = b2.build_inputs(feats, json.loads((K.CORPUS / "grids" / f"{sid}.json").read_text())["beats"], mean, std)
            z = l4_blocks(model, x)
            tmp = d / f"{sid}.tmp.npy"
            np.save(tmp, z)
            tmp.replace(p)
            done += len(x) / 100.0
            print(f"{split} {sid} {len(x) / 100:.0f}s (elapsed {time.time() - t0:.0f}s, {done / 3600:.2f} audio h)", flush=True)


def cmd_fit():
    sp = json.loads((K5 / "splits.json").read_text())
    n, s, ss = 0, None, None
    for sid in sp["train"]["ids"]:
        z = np.load(S3 / "raw_l4" / "train" / f"{sid}.npy").astype(np.float64)
        if s is None:
            s, ss = np.zeros(z.shape[1]), np.zeros((z.shape[1], z.shape[1]))
        n += len(z)
        s += z.sum(0)
        ss += z.T @ z
    mu = s / n
    cov = ss / n - np.outer(mu, mu)
    w, v = np.linalg.eigh(cov)
    o = np.argsort(w)[::-1]
    w, v = w[o], v[:, o]
    comp = v[:, :NPC].T.copy()
    for i in range(NPC):
        if comp[i][np.argmax(np.abs(comp[i]))] < 0:
            comp[i] = -comp[i]
    ratio = w / w.sum()
    # column mean / sd of the 13 slow columns over the train blocks (second pass)
    cs, css, cn = np.zeros(13), np.zeros(13), 0
    for sid in sp["train"]["ids"]:
        c = raw_columns("train", sid, comp, mu)
        cs += c.sum(0)
        css += (c.astype(np.float64) ** 2).sum(0)
        cn += len(c)
    cm = cs / cn
    csd = np.sqrt(np.maximum(css / cn - cm ** 2, 0.0))
    csd = np.where(csd < 1e-8, 1.0, csd)
    commit = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=HERE).stdout.strip()
    norm = {"columns": COLS, "pca_mean": mu.tolist(), "pca_components": comp.tolist(), "eigenvalues_top8": w[:NPC].tolist(), "explained_variance_ratio_top8": ratio[:NPC].tolist(),
            "explained_variance_top8_cumulative": float(ratio[:NPC].sum()), "col_mean": cm.tolist(), "col_sd": csd.tolist(), "n_train_blocks": int(cn), "n_train_songs": len(sp["train"]["ids"]),
            "checkpoint": "B7 epoch 6", "git_commit": commit}
    (S3 / "slow").mkdir(parents=True, exist_ok=True)
    (S3 / "slow" / "norm.json").write_text(json.dumps(norm))
    print("blocks", cn, "explained variance top 8:", np.round(ratio[:NPC], 4).tolist(), "cumulative", round(float(ratio[:NPC].sum()), 4))


def raw_columns(split, sid, comp, mu):
    """Unnormalised 13 columns of one song (nb, 13) float64."""
    raw = np.load(S3 / "raw_l4" / split / f"{sid}.npy").astype(np.float64)
    z = np.load(K5 / "lanes" / split / f"{sid}.npz")
    nb = len(z["y"])
    assert len(raw) == nb, (sid, len(raw), nb)
    pcs = (raw - mu) @ comp.T
    return np.concatenate([pcs, surprisal_integral(z["s10"][:, 4], nb)[:, None], np.asarray(z["y"][:, 4:8], np.float64)], 1)


def load_norm():
    n = json.loads((S3 / "slow" / "norm.json").read_text())
    return np.array(n["pca_components"]), np.array(n["pca_mean"]), np.array(n["col_mean"]), np.array(n["col_sd"])


def slow_of(split, sid, norm=None):
    comp, mu, cm, csd = norm or load_norm()
    return ((raw_columns(split, sid, comp, mu) - cm) / csd).astype(np.float32)


def cmd_build():
    sp = json.loads((K5 / "splits.json").read_text())
    norm = load_norm()
    for split in ("train", "val", "check"):
        d = S3 / "slow" / split
        d.mkdir(parents=True, exist_ok=True)
        for sid in sp[split]["ids"]:
            p = d / f"{sid}.npz"
            if not p.exists():
                tmp = d / f"{sid}.tmp.npz"
                np.savez_compressed(tmp, slow=slow_of(split, sid, norm))
                tmp.replace(p)
        print(split, "done", len(sp[split]["ids"]), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("raw", "fit", "build"))
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--out", help="raw only, test: root dir instead of s3")
    ap.add_argument("--limit", type=int, help="raw only, test: first N songs per split")
    a = ap.parse_args()
    {"raw": lambda: cmd_raw(a.threads, Path(a.out) if a.out else None, a.limit), "fit": cmd_fit, "build": cmd_build}[a.what]()


if __name__ == "__main__":
    main()
