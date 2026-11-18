"""WO52 (BRAIN_SPEC 7.81 item 4): movement rhythm vs beat and event responses in human data. Rules: docs/RHYTHM_EVENTS_RULES.md. Brain env.

    rhythm_events.py scan [PROCS]       inputs present and readable -> rhythm/scan.json
    rhythm_events.py extract [PROCS]    per-window rhythm, per-token response raws, music events -> rhythm/{windows,tokens}_<ds>.npz, events.json
    rhythm_events.py analyse [PROCS]    analyses A and B -> rhythm/results.json, lock_<ds>.npz, hist.png
Report only; nothing upstream is recomputed.
"""
import json
import re
import sys
import warnings
from multiprocessing import Pool
from pathlib import Path

import numpy as np
from scipy.signal import detrend

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
warnings.filterwarnings("ignore", "All-NaN slice")
warnings.filterwarnings("ignore", "Mean of empty slice")

B = Path("/secondary/hyst-data/body")
OUT = B / "rhythm"
DS = ("finedance", "aioz", "phantom", "motorica")
SEQ = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}
LANES = {"finedance": B / "t0/lanes", "aioz": B / "t0/lanes", "phantom": B / "t0_phantom/lanes", "motorica": B / "t0_motorica/lanes"}
FS, TOK, NT = 50, 25, 40
LAG_LO, LAG_HI = 10, 125                     # 0.2 .. 2.5 s at 50 Hz
STRENGTH, STRENGTH_N = 0.2, 0.3
EDGES = ((0.4, 0.6), (0.8, 1.25), (1.6, 2.5))
EDGES_N = ((0.45, 0.55), (0.9, 1.11), (1.8, 2.22))
BIN_NAMES = ("none", "1/2", "1", "2", "other")
WS = (3, 4)
PAD_LIB = 1.5
HOLD_TH, BURST_SD = 0.2, (1.0, 1.5)
LAGS = np.round(np.arange(-1.0, 1.0, 0.1), 2)       # bin starts; bin j = [LAGS[j], LAGS[j] + 0.1)
NSHIFT, NBOOT, NDRAW = 200, 2000, 20
SEED_BOOT, SEED_SHIFT, SEED_C1, SEED_C2 = 52101, 52102, 52103, 52104
RESP = ("hold", "change", "change_fam", "change_post", "burst", "burst15")
EVENTS = ("onset", "dropout_on", "dropout_end", "novelty", "cortex_L2", "cortex_total")
SIGNALS = ("lamp", "joint", "yaw")


def music_key(key):
    return re.sub(r"_p\d+$", "", key.split("__")[0])


# ---------------------------------------------------------------------------------------------------- rhythm
def rhythm(x):
    """speed samples (50 Hz) -> (period s, strength); (nan, 0) when no peak or no variance"""
    x = detrend(np.asarray(x, np.float64), type="linear")
    e = (x ** 2).sum()
    if e < 1e-12 or len(x) <= LAG_HI + 1:
        return np.nan, 0.0
    n = len(x)
    f = np.fft.rfft(x, 2 * n)
    a = np.fft.irfft(f * np.conj(f))[:n] / e
    l = np.arange(LAG_LO, LAG_HI + 1)
    loc = l[(a[l] > a[l - 1]) & (a[l] >= a[l + 1])]
    if not len(loc):
        return np.nan, 0.0
    k = int(loc[np.argmax(a[loc])])
    y0, y1, y2 = a[k - 1], a[k], a[k + 1]
    den = y0 - 2 * y1 + y2
    d = 0.5 * (y0 - y2) / den if den < 0 else 0.0
    return (k + float(np.clip(d, -0.5, 0.5))) / FS, float(a[k])


def bins(r, strength, narrow=False):
    """ratio and strength arrays -> bin codes 0 none, 1 '1/2', 2 '1', 3 '2', 4 other"""
    r, s = np.asarray(r, float), np.asarray(strength, float)
    out = np.full(r.shape, 4, np.int8)
    for i, (lo, hi) in enumerate(EDGES_N if narrow else EDGES):
        out[(r >= lo) & (r <= hi)] = i + 1
    out[~np.isfinite(r) | (s < (STRENGTH_N if narrow else STRENGTH))] = 0
    return out


def lib_period(beats, a, b):
    bb = beats[(beats >= a - PAD_LIB) & (beats <= b + PAD_LIB)]
    return float(np.median(np.diff(bb))) if len(bb) >= 4 else np.nan


def speeds(q50, lamp):
    w = np.gradient(np.asarray(q50, float), axis=0) * FS
    v = np.gradient(np.asarray(lamp, float), axis=0) * FS
    return dict(lamp=np.linalg.norm(v, axis=1), joint=np.abs(w).sum(1), yaw=np.abs(w[:, 0]))


# ---------------------------------------------------------------------------------------------------- responses and events
def hold_time(speed, k):
    """time (s, window-relative) of the first sample of the still run overlapping token k, or the token start"""
    import controls_lib as CL
    pm = CL.pause_mask(speed)
    idx = np.flatnonzero(pm[k * TOK:(k + 1) * TOK])
    if not len(idx):
        return k * TOK / FS
    i = k * TOK + int(idx[0])
    while i > 0 and pm[i - 1]:
        i -= 1
    return i / FS


def peaks_q(x, span, q):
    """cortexev.peaks with percentile q (causal 0.3 s mean, max within +-1 s, above the preceding 1 s)"""
    import cortexev as CE
    s = CE.causal_mean(x, 3)
    ok = span & np.isfinite(s)
    if ok.sum() < 20:
        return np.zeros(0, int)
    th = np.percentile(s[ok], q)
    out = []
    for k in np.flatnonzero(ok & (s >= th)):
        if k >= 10 and s[k] >= np.nanmax(s[max(k - 10, 0):k + 11]) and s[k] > np.nanmax(s[k - 10:k]):
            out.append(k)
    return np.array(out, int)


def dropouts_low(L):
    """cortexev.dropouts with the low-band condition only (WO50 amendment)"""
    import cortexev as CE
    mL = CE.run_median(L)
    n, on, end, k = len(L), [], [], 0
    while k < n:
        bl = mL[k]
        c = lambda j: L[j] < 0.25 * bl  # noqa: E731
        if not (np.isfinite(bl) and bl > 0 and c(k) and k + 4 <= n and all(c(j) for j in range(k, k + 4))):
            k += 1
            continue
        j, e = k + 4, None
        while j + 3 <= n:
            if not any(c(i) for i in range(j, j + 3)):
                e = j
                break
            j += 1
        on.append(k)
        if e is None:
            break
        end.append(e)
        k = e
    return np.array(on, int), np.array(end, int)


_ST = {}


def music_events(song, ds):
    import cortexev as CE
    if not _ST:
        import braindump as bd
        import librosa
        _ST["mean"], _ST["std"] = (np.asarray(x, np.float64) for x in bd.stats())
        cen = librosa.mel_frequencies(n_mels=34, fmin=30, fmax=16000)[1:-1]
        _ST["lo"] = np.flatnonzero(cen < 200)
    z = np.load(LANES[ds] / f"{song}.npz")
    ear, s10 = z["ear"].astype(np.float64), z["s10"].astype(np.float64)
    n10 = min(len(s10), len(ear) // 10)
    ts = (10 * np.arange(n10) + 9) / 100.0
    raw = ear * _ST["std"] + _ST["mean"]
    L = CE.ten(10 ** (raw[:, _ST["lo"]] / 10).mean(1), n10)
    on, end = dropouts_low(L)
    every = np.ones(n10, bool)
    ev = dict(onset=ts[peaks_q(CE.ten(raw[:, 40], n10), every, 95)], dropout_on=ts[on], dropout_end=ts[end],
              novelty=np.asarray(np.load(B / f"pulse2/songs/{song}.npz")["boundaries"], float),
              cortex_L2=ts[peaks_q(s10[:n10, 1], every, 90)], cortex_total=ts[peaks_q(s10[:n10, 4], ts >= 16.0, 90)])
    return {k: np.sort(v).round(3).tolist() for k, v in ev.items()}, int(z["n_frames"]) / 100.0


# ---------------------------------------------------------------------------------------------------- per sequence
_FAM = {}


def seq_extract(args):
    ds, key, rows = args          # rows: list of (win, ctl (40,18), code1 (40,), group)
    try:
        song = music_key(key)
        q = np.load(B / f"controls/q50/{ds}/{key}.npz")
        qwin = list(q["win"])
        post = np.asarray(np.load(SEQ[ds] / f"{key}.npz")["posture"], np.float64)
        beats = np.asarray(json.loads((B / f"beatv/librosa/{song}.json").read_text())["beats"], float)
        p2 = np.load(B / f"pulse2/songs/{song}.npz")
        per, conf = np.asarray(p2["period"], float), np.asarray(p2["conf"], float)
        W, T = [], []
        for w, ctl, c1, group in rows:
            i = qwin.index(w)
            sp = speeds(q["q50"][i], q["lamp"][i])
            t0 = 20.0 * w
            for Wn in WS:
                for s in range(0, 21 - Wn):
                    a, b = t0 + s, t0 + s + Wn
                    sl = slice(s * FS, (s + Wn) * FS)
                    rec = dict(W=Wn, win=w, start=a)
                    for sig in SIGNALS:
                        rec[f"per_{sig}"], rec[f"str_{sig}"] = rhythm(sp[sig][sl])
                    fr = slice(int(round(a * 100)), int(round(b * 100)))
                    rec["lib"] = lib_period(beats, a, b)
                    rec["pul"] = float(np.median(per[fr])) if len(per[fr]) else np.nan
                    rec["conf"] = float(np.median(conf[fr])) if len(conf[fr]) else np.nan
                    W.append(rec)
            pt = post[w * NT * 50:(w + 1) * NT * 50].reshape(NT, 50, 5).mean(1)
            for k in range(NT):
                T.append(dict(win=w, k=k, t=t0 + 0.5 * k, pause=float(ctl[k, 14]), vig=float(ctl[k, 0]), fam=int(_FAM["m"][int(c1[k])]),
                              post=pt[k], hold_t=t0 + hold_time(sp["lamp"], k)))
        return ds, key, song, rows[0][3], W, T, None
    except Exception as e:  # noqa: BLE001
        return ds, key, None, None, None, None, repr(e)


def song_extract(args):
    ds, song = args
    try:
        ev, dur = music_events(song, ds)
        return song, ev, dur, None
    except Exception as e:  # noqa: BLE001
        return song, None, None, repr(e)


def windows_by_seq(ds):
    z = {k: np.load(B / f"grammar/win_{ds}.npz")[k] for k in ("key", "win", "ctl", "code1", "group")}
    out = {}
    for i in range(len(z["key"])):
        key = str(z["key"][i])
        if key.split("__")[1] not in ("V1", "V2"):
            continue
        out.setdefault(key, []).append((int(z["win"][i]), z["ctl"][i], z["code1"][i], str(z["group"][i])))
    return {k: sorted(v, key=lambda r: r[0]) for k, v in out.items()}


def scan(procs):
    OUT.mkdir(parents=True, exist_ok=True)
    res = {}
    for ds in DS:
        seqs = windows_by_seq(ds)
        bad = []
        for key, rows in seqs.items():
            song = music_key(key)
            try:
                q = np.load(B / f"controls/q50/{ds}/{key}.npz")
                assert set(r[0] for r in rows) <= set(int(w) for w in q["win"]), "window missing in q50"
                assert np.isfinite(q["lamp"]).all() and np.isfinite(q["q50"]).all(), "q50 non-finite"
                assert (SEQ[ds] / f"{key}.npz").exists(), "seq"
                b = json.loads((B / f"beatv/librosa/{song}.json").read_text())["beats"]
                assert len(b) > 0, "no librosa beats"
                assert (B / f"pulse2/songs/{song}.npz").exists() and (LANES[ds] / f"{song}.npz").exists(), "pulse2 / lanes"
                assert all(np.isfinite(r[1]).all() for r in rows), "ctl non-finite"
            except Exception as e:  # noqa: BLE001
                bad.append([key, repr(e)])
        res[ds] = dict(sequences=len(seqs), windows=sum(len(v) for v in seqs.values()), songs=len({music_key(k) for k in seqs}),
                       groups=len({v[0][3] for v in seqs.values()}), bad=bad)
        print("SCAN", ds, {k: (v if k != "bad" else len(v)) for k, v in res[ds].items()}, flush=True)
    (OUT / "scan.json").write_text(json.dumps(res, indent=1))


def extract(procs):
    import t1b_tokens as TK
    cb1 = TK.load_vq().vq.vq1.cb.numpy().astype(np.float64)
    _FAM["m"] = TK.nearest(cb1, TK.kmeans(cb1, 32, 45004))
    allev, durs, fails = {}, {}, []
    with Pool(procs, initializer=_FAM.update, initargs=(dict(m=_FAM["m"]),)) as pool:
        for ds in DS:
            seqs = windows_by_seq(ds)
            Wrec, Trec = [], []
            for ds_, key, song, group, W, T, err in pool.imap_unordered(seq_extract, [(ds, k, v) for k, v in sorted(seqs.items())], chunksize=4):
                if err:
                    fails.append([ds, key, err])
                    print("FAIL", ds, key, err, flush=True)
                    continue
                for r in W:
                    r.update(key=key, song=song, group=group)
                for r in T:
                    r.update(key=key, song=song, group=group)
                Wrec += W
                Trec += T
            np.savez(OUT / f"windows_{ds}.npz", **{k: np.array([r[k] for r in Wrec]) for k in Wrec[0]})
            np.savez(OUT / f"tokens_{ds}.npz", **{k: np.array([r[k] for r in Trec]) for k in Trec[0]})
            songs = sorted({r["song"] for r in Wrec})
            for song, ev, dur, err in pool.imap_unordered(song_extract, [(ds, s) for s in songs]):
                if err:
                    fails.append([ds, song, err])
                    print("FAIL", ds, song, err, flush=True)
                    continue
                allev[song], durs[song] = dict(ev, ds=ds), dur
            print("extracted", ds, len(seqs), "sequences", len(Wrec), "analysis windows", len(songs), "songs", flush=True)
    (OUT / "events.json").write_text(json.dumps(dict(events=allev, duration_s=durs, failures=fails)))
    print("EXTRACT DONE failures", len(fails), flush=True)


# ---------------------------------------------------------------------------------------------------- analysis A
def boot_idx(n, seed=SEED_BOOT):
    return np.random.default_rng(seed).integers(0, n, (NBOOT, n))


def ci(x):
    return [float(v) for v in np.percentile(x, [2.5, 97.5])]


def chance_periods(per, song, group, tempo, rng_c1, rng_c2):
    """beat periods per window (nan = none) -> (c1 (n, NDRAW), c2 (n, NDRAW)) replacement periods (nan where unavailable)"""
    n = len(per)
    ok = np.isfinite(per)
    c1 = np.full((n, NDRAW), np.nan)
    songs = np.unique(song)
    by_song = {s: per[(song == s) & ok] for s in songs}
    grp = {s: group[song == s][0] for s in songs}
    tsongs = np.array([s for s in songs if np.isfinite(tempo.get(s, np.nan)) and len(by_song[s])])
    tt = np.array([tempo[s] for s in tsongs])
    tg = np.array([grp[s] for s in tsongs])
    for s in songs:
        idx = np.flatnonzero((song == s) & ok)
        if not len(idx) or not np.isfinite(tempo.get(s, np.nan)):
            continue
        cand = tsongs[(np.abs(tt / tempo[s] - 1) <= 0.10) & (tg != grp[s])]
        if not len(cand):
            continue
        pick = rng_c1.integers(0, len(cand), (len(idx), NDRAW))
        for j, cs in enumerate(cand):
            m = pick == j
            if m.any():
                pool = by_song[cs]
                c1[idx[:, None].repeat(NDRAW, 1)[m], np.nonzero(m)[1]] = pool[rng_c1.integers(0, len(pool), m.sum())]
    c2 = np.full((n, NDRAW), np.nan)
    good = np.flatnonzero(ok)
    for d in range(NDRAW):
        c2[good, d] = per[good][rng_c2.permutation(len(good))]
    return c1, c2


def song_stats(groups, gid, movp, stren, per, c1, c2, narrow):
    """per group sums: n_rh, n_cl, z (complex sum), bin counts; chance n_rh, n_cl, z (mean over draws)"""
    G = len(groups)
    ok = np.isfinite(per)
    bn = bins(movp / per, stren, narrow)
    rh = ok & (bn > 0)
    th = STRENGTH_N if narrow else STRENGTH
    rhm = np.isfinite(movp) & (stren >= th)
    lr = np.log2(movp / per)
    st = dict(n_rh=np.bincount(gid[rh], minlength=G).astype(float), n_cl=np.bincount(gid[rh & (bn >= 1) & (bn <= 3)], minlength=G).astype(float),
              z=np.bincount(gid[rh], np.cos(2 * np.pi * lr[rh]), G) + 1j * np.bincount(gid[rh], np.sin(2 * np.pi * lr[rh]), G),
              bins=np.stack([np.bincount(gid[ok & (bn == b)], minlength=G) for b in range(5)], 1).astype(float))
    for name, C in (("c1", c1), ("c2", c2)):
        n_rh, n_cl, z = np.zeros(G), np.zeros(G), np.zeros(G, complex)
        for d in range(NDRAW):
            p = C[:, d]
            m = rhm & ok & np.isfinite(p)
            b = bins(movp / p, stren, narrow)
            l2 = np.log2(movp[m] / p[m])
            n_rh += np.bincount(gid[m], minlength=G)
            n_cl += np.bincount(gid[m & (b >= 1) & (b <= 3)], minlength=G)
            z += np.bincount(gid[m], np.cos(2 * np.pi * l2), G) + 1j * np.bincount(gid[m], np.sin(2 * np.pi * l2), G)
        st[f"{name}_n_rh"], st[f"{name}_n_cl"], st[f"{name}_z"] = n_rh / NDRAW, n_cl / NDRAW, z / NDRAW
    return st


def summarise_A(st, idx):
    def share(a, b, ix=None):
        a, b = (a, b) if ix is None else (a[ix].sum(-1), b[ix].sum(-1))
        return a.sum(-1) / np.maximum(b.sum(-1), 1e-12) if ix is None else a / np.maximum(b, 1e-12)

    def conc(z, n, ix=None):
        return np.abs(z.sum(-1)) / np.maximum(n.sum(-1), 1e-12) if ix is None else np.abs(z[ix].sum(-1)) / np.maximum(n[ix].sum(-1), 1e-12)

    out = dict(groups=int(len(st["n_rh"])), windows=int(st["bins"].sum()), rhythmic=int(st["n_rh"].sum()),
               bin_share_all={BIN_NAMES[b]: float(st["bins"][:, b].sum() / max(st["bins"].sum(), 1)) for b in range(5)},
               bin_share_rhythmic={BIN_NAMES[b]: float(st["bins"][:, b].sum() / max(st["bins"][:, 1:].sum(), 1)) for b in range(1, 5)},
               cluster=float(share(st["n_cl"], st["n_rh"])), conc=float(conc(st["z"], st["n_rh"])))
    for c in ("c1", "c2"):
        keep = st[f"{c}_n_rh"] > 0
        ix = idx
        cs = share(st[f"{c}_n_cl"], st[f"{c}_n_rh"])
        cc = conc(st[f"{c}_z"], st[f"{c}_n_rh"])
        # observed restricted to the groups that have this chance (c1 drops groups with no tempo partner)
        n_rh_o = np.where(keep, st["n_rh"], 0)
        n_cl_o = np.where(keep, st["n_cl"], 0)
        z_o = np.where(keep, st["z"], 0)
        obs_s, obs_c = share(n_cl_o, n_rh_o), conc(z_o, n_rh_o)
        bs = share(n_cl_o, n_rh_o, ix) - share(st[f"{c}_n_cl"], st[f"{c}_n_rh"], ix)
        bc = conc(z_o, n_rh_o, ix) - conc(st[f"{c}_z"], st[f"{c}_n_rh"], ix)
        out[c] = dict(groups=int(keep.sum()), groups_left_out=int((~keep & (st["n_rh"] > 0)).sum()), cluster_obs=float(obs_s), cluster_chance=float(cs),
                      excess=float(obs_s - cs), excess_ci=ci(bs), conc_obs=float(obs_c), conc_chance=float(cc), conc_excess=float(obs_c - cc), conc_excess_ci=ci(bc))
    return out


def analyse_A(procs):
    res, hist = {}, {}
    per_ds = {}
    for ds in DS:
        z = dict(np.load(OUT / f"windows_{ds}.npz"))
        groups, gid = np.unique(z["group"], return_inverse=True)
        per_ds[ds] = (z, groups, gid)
    for ds in DS:
        z, groups, gid = per_ds[ds]
        for Wn in WS:
            m = z["W"] == Wn
            zz = {k: v[m] for k, v in z.items()}
            g = gid[m]
            for src, per in (("librosa", zz["lib"]), ("pulse2", zz["pul"])):
                tempo = {}
                ref = (z["W"] == 3) & np.isfinite(z["lib" if src == "librosa" else "pul"])
                for s in np.unique(z["song"][ref]):
                    tempo[s] = float(np.median(z["lib" if src == "librosa" else "pul"][ref & (z["song"] == s)]))
                rng1 = np.random.default_rng([SEED_C1, DS.index(ds), Wn, int(src == "pulse2")])
                rng2 = np.random.default_rng([SEED_C2, DS.index(ds), Wn, int(src == "pulse2")])
                c1, c2 = chance_periods(per, zz["song"], zz["group"], tempo, rng1, rng2)
                for sig in SIGNALS:
                    for narrow in (False, True):
                        if Wn == 4 and narrow:
                            continue
                        var = "W4" if Wn == 4 else ("narrow" if narrow else "main")
                        if sig != "lamp" and var != "main":
                            continue
                        movp, stren = zz[f"per_{sig}"], zz[f"str_{sig}"]
                        subsets = [("all", np.ones(len(per), bool))]
                        if src == "pulse2" and sig == "lamp" and var == "main":
                            subsets += [("conf>=0.3", zz["conf"] >= 0.3), ("conf<0.3", zz["conf"] < 0.3)]
                        if sig == "lamp" and var == "main":
                            subsets += [("V1", np.char.endswith(zz["key"], "__V1")), ("V2", np.char.endswith(zz["key"], "__V2"))]
                        for sub, sm in subsets:
                            pp = np.where(sm, per, np.nan)
                            st = song_stats(groups, g, movp, stren, pp, np.where(sm[:, None], c1, np.nan), np.where(sm[:, None], c2, np.nan), narrow)
                            per_ds.setdefault(("st", src, sig, var, sub), {})[ds] = st
                        if var == "main":
                            ok = np.isfinite(per) & np.isfinite(movp) & (stren >= STRENGTH)
                            hist[f"{ds}|{src}|{sig}"] = np.histogram(np.log2(movp[ok] / per[ok]), np.arange(-3, 3.0001, 0.05))[0].tolist()
                print("A", ds, Wn, src, flush=True)
    for k, v in per_ds.items():
        if not (isinstance(k, tuple) and k[0] == "st"):
            continue
        _, src, sig, var, sub = k
        for ds in list(DS) + ["all"]:
            if ds == "all":
                st = {f: np.concatenate([v[d][f] for d in DS]) for f in v[DS[0]]}
            else:
                st = v[ds]
            res[f"{ds}|{src}|{sig}|{var}|{sub}"] = summarise_A(st, boot_idx(len(st["n_rh"])))
    return res, hist


# ---------------------------------------------------------------------------------------------------- analysis B
def segments(win):
    """sorted window indices -> list of lists of consecutive windows"""
    segs = []
    for w in sorted(win):
        if segs and w == segs[-1][-1] + 1:
            segs[-1].append(w)
        else:
            segs.append([w])
    return segs


def lock_counts(resp, ev, span, rng, nshift=NSHIFT):
    """response times, music event times, (a, b) span -> obs counts (20,), n events, shifted counts (nshift, 20)"""
    a, b = span
    ev = np.asarray(ev, float)
    ev = ev[(ev - 1.1 >= a) & (ev + 1.1 <= b)]
    resp = np.asarray(resp, float)
    resp = resp[(resp >= a) & (resp < b)]
    nb = len(LAGS)
    if not len(ev):
        return np.zeros(nb), 0, np.zeros((nshift, nb))
    edges = np.append(LAGS, 1.0)

    def cnt(r):
        d = (r[..., None, :] - ev[:, None]).reshape(*r.shape[:-1], -1)
        j = np.floor((d + 1.0) / 0.1 + 1e-9).astype(int)
        ok = (d >= edges[0] - 1e-9) & (d < edges[-1] - 1e-9)
        if r.ndim == 1:
            return np.bincount(j[ok], minlength=nb)[:nb].astype(float)
        rows = np.broadcast_to(np.arange(r.shape[0])[:, None], j.shape)
        out = np.zeros((r.shape[0], nb))
        np.add.at(out, (rows[ok], j[ok]), 1)
        return out
    obs = cnt(resp)
    if not len(resp):
        return obs, len(ev), np.zeros((nshift, nb))
    off = rng.uniform(0, b - a, nshift)
    sh = a + np.mod(resp[None] - a + off[:, None], b - a)
    return obs, len(ev), cnt(sh)


def responses(T, D, vsd):
    """tokens of one sequence copy (dict of arrays, sorted by win, k) -> {resp: times}, spans"""
    out = {r: [] for r in RESP}
    spans = []
    for seg in segments(np.unique(T["win"])):
        m = np.isin(T["win"], seg)
        t, pause, vig, fam, post, ht = T["t"][m], T["pause"][m], T["vig"][m], T["fam"][m], T["post"][m], T["hold_t"][m]
        spans.append((t[0] + 0.5, t[-1] + 0.5))
        dpost = np.r_[np.nan, np.linalg.norm(np.diff(post, axis=0), axis=1)]
        prev = np.r_[False, np.ones(len(t) - 1, bool)]
        hold = prev & (pause >= HOLD_TH) & (np.r_[np.inf, pause[:-1]] < HOLD_TH)
        cf = prev & (fam != np.r_[-1, fam[:-1]])
        cp = prev & (dpost > D)
        dv = np.r_[np.nan, np.diff(vig)]
        out["hold"].append(ht[hold])
        out["change"].append(t[cf | cp])
        out["change_fam"].append(t[cf])
        out["change_post"].append(t[cp])
        out["burst"].append(t[prev & (dv > BURST_SD[0] * vsd)])
        out["burst15"].append(t[prev & (dv > BURST_SD[1] * vsd)])
    return {r: v for r, v in out.items()}, spans


def lock_ds(args):
    ds, D, vsd, events = args
    z = dict(np.load(OUT / f"tokens_{ds}.npz"))
    groups = np.unique(z["group"])
    gi = {g: i for i, g in enumerate(groups)}
    G, nb = len(groups), len(LAGS)
    obs = np.zeros((len(RESP), len(EVENTS), G, nb))
    nev = np.zeros((len(RESP), len(EVENTS), G))
    chm = np.zeros((len(RESP), len(EVENTS), G, nb))
    chs = np.zeros((len(RESP), len(EVENTS), NSHIFT, nb))
    rates = np.zeros((len(RESP), 2))       # responses, exposure seconds
    order = np.lexsort((z["k"], z["win"], z["key"]))
    z = {k: v[order] for k, v in z.items()}
    keys, starts = np.unique(z["key"], return_index=True)
    bounds = list(starts) + [len(z["key"])]
    for ki, key in enumerate(keys):
        sl = slice(bounds[ki], bounds[ki + 1])
        T = {k: v[sl] for k, v in z.items()}
        song, g = str(T["song"][0]), gi[str(T["group"][0])]
        if song not in events:
            continue
        rs, spans = responses(T, D, vsd)
        rng = np.random.default_rng([SEED_SHIFT, DS.index(ds), ki])
        for si, span in enumerate(spans):
            for ri, r in enumerate(RESP):
                rates[ri] += [len(rs[r][si]), span[1] - span[0]]
                for ei, e in enumerate(EVENTS):
                    o, n, c = lock_counts(rs[r][si], events[song][e], span, rng)
                    obs[ri, ei, g] += o
                    nev[ri, ei, g] += n
                    chm[ri, ei, g] += c.mean(0)
                    chs[ri, ei] += c
    np.savez(OUT / f"lock_{ds}.npz", obs=obs, nev=nev, chm=chm, chs=chs, groups=groups, rates=rates)
    return ds


def summarise_B(obs, nev, chm, chs, idx):
    """one response x event: obs/chm (G, nb), nev (G,), chs (NSHIFT, nb) -> dict"""
    N = nev.sum()
    if N == 0:
        return dict(events=0)
    ro, rc = obs.sum(0) / (N * 0.1), chm.sum(0) / (N * 0.1)
    ex = ro - rc
    j = int(np.argmax(ex))
    rs = chs / (N * 0.1)
    mx = (rs - rs.mean(0)).max(1)
    nb_ = nev[idx].sum(1)
    exb = (obs[idx].sum(1) - chm[idx].sum(1)) / (np.maximum(nb_, 1e-12)[:, None] * 0.1)
    c3 = (np.abs(LAGS + 0.05) <= 0.3 + 1e-9)
    return dict(events=int(N), rate_obs=ro.round(4).tolist(), rate_chance=rc.round(4).tolist(), peak_lag=float(LAGS[j] + 0.05), peak_excess=float(ex[j]),
                peak_excess_ci=ci(exb[:, j]), peak_ratio=float(ro[j] / max(rc[j], 1e-12)), p_max=float((1 + (mx >= ex[j]).sum()) / (1 + len(mx))),
                mean_rate_chance=float(rc.mean()), excess_pm03=float(ex[c3].mean()), excess_pm03_ci=ci(exb[:, c3].mean(1)))


def analyse_B(procs):
    ev = json.loads((OUT / "events.json").read_text())["events"]
    events = {s: {e: np.asarray(v[e], float) for e in EVENTS} for s, v in ev.items()}
    # pooled thresholds: posture distance p90 and vigour sd over all analysed tokens
    dists, vigs = [], []
    for ds in DS:
        z = np.load(OUT / f"tokens_{ds}.npz")
        order = np.lexsort((z["k"], z["win"], z["key"]))
        key, win, post = z["key"][order], z["win"][order], z["post"][order]
        same = (key[1:] == key[:-1]) & (win[1:] - win[:-1] <= 1)
        dists.append(np.linalg.norm(np.diff(post, axis=0), axis=1)[same])
        vigs.append(z["vig"])
    D, vsd = float(np.percentile(np.concatenate(dists), 90)), float(np.concatenate(vigs).std())
    print("thresholds D", D, "vigour sd", vsd, flush=True)
    with Pool(min(procs, len(DS))) as pool:
        list(pool.imap_unordered(lock_ds, [(ds, D, vsd, {s: events[s] for s in events if events[s] is not None}) for ds in DS]))
    res = {}
    L = {ds: dict(np.load(OUT / f"lock_{ds}.npz")) for ds in DS}
    for ds in list(DS) + ["all"]:
        if ds == "all":
            obs, nev, chm = (np.concatenate([L[d][f] for d in DS], 2) for f in ("obs", "nev", "chm"))
            chs = sum(L[d]["chs"] for d in DS)
            rates = sum(L[d]["rates"] for d in DS)
        else:
            obs, nev, chm, chs, rates = L[ds]["obs"], L[ds]["nev"], L[ds]["chm"], L[ds]["chs"], L[ds]["rates"]
        idx = boot_idx(obs.shape[2])
        for ri, r in enumerate(RESP):
            res[f"{ds}|{r}|rate_per_s"] = float(rates[ri, 0] / max(rates[ri, 1], 1e-12))
            for ei, e in enumerate(EVENTS):
                res[f"{ds}|{r}|{e}"] = summarise_B(obs[ri, ei], nev[ri, ei], chm[ri, ei], chs[ri, ei], idx)
    return res, dict(D_posture_deg=D, vigour_sd=vsd)


def hist_png(hist):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = np.arange(-3, 3, 0.05) + 0.025
    fig, axs = plt.subplots(2, 4, figsize=(16, 6), sharex=True)
    for i, src in enumerate(("librosa", "pulse2")):
        for j, ds in enumerate(DS):
            h = np.asarray(hist[f"{ds}|{src}|lamp"], float)
            ax = axs[i, j]
            ax.bar(x, h / max(h.sum(), 1), width=0.05, color="#4a6fa5")
            for v in (-1, 0, 1):
                ax.axvline(v, color="#c0504d", lw=0.8)
            ax.set_title(f"{ds} / {src}", fontsize=9)
            if i == 1:
                ax.set_xlabel("log2(movement period / beat period)")
    fig.tight_layout()
    fig.savefig(OUT / "hist.png", dpi=110)


def analyse(procs):
    resA, hist = analyse_A(procs)
    resB, th = analyse_B(procs)
    (OUT / "results.json").write_text(json.dumps(dict(A=resA, B=resB, hist=hist, thresholds=th), indent=1))
    hist_png(hist)
    print("ANALYSE DONE", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    if cmd in ("scan", "extract", "analyse"):
        globals()[cmd](procs)
    else:
        print(__doc__)
