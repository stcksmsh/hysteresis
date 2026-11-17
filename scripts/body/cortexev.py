"""BRAIN_SPEC 7.79 Step 2: cortex surprisal peaks vs ear-feature event detectors (rules: docs/CORTEX_EVENTS_RULES.md). Brain env.

    cortexev.py run        song set, detectors, scores -> /secondary/hyst-data/body/cortexev/{songs,per_song,results}.json, tables.md, v4_events.md
Report only; reads the stored T0 lanes, computes nothing in the cortex.
"""
import json
import warnings
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
sys.path.insert(0, str(HERE.parent))

warnings.filterwarnings("ignore", "All-NaN slice")
warnings.filterwarnings("ignore", "Mean of empty slice")
B = Path("/secondary/hyst-data/body")
OUT = B / "cortexev"
LANES = {"fd": B / "t0/lanes", "aioz": B / "t0/lanes", "ph": B / "t0_phantom/lanes", "mo": B / "t0_motorica/lanes"}
LISTS = {"fd": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "ph": B / "t0_phantom/lanes_list.json", "mo": B / "t0_motorica/lanes_list.json"}
MANIFEST = B / "metric/spotcheck/manifest.json"
START, MIN_SPAN, NPER = 16.0, 12.0, 50
SEED_SHIFT, SEED_BOOT, SEED_SONGS = 79201, 79202, 79203
NSHIFT, NBOOT = 200, 2000
WINDOWS = (0.5, 1.0)
LAYERS = ("L1", "L2", "L3", "L4", "total")
EARPK = ("E-onset", "E-lowflux", "E-change")
EVENTS = ("drop", "dropout_on", "dropout_end", "section")
REFS = EVENTS + ("any", "manifest")
PRED = LAYERS + EARPK + EVENTS


# ---------------------------------------------------------------------------------------------------- signals
def ten(x, n10):
    """100 Hz (T, ...) -> 10 Hz mean of the 10 frames ending at each stamp (10k + 9)"""
    return x[:n10 * 10].reshape(n10, 10, *x.shape[1:]).mean(1)


def run_median(x, n=100):
    """median of the n values before each index (current excluded); NaN with fewer than 10"""
    p = np.concatenate([np.full(n, np.nan), x])
    w = np.lib.stride_tricks.sliding_window_view(p, n)[:len(x)]
    with np.errstate(all="ignore"):
        m = np.nanmedian(np.where(np.isfinite(w), w, np.nan), 1) if len(x) else np.zeros(0)
    m[np.isfinite(w).sum(1) < 10] = np.nan
    return m


def causal_mean(x, n):
    p = np.concatenate([np.full(n - 1, np.nan), x])
    w = np.lib.stride_tricks.sliding_window_view(p, n)
    with np.errstate(all="ignore"):
        return np.nanmean(w, 1)


def dropouts(L, O):
    """-> (onset stamps, end stamps); rules section 1"""
    mL, mO = run_median(L), run_median(O)
    n, on, end, k = len(L), [], [], 0
    while k < n:
        bl, bo = mL[k], mO[k]
        c = lambda j: L[j] < 0.25 * bl and O[j] < 0.5 * bo  # noqa: E731
        if not (np.isfinite(bl) and np.isfinite(bo) and bl > 0 and bo > 0 and c(k)):
            k += 1
            continue
        if not (k + 4 <= n and all(c(j) for j in range(k, k + 4))):
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


def drops(L, F):
    mL, mF = run_median(L), run_median(F)
    out, last = [], -10 ** 9
    for t in range(10, len(L)):
        base = mL[t - 10]
        if t - last < 40 or not (np.isfinite(base) and base > 0 and np.isfinite(mF[t])):
            continue
        if L[t - 10:t].mean() < 0.5 * base and F[t] > 3 * mF[t] and L[t] >= 0.5 * base:
            out.append(t)
            last = t
    return np.array(out, int)


def sections(ear):
    import controls_stats as CS
    n = len(ear) // 50
    Fk = ear[:n * 50].reshape(n, 50, -1).mean(1)
    Fk = (Fk - Fk.mean(0)) / np.maximum(Fk.std(0), 1e-6)
    nv = CS.novelty(Fk, half=16, sigma=8.0)
    return 0.5 * CS.peaks(nv, min_dist=16) + 0.25


def peaks(x, span):
    """smoothed lane (causal 0.3 s mean) -> peak stamps: max within +-1 s, >= song p90 over the span"""
    s = causal_mean(x, 3)
    v = s[span & np.isfinite(s)]
    if len(v) < 20:
        return np.zeros(0, int)
    th = np.percentile(v, 90)
    out = []
    for k in np.flatnonzero(span & np.isfinite(s) & (s >= th)):
        w = s[max(k - 10, 0):k + 11]
        if k >= 10 and s[k] >= np.nanmax(w) and s[k] > np.nanmax(s[k - 10:k]):
            out.append(k)
    return np.array(out, int)


def song_detect(key, ds, mean, std, cen_lo):
    z = np.load(LANES[ds] / f"{key}.npz")
    ear, s10 = z["ear"].astype(np.float64), z["s10"].astype(np.float64)
    n10 = min(len(s10), len(ear) // 10)
    ts = (10 * np.arange(n10) + 9) / 100.0
    raw = ear * std + mean
    L = ten(10 ** (raw[:, cen_lo] / 10).mean(1), n10)
    O = causal_mean(ten(raw[:, 40], n10), 5)
    F = ten(raw[:, 32], n10)
    span = ts >= START
    c = np.cumsum(np.concatenate([np.zeros((1, 44)), ear]), 0)
    f = 10 * np.arange(n10) + 9
    ok = f >= 199
    chg = np.full(n10, np.nan)
    m1 = (c[f[ok] + 1] - c[f[ok] - 99]) / 100
    m0 = (c[f[ok] - 99] - c[f[ok] - 199]) / 100
    chg[ok] = np.linalg.norm(m1 - m0, axis=1)
    lanes = {name: s10[:n10, i] for i, name in enumerate(LAYERS)}
    lanes.update({"E-onset": ten(raw[:, 40], n10), "E-lowflux": F, "E-change": chg})
    pred = {name: ts[peaks(x, span)] for name, x in lanes.items()}
    on, end = dropouts(L, O)
    ev = {"drop": ts[drops(L, F)], "dropout_on": ts[on], "dropout_end": ts[end], "section": sections(ear)}
    a, b = START, n10 / 10.0
    ev = {k: np.sort(v[(v >= a) & (v <= b)]) for k, v in ev.items()}
    pred.update(ev)
    smooth = {name: causal_mean(lanes[name], 3) for name in LAYERS}
    return dict(span=(a, b), pred=pred, ref=dict(ev), smooth=smooth, ts=ts)


# ---------------------------------------------------------------------------------------------------- scoring
def counts(p, r, w):
    p, r = np.asarray(p), np.sort(np.asarray(r))
    if len(p) == 0 or len(r) == 0:
        return np.array([0, len(p), 0, len(r)], float)
    near = lambda x, y: np.abs(x[:, None] - y[None]).min(1) <= w + 1e-9  # noqa: E731
    return np.array([near(p, r).sum(), len(p), near(r, np.sort(p)).sum(), len(r)], float)


def shifted_counts(P, r, w):
    """P (S, n) shifted peak times -> (S, 4) counts"""
    S, n = P.shape
    out = np.zeros((S, 4))
    out[:, 1], out[:, 3] = n, len(r)
    if n and len(r):
        d = np.abs(P[:, :, None] - np.asarray(r)[None, None]) <= w + 1e-9
        out[:, 0], out[:, 2] = d.any(2).sum(1), d.any(1).sum(1)
    return out


def f1(c):
    c = np.asarray(c)
    P = c[..., 0] / np.maximum(c[..., 1], 1e-12)
    R = c[..., 2] / np.maximum(c[..., 3], 1e-12)
    return np.where(P + R > 0, 2 * P * R / np.maximum(P + R, 1e-12), 0.0), P, R


def ref_for(sd, pname, rname, man):
    if rname == "manifest":
        return man
    if rname == "any":
        return np.sort(np.concatenate([sd["ref"][k] for k in EVENTS if k != pname]))
    return sd["ref"][rname]


def score(per, mans, offs):
    keys = list(per)
    res = {}
    for w in WINDOWS:
        for pn in PRED:
            for rn in REFS:
                if pn == rn:
                    continue
                ks = [k for k in keys if rn != "manifest" or k in mans]
                ob, ch = np.zeros((len(ks), 4)), np.zeros((len(ks), NSHIFT, 4))
                for i, k in enumerate(ks):
                    sd = per[k]
                    a, b = sd["span"]
                    r = ref_for(sd, pn, rn, mans.get(k))
                    r = r[(r >= a) & (r <= b)]
                    p = sd["pred"][pn]
                    ob[i] = counts(p, r, w)
                    ch[i] = shifted_counts(a + np.mod(p[None] - a + offs[k][:, None], b - a), r, w)
                fo, P, R = f1(ob.sum(0))
                fsh = f1(ch.sum(0))[0]
                idx = np.random.default_rng(SEED_BOOT).integers(0, len(ks), (NBOOT, len(ks)))
                fb = f1(ob[idx].sum(1))[0]
                cb = f1(ch.mean(1)[idx].sum(1))[0]
                res[f"{pn}|{rn}|{w}"] = dict(pred=pn, ref=rn, window=w, songs=len(ks), n_pred=int(ob[:, 1].sum()), n_ref=int(ob[:, 3].sum()),
                                            precision=float(P), recall=float(R), f1=float(fo), chance_f1=float(fsh.mean()),
                                            excess=float(fo - fsh.mean()), f1_ci=[float(x) for x in np.percentile(fb, [2.5, 97.5])],
                                            excess_ci=[float(x) for x in np.percentile(fb - cb, [2.5, 97.5])],
                                            p=float((1 + (fsh >= fo).sum()) / (1 + NSHIFT)))
    return res


def lag_profile(per):
    lags = np.arange(-40, 121)
    out = {}
    for ln in LAYERS:
        for rn in EVENTS:
            acc = []
            for sd in per.values():
                x = sd["smooth"][ln]
                v = x[(sd["ts"] >= START) & np.isfinite(x)]
                if len(v) < 20 or v.std() == 0:
                    continue
                zx = (x - v.mean()) / v.std()
                for e in sd["ref"][rn]:
                    k = int(round(e * 10 - 0.9))
                    j = k + lags
                    row = np.full(len(lags), np.nan)
                    ok = (j >= 0) & (j < len(zx))
                    row[ok] = zx[j[ok]]
                    acc.append(row)
            if acc:
                with np.errstate(all="ignore"):
                    m = np.nanmean(np.array(acc), 0)
                i = int(np.nanargmax(m))
                out[f"{ln}|{rn}"] = dict(n=len(acc), peak_lag_s=float(lags[i] / 10), peak_z=float(m[i]), z_at_0=float(m[40]),
                                         profile=[None if not np.isfinite(x) else round(float(x), 3) for x in m])
    return out


# ---------------------------------------------------------------------------------------------------- song set
def song_set():
    man = json.loads(MANIFEST.read_text())["songs"]
    v4 = [(s["song"], {"finedance": "fd", "aioz": "aioz", "phantom": "ph", "motorica": "mo"}[s["dataset"]]) for s in man]
    v4keys = {k for k, _ in v4}
    v4ids = {k.split("_")[1] for k, ds in v4 if ds == "aioz"}
    rng = np.random.default_rng(SEED_SONGS)
    picked, elig = [], {}
    for ds in ("fd", "aioz", "ph", "mo"):
        items = [it["key"] for it in json.loads(LISTS[ds].read_text()) if (LANES[ds] / f"{it['key']}.npz").exists()]
        ok = sorted(k for k in items if k not in v4keys and int(np.load(LANES[ds] / f"{k}.npz")["n_frames"]) / 100 >= START + MIN_SPAN)
        if ds == "aioz":
            seen, one = set(v4ids), []
            for k in ok:
                if k.split("_")[1] not in seen:
                    seen.add(k.split("_")[1])
                    one.append(k)
            ok = one
        elig[ds] = len(ok)
        picked += [(ok[i], ds) for i in sorted(rng.choice(len(ok), min(NPER, len(ok)), replace=False))]
    mans = {s["song"]: np.array([b["boundary_s"] for b in s["boundaries"]]) for s in man}
    return v4, picked, mans, elig


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def v4_sheet(per, v4, mans):
    lines = ["# V4 songs: ear-feature events and cortex peaks away from them (for Kosta's ear check; not served)", "",
             "Rules: `docs/CORTEX_EVENTS_RULES.md`. Times mm:ss.s from the song start, only from 0:16 on (the scoring span).",
             "Reference events are ear-feature detections, not ground truth. A cortex peak is listed if no reference event (any type, or a",
             "manifest boundary) lies within ±1 s. L3/L4 surprisal answers up to 2 s / 8 s after a change by construction.", ""]
    for k, ds in v4:
        sd = per[k]
        lines += [f"## {k} ({ds}, {sd['span'][1]:.0f} s)", ""]
        allref = np.sort(np.concatenate([sd["ref"][e] for e in EVENTS] + [mans[k][mans[k] >= START]]))
        for e in EVENTS:
            lines.append(f"- {e}: " + (", ".join(mmss(t) for t in sd["ref"][e]) or "none"))
        lines.append("- manifest boundary: " + (", ".join(mmss(t) for t in mans[k] if t >= START) or "none"))
        for ln in LAYERS:
            p = sd["pred"][ln]
            lone = [t for t in p if not len(allref) or np.abs(allref - t).min() > 1.0]
            lines.append(f"- cortex {ln} peaks not near an event ({len(lone)} of {len(p)}): " + (", ".join(mmss(t) for t in lone) or "none"))
        lines.append("")
    return "\n".join(lines)


def tables(res, lag, per, info):
    L = []
    for w in WINDOWS:
        L += [f"### F1 at ±{w} s: F1 (excess over chance [95 % CI]); columns = reference event type", "",
              "| detector | " + " | ".join(REFS) + " |", "|---|" + "---|" * len(REFS)]
        for pn in PRED:
            row = []
            for rn in REFS:
                r = res.get(f"{pn}|{rn}|{w}")
                row.append("—" if r is None else f"{r['f1']:.3f} ({r['excess']:+.3f} [{r['excess_ci'][0]:+.3f}, {r['excess_ci'][1]:+.3f}])")
            L.append(f"| {pn} | " + " | ".join(row) + " |")
        L.append("")
        L += [f"### Detail vs `any` at ±{w} s", "", "| detector | peaks | events | precision | recall | F1 [95 % CI] | chance F1 | p |", "|---|---|---|---|---|---|---|---|"]
        for pn in PRED:
            r = res[f"{pn}|any|{w}"]
            L.append(f"| {pn} | {r['n_pred']} | {r['n_ref']} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} [{r['f1_ci'][0]:.3f}, {r['f1_ci'][1]:.3f}] | {r['chance_f1']:.3f} | {r['p']:.3f} |")
        L.append("")
    L += ["### Event-locked surprisal (z within song): lag of the maximum in −4..+12 s, its z, and z at lag 0", "",
          "| layer | " + " | ".join(EVENTS) + " |", "|---|" + "---|" * len(EVENTS)]
    for ln in LAYERS:
        L.append(f"| {ln} | " + " | ".join(f"{lag[f'{ln}|{e}']['peak_lag_s']:+.1f} s, z {lag[f'{ln}|{e}']['peak_z']:.2f}, z0 {lag[f'{ln}|{e}']['z_at_0']:.2f} (n {lag[f'{ln}|{e}']['n']})" if f"{ln}|{e}" in lag else "—" for e in EVENTS) + " |")
    L.append("")
    return "\n".join(L)


def main():
    import braindump as bd
    import librosa
    mean, std = (np.asarray(x, np.float64) for x in bd.stats())
    cen = librosa.mel_frequencies(n_mels=34, fmin=30, fmax=16000)[1:-1]
    cen_lo = np.flatnonzero(cen < 200)
    v4, picked, mans, elig = song_set()
    OUT.mkdir(parents=True, exist_ok=True)
    per = {}
    for k, ds in v4 + picked:
        per[k] = song_detect(k, ds, mean, std, cen_lo)
        per[k]["ds"] = ds
        print("song", k, {e: len(v) for e, v in per[k]["ref"].items()}, flush=True)
    rng = np.random.default_rng(SEED_SHIFT)
    offs = {k: rng.uniform(0, per[k]["span"][1] - per[k]["span"][0], NSHIFT) for k in per}
    res = score(per, mans, offs)
    lag = lag_profile(per)
    ds_of = {k: per[k]["ds"] for k in per}
    (OUT / "songs.json").write_text(json.dumps(dict(v4=[k for k, _ in v4], sample=[k for k, _ in picked], dataset=ds_of, eligible=elig,
                                                    span_s={k: per[k]["span"] for k in per}), indent=1))
    (OUT / "per_song.json").write_text(json.dumps({k: dict(ds=sd["ds"], span=sd["span"], events={e: sd["ref"][e].round(2).tolist() for e in EVENTS},
                                                           peaks={p: sd["pred"][p].round(2).tolist() for p in LAYERS + EARPK},
                                                           counts={f"{pn}|{rn}|{w}": counts(sd["pred"][pn], ref_for(sd, pn, rn, mans.get(k)), w).tolist()
                                                                   for w in WINDOWS for pn in PRED for rn in REFS if pn != rn and (rn != "manifest" or k in mans)})
                                                  for k, sd in per.items()}))
    (OUT / "results.json").write_text(json.dumps(dict(scores=res, lag=lag), indent=1))
    (OUT / "tables.md").write_text(tables(res, lag, per, elig))
    (OUT / "v4_events.md").write_text(v4_sheet(per, v4, mans))
    print("DONE", len(per), "songs", flush=True)


if __name__ == "__main__":
    if sys.argv[1:] == ["run"]:
        main()
    else:
        print(__doc__)
