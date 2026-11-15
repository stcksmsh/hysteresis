"""WO41 T1b targets (docs/T1B_RULES.md section 2). Brain env.

    t1b_tokens.py encode [THREADS]   every FineDance T0 sequence (4 copies) -> t1b/tokens/<seq>.npz with the frozen vocabulary (t1a2/runB/best.pt)
    t1b_tokens.py fit                vigour bins and posture vocabulary from the TRAIN split -> t1b/vocab.npz + vocab.json (STOP if posture variance explained < 0.9)
    t1b_tokens.py assign             vigour bin and posture entry for every token (needs vocab.npz) -> added to the token files

Token k of a sequence covers rows [50 k, 50 k + 50) of the 100 Hz target. Only the n_win x 40 tokens of the T0 20 s windows are kept; `ok` = the token's window passed the T0 gate.
Stored per file: code1, code2 (int16), vig (float32, floored RMS a_n of the chunk in scaled units), pdelta (float32 (n, 5) = posture[50 (k+1)] - posture[50 k], raw units),
ok (bool), split, group, weight, and after `assign`: vbin (int8), pent (int16).
"""
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
T0 = Path("/secondary/hyst-data/body/t0")
OUT = Path("/secondary/hyst-data/body/t1b")
RUNB = Path("/secondary/hyst-data/body/t1a2/runB/best.pt")
SCALE = Path("/secondary/hyst-data/body/t1a/scale.json")
NV, NP = 32, 256
SEED_KM = 36001
CH = 50


def seqs():
    return sorted((T0 / "seq" / "finedance").glob("*.npz"))


def load_vq():
    import torch
    import t1a2_train as TR2
    m = TR2.make("B")
    m.load_state_dict(torch.load(RUNB))
    m.eval()
    return m


def encode_one(model, z, sd):
    import torch
    import t1a_model as M
    nw = int(z["n_win"])
    n = 40 * nw
    g = np.asarray(z["gesture"], np.float32)[:n * CH] / sd
    x = torch.from_numpy(g.reshape(n, CH, 5))
    with torch.no_grad():
        _, a_n, u = M.vigour(x)
        _, (i1, i2), _ = model.vq(model.enc(u))
    post = np.asarray(z["posture"], np.float64)
    pd = (post[CH:(n + 1) * CH:CH] - post[0:n * CH:CH]).astype(np.float32)
    ok = np.repeat(np.asarray(z["win_pass"], bool)[:nw], 40)
    return dict(code1=i1.numpy().astype(np.int16), code2=i2.numpy().astype(np.int16), vig=a_n.numpy().astype(np.float32), pdelta=pd, ok=ok,
                split=str(z["split"]), group=str(z["group"]), weight=float(z["weight"]))


def cmd_encode(threads):
    import torch
    torch.set_num_threads(threads)
    (OUT / "tokens").mkdir(parents=True, exist_ok=True)
    sd = np.asarray(json.loads(SCALE.read_text())["sd"], np.float32)
    model = load_vq()
    for p in seqs():
        q = OUT / "tokens" / p.name
        if q.exists():
            continue
        r = encode_one(model, np.load(p), sd)
        np.savez(str(q) + ".tmp.npz", **r)
        Path(str(q) + ".tmp.npz").replace(q)
    print("encoded", len(list((OUT / "tokens").glob("*.npz"))), flush=True)


def kmeans(x, k, seed, iters=60):
    """k-means++ init, Lloyd iterations; x (N, d) float64 -> centres (k, d)"""
    rng = np.random.default_rng(seed)
    c = [x[rng.integers(len(x))]]
    d2 = ((x - c[0]) ** 2).sum(1)
    for _ in range(k - 1):
        c.append(x[rng.choice(len(x), p=d2 / d2.sum())])
        d2 = np.minimum(d2, ((x - c[-1]) ** 2).sum(1))
    c = np.array(c)
    for _ in range(iters):
        a = nearest(x, c)
        for j in range(k):
            m = a == j
            c[j] = x[m].mean(0) if m.any() else x[rng.integers(len(x))]
    return c


def nearest(x, c, step=20000):
    out = [np.zeros(0, np.int64)]
    for i in range(0, len(x), step):
        xx = x[i:i + step]
        out.append(((xx ** 2).sum(1)[:, None] - 2 * xx @ c.T + (c ** 2).sum(1)[None]).argmin(1))
    return np.concatenate(out)


def load_tokens(split=None):
    out = []
    for p in sorted((OUT / "tokens").glob("*.npz")):
        z = np.load(p)
        if split is None or str(z["split"]) == split:
            out.append((p.stem, z))
    return out


def cmd_fit():
    tr = [z for _, z in load_tokens("train")]
    ok = np.concatenate([z["ok"] for z in tr])
    vig = np.concatenate([z["vig"] for z in tr])[ok]
    lo, hi = np.percentile(vig, [0.5, 99.5])
    edges = np.exp(np.linspace(np.log(lo), np.log(hi), NV + 1))                 # NV log-spaced bins; values outside go to the end bins
    centres = np.sqrt(edges[:-1] * edges[1:])
    pd = np.concatenate([z["pdelta"] for z in tr])[ok].astype(np.float64)
    psd = pd.std(0)
    x = pd / psd
    c = kmeans(x, NP, SEED_KM)
    a = nearest(x, c)
    resid = ((x - c[a]) ** 2).sum()
    ve = 1 - resid / ((x - x.mean(0)) ** 2).sum()
    ve_raw = 1 - (((pd - c[a] * psd) ** 2).sum() / ((pd - pd.mean(0)) ** 2).sum())
    ve_joint = (1 - ((pd - c[a] * psd) ** 2).sum(0) / ((pd - pd.mean(0)) ** 2).sum(0)).tolist()
    np.savez(OUT / "vocab.npz", vig_edges=edges, vig_centres=centres, post_centres=c * psd, post_sd=psd)
    res = dict(n_train_tokens=int(ok.sum()), vig_p0_5=float(lo), vig_p99_5=float(hi), vig_floor_share=float((vig <= 0.05 + 1e-9).mean()), posture_sd=psd.tolist(),
               posture_variance_explained_standardised=float(ve), posture_variance_explained_raw=float(ve_raw), per_joint_raw=ve_joint, entries_used=int(len(np.unique(a))),
               stop=bool(ve < 0.9))
    (OUT / "vocab.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res))
    if ve < 0.9:
        print("STOP posture variance explained", ve)
        sys.exit(2)


def cmd_assign():
    v = np.load(OUT / "vocab.npz")
    for p in sorted((OUT / "tokens").glob("*.npz")):
        z = dict(np.load(p))
        z["vbin"] = np.clip(np.searchsorted(v["vig_edges"], z["vig"], side="right") - 1, 0, NV - 1).astype(np.int8)
        z["pent"] = nearest(z["pdelta"].astype(np.float64) / v["post_sd"], v["post_centres"] / v["post_sd"]).astype(np.int16)
        np.savez(str(p) + ".tmp.npz", **z)
        Path(str(p) + ".tmp.npz").replace(p)
    print("assigned", flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"encode": lambda: cmd_encode(int(a[1]) if len(a) > 1 else 2), "fit": cmd_fit, "assign": cmd_assign}[a[0]]()
