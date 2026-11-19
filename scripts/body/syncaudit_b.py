"""WO54 B (agent 2): A3 per-song lag diagnostic, shifted-foil reading, A2 AIST++ reference. Rules: docs/SYNCAUDIT_RULES_B.md. Brain env. Report only.

    syncaudit_b.py a3 [PROCS]     per-song lag curves per dataset/version/signal + chance -> syncaudit/b/a3_<ds>.npz
    syncaudit_b.py a3report       tables -> syncaudit/b/a3_results.json, a3_tables.md
    syncaudit_b.py foil           the shifted-foil reading of the mismatch clips -> syncaudit/b/foil.json
    syncaudit_b.py a2 [PROCS]     AIST++ per-stage lag and BAS -> syncaudit/b/a2_<seq>.json
    syncaudit_b.py a2report       -> a2_results.json, a2_tables.md
Sign: positive lag = movement LATER than the music. c(L) = corr_t(m(t), e(t - L)). Nothing upstream is recomputed or edited.
"""
import json
import re
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))

B = Path("/secondary/hyst-data/body")
OUT = B / "syncaudit/b"
FS = 50
KMAX = 150                       # +-3 s
KPK = 75                         # peak search +-1.5 s
DS = ("finedance", "aioz", "phantom", "motorica")
LANES = {"finedance": B / "t0/lanes", "aioz": B / "t0/lanes", "phantom": B / "t0_phantom/lanes", "motorica": B / "t0_motorica/lanes"}
NDRAW, NBOOT = 20, 2000
SEED_CH, SEED_BOOT = 54203, 54204
QS = (5, 25, 50, 75, 95)


# ---------------------------------------------------------------------------------------------------- measuring core
def demean(x, n=2 * FS):
    """subtract a centred moving mean of n samples (edge-normalised)"""
    x = np.asarray(x, np.float64)
    k = np.ones(n)
    return x - np.convolve(x, k, "same") / np.convolve(np.ones(len(x)), k, "same")


def curve(m, env, base=0, lo=0, hi=None, kmax=KMAX):
    """c(k) for k in -kmax..kmax (samples); motion samples m[lo:hi] against env[base + i - k] (env on the same grid, both already de-meaned).
    Positive k: motion later than the music. Returns nan array if the env range does not fit or a segment is constant."""
    hi = len(m) if hi is None else hi
    i = np.arange(lo, hi)
    ks = np.arange(-kmax, kmax + 1)
    idx = base + i[None, :] - ks[:, None]
    if idx.min() < 0 or idx.max() >= len(env):
        return np.full(len(ks), np.nan)
    x = m[lo:hi] - m[lo:hi].mean()
    sx = np.sqrt((x ** 2).sum())
    e = env[idx]
    e = e - e.mean(1, keepdims=True)
    se = np.sqrt((e ** 2).sum(1))
    if sx < 1e-12:
        return np.full(len(ks), np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        return (e @ x) / (se * sx)


def peak(c, kpk=KPK, kmax=KMAX):
    """(lag s, height) of the maximum of c within +-kpk samples, parabolic sub-sample; (nan, nan) if c has nan"""
    c = np.asarray(c, float)
    if not np.isfinite(c).all():
        return np.nan, np.nan
    mid = kmax
    seg = c[mid - kpk:mid + kpk + 1]
    j = int(np.argmax(seg))
    d = 0.0
    if 0 < j < len(seg) - 1:
        y0, y1, y2 = seg[j - 1], seg[j], seg[j + 1]
        den = y0 - 2 * y1 + y2
        d = float(np.clip(0.5 * (y0 - y2) / den, -0.5, 0.5)) if den < 0 else 0.0
    return (j - kpk + d) / FS, float(seg[j])


def mean_curve(cs):
    cs = [c for c in cs if np.isfinite(c).all()]
    return np.mean(cs, 0) if cs else np.full(2 * KMAX + 1, np.nan)


def block50(x100):
    n = len(x100) // 2 * 2
    return np.asarray(x100[:n], np.float64).reshape(-1, 2).mean(1)


# ---------------------------------------------------------------------------------------------------- song material
def music_key(key):
    return re.sub(r"_p\d+$", "", key.split("__")[0])


def song_env(ds, song):
    """-> dict name -> de-meaned 50 Hz envelope ('ear40' main, 'energy')"""
    z = np.load(LANES[ds] / f"{song}.npz")
    ear = block50(z["ear"][:, 40])
    p2 = np.load(B / f"pulse2/songs/{song}.npz")
    rms = np.asarray(p2["rms"], np.float64)
    en = block50(np.convolve(rms, np.ones(50) / 50, "same"))           # 0.5 s moving mean at 100 Hz
    return dict(ear40=demean(ear), energy=demean(en))


def tempo(song):
    b = np.asarray(json.loads((B / f"beatv/librosa/{song}.json").read_text())["beats"], float)
    return 60.0 / np.median(np.diff(b)) if len(b) > 4 else np.nan


def lamp_speed(lamp):
    return np.linalg.norm(np.gradient(np.asarray(lamp, float), axis=0) * FS, axis=1)


CORE = (3 * FS, 17 * FS + 1)


# ---------------------------------------------------------------------------------------------------- A3
RAW_SIGS = ("lwr", "rwr", "lft", "rft", "pel", "head", "mean", "mean_rel")
_G = {}


def inventory(ds):
    """song -> {version: (key, path)} over the q50 files (mirror copies excluded)"""
    out = {}
    for p in sorted((B / "controls/q50" / ds).glob("*.npz")):
        key = p.stem
        ver = key.split("__")[1]
        if ver not in ("V1", "V2"):
            continue
        out.setdefault(music_key(key), {})[ver] = (key, p)
    return out


def _init(poolinfo):
    import rawrhythm as RW
    _G["pool"] = poolinfo
    _G["cat"] = RW.catalogues()
    _G["cache"] = {}


def foil_env(ds, song):
    c = _G["cache"]
    k = (ds, song)
    if k not in c:
        if len(c) > 12:
            c.pop(next(iter(c)))
        c[k] = song_env(ds, song)
    return c[k]


def window_curves(sigs, env, wins):
    """sigs: motion arrays (1001,) per window, env de-meaned full-song array -> mean curve over windows (nan if none valid)"""
    return mean_curve([curve(m, env, base=w * 20 * FS, lo=CORE[0], hi=CORE[1]) for w, m in zip(wins, sigs)])


def chance_peaks(sigs, wins, song, ds, tp, nlen, music, rng):
    """(NDRAW, 2) peak lag/height against another song of similar tempo, and against the own music shifted 2-6 s"""
    cands = [(d, s) for d, s, t, n in _G["pool"] if s != song and abs(t / tp - 1) <= 0.05 and n >= nlen] if np.isfinite(tp) else []
    own = foil_env(ds, song)[music]
    A = np.full((NDRAW, 2), np.nan)
    if cands:
        pick = rng.choice(len(cands), NDRAW, replace=len(cands) < NDRAW)
        for i, j in enumerate(pick):
            A[i] = peak(window_curves(sigs, foil_env(*cands[j])[music], wins))
    Bm = np.full((NDRAW, 2), np.nan)
    for i in range(NDRAW):
        sh = int(round(rng.uniform(2, 6) * FS)) * int(rng.choice((-1, 1)))
        Bm[i] = peak(window_curves(sigs, np.roll(own, sh), wins))
    return A, Bm


def song_job(args):
    import zlib
    import rawrhythm as RW
    ds, song, vers = args
    try:
        env = song_env(ds, song)
        rng = np.random.default_rng(SEED_CH + zlib.crc32(song.encode()))
        tp = tempo(song)
        nlen = len(env["ear40"])
        res = dict(song=song, ds=ds, tempo=tp, curves={}, chance={}, nwin={})
        sp, wins = {}, {}
        for v, (key, path) in vers.items():
            z = np.load(path)
            w = [int(x) for x in z["win"]]
            ok = [i for i in range(len(w)) if (w[i] * 20 + 20) * FS <= nlen]
            wins[v] = [w[i] for i in ok]
            sp[v] = [demean(lamp_speed(z["lamp"][i])) for i in ok]
            res["nwin"][v] = len(ok)
            for mu in ("ear40", "energy"):
                res["curves"][f"lamp_{v}|{mu}"] = window_curves(sp[v], env[mu], wins[v])
            res["chance"][f"lamp_{v}|ear40"] = chance_peaks(sp[v], wins[v], song, ds, tp, nlen, "ear40", rng)
        v0 = "V1" if "V1" in vers else "V2"                       # raw joints: windows of the first version present
        perf = RW.perf_of(vers[v0][0])
        raw = RW.speeds50(RW.raw_positions(ds, perf, _G["cat"]))
        rs, rw = {s: [] for s in RAW_SIGS}, []
        for w in wins[v0]:
            i0 = w * 20 * FS
            if i0 + 1001 > len(raw["mean"]):
                continue
            rw.append(w)
            for s in RAW_SIGS:
                rs[s].append(demean(raw[s][i0:i0 + 1001]))
        res["nwin"]["raw"] = len(rw)
        for s in RAW_SIGS:
            res["curves"][f"raw_{s}|ear40"] = window_curves(rs[s], env["ear40"], rw)
        res["curves"]["raw_mean|energy"] = window_curves(rs["mean"], env["energy"], rw)
        res["chance"]["raw_mean|ear40"] = chance_peaks(rs["mean"], rw, song, ds, tp, nlen, "ear40", rng)
        for v in vers:                                           # lamp against raw mean, no music: L > 0 lamp later than raw
            cs = []
            for wi, w in enumerate(wins[v]):
                if w in rw:
                    cs.append(curve(sp[v][wi], rs["mean"][rw.index(w)], base=0, lo=CORE[0], hi=CORE[1]))
            res["curves"][f"lampVSraw_{v}"] = mean_curve(cs)
        return res, None
    except Exception as e:  # noqa: BLE001
        return None, f"{ds} {song} {e!r}"


def a3(procs=6):
    OUT.mkdir(parents=True, exist_ok=True)
    inv = {ds: inventory(ds) for ds in DS}
    poolinfo = []
    for ds in DS:
        for song in inv[ds]:
            try:
                poolinfo.append((ds, song, tempo(song), len(song_env(ds, song)["ear40"])))
            except Exception as ex:  # noqa: BLE001
                print("NOINFO", ds, song, repr(ex), flush=True)
    print("songs", {ds: len(inv[ds]) for ds in DS}, "pool", len(poolinfo), flush=True)
    for ds in DS:
        dst = OUT / f"a3_{ds}.npz"
        if dst.exists():
            continue
        jobs = [(ds, s, v) for s, v in inv[ds].items()]
        rows, bad = [], []
        with Pool(procs, initializer=_init, initargs=(poolinfo,)) as pool:
            for i, (r, err) in enumerate(pool.imap_unordered(song_job, jobs, chunksize=2)):
                if r:
                    rows.append(r)
                else:
                    bad.append(err)
                    print("FAIL", err, flush=True)
                if i % 25 == 0:
                    print(ds, i, "/", len(jobs), flush=True)
        rows.sort(key=lambda r: r["song"])
        d = dict(song=np.array([r["song"] for r in rows]), tempo=np.array([r["tempo"] for r in rows]))
        for k in sorted({k for r in rows for k in r["curves"]}):
            d["curve|" + k] = np.array([r["curves"].get(k, np.full(2 * KMAX + 1, np.nan)) for r in rows])
        for k in sorted({k for r in rows for k in r["chance"]}):
            for fam, j in (("tempo", 0), ("shift", 1)):
                d[f"chance_{fam}|{k}"] = np.array([r["chance"][k][j] if k in r["chance"] else np.full((NDRAW, 2), np.nan) for r in rows])
        for k in ("V1", "V2", "raw"):
            d["nwin|" + k] = np.array([r["nwin"].get(k, 0) for r in rows])
        np.savez_compressed(dst, **d)
        (OUT / f"a3_{ds}_failed.txt").write_text("\n".join(bad))
        print("DONE", ds, len(rows), "failed", len(bad), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1]
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    if cmd == "a3":
        a3(procs)
