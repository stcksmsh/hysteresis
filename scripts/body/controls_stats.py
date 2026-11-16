"""WO43 Steps 0b and 0c (numbers only). Rules: docs/CONTROLS_RULES.md sections 5-7. Brain env (numpy, scipy, librosa).

    controls_stats.py table        token tables controls/tables/<ds>.npz (+ <ds>_songs.npz acoustic measures per song) from controls/<ds>/*.npz and the T0 lanes
    controls_stats.py b            Step 0b -> controls/stats/b_<ds>.json
    controls_stats.py c            Step 0c relations -> controls/stats/c_<ds>.json
    controls_stats.py struct       structure layer -> controls/stats/s_<ds>.json
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
B = Path("/secondary/hyst-data/body")
OUT = B / "controls"
TAB, STA = OUT / "tables", OUT / "stats"
DS = ("finedance", "aioz", "phantom", "motorica")
LANES = {"finedance": B / "t0/lanes", "aioz": B / "t0/lanes", "phantom": B / "t0_phantom/lanes", "motorica": B / "t0_motorica/lanes"}
BEATS = B / "t1b/cortex/beats"
SC = ["vigour", "vj", "vl", "height", "accent_mean", "sharp", "pause_prob", "activity", "dir_z", "dir_absx", "dir_absy"]     # 0b scalars
EXTRA = ["lead", "accent_peak"]                                                                                           # distributions only
CTL_C = ["vigour", "vj", "vl", "height", "sharp", "pause_prob", "accent_mean", "dir_z"]                                    # related to acoustics in 0c
MEAS = ["rms_db", "flux", "onset", "low_db", "high_db", "centroid", "dyn_range", "beat_strength"]
LAGS = (-2, -1, 0, 1, 2)
NB, SEED = 200, 4301
SPLITS = ("train", "validation", "test")


def lane_key(name):
    s = name.split("__")[0]
    return re.sub(r"_p\d+$", "", s) if s.startswith("aioz_") else s


# ---------------------------------------------------------------------------------------------------- tables
def acoustic(ear, mean, std, beats=None):
    """ear (T, 44) standardised, clipped lane features -> (n_tok, 8) token measures (rules 7)"""
    import librosa
    raw = ear * std + mean
    n_tok = len(raw) // 50
    cen = librosa.mel_frequencies(n_mels=34, fmin=30, fmax=16000)[1:-1]
    lo, hi = np.flatnonzero(cen < 200), np.flatnonzero(cen >= 3200)
    rms_db = 20 * np.log10(np.maximum(raw[:, 41], 1e-4))
    o = np.zeros((n_tok, 8))
    for k in range(n_tok):
        s = slice(50 * k, 50 * k + 50)
        c = 50 * k + 25
        w = rms_db[max(c - 200, 0):c + 200]
        o[k] = [rms_db[s].mean(), raw[s, 32:40].mean(), raw[s, 40].mean(), raw[s][:, lo].mean(), raw[s][:, hi].mean(), raw[s, 42].mean(), np.percentile(w, 95) - np.percentile(w, 5), np.nan]
    if beats is not None:
        for b in beats:
            k = int(b // 0.5)
            if k < n_tok:
                f = int(round(b * 100))
                v = raw[max(f - 5, 0):f + 6, 40].max()
                o[k, 7] = v if np.isnan(o[k, 7]) else max(o[k, 7], v)
    return o


def cmd_table():
    import braindump as bd
    mean, std = bd.stats()
    TAB.mkdir(exist_ok=True)
    for ds in DS:
        files = sorted((OUT / ds).glob("*.npz"))
        cols, songs = {}, {}
        rows = []
        for fi, p in enumerate(files):
            z = np.load(p)
            n = len(z["win"])
            if n == 0:
                continue
            lk = lane_key(p.name)
            cp = ("V1", "V2", "V1m", "V2m").index(p.stem.split("__")[1])
            d = z["dir"].reshape(n * 40, 3)
            r = {k: z[k].reshape(n * 40) for k in ("vigour", "vj", "vl", "height", "accent_mean", "accent_peak", "sharp", "pause_prob", "activity", "lead", "z_mean", "vl_z", "vj_z")}
            r["dir_x"], r["dir_y"], r["dir_z"] = (np.where(z["dir_ok"].reshape(-1) == 1, d[:, i], np.nan) for i in range(3))
            r["dir_absx"], r["dir_absy"] = np.abs(r["dir_x"]), np.abs(r["dir_y"])
            r["win"] = np.repeat(z["win"], 40)
            r["k"] = np.tile(np.arange(40), n)
            r["gtok"] = r["win"] * 40 + r["k"]
            r["copy"] = np.full(n * 40, cp)
            r["split"] = np.full(n * 40, SPLITS.index(str(z["split"])))
            r["group"] = np.full(n * 40, str(z["group"]), dtype=object)
            r["lane"] = np.full(n * 40, lk, dtype=object)
            r["fidx"] = np.full(n * 40, fi)
            for ii in range(1, 6):
                r[f"vjoint{ii}"] = z["vjoint"].reshape(n * 40, 5)[:, ii - 1]
            rows.append(r)
            if lk not in songs:
                lz = np.load(LANES[ds] / f"{lk}.npz")
                beats = None
                if ds == "finedance" and (BEATS / f"{lk}.json").exists():
                    beats = json.loads((BEATS / f"{lk}.json").read_text())["beats"]
                songs[lk] = acoustic(lz["ear"], mean, std, beats)
        keys = rows[0].keys()
        tab = {k: np.concatenate([r[k] for r in rows]) for k in keys}
        gl, gi = np.unique(tab["group"].astype(str), return_inverse=True)
        tab["gid"], tab["group"], tab["lane"] = gi.astype(np.int32), tab["group"].astype(str), tab["lane"].astype(str)
        np.savez_compressed(TAB / f"{ds}.npz", **tab)
        np.savez_compressed(TAB / f"{ds}_songs.npz", **songs)
        print(ds, "tokens", len(gi), "groups", len(gl), "songs", len(songs), flush=True)


def load(ds):
    z = np.load(TAB / f"{ds}.npz", allow_pickle=False)
    return {k: z[k] for k in z.files}


# ---------------------------------------------------------------------------------------------------- bootstrap helpers
def mult(G, seed=SEED):
    return np.random.default_rng(seed).multinomial(G, np.full(G, 1 / G), size=NB).astype(float)


def pstats(x, y, gid, G):
    m = np.isfinite(x) & np.isfinite(y)
    g = gid[m]
    xs, ys = x[m], y[m]
    return np.stack([np.bincount(g, minlength=G).astype(float)] + [np.bincount(g, w, G) for w in (xs, ys, xs * xs, ys * ys, xs * ys)], 1)


def r_of(t):
    n, sx, sy, sxx, syy, sxy = (t[..., i] for i in range(6))
    with np.errstate(all="ignore"):
        return (n * sxy - sx * sy) / np.sqrt((n * sxx - sx ** 2) * (n * syy - sy ** 2))


def corr_ci(x, y, gid, G, M):
    st = pstats(x, y, gid, G)
    r = float(r_of(st.sum(0)))
    b = r_of(M @ st)
    return [r, float(np.nanpercentile(b, 2.5)), float(np.nanpercentile(b, 97.5)), int(st[:, 0].sum())]


def ranks(x):
    out = np.full(len(x), np.nan)
    m = np.isfinite(x)
    out[m] = rankdata(x[m])
    return out


def demean(x, gid, G):
    m = np.isfinite(x)
    s = np.bincount(gid[m], x[m], G)
    n = np.bincount(gid[m], minlength=G)
    return x - (s / np.maximum(n, 1))[gid]


def wmedian(xs, w):
    c = np.cumsum(w)
    return xs[min(np.searchsorted(c, c[-1] / 2.0), len(xs) - 1)]


def median_ci(x, gid, M):
    m = np.isfinite(x)
    o = np.argsort(x[m])
    xs, g = x[m][o], gid[m][o]
    meds = [wmedian(xs, M[b][g]) for b in range(NB)]
    return [float(np.median(xs)), float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))]


def varshare_ci(x, gid, G, M):
    m = np.isfinite(x)
    g, v = gid[m], x[m]
    n, s, q = np.bincount(g, minlength=G).astype(float), np.bincount(g, v, G), np.bincount(g, v * v, G)

    def share(w):
        N, S, Q = (w * n).sum(), (w * s).sum(), (w * q).sum()
        tot = Q - S * S / N
        bet = (w * s * s / np.maximum(n, 1)).sum() - S * S / N
        return bet / tot
    est = share(np.ones(G))
    bs = [share(M[b]) for b in range(NB)]
    return [float(est), float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]


# ---------------------------------------------------------------------------------------------------- Step 0b
def cmd_b():
    STA.mkdir(exist_ok=True)
    fd = load("finedance")
    tr = fd["split"] == 0
    edges = {k: np.nanpercentile(fd[k][tr], [0.5, 99.5]).tolist() for k in SC + EXTRA}
    res = dict(edges=edges)
    for ds in DS:
        t = load(ds)
        gid, G = t["gid"], int(t["gid"].max()) + 1
        M = mult(G)
        out = dict(n_tokens=len(gid), n_groups=G, sc=SC, extra=EXTRA, dist={}, corr={}, varshare={}, nan_share={})
        for k in SC + EXTRA:
            x = t[k]
            fin = np.isfinite(x)
            out["nan_share"][k] = float(1 - fin.mean())
            q = np.nanpercentile(x, [1, 5, 25, 50, 75, 95, 99]).tolist()
            lo, hi = edges[k]
            h = np.histogram(np.clip(x[fin], lo, hi), bins=20, range=(lo, hi))[0].tolist()
            out["dist"][k] = dict(q=q, median_ci=median_ci(x, gid, M), hist=h, hist_range=[lo, hi])
            out["varshare"][k] = varshare_ci(x, gid, G, M)
        P, S = {}, {}
        rk = {k: ranks(t[k]) for k in SC}
        for i, a in enumerate(SC):
            for b in SC[i + 1:]:
                P[f"{a}|{b}"] = corr_ci(t[a], t[b], gid, G, M)
                S[f"{a}|{b}"] = corr_ci(rk[a], rk[b], gid, G, M)
        out["corr"] = dict(pearson=P, spearman=S)
        out["redundant"] = [k for k in P if abs(P[k][0]) > 0.7 or abs(S[k][0]) > 0.7]
        if ds == "finedance":                                                  # split-wise check of the same matrix (point estimates)
            out["corr_by_split"] = {SPLITS[s]: {f"{a}|{b}": float(r_of(pstats(t[a][t["split"] == s], t[b][t["split"] == s], gid[t["split"] == s], G).sum(0))) for i, a in enumerate(SC) for b in SC[i + 1:]} for s in range(3)}
        out["tokens_by_split"] = {SPLITS[s]: int((t["split"] == s).sum()) for s in range(3)}
        out["token_share_by_copy"] = {c: float((t["copy"] == i).mean()) for i, c in enumerate(("V1", "V2", "V1m", "V2m"))}
        res[ds] = out
        (STA / f"b_{ds}.json").write_text(json.dumps(out, indent=1))
        print("0b", ds, "redundant", out["redundant"], flush=True)
    (STA / "b_edges.json").write_text(json.dumps(edges))


# ---------------------------------------------------------------------------------------------------- Step 0c
def measure_at(t, songs, lag):
    """measure matrix (n, 8) of the token gtok + lag of each row's song"""
    out = np.full((len(t["gid"]), 8), np.nan)
    for lk in np.unique(t["lane"]):
        m = np.flatnonzero(t["lane"] == lk)
        a = songs[lk]
        idx = t["gtok"][m] + lag
        ok = (idx >= 0) & (idx < len(a))
        out[m[ok]] = a[idx[ok]]
    return out


def cmd_c():
    for ds in DS:
        t = load(ds)
        songs = np.load(TAB / f"{ds}_songs.npz")
        gid, G = t["gid"], int(t["gid"].max()) + 1
        M = mult(G)
        res = dict(controls=CTL_C, measures=MEAS, lags=list(LAGS), global_={}, within={}, per_song={})
        grp_n = np.bincount(gid, minlength=G)
        for lag in LAGS:
            A = measure_at(t, songs, lag)
            for ci, c in enumerate(CTL_C):
                x = t[c]
                xd = demean(x, gid, G)
                rx, rxd = ranks(x), None
                for mi, mn in enumerate(MEAS):
                    y = A[:, mi]
                    if not np.isfinite(y).any():
                        continue
                    yd = demean(y, gid, G)
                    key = f"{c}|{mn}|{lag}"
                    res["global_"][key] = dict(pearson=corr_ci(x, y, gid, G, M), spearman=corr_ci(rx, ranks(y), gid, G, M))
                    res["within"][key] = dict(pearson=corr_ci(xd, yd, gid, G, M), spearman=corr_ci(ranks(xd), ranks(yd), gid, G, M))
                    if lag == 0:
                        rs = []
                        for g in np.flatnonzero(grp_n >= 60):
                            mm = (gid == g) & np.isfinite(x) & np.isfinite(y)
                            if mm.sum() >= 60 and np.ptp(x[mm]) > 0 and np.ptp(y[mm]) > 0:
                                rs.append(spearmanr(x[mm], y[mm])[0])
                        if rs:
                            res["per_song"][key] = dict(n=len(rs), median=float(np.median(rs)), q25=float(np.percentile(rs, 25)), q75=float(np.percentile(rs, 75)), share_positive=float(np.mean(np.array(rs) > 0)))
            print("0c", ds, "lag", lag, flush=True)
        (STA / f"c_{ds}.json").write_text(json.dumps(res, indent=1))


# ---------------------------------------------------------------------------------------------------- structure layer
def novelty(F, half=4, sigma=2.0):
    """F (n, d): cosine self-similarity, Gaussian-tapered checkerboard kernel -> novelty (n,), NaN where the kernel does not fit"""
    n = len(F)
    Fn = F / np.maximum(np.linalg.norm(F, axis=1, keepdims=True), 1e-9)
    S = Fn @ Fn.T
    i = np.arange(-half, half) + 0.5
    K = np.outer(np.sign(i), np.sign(i)) * np.exp(-(i[:, None] ** 2 + i[None] ** 2) / (2 * sigma ** 2))
    nov = np.full(n, np.nan)
    for t in range(half, n - half + 1):
        nov[t] = (K * S[t - half:t + half, t - half:t + half]).sum()
    return nov


def peaks(nov, min_dist=4):
    v = nov[np.isfinite(nov)]
    if len(v) < 3:
        return np.array([], int)
    th = v.mean() + v.std()
    cand = [t for t in range(1, len(nov) - 1) if np.isfinite(nov[t]) and np.isfinite(nov[t - 1]) and np.isfinite(nov[t + 1]) and nov[t] >= nov[t - 1] and nov[t] >= nov[t + 1] and nov[t] >= th]
    cand.sort(key=lambda t: -nov[t])
    keep = []
    for t in cand:
        if all(abs(t - u) >= min_dist for u in keep):
            keep.append(t)
    return np.array(sorted(keep), int)


def repetition(F, blk=4, gap=8):
    n = len(F)
    nb = n - blk + 1
    X = np.stack([F[k:k + blk].ravel() for k in range(nb)])
    X = X / np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-9)
    S = X @ X.T
    rep = np.full(n, np.nan)
    for k in range(nb):
        far = np.abs(np.arange(nb) - k) >= gap
        if far.any():
            rep[k] = S[k, far].max()
    return rep


def music_features(ds, lk, cortex):
    """token music features (n_tok, d) of one song: the stored 44 ear + 32 mode columns (any copy's tokens), or the frozen cortex token means (FineDance)"""
    if cortex:
        a = np.load(B / "t1b/cortex" / f"{lk}.npy", mmap_mode="r")
        n = len(a) // 50
        return np.stack([np.asarray(a[50 * k:50 * k + 50, :2048], np.float32).mean(0) for k in range(n)])
    root = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}[ds]
    p = next(iter(sorted(root.glob(f"{lk}*__V1.npz"))))
    return np.load(p)["tokens"][:, :76]


def cmd_struct():
    fd = load("finedance")
    tr = fd["split"] == 0
    cn = ["vigour", "height", "sharp", "pause_prob", "accent_mean"]
    mu = {k: float(np.nanmean(fd[k][tr])) for k in cn}
    sd = {k: float(np.nanstd(fd[k][tr])) for k in cn}
    rng = np.random.default_rng(SEED)
    for ds in DS:
        t = load(ds)
        gid, G = t["gid"], int(t["gid"].max()) + 1
        M = mult(G)
        res = {}
        for variant in ("tokens", "cortex") if ds == "finedance" else ("tokens",):
            mf = {}
            for lk in np.unique(t["lane"]):
                F = music_features(ds, lk, variant == "cortex")
                F = (F - F.mean(0)) / np.maximum(F.std(0), 1e-6)
                nv = novelty(F)
                mf[lk] = (nv, peaks(nv), repetition(F))
            hit = np.zeros(G)
            chance = np.zeros(G)
            cnt = np.zeros(G)
            nwin = np.zeros(G)
            c_nov = []
            mb = []
            mrep = []
            for fidx in np.unique(t["fidx"]):
                r = np.flatnonzero(t["fidx"] == fidx)
                lk, g = t["lane"][r[0]], t["gid"][r[0]]
                nv, pk, rp = mf[lk]
                n_tok = len(nv)
                bm = np.zeros(n_tok, bool)
                bm[pk] = True
                shifts = rng.integers(10, max(n_tok - 10, 11), size=20)
                for w in np.unique(t["win"][r]):
                    rr = r[t["win"][r] == w]
                    V = np.stack([np.nan_to_num((t[k][rr] - mu[k]) / sd[k]) for k in cn], 1)
                    if len(V) < 40:
                        continue
                    mn = novelty(V)
                    mp = peaks(mn)
                    nwin[g] += 1
                    mb.append(len(mp))
                    mrep.append(np.nanmean(repetition(V)))
                    gt = w * 40 + mp
                    gt = gt[gt < n_tok - 1]
                    h = sum(bm[max(x - 1, 0):x + 2].any() for x in gt)
                    ch = np.mean([sum(np.roll(bm, s)[max(x - 1, 0):x + 2].any() for x in gt) for s in shifts]) if len(gt) else 0.0
                    hit[g] += h
                    chance[g] += ch
                    cnt[g] += len(gt)
                    gi = w * 40 + np.arange(4, 36)
                    gi = gi[gi < n_tok]
                    c_nov.append((mn[4:4 + len(gi)], nv[gi]))
            st = np.stack([cnt, hit, chance, nwin], 1)
            tot = st.sum(0)
            b = M @ st
            diff = b[:, 1] / np.maximum(b[:, 0], 1) - b[:, 2] / np.maximum(b[:, 0], 1)
            a = np.concatenate([x for x, _ in c_nov])
            bb = np.concatenate([y for _, y in c_nov])
            ok = np.isfinite(a) & np.isfinite(bb)
            res[variant] = dict(motion_boundaries=float(tot[0]), windows=float(tot[3]), motion_boundaries_per_window=float(tot[0] / max(tot[3], 1)), music_boundaries_per_min=float(np.mean([len(v[1]) / (len(v[0]) * 0.5 / 60) for v in mf.values()])),
                                music_repetition_mean=float(np.nanmean(np.concatenate([v[2] for v in mf.values()]))), motion_repetition_mean=float(np.mean(mrep)),
                                hit_rate=float(tot[1] / max(tot[0], 1)), chance_rate=float(tot[2] / max(tot[0], 1)), hit_minus_chance=float((tot[1] - tot[2]) / max(tot[0], 1)),
                                hit_minus_chance_ci=[float(np.percentile(diff, 2.5)), float(np.percentile(diff, 97.5))],
                                novelty_spearman=float(spearmanr(a[ok], bb[ok])[0]), n_novelty_pairs=int(ok.sum()))
            print("struct", ds, variant, json.dumps(res[variant]), flush=True)
        (STA / f"s_{ds}.json").write_text(json.dumps(dict(res, motion_vector=cn, motion_mu=mu, motion_sd=sd), indent=1))


if __name__ == "__main__":
    {"table": cmd_table, "b": cmd_b, "c": cmd_c, "struct": cmd_struct}[sys.argv[1]]()
