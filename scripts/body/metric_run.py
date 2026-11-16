"""WO46 part 2 per-sequence analysis (docs/METRIC_RULES.md). Brain env.   metric_run.py [PROCS]
Reads metric/q50 (whole realised sequences), beat grids, T0 lanes; writes metric/results/<dataset>/<name>.pkl (resumable): phase statistics with controls, hit scans, pause/tempo/density
numbers, whole-song control tokens with acoustic measures, structure alignment. Aggregation: metric_report.py."""
import json
import multiprocessing as mp
import pickle
import sys
import zlib
from pathlib import Path

import numpy as np
from scipy.signal import find_peaks
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import controls_lib as C  # noqa: E402
import controls_stats as CS  # noqa: E402
import metric_lib as M  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "metric"
RES = OUT
DS = CS.DS
N_SHUF, N_DONOR, N_CIRC = 100, 20, 200
DELAYS = np.arange(-4, 5)
SCALES = (4, 16)
TYPES = ["E1", "E2", "E4", "E5"] + [f"E3_{j}" for j in range(5)]
CTL_NAMES = ["vigour", "vj", "vl", "height", "sharp", "pause_prob", "accent_mean", "dir_z"]
_cache = {}


def beats_path(lk):
    p = CS.BEATS / f"{lk}.json"
    return p if p.exists() else OUT / "beats" / f"{lk}.json"


def load_beats(lk):
    return np.array(json.loads(beats_path(lk).read_text())["beats"], float)


def tempo_table():
    """lane key -> median ibi for every song with a grid"""
    if "tt" not in _cache:
        t = {}
        for p in list(CS.BEATS.glob("*.json")) + list((OUT / "beats").glob("*.json")):
            b = json.loads(p.read_text())["beats"]
            if len(b) > 4:
                t[p.stem] = float(np.median(np.diff(b)))
        _cache["tt"] = t
    return _cache["tt"]


def consts():
    if "c" not in _cache:
        nm = json.loads((B / "controls/norm.json").read_text())
        _cache["c"] = (nm["accent"]["A"], np.array(nm["p90_abs_w"]), nm)
    return _cache["c"]


def lamp_p90():
    f = OUT / "lamp_p90.json"
    if f.exists():
        return json.loads(f.read_text())["P"]
    sp = []
    for p in sorted((OUT / "q50/finedance").glob("*__V1.npz")):
        l = np.load(p)["lamp"].astype(float)
        sp.append(np.linalg.norm(np.gradient(l, axis=0) * 50, axis=1)[::5])
    P = float(np.percentile(np.concatenate(sp), 90))
    f.write_text(json.dumps(dict(P=P)))
    return P


def music_feat(ds, lk, cortex):
    k = (ds, lk, cortex)
    if k not in _cache:
        F = CS.music_features(ds, lk, cortex)
        _cache[k] = (F - F.mean(0)) / np.maximum(F.std(0), 1e-6)
    return _cache[k]


def runs(mask):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]]))
    return np.flatnonzero(d == 1), np.flatnonzero(d == -1)


# ---------------------------------------------------------------------------------------------------- phase statistics
def donors_for(lk, ds, rng):
    tt = tempo_table()
    mine = tt[lk]
    own = lk.split("_")[1] if lk.startswith("aioz_") else lk
    pool = [k for k, v in tt.items() if abs(v / mine - 1) <= 0.05 and k != lk and (k.split("_")[1] if k.startswith("aioz_") else k) != own and k.startswith(lk.split("_")[0])]
    if len(pool) < 5:
        pool = [k for k, v in tt.items() if abs(v / mine - 1) <= 0.05 and k != lk and (k.split("_")[1] if k.startswith("aioz_") else k) != own]
    if not pool:
        return []
    return [pool[i] for i in rng.choice(len(pool), N_DONOR, replace=len(pool) < N_DONOR)]


def stats_for_grid(t, b, par, off):
    """R and preferred phase at the four levels, hit scans at beat and half-beat grids"""
    R, P = [], []
    for lev in M.LEVELS:
        ph = M.phases(t, b, lev, par, off)
        if len(ph) == 0:
            R.append(np.nan), P.append(np.nan)
        else:
            r, p, _ = M.resultant(ph)
            R.append(r), P.append(p)
    return np.array(R), np.array(P), M.hit_scan(t, b), M.hit_scan(t, M.half_grid(b))


def phase_results(ev, win_pass, beats, lk, ds, par, off, dur):
    rng = np.random.default_rng(46102 + zlib.crc32(lk.encode()))
    rngd = np.random.default_rng(46103 + zlib.crc32(lk.encode()))
    shuf = [M.shuffle_ibi(beats, rng) for _ in range(N_SHUF)]
    donors = [M.donor_grid(load_beats(d), beats[0], max(beats[-1], dur)) for d in donors_for(lk, ds, rngd)]
    res = {}
    wp = np.asarray(win_pass, bool)
    for name, t_all in ev.items():
        win = (t_all * 50).astype(int) // 1000
        for setname, t in (("ALL", t_all), ("PASS", t_all[(win < len(wp)) & wp[np.minimum(win, len(wp) - 1)]])):
            t = t[(t >= beats[0]) & (t < beats[-1])]
            r = dict(n=len(t), off_med=float(np.median(M.signed_offset(t, beats))) if len(t) else np.nan)
            r["real"] = stats_for_grid(t, beats, par, off) if len(t) else None
            if len(t) >= 30:
                for cname, grids in (("shuf", shuf), ("donor", donors)):
                    if not grids:
                        r[cname] = None
                        continue
                    acc = [stats_for_grid(t, g, par, off) for g in grids]
                    r[cname] = tuple(np.nanmean([a[i] for a in acc], 0) for i in range(4))
            res[(setname, name)] = r
    return res


# ---------------------------------------------------------------------------------------------------- tempo, density, pauses
def song_numbers(speed, o, beats, ev_rates, dur_motion):
    mad = 1.4826 * np.median(np.abs(o - np.median(o)))
    pk, _ = find_peaks(o, prominence=max(mad, 1e-9), distance=10)
    x = o - o.mean()
    f = np.fft.rfft(x, 2 * len(x))
    ac = np.fft.irfft(f * np.conj(f))[:len(x)]
    ac = ac / ac[0]
    p1 = float(ac[30:121].max())
    f_b = np.clip(np.round(beats * 100).astype(int), 0, len(o) - 1)
    ob = np.array([o[max(i - 3, 0):i + 4].max() for i in f_b])
    p2 = float(ob.mean() / max(o.mean(), 1e-9))
    pm = C.pause_mask(speed)
    s, e = runs(pm)
    d = (e - s) / 50.0
    T = len(speed) / 50.0
    mid = (d >= 2) & (d <= 8)
    return dict(tempo=60 / float(np.median(np.diff(beats))), onset_density=len(pk) / (len(o) / 100.0), P1=p1, P2=p2, pause_occ=float(pm.mean()), long_occ=float(d[mid].sum() / T),
                over8_occ=float(d[d > 8].sum() / T), pause_n=len(d), long_n_per_min=float(mid.sum() / (T / 60)), long_mean_dur=float(d[mid].mean()) if mid.any() else np.nan, rate=ev_rates, dur=T)


# ---------------------------------------------------------------------------------------------------- structure
def peaks_of(F, half):
    nv = CS.novelty(F, half=half, sigma=half / 2)
    return nv, CS.peaks(nv, min_dist=half)


def blocks(F, blk=4):
    n = len(F)
    X = np.full((n, F.shape[1] * blk), np.nan)
    for k in range(n - blk + 1):
        X[k] = F[k:k + blk].ravel()
    return X


def novelty_blocks(X, half):
    ok = np.isfinite(X[:, 0])
    nv = np.full(len(X), np.nan)
    nv[:ok.sum()] = CS.novelty(X[ok], half=half, sigma=half / 2)
    return nv, CS.peaks(nv, min_dist=half)


def corr_many(x, Y):
    """Pearson of x (n,) with each row of Y (k, n) over the pairwise finite samples, vectorised; < 10 samples -> NaN"""
    m = np.isfinite(x)[None] & np.isfinite(Y)
    xm, Ym = np.where(m, x[None], 0.0), np.where(m, Y, 0.0)
    n = m.sum(1)
    sx, sy = xm.sum(1), Ym.sum(1)
    cov = (xm * Ym).sum(1) - sx * sy / np.maximum(n, 1)
    vx, vy = (xm ** 2).sum(1) - sx ** 2 / np.maximum(n, 1), (Ym ** 2).sum(1) - sy ** 2 / np.maximum(n, 1)
    with np.errstate(invalid="ignore", divide="ignore"):
        r = cov / np.sqrt(vx * vy)
    return np.where((n >= 10) & (vx > 0) & (vy > 0), r, np.nan)


def ranked(x):
    """ranks over the finite values once (NaN kept): the Spearman used for repetition curves ranks each curve once, not per shift"""
    r = np.full(len(x), np.nan)
    m = np.isfinite(x)
    r[m] = rankdata(x[m])
    return r


def align(mot_pk, mot_curve, mus_pk, mus_curve, n, rng, tok_ok, rep_m=None, rep_u=None):
    """per delay: boundary hit share (real, circular-shift null mean), novelty Pearson (real, null mean, null 2.5/97.5), repetition Spearman (same)"""
    shifts = [int(rng.integers(10, max(n - 10, 11))) for _ in range(N_CIRC)]
    mp_ = np.asarray([k for k in mot_pk if tok_ok[k]], int)
    res = dict(n_mot=len(mp_), n_mus=len(mus_pk))
    hit_r, hit_n, c_r, c_n, c_lo, c_hi, r_r, r_n = [], [], [], [], [], [], [], []
    for d in DELAYS:
        def hit(bset):
            if len(mp_) == 0 or len(bset) == 0:
                return np.nan
            tgt = np.asarray(bset) - d
            return float(np.mean([np.abs(tgt - k).min() <= 1 for k in mp_]))
        hit_r.append(hit(mus_pk))
        hit_n.append(np.nanmean([hit((np.asarray(mus_pk) + s) % n) for s in shifts[:100]]) if len(mus_pk) and len(mp_) else np.nan)
        x = np.where(tok_ok, mot_curve, np.nan)
        idx = (np.arange(n)[None] - (np.asarray(shifts)[:, None] - d)) % n
        c_r.append(corr_many(x, np.roll(mus_curve, -d)[None])[0])
        cn = corr_many(x, mus_curve[idx])
        c_n.append(np.nanmean(cn)), c_lo.append(np.nanpercentile(cn, 2.5)), c_hi.append(np.nanpercentile(cn, 97.5))
        if rep_m is not None:
            xr = ranked(np.where(tok_ok, rep_m, np.nan))
            ru = ranked(rep_u)
            r_r.append(corr_many(xr, np.roll(ru, -d)[None])[0])
            r_n.append(np.nanmean(corr_many(xr, ru[idx])))
    res.update(hit=np.array(hit_r), hit_null=np.array(hit_n), corr=np.array(c_r), corr_null=np.array(c_n), corr_lo=np.array(c_lo), corr_hi=np.array(c_hi))
    if rep_m is not None:
        res.update(rep=np.array(r_r), rep_null=np.array(r_n))
    return res


def control_tokens(q50, lamp, win_pass, nm):
    """whole-song control tokens from consecutive 1000-sample windows -> (n_tok, 8) in CTL_NAMES order, (n_tok, 5) structure vector, token pass mask"""
    nwin = (len(q50) - 1) // 1000
    cols = []
    for w in range(nwin):
        r = C.finalise(C.raw_window(q50[1000 * w:1000 * w + 1001].astype(float), lamp[1000 * w:1000 * w + 1001].astype(float)), nm)
        cols.append(np.column_stack([r["vigour"], r["vj"], r["vl"], r["height"], r["sharp"], r["pause_prob"], r["accent_mean"], r["dir"][:, 2]]))
    if not cols:
        return None, None, None
    T = np.concatenate(cols)
    ok = np.repeat(np.asarray(win_pass, bool)[:nwin], C.NTOK)
    S = np.column_stack([T[:, 0], T[:, 3], np.nan_to_num(T[:, 4]), T[:, 5], T[:, 6]])
    S = (S - S.mean(0)) / np.maximum(S.std(0), 1e-9)
    return T, S, ok


def structure(ds, lk, S, ok, rng):
    out = {}
    n = len(S)
    Xb = blocks(S)
    rep_m = CS.repetition(S)
    musics = [("ear", music_feat(ds, lk, False))] + ([("cortex", music_feat(ds, lk, True))] if ds == "finedance" else [])
    for mname, F in musics:
        m = min(n, len(F))
        Fm = F[:m]
        rep_u = CS.repetition(Fm)
        for half in SCALES:
            nv_u, pk_u = peaks_of(Fm, half)
            for kind, curve_fn in (("control", lambda h: peaks_of(S[:m], h)), ("motif", lambda h: novelty_blocks(Xb[:m], h))):
                nv_m, pk_m = curve_fn(half)
                for setname, tok_ok in (("ALL", np.ones(m, bool)), ("PASS", ok[:m])):
                    out[(setname, mname, kind, half)] = align(pk_m, nv_m, pk_u, nv_u, m, rng, tok_ok, rep_m[:m] if half == SCALES[0] else None, rep_u if half == SCALES[0] else None)
    return out


# ---------------------------------------------------------------------------------------------------- per sequence
def run_one(args):
    ds, path = args
    dst = RES / "results" / ds / (path.stem + ".pkl")
    if dst.exists():
        return path.name, "skip"
    lk = CS.lane_key(path.name)
    if not beats_path(lk).exists() or not (CS.LANES[ds] / f"{lk}.npz").exists():
        return path.name, "no grid or lanes"
    import braindump as bd
    z = np.load(path)
    q50, lamp, wp = z["q50"].astype(float), z["lamp"].astype(float), z["win_pass"]
    beats = load_beats(lk)
    if len(beats) < 8:
        return path.name, "few beats"
    mean, std = bd.stats()
    ear = np.load(CS.LANES[ds] / f"{lk}.npz")["ear"]
    raw = ear * std + mean
    o = raw[:, 40]
    f_b = np.clip(np.round(beats * 100).astype(int), 0, len(o) - 1)
    par, off = M.choose_bar(beats, [o[max(i - 3, 0):i + 4].max() for i in f_b])
    A, p90, nm = consts()
    ev = M.events(q50, lamp, A, p90, lamp_p90())
    dur = len(q50) / 50
    speed = np.linalg.norm(np.gradient(lamp, axis=0) * 50, axis=1)
    rate = {k: len(v) / (dur / 60) for k, v in ev.items()}
    res = dict(ds=ds, name=path.name, lk=lk, group=str(z["group"]), split=str(z["split"]), par=par, off=off, n_beats=len(beats), dur=dur)
    res["phase"] = phase_results(ev, wp, beats, lk, ds, par, off, dur)
    res["numbers"] = song_numbers(speed, o, beats, rate, dur)
    tok = control_tokens(q50, lamp, wp, nm)
    if tok[0] is not None:
        T, S, ok = tok
        ac = CS.acoustic(ear, mean, std, beats if True else None)
        n = min(len(T), len(ac))
        res["tokens"] = dict(ctl=T[:n].astype(np.float32), ac=ac[:n].astype(np.float32), ok=ok[:n])
        res["struct"] = structure(ds, lk, S[:n], ok[:n], np.random.default_rng(46105 + zlib.crc32(path.name.encode())))
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp")
    tmp.write_bytes(pickle.dumps(res))
    tmp.replace(dst)
    return path.name, "ok"


def main(procs=6):
    lamp_p90()
    jobs = [(ds, p) for ds in DS for p in sorted((OUT / "q50" / ds).glob("*.npz"))]
    cnt = {}
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (name, st) in enumerate(pool.imap_unordered(run_one, jobs, chunksize=2)):
            cnt[st] = cnt.get(st, 0) + 1
            if i % 50 == 0:
                print(i, "/", len(jobs), name, st, cnt, flush=True)
    print("RUN DONE", cnt, flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
