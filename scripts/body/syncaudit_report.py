"""WO54 B reports: A3 tables, the shifted-foil reading, A2 tables. Called from syncaudit_b.py (a3report | foil | a2report). Brain env."""
import json
from pathlib import Path

import numpy as np

import syncaudit_b as S

OUT, FS, KMAX = S.OUT, S.FS, S.KMAX
LAGS = np.arange(-KMAX, KMAX + 1) / FS
EDGES = np.arange(-1.5, 1.51, 0.2)


def peaks_of(curves, kmax=KMAX, kpk=S.KPK):
    p = np.array([S.peak(c, kpk, kmax) for c in curves])
    return p[:, 0], p[:, 1]


def pooled(curves, kmax=KMAX, kpk=S.KPK):
    ok = np.isfinite(curves).all(1)
    return S.peak(np.nanmean(curves[ok], 0), kpk, kmax) if ok.any() else (np.nan, np.nan), ok


def boot_pooled(curves, seed, nboot=S.NBOOT, kmax=KMAX, kpk=S.KPK):
    c = curves[np.isfinite(curves).all(1)]
    if len(c) < 3:
        return [np.nan, np.nan]
    rng = np.random.default_rng(seed)
    v = [S.peak(c[rng.integers(0, len(c), len(c))].mean(0), kpk, kmax)[0] for _ in range(nboot)]
    return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]


def q(x, qs=S.QS):
    x = x[np.isfinite(x)]
    return [float(np.percentile(x, p)) for p in qs] if len(x) else [np.nan] * len(qs)


def summarise(curves, chance_t=None, chance_s=None, seed=S.SEED_BOOT):
    lag, h = peaks_of(curves)
    ok = np.isfinite(lag)
    (pl, ph), _ = pooled(curves)
    d = dict(n=int(ok.sum()), lag_q=q(lag), share_100ms=float((np.abs(lag[ok]) <= 0.1).mean()) if ok.any() else np.nan,
             height_median=float(np.nanmedian(h)) if ok.any() else np.nan, pooled_lag=pl, pooled_height=ph, pooled_lag_ci=boot_pooled(curves, seed),
             hist=np.histogram(lag[ok], EDGES)[0].tolist())
    for nm, c in (("tempo", chance_t), ("shift", chance_s)):
        if c is not None and np.isfinite(c).any():
            cl, chh = c[..., 0].ravel(), c[..., 1].ravel()
            d[f"chance_{nm}"] = dict(height_median=float(np.nanmedian(chh)), lag_q=q(cl), share_100ms=float((np.abs(cl[np.isfinite(cl)]) <= 0.1).mean()),
                                     frac_song_height_above_chance=float(np.nanmean(h > np.nanmedian(c[..., 1], 1))))
    return d


def a3report():
    res = {}
    for ds in S.DS:
        p = OUT / f"a3_{ds}.npz"
        if not p.exists():
            continue
        z = np.load(p)
        sigs = sorted({k.split("|", 1)[1] for k in z.files if k.startswith("curve|")})
        res[ds] = dict(n_songs=len(z["song"]), nwin={k: int(z["nwin|" + k].sum()) for k in ("V1", "V2", "raw")}, signals={})
        for s in sigs:
            c = z["curve|" + s]
            ct = z.get(f"chance_tempo|{s}") if f"chance_tempo|{s}" in z.files else None
            cs = z.get(f"chance_shift|{s}") if f"chance_shift|{s}" in z.files else None
            kmax = KMAX
            res[ds]["signals"][s] = summarise(c, ct, cs)
    (OUT / "a3_results.json").write_text(json.dumps(res, indent=1))
    L = ["# A3 per-song lag diagnostic (tables)\n", "Positive lag = movement later than the music. Peak within +-1.5 s of the per-song mean curve; `chance` = same statistic against another song of similar tempo (T) or the own music shifted 2-6 s (S).\n"]
    for ds, r in res.items():
        L += [f"\n## {ds} ({r['n_songs']} songs; windows {r['nwin']})\n",
              "| signal | n | lag q5 / q25 / q50 / q75 / q95 (s) | share \\|lag\\|<=0.1 s | median height | chance T height / share | chance S height / share | pooled lag (95 % CI) s | pooled height |",
              "|---|---|---|---|---|---|---|---|---|"]
        for s, d in r["signals"].items():
            cT, cS = d.get("chance_tempo"), d.get("chance_shift")
            f = lambda c: f"{c['height_median']:.3f} / {c['share_100ms']:.2f}" if c else "-"  # noqa: E731
            L.append(f"| {s} | {d['n']} | " + " / ".join(f"{x:.2f}" for x in d["lag_q"]) + f" | {d['share_100ms']:.2f} | {d['height_median']:.3f} | {f(cT)} | {f(cS)} | "
                     f"{d['pooled_lag']:.3f} ({d['pooled_lag_ci'][0]:.3f}, {d['pooled_lag_ci'][1]:.3f}) | {d['pooled_height']:.3f} |")
        L.append("\nHistogram of the per-song peak lag (0.2 s bins from -1.5 s; counts), headline signals:\n")
        L.append("| signal | " + " | ".join(f"{a:.1f}" for a in EDGES[:-1]) + " |")
        L.append("|---|" + "---|" * (len(EDGES) - 1))
        for s in ("lamp_V1|ear40", "lamp_V2|ear40", "raw_mean|ear40", "lampVSraw_V1", "lampVSraw_V2"):
            if s in r["signals"]:
                L.append(f"| {s} | " + " | ".join(str(x) for x in r["signals"][s]["hist"]) + " |")
    (OUT / "a3_tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


# ---------------------------------------------------------------------------------------------------- shifted foil
DSMAP = {"finedance": "finedance", "phantomdance": "phantom", "motorica": "motorica", "aioz": "aioz"}


def foil():
    items = json.loads((B_MISMATCH / "material_key.json").read_text())["items"]
    rows = []
    for i, v in items.items():
        if v["kind"] != "shifted":
            continue
        ds = DSMAP[v["dataset"]]
        song, w = v["song"], int(v["window"])
        fs_, fd = v["foil"]["song"], DSMAP[v["foil"]["dataset"]]
        q = np.load(S.B / f"controls/q50/{ds}/{song}__{v['version']}.npz")
        wi = list(q["win"]).index(w)
        sp = S.demean(S.lamp_speed(q["lamp"][wi]))
        off0 = int(round((v["excerpt_start_s"] - 20 * w) * FS))
        m = sp[off0:off0 + 10 * FS]
        er, ef = S.song_env(ds, song), S.song_env(fd, fs_)
        r = dict(id=i, repeat=v["repeat"], dataset=ds, version=v["version"], song=song, offset_s=v["foil"]["offset_s"], real_side=v["real_side"])
        for mu in ("ear40", "energy"):
            base_r = int(round(v["excerpt_start_s"] * FS))
            base_f = int(round(v["foil"]["excerpt_start_s"] * FS))
            cr = S.curve(m, er[mu], base=base_r, lo=0, hi=len(m), kmax=300)
            cf0 = S.curve(m, ef[mu], base=base_f, lo=0, hi=len(m), kmax=0)[0]
            k_off = int(round(-v["foil"]["offset_s"] * FS))                      # foil music = real music at t + offset  <=>  lag L = -offset in the c(L) convention
            r[mu] = dict(c_real_0=float(cr[300]), c_foil_0=float(cf0), c_real_at_minus_offset=float(cr[300 + k_off]) if np.isfinite(cr).all() else None,
                         best_lag_within_1p5=S.peak(cr, 75, 300)[0], best_height=S.peak(cr, 75, 300)[1], c_foil_minus_real=float(cf0 - cr[300]))
        rows.append(r)
    (OUT / "foil.json").write_text(json.dumps(rows, indent=1))
    L = ["| id | rep | ds | ver | offset s | real side | ear40: c_real(0) | c_foil(0) | c_real(L=-offset) | best lag (s) | energy: c_real(0) | c_foil(0) |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        e, g = r["ear40"], r["energy"]
        f = lambda x: "nan" if x is None or not np.isfinite(x) else f"{x:.3f}"  # noqa: E731
        L.append(f"| {r['id']} | {int(r['repeat'])} | {r['dataset']} | {r['version']} | {r['offset_s']:+.1f} | {r['real_side']} | {f(e['c_real_0'])} | {f(e['c_foil_0'])} | {f(e['c_real_at_minus_offset'])} | {f(e['best_lag_within_1p5'])} | {f(g['c_real_0'])} | {f(g['c_foil_0'])} |")
    pairs = [r for r in rows if not r["repeat"]]
    for mu in ("ear40", "energy"):
        a = np.array([r[mu]["c_foil_minus_real"] for r in pairs])
        L.append(f"\n{mu}: foil minus real c(0) over the {len(a)} shifted pairs: mean {a.mean():+.3f}, median {np.median(a):+.3f}, foil higher in {int((a > 0).sum())}/{len(a)}")
    (OUT / "foil_table.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


B_MISMATCH = S.B / "mismatch"


# ---------------------------------------------------------------------------------------------------- A2
def a2report():
    files = sorted((OUT / "a2").glob("*.npz"))
    tags = {}
    for p in files:
        z = np.load(p)
        for k in z.files:
            t = k.rsplit("|", 1)[0]
            tags.setdefault(t, []).append(p.stem)
    data = {t: {} for t in tags}
    for p in files:
        z = np.load(p)
        for k in z.files:
            t, f = k.rsplit("|", 1)
            data[t].setdefault(f, []).append(z[k])
    order = ["kp_optim", "kp_raw"] + [f"{v}|{s}" for v in ("V1", "V2") for s in S.STAGES[2:]]
    rng = np.random.default_rng(S.SEED_BOOT2)
    res = {}
    for t in order:
        if t not in data:
            continue
        d = {f: np.array(v) for f, v in data[t].items()}
        n = len(d["n"])
        row = dict(n=n)
        for mu in ("onset", "energy"):
            c = d[f"curve_{mu}"]
            lag, h = d[f"peak_{mu}"][:, 0], d[f"peak_{mu}"][:, 1]
            ok = np.isfinite(c).all(1)
            pl = S.peak(c[ok].mean(0), K2, K2)[0] if ok.any() else np.nan
            bs = [S.peak(c[ok][rng.integers(0, ok.sum(), ok.sum())].mean(0), K2, K2)[0] for _ in range(S.NBOOT)] if ok.sum() > 2 else [np.nan]
            ch = d[f"chance_{mu}"]
            row[mu] = dict(lag_q=q(lag), share_100ms=float((np.abs(lag[np.isfinite(lag)]) <= 0.1).mean()), height_median=float(np.nanmedian(h)),
                           chance_height_median=float(np.nanmedian(ch[..., 1])), pooled_lag=pl, pooled_lag_ci=[float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))])
        kp = d["peak_kp"][:, 0]
        row["vs_kp_lag_q"] = q(kp)
        if "peak_prev" in d:
            pv = d["peak_prev"][:, 0]
            pvh = d["peak_prev"][:, 1]
            bs = [np.nanmedian(pv[rng.integers(0, n, n)]) for _ in range(S.NBOOT)]
            row["vs_prev"] = dict(lag_q=q(pv), median_ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], height_median=float(np.nanmedian(pvh)))
        for sg in ("0.1", "0.05"):
            b, c = d[f"bas_music_{sg}"], d[f"chance_music_{sg}"]
            bb = [np.nanmean(b[i]) - np.nanmean(c[i]) for i in (rng.integers(0, n, n) for _ in range(S.NBOOT))]
            row[f"bas_{sg}"] = dict(bas=float(np.nanmean(b)), chance=float(np.nanmean(c)), excess=float(np.nanmean(b) - np.nanmean(c)), excess_ci=[float(np.percentile(bb, 2.5)), float(np.percentile(bb, 97.5))])
        res[t] = row
    ref = res["kp_optim"]["onset"]["pooled_lag"]
    for t, r in res.items():
        r["pooled_lag_minus_raw_ms"] = (r["onset"]["pooled_lag"] - ref) * 1000
    (OUT / "a2_results.json").write_text(json.dumps(res, indent=1))
    L = ["# A2 AIST++ per-stage lag and BAS\n", f"Sequences: {len(files)}. Positive lag = later. Music = librosa onset strength.\n",
         "| stage | n | lag vs music q25/q50/q75 (s) | share \\|lag\\|<=0.1 | height / chance | pooled lag (95 % CI) s | pooled minus raw kp (ms) | lag vs previous stage q25/q50/q75 (s) | median CI | BAS 0.1 (excess, CI) | BAS 0.05 (excess, CI) |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for t, r in res.items():
        o = r["onset"]
        pv = r.get("vs_prev")
        L.append(f"| {t} | {r['n']} | {o['lag_q'][1]:.2f} / {o['lag_q'][2]:.2f} / {o['lag_q'][3]:.2f} | {o['share_100ms']:.2f} | {o['height_median']:.3f} / {o['chance_height_median']:.3f} | "
                 f"{o['pooled_lag']:.3f} ({o['pooled_lag_ci'][0]:.3f}, {o['pooled_lag_ci'][1]:.3f}) | {r['pooled_lag_minus_raw_ms']:+.0f} | "
                 + (f"{pv['lag_q'][1]:+.3f} / {pv['lag_q'][2]:+.3f} / {pv['lag_q'][3]:+.3f} | ({pv['median_ci'][0]:+.3f}, {pv['median_ci'][1]:+.3f}) | " if pv else "- | - | ")
                 + f"{r['bas_0.1']['bas']:.3f} ({r['bas_0.1']['excess']:+.3f}, {r['bas_0.1']['excess_ci'][0]:+.3f}..{r['bas_0.1']['excess_ci'][1]:+.3f}) | "
                 f"{r['bas_0.05']['bas']:.3f} ({r['bas_0.05']['excess']:+.3f}, {r['bas_0.05']['excess_ci'][0]:+.3f}..{r['bas_0.05']['excess_ci'][1]:+.3f}) |")
    (OUT / "a2_tables.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


K2 = S.K2
