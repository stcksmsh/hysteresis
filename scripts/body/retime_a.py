"""WO55 part A (BRAIN_SPEC 7.87): re-timed WO47 / WO52 / WO53 lamp analyses and the token-level effect. Rules: docs/RETIME_RULES.md. Brain env.

    retime_a.py bas [PROCS]      WO47 realised BAS, lamp re-timed               -> retime/a/bas/<ds>.json
    retime_a.py v3 [PROCS]       WO47 V3 realised table, lamp/joints re-timed   -> retime/a/v3.json
    retime_a.py events [PROCS]   WO52 analysis B, response times re-timed       -> retime/a/events/{orig,ret}/results.json
    retime_a.py rhythm [PROCS]   WO53 B lamp column, lamp re-timed              -> retime/a/rawrhythm/{orig,ret}/results.json
    retime_a.py tokens [PROCS]   token-level effect on A's controls            -> retime/a/tokens.json
    retime_a.py report           headline tables                                 -> retime/a/tables.md
Report only; nothing upstream is recomputed or overwritten. Errors are caught per item and logged to retime/a/failed.txt.
"""
import json
import pickle
import sys
import zlib
from multiprocessing import Pool
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))
import retime as RT  # noqa: E402

B = Path("/secondary/hyst-data/body")
OUT = B / "retime/a"
DS = ("finedance", "aioz", "phantom", "motorica")
FS = 50
NB, SEED_BOOT47, SEED_BOOT52 = 2000, 47101, 52101


def var_of(key):
    """'fd_001__V1' / '..__V2m' / 'fd_001__V1.npz' -> 'V1' / 'V2'"""
    return Path(key).stem.split("__")[1][:2] if "__" in key else Path(key).name.split("__")[1][:2]


def fail(what, e):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "failed.txt", "a") as f:
        f.write(f"{what} {type(e).__name__}: {e}\n")


def boot_ci(per_group_vals, seed, stat=np.mean):
    x = np.asarray(per_group_vals, float)
    x = x[np.isfinite(x)]
    if len(x) < 3:
        return [float(stat(x)) if len(x) else np.nan, np.nan, np.nan]
    rng = np.random.default_rng(seed)
    b = [stat(x[rng.integers(len(x), size=len(x))]) for _ in range(NB)]
    return [float(stat(x)), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def outside(ret, orig_ci):
    """distance by which the re-timed point lies outside the original's 95 % interval (0 inside)"""
    v, lo, hi = ret, orig_ci[1], orig_ci[2]
    if not (np.isfinite(v) and np.isfinite(lo) and np.isfinite(hi)):
        return np.nan
    return float(max(lo - v, v - hi, 0.0))


# ---------------------------------------------------------------------------------------------------- (a) WO47 BAS
def lamp_bas(lamp, grids, dur, rng):
    import beatv_lib as BL
    kb = BL.kin_beats(np.linalg.norm(np.gradient(lamp, axis=0) * FS, axis=1), FS)
    out = {}
    for gn in ("proj", "lib"):
        for mode in ("music", "kin"):
            out[f"{gn}|{mode}"] = (BL.bas(grids[gn], kb, dur, mode=mode), BL.bas_chance(grids[gn], kb, dur, rng, mode=mode))
    return out


def bas_one(args):
    ds, path = args
    try:
        import controls_stats as CS
        import metric_run as R
        pk = B / "beatv/real" / ds / (path.stem + ".pkl")
        if not pk.exists():
            return None
        orig = pickle.loads(pk.read_bytes())
        lk = CS.lane_key(path.name)
        grids = dict(proj=np.array(json.loads(R.beats_path(lk).read_text())["beats"], float),
                     lib=np.array(json.loads((B / "beatv/librosa" / f"{lk}.json").read_text())["beats"], float))
        z = np.load(path)
        lamp = z["lamp"].astype(float)
        var = var_of(path.name)
        seed = 47104 + zlib.crc32(path.name.encode())
        rec = lamp_bas(lamp, grids, len(lamp) / FS, np.random.default_rng(seed))           # original code path, reproduction check
        lr, n = RT.retime(lamp, FS, var)
        ret = lamp_bas(lr, grids, n / FS, np.random.default_rng(seed))                       # same per-file stream, lamp draws first as in beatv_real
        o = {f"{gn}|{m}": tuple(orig["bas"][("lamp", gn, m)]) for gn in ("proj", "lib") for m in ("music", "kin")}
        chk = max(abs(rec[k][i] - o[k][i]) for k in o for i in (0, 1) if np.isfinite(o[k][i]))
        return dict(name=path.name, group=orig["group"], var=var, orig=o, ret=ret, repro_maxdiff=float(chk))
    except Exception as e:  # noqa: BLE001
        fail(f"bas {ds} {path.name}", e)
        return None


def bas(procs):
    (OUT / "bas").mkdir(parents=True, exist_ok=True)
    with Pool(procs) as pool:
        for ds in DS:
            jobs = [(ds, p) for p in sorted((B / "metric/q50" / ds).glob("*.npz"))]
            rs = [r for r in pool.imap_unordered(bas_one, jobs, chunksize=4) if r is not None]
            (OUT / "bas" / f"{ds}.json").write_text(json.dumps(rs))
            print("BAS", ds, len(rs), "of", len(jobs), "max repro diff", max([r["repro_maxdiff"] for r in rs] or [np.nan]), flush=True)


def bas_table():
    rows = []
    for ds in DS:
        f = OUT / "bas" / f"{ds}.json"
        if not f.exists():
            continue
        rs = json.loads(f.read_text())
        for var in ("V1", "V2"):
            sub = [r for r in rs if r["var"] == var]
            for gn in ("lib", "proj"):
                for mode in ("music", "kin"):
                    k = f"{gn}|{mode}"
                    vals = {}
                    for side in ("orig", "ret"):
                        g = {}
                        for r in sub:
                            b, c = r[side][k]
                            if b is not None and c is not None and np.isfinite(b) and np.isfinite(c):
                                g.setdefault(r["group"], []).append((b, c))
                        gb = np.array([np.mean([x[0] for x in v]) for v in g.values()])
                        gc = np.array([np.mean([x[1] for x in v]) for v in g.values()])
                        vals[side] = dict(bas=boot_ci(gb, SEED_BOOT47), chance=boot_ci(gc, SEED_BOOT47), excess=boot_ci(gb - gc, SEED_BOOT47), groups=len(gb))
                    rows.append(dict(ds=ds, var=var, grid=gn, mode=mode, n=len(sub), **vals,
                                     outside_excess=outside(vals["ret"]["excess"][0], vals["orig"]["excess"]),
                                     outside_bas=outside(vals["ret"]["bas"][0], vals["orig"]["bas"]),
                                     repro_maxdiff=max([r["repro_maxdiff"] for r in sub] or [np.nan])))
    return rows


# ---------------------------------------------------------------------------------------------------- (a) WO47 V3 realised
def v3_one(n):
    """beatv_v3curve.one with the realised lamp and joints re-timed; raw scan first so the per-file stream is consumed as in WO47"""
    try:
        import beatv_lib as BL
        import librosa
        FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
        y, sr = librosa.load(str(FD / "music_wav" / f"{n}.wav"), sr=22050)
        rng = np.random.default_rng(47103 + int(n))
        m = np.load(FD / "motion" / f"{n}.npy").astype(float)
        e30 = librosa.onset.onset_strength(y=y, sr=sr, hop_length=735)
        en = BL.angle_speed(BL.local_rots(m), 30).sum(1)
        M = min(len(en), len(e30))
        res = dict(n=n, raw_k=BL.sync_scan(en[:M], e30[:M], 30, rng)[0])
        e50 = librosa.onset.onset_strength(y=y, sr=sr, hop_length=441)
        for var in ("V1", "V2"):
            p = B / "metric/q50/finedance" / f"fd_{n}__{var}.npz"
            if not p.exists():
                continue
            z_ = np.load(p)
            q, _ = RT.retime(z_["q50"].astype(float), FS, var)
            lamp, _ = RT.retime(z_["lamp"].astype(float), FS, var)
            lsp = np.linalg.norm(np.gradient(lamp, axis=0) * FS, axis=1)
            jsp = np.abs(np.gradient(q, axis=0) * FS).sum(1)
            for nm, a in (("lamp", lsp), ("joints", jsp)):
                M = min(len(a), len(e50))
                k, c, zz, p95, cc = BL.sync_scan(a[:M], e50[:M], 50, rng, min_shift_frames=250)
                res[f"{var}_{nm}"] = dict(k=k, cmax=c, z=zz, p95=p95, c=cc.tolist())
        return n, res
    except Exception as e:  # noqa: BLE001
        fail(f"v3 {n}", e)
        return n, None


def v3(procs):
    orig = json.loads((B / "beatv/v3.json").read_text())
    ns = sorted(orig)
    out = {}
    with Pool(procs) as pool:
        for i, (n, r) in enumerate(pool.imap_unordered(v3_one, ns)):
            if r is not None:
                out[n] = r
            if i % 20 == 0:
                print("V3", i, "/", len(ns), flush=True)
    rawdiff = max(abs(out[n]["raw_k"] - orig[n]["raw"]["k"]) for n in out)
    (OUT / "v3.json").write_text(json.dumps(dict(ret=out, raw_k_maxdiff=int(rawdiff))))
    print("V3 DONE", len(out), "raw best-offset max diff vs WO47", rawdiff, flush=True)


def v3_table():
    f = OUT / "v3.json"
    if not f.exists():
        return []
    ret = json.loads(f.read_text())["ret"]
    orig = json.loads((B / "beatv/v3.json").read_text())
    rows = []
    for key in ("V1_lamp", "V2_lamp", "V1_joints", "V2_joints"):
        ns = sorted(n for n in ret if key in ret[n] and key in orig[n])
        side = {}
        for nm, src in (("orig", orig), ("ret", ret)):
            k = np.array([src[n][key]["k"] for n in ns], float) / FS
            cm = np.array([src[n][key]["cmax"] for n in ns])
            z = np.array([src[n][key]["z"] for n in ns])
            ex = np.array([src[n][key]["cmax"] > src[n][key]["p95"] for n in ns])
            cs = np.array([src[n][key]["c"] for n in ns]).mean(0)
            side[nm] = dict(q=np.percentile(k, [5, 25, 50, 75, 95]).round(3).tolist(), med=boot_ci(k, SEED_BOOT47, np.median),
                            share50=float(np.mean(np.abs(k) <= 0.05)), cmax_med=float(np.median(cm)), z_med=float(np.median(z)), above95=float(ex.mean()),
                            curve_peak_s=float((np.argmax(cs) - 50) / FS), curve_max=float(cs.max()))
        dk = np.array([ret[n][key]["k"] - orig[n][key]["k"] for n in ns], float) / FS
        rows.append(dict(key=key, files=len(ns), **side, shift_med=float(np.median(dk)), L=RT.L[key[:2]],
                         outside_med=outside(side["ret"]["med"][0], side["orig"]["med"])))
    return rows


# ---------------------------------------------------------------------------------------------------- (b) WO52 event locks
def events(procs):
    import rhythm_events as RE
    for side in ("orig", "ret"):
        d = OUT / "events" / side
        d.mkdir(parents=True, exist_ok=True)
        ev = d / "events.json"
        if not ev.exists():
            ev.symlink_to(B / "rhythm/events.json")
        for ds in DS:
            z = dict(np.load(B / f"rhythm/tokens_{ds}.npz"))
            if side == "ret":
                sh = np.array([RT.L[var_of(str(k))] for k in z["key"]])
                z["t"] = z["t"] - sh
                z["hold_t"] = z["hold_t"] - sh
            np.savez(d / f"tokens_{ds}.npz", **z)
        RE.OUT = d                                    # analyse_B reads tokens/events and writes lock_<ds>.npz here (fork pool inherits it)
        resB, th = RE.analyse_B(procs)
        (d / "results.json").write_text(json.dumps(dict(B=resB, thresholds=th), indent=1))
        print("EVENTS", side, "done", flush=True)


def events_table():
    import rhythm_events as RE
    f = {s: OUT / "events" / s / "results.json" for s in ("orig", "ret")}
    if not all(p.exists() for p in f.values()):
        return [], None
    o, r = (json.loads(f[s].read_text())["B"] for s in ("orig", "ret"))
    wo52 = json.loads((B / "rhythm/results.json").read_text())["B"]
    repro = max(abs(o[k]["peak_excess"] - wo52[k]["peak_excess"]) for k in o if isinstance(o[k], dict) and o[k].get("events"))
    rows = []
    for ds in list(DS) + ["all"]:
        for x in RE.RESP:
            for e in RE.EVENTS:
                k = f"{ds}|{x}|{e}"
                a, b = o[k], r[k]
                if not a.get("events"):
                    continue
                oc = [a["peak_excess"]] + a["peak_excess_ci"]
                pm = [a["excess_pm03"]] + a["excess_pm03_ci"]
                rows.append(dict(ds=ds, resp=x, ev=e, n_orig=a["events"], n_ret=b.get("events", 0),
                                 orig=(a["peak_excess"], a["peak_lag"], a["peak_excess_ci"], a["p_max"], a["excess_pm03"], a["excess_pm03_ci"]),
                                 ret=(b.get("peak_excess", np.nan), b.get("peak_lag", np.nan), b.get("peak_excess_ci", [np.nan, np.nan]), b.get("p_max", np.nan),
                                      b.get("excess_pm03", np.nan), b.get("excess_pm03_ci", [np.nan, np.nan])),
                                 outside_peak=outside(b.get("peak_excess", np.nan), oc), outside_pm03=outside(b.get("excess_pm03", np.nan), pm)))
    return rows, repro


# ---------------------------------------------------------------------------------------------------- (c) WO53 B lamp column
def lamp_rhythm_rows(args):
    """one sequence copy: rows (W, start, win) -> re-timed lamp (period, strength) and the original recomputed, or NaN where the window reaches the dropped tail"""
    ds, key, rows = args
    import rhythm_events as RE
    try:
        q = np.load(B / f"controls/q50/{ds}/{key}.npz")
        qwin = [int(w) for w in q["win"]]
        var = var_of(key)
        out = []
        cache = {}
        for W, start, win in rows:
            if win not in cache:
                lamp = q["lamp"][qwin.index(win)].astype(float)
                lr, n = RT.retime(lamp, FS, var)
                sp = lambda a: np.linalg.norm(np.gradient(a, axis=0) * FS, axis=1)  # noqa: E731
                cache[win] = (sp(lamp), sp(lr), n)
            so, sr, n = cache[win]
            s = int(round(start - 20.0 * win))
            sl = slice(s * FS, (s + int(W)) * FS)
            keep = (s + int(W)) * FS <= n
            po, to = RE.rhythm(so[sl])
            pr, tr = RE.rhythm(sr[sl]) if keep else (np.nan, 0.0)
            out.append((keep, po, to, pr, tr))
        return key, out, None
    except Exception as e:  # noqa: BLE001
        return key, None, repr(e)


def rhythm(procs):
    import rawrhythm as RR
    for side in ("orig", "ret"):
        (OUT / "rawrhythm" / side).mkdir(parents=True, exist_ok=True)
    chk = {}
    with Pool(procs) as pool:
        for ds in DS:
            z = dict(np.load(B / f"rawrhythm/windows_{ds}.npz"))
            n = len(z["key"])
            idx = {}
            for i, k in enumerate(z["key"]):
                idx.setdefault(str(k), []).append(i)
            jobs = [(ds, k, [(int(z["W"][i]), float(z["start"][i]), int(z["win"][i])) for i in ii]) for k, ii in idx.items()]
            keep, po, to, pr, tr = np.zeros(n, bool), np.full(n, np.nan), np.zeros(n), np.full(n, np.nan), np.zeros(n)
            for key, res, err in pool.imap_unordered(lamp_rhythm_rows, jobs, chunksize=8):
                if err:
                    fail(f"rhythm {ds} {key}", err)
                    continue
                ii = idx[key]
                a = np.array(res, dtype=object)
                keep[ii] = a[:, 0].astype(bool)
                po[ii], to[ii], pr[ii], tr[ii] = (a[:, j].astype(float) for j in (1, 2, 3, 4))
            # reproduction of the stored WO52 lamp column on every row
            same = np.isclose(po, z["per_lamp"], equal_nan=True, atol=1e-9) & np.isclose(to, z["str_lamp"], atol=1e-9)
            chk[ds] = dict(rows=int(n), kept=int(keep.sum()), dropped=int((~keep).sum()), repro_mismatch=int((~same).sum()))
            for side, (p, s) in (("orig", (z["per_lamp"], z["str_lamp"])), ("ret", (pr, tr))):
                zz = {k: v[keep] for k, v in z.items()}
                zz["per_lamp"], zz["str_lamp"] = p[keep], s[keep]
                np.savez(OUT / "rawrhythm" / side / f"windows_{ds}.npz", **zz)
            print("RHYTHM rows", ds, chk[ds], flush=True)
    (OUT / "rawrhythm/check.json").write_text(json.dumps(chk, indent=1))
    for side in ("orig", "ret"):
        RR.OUT = OUT / "rawrhythm" / side
        RR.analyse()
        print("RHYTHM analyse", side, "done", flush=True)


def rhythm_table():
    f = {s: OUT / "rawrhythm" / s / "results.json" for s in ("orig", "ret")}
    if not all(p.exists() for p in f.values()):
        return [], None
    o, r = (json.loads(f[s].read_text()) for s in ("orig", "ret"))
    rows = []
    for ds in list(DS) + ["all"]:
        for src in ("librosa", "pulse2"):
            for var in ("main", "narrow", "W4"):
                k = f"{ds}|{src}|lamp|{var}"
                a, b = o["A"][k], r["A"][k]
                row = dict(ds=ds, src=src, var=var, rh_o=1 - a["bin_share_all"]["none"], rh_r=1 - b["bin_share_all"]["none"],
                           bins_o=a["bin_share_rhythmic"], bins_r=b["bin_share_rhythmic"], cl_o=a["cluster"], cl_r=b["cluster"], conc_o=a["conc"], conc_r=b["conc"])
                for c in ("c1", "c2"):
                    oc = [a[c]["excess"]] + a[c]["excess_ci"]
                    row[f"{c}_o"], row[f"{c}_r"] = oc, [b[c]["excess"]] + b[c]["excess_ci"]
                    row[f"{c}_out"] = outside(b[c]["excess"], oc)
                rows.append(row)
    pair = []
    for ds in list(DS) + ["all"]:
        for src in ("librosa", "pulse2"):
            for sig in ("mean", "mean_rel", "lwr", "rwr"):
                k = f"{ds}|{src}|{sig}"
                pair.append(dict(ds=ds, src=src, sig=sig, o=o["paired"][k], r=r["paired"][k]))
    qs = {k: (o["quantiles"][k], r["quantiles"][k]) for k in o["quantiles"] if "|lamp|" in k}
    return rows, dict(pair=pair, quant=qs)


# ---------------------------------------------------------------------------------------------------- (3) token-level effect
CTL = ("vigour", "height", "sharp", "pause_on")
FEATS = ("low", "onset")
CLAGS = np.round(np.arange(-1.0, 1.0001, 0.1), 2)
ALIGN = ("orig", "ret", "tok1")
_ST = {}


def song_feats(song, ds):
    """10 Hz low-band energy (as WO52 dropouts) and raw onset strength (ear col 40), stamp times"""
    import cortexev as CE
    import rhythm_events as RE
    if not _ST:
        import braindump as bd
        import librosa
        _ST["mean"], _ST["std"] = (np.asarray(x, np.float64) for x in bd.stats())
        cen = librosa.mel_frequencies(n_mels=34, fmin=30, fmax=16000)[1:-1]
        _ST["lo"] = np.flatnonzero(cen < 200)
    z = np.load(RE.LANES[ds] / f"{song}.npz")
    ear = z["ear"].astype(np.float64)
    n10 = len(ear) // 10
    raw = ear * _ST["std"] + _ST["mean"]
    ts = (10 * np.arange(n10) + 9) / 100.0
    return ts, dict(low=CE.ten(10 ** (raw[:, _ST["lo"]] / 10).mean(1), n10), onset=CE.ten(raw[:, 40], n10))


def interval_mean(ts, cs, lo, hi):
    """mean of the 10 Hz feature with stamps in [lo, hi) per token (cs = cumulative sum with leading 0); NaN when empty"""
    a, b = np.searchsorted(ts, lo), np.searchsorted(ts, hi)
    n = b - a
    with np.errstate(all="ignore"):
        return np.where(n > 0, (cs[b] - cs[a]) / np.maximum(n, 1), np.nan)


def token_controls(ctl):
    """(n, 18) ctl of consecutive tokens -> dict of (n,) control series; NaN where undefined (sharpness flag 0, first token's pause onset)"""
    p = ctl[:, 14]
    on = np.r_[np.nan, ((p[1:] >= 0.2) & (p[:-1] < 0.2)).astype(float)]
    return dict(vigour=ctl[:, 0].astype(float), height=ctl[:, 1].astype(float), sharp=np.where(ctl[:, 15] > 0.5, ctl[:, 10], np.nan).astype(float), pause_on=on)


def shift_of(align, var):
    return dict(orig=0.0, ret=RT.L[var], tok1=0.5)[align]


def tok_seq(args):
    """one sequence copy -> per-alignment event-locked sums and correlation sums"""
    ds, ki, key, song, rows, ev = args
    import rhythm_events as RE
    try:
        var = var_of(key)
        ts, F = song_feats(song, ds)
        CS_ = {f: np.r_[0.0, np.cumsum(np.nan_to_num(F[f]))] for f in FEATS}
        okc = {f: np.r_[0, np.cumsum(np.isfinite(F[f]))] for f in FEATS}
        nE, nC, nF, nA, nL = len(RE.EVENTS), len(CTL), len(FEATS), len(ALIGN), len(CLAGS)
        el = np.zeros((nA, nC, nE, 4))                 # obs sum, obs n, chance sum, chance n
        cr = np.zeros((nA, nC, nF, nL, 3))              # sum xy, sum xx, sum yy (demeaned per sequence copy)
        rng = np.random.default_rng([52102, DS.index(ds), ki])
        segs = RE.segments([r[0] for r in rows])
        byw = {r[0]: r[1] for r in rows}
        X = {c: [] for c in CTL}
        T0 = []
        for seg in segs:
            ctl = np.concatenate([byw[w] for w in seg])
            tt = np.concatenate([20.0 * w + 0.5 * np.arange(40) for w in seg])
            cc = token_controls(ctl)
            cc["pause_on"][0] = np.nan                  # first token of a segment has no predecessor
            for c in CTL:
                X[c].append(cc[c])
            T0.append(tt)
            for ai, al in enumerate(ALIGN):
                d = shift_of(al, var)
                a, b = tt[0] + 0.5 - d, tt[-1] + 0.5 - d       # WO52 span, moved with the tokens
                off = rng.uniform(0, b - a, 200)
                for ei, e in enumerate(RE.EVENTS):
                    evs = np.asarray(ev[e], float)
                    evs = evs[(evs - 1.1 >= a) & (evs + 1.1 <= b)]
                    if not len(evs):
                        continue
                    sh = a + np.mod(evs[None] - a + off[:, None], b - a)
                    j0 = np.floor((evs - (tt[0] - d)) / 0.5).astype(int)
                    js = np.clip(np.floor((sh - (tt[0] - d)) / 0.5).astype(int), 0, len(tt) - 1)
                    for ci, c in enumerate(CTL):
                        v0, vs = cc[c][j0], cc[c][js]
                        el[ai, ci, ei] += [np.nansum(v0), np.isfinite(v0).sum(), np.nansum(vs) / 200, np.isfinite(vs).sum() / 200]
        tt = np.concatenate(T0)
        for c in CTL:
            X[c] = np.concatenate(X[c])
        for ai, al in enumerate(ALIGN):
            d = shift_of(al, var)
            for li, lag in enumerate(CLAGS):
                lo, hi = tt - d + lag, tt - d + lag + 0.5
                for fi, f in enumerate(FEATS):
                    y = interval_mean(ts, CS_[f], lo, hi)
                    a_, b_ = np.searchsorted(ts, lo), np.searchsorted(ts, hi)
                    y = np.where(okc[f][b_] - okc[f][a_] == b_ - a_, y, np.nan)
                    for ci, c in enumerate(CTL):
                        x = X[c]
                        m = np.isfinite(x) & np.isfinite(y)
                        if m.sum() < 3:
                            continue
                        xd, yd = x[m] - x[m].mean(), y[m] - y[m].mean()
                        cr[ai, ci, fi, li] += [(xd * yd).sum(), (xd * xd).sum(), (yd * yd).sum()]
        return ds, key, el, cr, None
    except Exception as e:  # noqa: BLE001
        return ds, key, None, None, repr(e)


def tokens(procs):
    import rhythm_events as RE
    evj = json.loads((B / "rhythm/events.json").read_text())["events"]
    acc = {}
    with Pool(procs) as pool:
        for ds in DS:
            z = {k: np.load(B / f"grammar/win_{ds}.npz")[k] for k in ("key", "win", "ctl", "group")}
            seqs = {}
            for i in range(len(z["key"])):
                key = str(z["key"][i])
                if key.split("__")[1] not in ("V1", "V2"):
                    continue
                seqs.setdefault(key, []).append((int(z["win"][i]), z["ctl"][i], str(z["group"][i])))
            jobs = []
            for ki, (key, rows) in enumerate(sorted(seqs.items())):
                song = RE.music_key(key)
                if evj.get(song) is None:
                    continue
                jobs.append((ds, ki, key, song, sorted([(w, c) for w, c, _ in rows], key=lambda r: r[0]), evj[song]))
            grp = {k: v[0][2] for k, v in seqs.items()}
            for ds_, key, el, cr, err in pool.imap_unordered(tok_seq, jobs, chunksize=4):
                if err:
                    fail(f"tokens {ds_} {key}", err)
                    continue
                g = acc.setdefault((ds, grp[key]), [np.zeros_like(el), np.zeros_like(cr)])
                g[0] += el
                g[1] += cr
            print("TOKENS", ds, len(jobs), "sequences", flush=True)
    keys = sorted(acc)
    np.savez(OUT / "tokens_groups.npz", ds=np.array([k[0] for k in keys]), group=np.array([k[1] for k in keys]),
             el=np.stack([acc[k][0] for k in keys]), cr=np.stack([acc[k][1] for k in keys]))
    print("TOKENS DONE", len(keys), "groups", flush=True)


def tokens_table():
    import rhythm_events as RE
    f = OUT / "tokens_groups.npz"
    if not f.exists():
        return None
    z = np.load(f)
    out = dict(el={}, cr={})
    for ds in list(DS) + ["all"]:
        m = np.ones(len(z["ds"]), bool) if ds == "all" else z["ds"] == ds
        el, cr = z["el"][m], z["cr"][m]
        G = len(el)
        if not G:
            continue
        idx = np.random.default_rng(SEED_BOOT52).integers(0, G, (NB, G))
        for ai, al in enumerate(ALIGN):
            for ci, c in enumerate(CTL):
                for ei, e in enumerate(RE.EVENTS):
                    s = el[:, ai, ci, ei]
                    if s[:, 1].sum() == 0:
                        continue
                    ex = lambda S: S[..., 0].sum(-1) / np.maximum(S[..., 1].sum(-1), 1e-12) - S[..., 2].sum(-1) / np.maximum(S[..., 3].sum(-1), 1e-12)  # noqa: E731
                    bs = ex(s[idx])
                    out["el"][f"{ds}|{al}|{c}|{e}"] = dict(obs=float(s[:, 0].sum() / s[:, 1].sum()), chance=float(s[:, 2].sum() / max(s[:, 3].sum(), 1e-12)),
                                                           excess=[float(ex(s))] + [float(v) for v in np.percentile(bs, [2.5, 97.5])], n=float(s[:, 1].sum()))
                for fi, ft in enumerate(FEATS):
                    S = cr[:, ai, ci, fi]                     # (G, nL, 3)
                    r = S[..., 0].sum(0) / np.sqrt(S[..., 1].sum(0) * S[..., 2].sum(0) + 1e-300)
                    Sb = S[idx].sum(1)                         # (NB, nL, 3)
                    rb = Sb[..., 0] / np.sqrt(Sb[..., 1] * Sb[..., 2] + 1e-300)
                    pk = int(np.argmax(np.abs(r)))
                    pkb = CLAGS[np.argmax(np.abs(rb), 1)]
                    out["cr"][f"{ds}|{al}|{c}|{ft}"] = dict(r=r.round(4).tolist(), r_ci=np.percentile(rb, [2.5, 97.5], 0).round(4).tolist(),
                                                            peak_lag=float(CLAGS[pk]), peak_r=float(r[pk]), peak_lag_ci=[float(v) for v in np.percentile(pkb, [2.5, 97.5])])
    (OUT / "tokens.json").write_text(json.dumps(out))
    return out


# ---------------------------------------------------------------------------------------------------- report
def report(procs=None):
    f3 = lambda x: "-" if x is None or not np.isfinite(x) else f"{x:+.3f}"  # noqa: E731
    fci = lambda v: f"{v[0]:+.3f} [{v[1]:+.3f}, {v[2]:+.3f}]"  # noqa: E731
    L = ["# WO55 part A tables (generated by `scripts/body/retime_a.py report`)", "", f"L = {RT.L} s (movement later than music; lamp read L later).", ""]
    rows = bas_table()
    if rows:
        L += ["## (a) WO47 lamp BAS, original vs re-timed (mean over song groups [95 % boot, seed 47101]); outside = distance of the re-timed value outside the original interval", "",
              "| dataset | var | grid | sum over | groups | BAS orig | BAS re-timed | BAS - chance orig | BAS - chance re-timed | outside (excess) | outside (BAS) | repro max diff |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['ds']} | {r['var']} | {r['grid']} | {r['mode']} | {r['ret']['groups']} | {fci(r['orig']['bas'])} | {fci(r['ret']['bas'])} | {fci(r['orig']['excess'])} | {fci(r['ret']['excess'])} | "
                     f"{f3(r['outside_excess'])} | {f3(r['outside_bas'])} | {r['repro_maxdiff']:.1e} |")
        L.append("")
    rows = v3_table()
    if rows:
        L += ["## (a) WO47 V3 realised (FineDance; k > 0 = music after motion), best offset (s)", "",
              "| signal | files | L | quantiles 5/25/50/75/95 orig | re-timed | median orig [95 %] | median re-timed [95 %] | median per-file shift | within 50 ms orig / re | max corr median orig / re | z median orig / re | above own 95 % orig / re | mean-curve peak (s) orig / re | outside (median) |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            o, t = r["orig"], r["ret"]
            L.append(f"| {r['key']} | {r['files']} | {r['L']} | {o['q']} | {t['q']} | {fci(o['med'])} | {fci(t['med'])} | {r['shift_med']:+.3f} | {o['share50']:.3f} / {t['share50']:.3f} | "
                     f"{o['cmax_med']:.3f} / {t['cmax_med']:.3f} | {o['z_med']:.2f} / {t['z_med']:.2f} | {o['above95']:.3f} / {t['above95']:.3f} | {o['curve_peak_s']:+.2f} / {t['curve_peak_s']:+.2f} | {f3(r['outside_med'])} |")
        L.append("")
    rows, repro = events_table()
    if rows:
        L += [f"## (b) WO52 event locks: peak excess (responses/s) @ lag [95 %], max-stat p; mean excess +-0.3 s [95 %]. Reproduction of WO52 (orig run vs stored): max |peak excess diff| {repro:.2e}", "",
              "| dataset | response | event | events orig / re | orig peak | re-timed peak | outside (peak) | orig +-0.3 | re-timed +-0.3 | outside (+-0.3) |", "|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            o, t = r["orig"], r["ret"]
            L.append(f"| {r['ds']} | {r['resp']} | {r['ev']} | {r['n_orig']} / {r['n_ret']} | {o[0]:+.3f} @ {o[1]:+.2f} [{o[2][0]:+.3f}, {o[2][1]:+.3f}] p {o[3]:.3f} | "
                     f"{t[0]:+.3f} @ {t[1]:+.2f} [{t[2][0]:+.3f}, {t[2][1]:+.3f}] p {t[3]:.3f} | {f3(r['outside_peak'])} | {o[4]:+.3f} [{o[5][0]:+.3f}, {o[5][1]:+.3f}] | "
                     f"{t[4]:+.3f} [{t[5][0]:+.3f}, {t[5][1]:+.3f}] | {f3(r['outside_pm03'])} |")
        L.append("")
    rows, extra = rhythm_table()
    if rows:
        chk = json.loads((OUT / "rawrhythm/check.json").read_text())
        L += [f"## (c) WO53 B lamp column, original vs re-timed on the same reduced rows. Rows: {chk}", "",
              "| dataset | source | variant | rhythmic share o / r | 1/2 o / r | 1 o / r | 2 o / r | cluster o / r | excess 1 orig | excess 1 re-timed | outside 1 | excess 2 orig | excess 2 re-timed | outside 2 | C o / r |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            bo, br = r["bins_o"], r["bins_r"]
            L.append(f"| {r['ds']} | {r['src']} | {r['var']} | {r['rh_o']:.3f} / {r['rh_r']:.3f} | {bo['1/2']:.3f} / {br['1/2']:.3f} | {bo['1']:.3f} / {br['1']:.3f} | {bo['2']:.3f} / {br['2']:.3f} | "
                     f"{r['cl_o']:.3f} / {r['cl_r']:.3f} | {fci(r['c1_o'])} | {fci(r['c1_r'])} | {f3(r['c1_out'])} | {fci(r['c2_o'])} | {fci(r['c2_r'])} | {f3(r['c2_out'])} | {r['conc_o']:.3f} / {r['conc_r']:.3f} |")
        L += ["", "### Raw vs lamp same-bin share per window (W = 3, main): same / expected if independent (n), lamp original vs re-timed", "",
              "| dataset | source | raw signal | all rows, orig lamp | all rows, re-timed lamp | both rhythmic, orig | both rhythmic, re-timed |", "|---|---|---|---|---|---|---|"]
        fp = lambda v: "-" if v is None else f"{v['same']:.3f} / {v['expected']:.3f} ({v['n']})"  # noqa: E731
        for p in extra["pair"]:
            L.append(f"| {p['ds']} | {p['src']} | {p['sig']} | {fp(p['o']['all'])} | {fp(p['r']['all'])} | {fp(p['o']['both_rhythmic'])} | {fp(p['r']['both_rhythmic'])} |")
        L += ["", "### Lamp period / ratio quantiles 5/25/50/75/95 (W = 3, rhythmic), orig vs re-timed", "", "| key | orig | re-timed |", "|---|---|---|"]
        for k, (a, b) in extra["quant"].items():
            fq = lambda x: "-" if x is None else (f"{x:.3f}" if not isinstance(x, list) else " / ".join(f"{v:.2f}" for v in x))  # noqa: E731
            L.append(f"| {k} | {fq(a)} | {fq(b)} |")
        L.append("")
    t = tokens_table()
    if t:
        L += ["## (3) Token-level effect: event-locked control at lag 0 (mean control of the token covering the event; pause_on = onsets per token), excess over circular-shift chance [95 % boot by song group]", "",
              "Alignments: orig = token at its own time; ret = token time - L (L = 0.70 / 0.56 token); tok1 = token time - 0.5 s (one whole token).", "",
              "| dataset | control | event | orig excess | re-timed excess | outside | one-token excess |", "|---|---|---|---|---|---|---|"]
        import rhythm_events as RE
        for ds in list(DS) + ["all"]:
            for c in CTL:
                for e in RE.EVENTS:
                    k = lambda al: t["el"].get(f"{ds}|{al}|{c}|{e}")  # noqa: E731
                    if k("orig") is None:
                        continue
                    o, r_, w = k("orig"), k("ret"), k("tok1")
                    L.append(f"| {ds} | {c} | {e} | {fci(o['excess'])} (obs {o['obs']:.3f}, n {o['n']:.0f}) | {fci(r_['excess'])} | {f3(outside(r_['excess'][0], o['excess']))} | {fci(w['excess'])} |")
        L += ["", "### Correlation of each control with music energy features (within-sequence demeaned, pooled r), lags -1..+1 s (lag > 0 = music after the token): peak lag (max |r|) [95 %], r at the peak, r at lag 0; peak move vs L", "",
              "| dataset | control | feature | orig peak lag [95 %] | orig r peak / r(0) | re-timed peak lag [95 %] | re-timed r peak / r(0) | move | L |", "|---|---|---|---|---|---|---|---|---|"]
        i0 = int(np.argmin(np.abs(CLAGS)))
        for ds in list(DS) + ["all"]:
            for c in CTL:
                for ft in FEATS:
                    o, r_ = t["cr"].get(f"{ds}|orig|{c}|{ft}"), t["cr"].get(f"{ds}|ret|{c}|{ft}")
                    if o is None:
                        continue
                    L.append(f"| {ds} | {c} | {ft} | {o['peak_lag']:+.1f} [{o['peak_lag_ci'][0]:+.1f}, {o['peak_lag_ci'][1]:+.1f}] | {o['peak_r']:+.3f} / {o['r'][i0]:+.3f} | "
                             f"{r_['peak_lag']:+.1f} [{r_['peak_lag_ci'][0]:+.1f}, {r_['peak_lag_ci'][1]:+.1f}] | {r_['peak_r']:+.3f} / {r_['r'][i0]:+.3f} | {r_['peak_lag'] - o['peak_lag']:+.1f} | 0.35 (V1) / 0.28 (V2) |")
        L.append("")
    (OUT / "tables.md").write_text("\n".join(L))
    print("REPORT", OUT / "tables.md", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    procs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    OUT.mkdir(parents=True, exist_ok=True)
    if cmd in ("bas", "v3", "events", "rhythm", "tokens", "report"):
        globals()[cmd](procs)
    else:
        print(__doc__)
