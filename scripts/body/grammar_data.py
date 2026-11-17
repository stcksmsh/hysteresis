"""WO45 data for A, the motor grammar (docs/A_RULES.md sections 1-3). Brain env.

    grammar_data.py scan                      every input file loaded and checked (empty / malformed / non-finite) -> grammar/scan.json; nothing is trained on a file that fails
    grammar_data.py encode [THREADS]          frozen run-B encoder (t1a2/runB/best.pt) on every kept window of every dataset: code1, code2, a_n, absolute posture, controls v2 -> grammar/win_<ds>.npz
    grammar_data.py fit                       vigour bins + absolute-posture residual vocabulary (2 x 256) from the TRAIN split, assign, per-code control statistics -> grammar/vocab.npz, stats.npz, vocab.json
Window = 40 tokens of 0.5 s (T0 20 s window, kept = win_pass). Token k covers rows [50 k, 50 k + 50) of the 100 Hz gesture / posture rows of its window.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
B = Path("/secondary/hyst-data/body")
G = B / "grammar"                           # WO45 data and first-run models: read-only for WO49
OUT = Path(os.environ.get("HYST_A_OUT", str(B / "grammar2")))   # WO49 outputs (runs, checks, logs, look)
ROOTS = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}
DS = list(ROOTS)
COPIES = ["V1", "V2", "V1m", "V2m"]
FD_LABELS = Path("/secondary/hyst-data/datasets/finedance/data/finedance/label_json")
RUNB, SCALE = B / "t1a2/runB/best.pt", B / "t1a/scale.json"
NT, CH, NV, NP, SEED_KM = 40, 50, 32, 256, 45001
YAW_ROLL = (0, 4)
AGG_MIN = 5                                  # per-code statistics: codes with fewer tokens are shrunk to the global mean with weight AGG_MIN
CD = 18                                      # controls_lib.CTL_DIM


def ctl_files(ds):
    return sorted((G / "ctl" / ds).glob("*.npz"))


def genre_of(ds, name, z):
    if ds == "motorica":
        return "mo_" + str(z["style"])
    if ds == "finedance":
        try:
            return str(json.loads((FD_LABELS / f"{name.split('__')[0].split('_')[1]}.json").read_text())["style1"])
        except (OSError, KeyError, ValueError):
            return "unlabelled"
    return "unlabelled"


def scan():
    out = {}
    for ds in DS:
        bad, nwin, nfile = [], 0, 0
        for p in ctl_files(ds):
            try:
                c = np.load(p)
                t = np.load(ROOTS[ds] / p.name)
                win = c["win"]
                ctl = c["ctl"]
                n_win = int(t["n_win"])
                if p.stem.split("__")[1] not in COPIES:
                    raise ValueError("copy suffix")
                if ctl.shape != (len(win), NT, CD) or not np.isfinite(ctl).all():
                    raise ValueError(f"ctl {ctl.shape} finite={bool(np.isfinite(ctl).all())}")
                if len(win) == 0 or win.max() >= n_win or not np.asarray(t["win_pass"])[win].all():
                    raise ValueError("windows not kept / out of range / empty")
                g, po = np.asarray(t["gesture"]), np.asarray(t["posture"])
                if len(g) < (win.max() + 1) * NT * CH or len(po) < (win.max() + 1) * NT * CH or not np.isfinite(g).all() or not np.isfinite(po).all():
                    raise ValueError("rows short or non-finite")
                nwin += len(win)
                nfile += 1
            except Exception as e:
                bad.append((p.name, repr(e)))
        out[ds] = dict(files=nfile, windows=nwin, tokens=nwin * NT, bad=bad)
    (G / "scan.json").write_text(json.dumps(out, indent=1))
    print("SCAN", json.dumps({k: {a: (b if a != "bad" else len(b)) for a, b in v.items()} for k, v in out.items()}), flush=True)
    return out


def encode(threads=8):
    import torch
    import t1b_tokens as TK
    import t1a_model as M
    torch.set_num_threads(threads)
    sd = np.asarray(json.loads(SCALE.read_text())["sd"], np.float32)
    model = TK.load_vq()
    bad = {ds: {n for n, _ in v["bad"]} for ds, v in json.loads((G / "scan.json").read_text()).items()}
    for ds in DS:
        dst = G / f"win_{ds}.npz"
        if dst.exists():
            continue
        acc = {k: [] for k in ("code1", "code2", "an", "post", "ctl")}
        meta = {k: [] for k in ("copy", "genre", "weight", "split", "group", "key", "win")}
        for p in ctl_files(ds):
            if p.name in bad[ds]:
                continue
            c, t = np.load(p), np.load(ROOTS[ds] / p.name)
            win = c["win"]
            g, po = np.asarray(t["gesture"], np.float32), np.asarray(t["posture"], np.float64)
            rows = np.concatenate([np.arange(w * NT * CH, (w + 1) * NT * CH) for w in win])
            x = torch.from_numpy(g[rows] / sd).reshape(len(win) * NT, CH, 5)
            with torch.no_grad():
                _, a_n, u = M.vigour(x)
                _, (i1, i2), _ = model.vq(model.enc(u))
            pw = po[rows].reshape(len(win), NT, CH, 5)
            post = pw.mean(2)                                                 # absolute posture of the token = mean of its 50 rows
            post[:, :, list(YAW_ROLL)] -= pw[:, :1, 0][:, :, list(YAW_ROLL)]  # yaw and roll relative to the window's first row
            gen = genre_of(ds, p.stem, t)
            acc["code1"].append(i1.numpy().reshape(len(win), NT).astype(np.int16))
            acc["code2"].append(i2.numpy().reshape(len(win), NT).astype(np.int16))
            acc["an"].append(a_n.numpy().reshape(len(win), NT).astype(np.float32))
            acc["post"].append(post.astype(np.float32))
            acc["ctl"].append(c["ctl"])
            meta["copy"] += [COPIES.index(p.stem.split("__")[1])] * len(win)
            meta["genre"] += [gen] * len(win)
            meta["weight"] += [float(t["weight"])] * len(win)
            meta["split"] += [str(t["split"])] * len(win)
            meta["group"] += [str(t["group"])] * len(win)
            meta["key"] += [p.stem] * len(win)
            meta["win"] += [int(w) for w in win]
        np.savez(str(dst) + ".tmp.npz", **{k: np.concatenate(v) for k, v in acc.items()}, **{k: np.array(v) for k, v in meta.items()})
        Path(str(dst) + ".tmp.npz").replace(dst)
        print("encoded", ds, sum(len(a) for a in acc["code1"]), "windows", flush=True)


def load(split=None, ds=None):
    """all windows (optionally one split / dataset) as dict of arrays; adds dsid (index in DS)"""
    parts = []
    for i, d in enumerate(DS):
        if ds is not None and d != ds:
            continue
        z = dict(np.load(G / f"win_{d}.npz"))
        z["dsid"] = np.full(len(z["code1"]), i, np.int8)
        parts.append(z)
    out = {k: np.concatenate([p[k] for p in parts]) for k in parts[0]}
    if split is not None:
        m = np.isin(out["split"], [split] if isinstance(split, str) else list(split))
        out = {k: v[m] for k, v in out.items()}
    return out


def fit():
    import t1b_tokens as TK
    tr = load("train")
    va = load("validation")
    an = tr["an"].reshape(-1)
    lo, hi = np.percentile(an, [0.5, 99.5])
    edges = np.exp(np.linspace(np.log(lo), np.log(hi), NV + 1))
    centres = np.sqrt(edges[:-1] * edges[1:])
    ptr, pva = tr["post"].reshape(-1, 5).astype(np.float64), va["post"].reshape(-1, 5).astype(np.float64)
    mu, sd = ptr.mean(0), ptr.std(0)
    xtr, xva = (ptr - mu) / sd, (pva - mu) / sd
    c1 = TK.kmeans(xtr, NP, SEED_KM)
    a1 = TK.nearest(xtr, c1)
    c2 = TK.kmeans(xtr - c1[a1], NP, SEED_KM + 1)
    out = {}
    for name, x in (("train", xtr), ("validation", xva)):
        e1 = TK.nearest(x, c1)
        e2 = TK.nearest(x - c1[e1], c2)
        tot = ((x - x.mean(0)) ** 2).sum(0)
        rec = c1[e1] + c2[e2]
        out[name] = dict(variance_explained_standardised=float(1 - ((x - rec) ** 2).sum() / tot.sum()), per_joint=(1 - ((x - rec) ** 2).sum(0) / tot).tolist(),
                         stage1_only=float(1 - ((x - c1[e1]) ** 2).sum() / tot.sum()), tokens=int(len(x)), entries_used_stage1=int(len(np.unique(e1))), entries_used_stage2=int(len(np.unique(e2))))
    np.savez(G / "vocab.npz", vig_edges=edges, vig_centres=centres, post_mu=mu, post_sd=sd, post_c1=c1, post_c2=c2)
    genres = sorted(set(np.concatenate([np.load(G / f"win_{d}.npz")["genre"] for d in DS]).tolist()))
    res = dict(vig_p0_5=float(lo), vig_p99_5=float(hi), n_train_tokens=int(len(xtr)), posture=out, genres=genres, copies=COPIES, datasets=DS, seed=SEED_KM,
               stop=bool(out["train"]["variance_explained_standardised"] < 0.9 or out["validation"]["variance_explained_standardised"] < 0.9))
    (G / "vocab.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res), flush=True)
    assign_all()
    code_stats()
    if res["stop"]:
        print("STOP posture variance explained below 0.9")
        sys.exit(2)


def assign(z, v):
    """window dict -> vbin (N, 40), p1, p2 (N, 40)"""
    import t1b_tokens as TK
    vbin = np.clip(np.searchsorted(v["vig_edges"], z["an"], side="right") - 1, 0, NV - 1).astype(np.int8)
    x = (z["post"].reshape(-1, 5).astype(np.float64) - v["post_mu"]) / v["post_sd"]
    e1 = TK.nearest(x, v["post_c1"])
    e2 = TK.nearest(x - v["post_c1"][e1], v["post_c2"])
    return vbin, e1.reshape(z["an"].shape).astype(np.int16), e2.reshape(z["an"].shape).astype(np.int16)


def assign_all():
    v = np.load(G / "vocab.npz")
    for d in DS:
        p = G / f"win_{d}.npz"
        z = dict(np.load(p))
        z["vbin"], z["p1"], z["p2"] = assign(z, v)
        np.savez(str(p) + ".tmp.npz", **z)
        Path(str(p) + ".tmp.npz").replace(p)
    print("assigned", flush=True)


def valid_mask(ctl):
    """(..., CD) controls -> bool mask of the entries that are defined (sharp, direction, accent pattern follow their flags)"""
    v = np.ones(ctl.shape, bool)
    v[..., 10] = ctl[..., 15] > 0
    v[..., 11:14] = (ctl[..., 16] > 0)[..., None]
    v[..., 2:10] = (ctl[..., 17] > 0)[..., None]
    return v


def code_stats():
    out = compute_stats(load("train"))
    np.savez(G / "stats.npz", **out)
    print("stats codes used", {k: int((out[f"{k}_n"] > 0).sum()) for k in ("c1", "c2", "p1", "p2")}, flush=True)


def compute_stats(tr, ks=None):
    """mean and covariance of the controls of the tokens assigned to each code (gesture stage 1, stage 2, posture stage 1, stage 2), TRAIN split only; undefined entries (flag 0) are
    excluded from a dimension's mean and filled with the global mean for the covariance; codes with < AGG_MIN tokens are shrunk to the global mean."""
    ctl = tr["ctl"].reshape(-1, CD).astype(np.float64)
    valid = valid_mask(ctl)
    gm = np.array([ctl[valid[:, j], j].mean() for j in range(CD)])
    gsd = np.array([ctl[valid[:, j], j].std() for j in range(CD)])
    filled = np.where(valid, ctl, gm)
    out = dict(global_mean=gm, global_sd=gsd)
    for name, codes, K in (("c1", tr["code1"], ks or 1024), ("c2", tr["code2"], ks or 1024), ("p1", tr["p1"], ks or NP), ("p2", tr["p2"], ks or NP)):
        a = codes.reshape(-1).astype(np.int64)
        n = np.bincount(a, minlength=K).astype(np.float64)
        mean, cov = np.zeros((K, CD)), np.zeros((K, CD, CD))
        for k in np.flatnonzero(n):
            m = a == k
            vk = valid[m]
            cnt = vk.sum(0)
            mean[k] = np.where(cnt > 0, (ctl[m] * vk).sum(0) / np.maximum(cnt, 1), gm)
            cov[k] = np.cov(filled[m].T) if m.sum() > 1 else 0.0
        w = (n / (n + AGG_MIN))[:, None]
        mean = w * mean + (1 - w) * gm
        mean[n == 0] = gm
        out[f"{name}_mean"], out[f"{name}_cov"], out[f"{name}_n"] = mean, cov.astype(np.float32), n
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    G.mkdir(parents=True, exist_ok=True)
    {"scan": scan, "encode": lambda: encode(int(a[1]) if len(a) > 1 else 8), "fit": fit}[a[0]]()
