"""WO48 internal pulse: run on every song + numeric check (docs/PULSE_RULES.md sections 3-5). Brain env.
    pulse_run.py scan            inputs: wav present and decodable, grids present -> pulse/scan.json
    pulse_run.py run [P]         whole-song causal pulse + per-song check, P processes, resumable -> pulse/songs/<key>.{npz,json}; errors -> pulse/failed.txt
    pulse_run.py report          aggregates -> pulse/summary.json, docs/PULSE_TABLES.md
"""
import json
import multiprocessing as mp
import sys
import traceback
from pathlib import Path

import numpy as np
from scipy.ndimage import uniform_filter1d

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
B = Path("/secondary/hyst-data/body")
OUT = B / "pulse"
LISTS = {"finedance": B / "t0/lanes_list_fd.json", "aioz": B / "t0/lanes_list_aioz.json", "phantom": B / "t0_phantom/lanes_list.json", "motorica": B / "t0_motorica/lanes_list.json"}
SPOT = B / "metric/spotcheck/manifest.json"
EXCERPTS = B / "beatv/clicks_visual/key.json"
EX_LEN = 30.0
RATIOS = [1 / 4, 1 / 3, 1 / 2, 2 / 3, 1.0, 3 / 2, 2.0, 3.0, 4.0]
RATIO_NAMES = ["1/4", "1/3", "1/2", "2/3", "1", "3/2", "2", "3", "4"]
# Kosta's judged level relative to librosa (docs/BEATV_V4_RESULT.md); None = not stated
JUDGED = {"fd_018": 0.5, "fd_053": 1.0, "fd_183": 1.0, "aioz_8JQ0zHmZBIg_05_0_1950": 1.0, "aioz_SZhU9XTCUiM_13_0_1950": None, "ph_084": 1.0, "ph_102": 1.0,
          "ph_137": 1.0, "mo_kthjazz_gJZ_sFM_sngl_d02_004": None, "mo_kthstreet_gLH_sFM_cAll_d02_mLH_ch01_yougonnaregretit_002": 1.0}
JUDGED_NOTE = {"aioz_SZhU9XTCUiM_13_0_1950": "slower than librosa ('too fast?'), level not stated", "mo_kthjazz_gJZ_sFM_sngl_d02_004": "not stated"}


def songs():
    return [(ds, it["key"], it["wav"]) for ds in LISTS for it in json.loads(LISTS[ds].read_text())]


def grid_path(key):
    return B / "t1b/cortex/beats" / f"{key}.json" if key.startswith("fd_") else B / "metric/beats" / f"{key}.json"


def load_beats(p):
    return np.asarray(json.loads(Path(p).read_text())["beats"], float)


# ---------------- check primitives (section 5) ----------------
def ioi(ev):
    d = np.diff(np.asarray(ev, float))
    return d


def tempo_bpm(ev):
    d = ioi(ev)
    return float(60.0 / np.median(d)) if len(d) else float("nan")


def longest_gap(ev, lo=None, hi=None):
    """longest interval without an event; with lo/hi the bounds count as ends"""
    ev = np.asarray(ev, float)
    if lo is not None:
        ev = np.concatenate([[lo], ev[(ev > lo) & (ev < hi)], [hi]])
    d = np.diff(ev)
    return float(d.max()) if len(d) else float("nan")


def regularity_ms(ev, win=8, hop=2):
    ev = np.asarray(ev, float)
    k = np.arange(win)
    res = []
    for i in range(0, len(ev) - win + 1, hop):
        bb = ev[i:i + win]
        T, t0 = np.polyfit(k, bb, 1)
        res.append(np.sqrt(((bb - (t0 + T * k)) ** 2).mean()) * 1000)
    return float(np.median(res)) if res else float("nan")


def level(r):
    if not np.isfinite(r) or r <= 0:
        return None, float("nan")
    j = int(np.argmin([abs(np.log2(r / q)) for q in RATIOS]))
    return RATIO_NAMES[j], float(r / RATIOS[j] - 1)


def series_stats(ev, lo=None, hi=None):
    ev = np.asarray(ev, float)
    if lo is not None:
        ev = ev[(ev >= lo) & (ev < hi)]
    d = ioi(ev)
    med = float(np.median(d)) if len(d) else float("nan")
    return dict(n=int(len(ev)), tempo_bpm=tempo_bpm(ev), median_ioi_s=med, longest_gap_s=longest_gap(ev) if lo is None else longest_gap(ev, lo, hi),
                longest_gap_ioi=(longest_gap(ev) if lo is None else longest_gap(ev, lo, hi)) / med if med == med else float("nan"),
                first_event_s=float(ev[0]) if len(ev) else float("nan"), regularity_ms=regularity_ms(ev))


def quiet_passages(rms, start_s=10.0, min_s=2.0, frac=0.5, rate=100):
    m = uniform_filter1d(np.asarray(rms, float), int(rate))
    q = m < frac * np.median(m)
    out, i, T = [], 0, len(q)
    while i < T:
        if q[i]:
            j = i
            while j < T and q[j]:
                j += 1
            if (j - i) >= min_s * rate and i >= start_s * rate:
                out.append((i / rate, j / rate))
            i = j
        else:
            i += 1
    return out


def grid_dropouts(grid, start_s=10.0):
    g = np.asarray(grid, float)
    d = np.diff(g)
    if not len(d):
        return []
    med = np.median(d)
    return [(float(g[i]), float(g[i + 1])) for i in np.flatnonzero(d > 2 * med) if g[i] >= start_s]


def persistence(passages, series, pulse_amp=None):
    """per passage: for each series the longest gap inside it (bounds count) / the series' own median IOI; kept = <= 1.5"""
    out = []
    for s, e in passages:
        row = dict(start=s, end=e)
        for name, ev in series.items():
            d = ioi(ev)
            med = float(np.median(d)) if len(d) else float("nan")
            g = longest_gap(ev, s, e) / med if med == med else float("nan")
            row[name] = dict(gap_ioi=g, kept=bool(g <= 1.5))
        if pulse_amp is not None:
            a0, a1 = pulse_amp[min(int(s * 100), len(pulse_amp) - 1)], pulse_amp[min(int(e * 100), len(pulse_amp) - 1)]
            row["pulse_amp_ratio"] = float(a1 / a0) if a0 > 0 else float("nan")
        out.append(row)
    return out


def following(rate, lib):
    lib = np.asarray(lib, float)
    k = np.arange(8)
    rows = []
    for i in range(0, len(lib) - 7, 2):
        bb = lib[i:i + 8]
        T, t0 = np.polyfit(k, bb, 1)
        if np.sqrt(((bb - (t0 + T * k)) ** 2).mean()) >= 0.020:
            continue
        a, b = int(bb[0] * 100), min(int(bb[-1] * 100), len(rate))
        if b <= a:
            continue
        pr = float(np.median(rate[a:b]))
        rows.append((1.0 / T, pr))
    if not rows:
        return dict(windows=0)
    lt, pr = np.log2(np.array(rows)).T
    lr = pr - lt
    d = lr - np.round(lr)
    out = dict(windows=len(rows), median_abs_fold_pct=float((2 ** np.median(np.abs(d)) - 1) * 100), share_within_4pct=float(np.mean(np.abs(d) <= np.log2(1.04))),
               lib_tempo_sd_log2=float(lt.std()))
    if lt.std() > 0.02 and pr.std() > 0:
        out["corr_log2"] = float(np.corrcoef(lt, pr)[0, 1])
    return out


def check_song(key, r, rms, lib, grid, excerpt=None):
    ev = r["events"]
    rate = r["rate"]
    med_rate = float(np.median(rate))
    sel = r["sel"]
    dur_min = len(rate) / 100 / 60
    jumps = int(np.sum(np.abs(np.diff(sel.astype(int))) > 2))
    whole = dict(pulse=series_stats(ev), lib=series_stats(lib), grid=series_stats(grid))
    whole["pulse"]["median_rate_bpm"] = 60 * med_rate
    pt = whole["pulse"]["tempo_bpm"]
    for nm in ("lib", "grid"):
        ratio = pt / whole[nm]["tempo_bpm"] if whole[nm]["tempo_bpm"] > 0 else float("nan")
        whole["level_vs_" + nm] = dict(ratio=ratio, nearest=level(ratio)[0], dev=level(ratio)[1])
    series = dict(pulse=ev, lib=lib, grid=grid)
    out = dict(key=key, duration_s=len(rate) / 100, f_max=float(r["f_max"]), whole=whole,
               stability=dict(jumps_per_min=jumps / dur_min, share_within_6pct=float(np.mean(np.abs(rate / med_rate - 1) <= 0.06)), median_amp=float(np.median(r["amp"]))),
               quiet=persistence(quiet_passages(rms), series, r["amp"]), dropouts=persistence(grid_dropouts(grid), dict(pulse=ev, lib=lib), r["amp"]),
               following=following(rate, lib))
    if excerpt is not None:
        lo, hi = excerpt, excerpt + EX_LEN
        ex = dict(start_s=lo, pulse=series_stats(ev, lo, hi), lib=series_stats(lib, lo, hi), grid=series_stats(grid, lo, hi))
        ex["pulse"]["median_rate_bpm"] = 60 * float(np.median(rate[int(lo * 100):int(hi * 100)]))
        for nm in ("lib", "grid"):
            ratio = ex["pulse"]["tempo_bpm"] / ex[nm]["tempo_bpm"]
            ex["level_vs_" + nm] = dict(ratio=ratio, nearest=level(ratio)[0], dev=level(ratio)[1])
        j = JUDGED.get(key)
        ex["judged"] = dict(factor_of_lib=j, note=JUDGED_NOTE.get(key, "librosa level judged right" if j == 1.0 else "half of librosa" if j == 0.5 else None),
                            pulse_over_judged=(ex["pulse"]["tempo_bpm"] / (j * ex["lib"]["tempo_bpm"])) if j else None)
        out["excerpt"] = ex
    return out


# ---------------- run ----------------
def excerpts():
    return {s["song"]: s["start_s"] for s in json.loads(EXCERPTS.read_text())["songs"]}


def run_one(a):
    ds, key, wav = a
    dst = OUT / "songs" / f"{key}.json"
    if dst.exists():
        return key, "skip"
    try:
        import fast_features as ff
        import pulse_lib as P
        F = ff.fast_features(ff.load_mono(wav))
        r = P.pulse(F)
        r["f_max"] = P.f_max()
        np.savez_compressed(OUT / "songs" / f"{key}.npz", rate=r["rate"].astype(np.float32), phase=r["phase"].astype(np.float32), amp=r["amp"].astype(np.float32),
                            sel=r["sel"].astype(np.int16), freq=r["freq"].astype(np.float32), events=r["events"], f_max=r["f_max"], rms=F[:, 41])
        lib = load_beats(B / "beatv/librosa" / f"{key}.json")
        grid = load_beats(grid_path(key))
        c = check_song(key, r, F[:, 41], lib, grid, excerpts().get(key))
        c["dataset"] = ds
        c["events"] = [round(float(e), 4) for e in r["events"]]
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(c))
        tmp.replace(dst)
        return key, f"{len(r['events'])} events, {c['whole']['pulse']['tempo_bpm']:.1f} bpm"
    except Exception as e:  # noqa: BLE001
        with open(OUT / "failed.txt", "a") as f:
            f.write(f"{key}\t{type(e).__name__}: {e}\n{traceback.format_exc()}\n")
        return key, f"FAILED {type(e).__name__}: {e}"


def cmd_scan():
    import soundfile as sf
    bad, n = [], 0
    for ds, key, wav in songs():
        n += 1
        try:
            info = sf.info(wav)
            if info.frames <= 0:
                bad.append((key, "empty"))
        except Exception as e:  # noqa: BLE001
            bad.append((key, f"audio: {e}"))
        for p in (B / "beatv/librosa" / f"{key}.json", grid_path(key)):
            if not p.exists():
                bad.append((key, f"missing {p}"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scan.json").write_text(json.dumps(dict(songs=n, bad=bad), indent=1))
    print("scan", n, "songs", len(bad), "bad", bad[:10], flush=True)


def cmd_run(procs=6):
    (OUT / "songs").mkdir(parents=True, exist_ok=True)
    jobs = songs()
    # the 10 spot-check songs first
    spot = {s["song"] for s in json.loads(SPOT.read_text())["songs"]}
    jobs.sort(key=lambda j: j[1] not in spot)
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (k, msg) in enumerate(pool.imap_unordered(run_one, jobs)):
            if i % 25 == 0 or "FAILED" in msg or k in spot:
                print(i, "/", len(jobs), k, msg, flush=True)
    print("PULSE RUN DONE", len(jobs), flush=True)


# ---------------- report ----------------
def q(x, ps=(5, 25, 50, 75, 95), d=1):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return "n/a" if not len(x) else " / ".join(f"{np.percentile(x, p):.{d}f}" for p in ps)


def cmd_report():
    rs = [json.loads(p.read_text()) for p in sorted((OUT / "songs").glob("*.json"))]
    spot = [s["song"] for s in json.loads(SPOT.read_text())["songs"]]
    by = {r["key"]: r for r in rs}
    L = ["# Pulse numeric check tables (WO48, docs/PULSE_RULES.md section 5)", "", f"Songs analysed: {len(rs)}. Per-song values: `/secondary/hyst-data/body/pulse/songs/<key>.json`.", ""]
    for scope in ("excerpt", "whole"):
        L += [f"## The 10 V4 songs, {'30 s excerpts (same as beatv/clicks_visual)' if scope == 'excerpt' else 'whole songs'}", "",
              "| song | pulse BPM | librosa BPM | grid BPM | pulse/librosa (level) | pulse/grid (level) | judged level | pulse/judged | longest gap s (pulse / lib / grid) | gap in IOIs (pulse / lib / grid) | regularity ms (pulse / lib / grid) |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for k in spot:
            r = by.get(k)
            if r is None:
                L.append(f"| {k} | missing |"); continue
            e = r["excerpt"] if scope == "excerpt" else r["whole"]
            jd = r["excerpt"]["judged"]
            pj = jd["pulse_over_judged"] if scope == "excerpt" else ((e["pulse"]["tempo_bpm"] / (jd["factor_of_lib"] * e["lib"]["tempo_bpm"])) if jd["factor_of_lib"] else None)
            L.append(f"| {k[:24]} | {e['pulse']['tempo_bpm']:.1f} | {e['lib']['tempo_bpm']:.1f} | {e['grid']['tempo_bpm']:.1f} | {e['level_vs_lib']['ratio']:.3f} ({e['level_vs_lib']['nearest']}) | "
                     f"{e['level_vs_grid']['ratio']:.3f} ({e['level_vs_grid']['nearest']}) | {jd['note']} | {'%.3f' % pj if pj else 'n/a'} | "
                     f"{e['pulse']['longest_gap_s']:.2f} / {e['lib']['longest_gap_s']:.2f} / {e['grid']['longest_gap_s']:.2f} | "
                     f"{e['pulse']['longest_gap_ioi']:.2f} / {e['lib']['longest_gap_ioi']:.2f} / {e['grid']['longest_gap_ioi']:.2f} | "
                     f"{e['pulse']['regularity_ms']:.1f} / {e['lib']['regularity_ms']:.1f} / {e['grid']['regularity_ms']:.1f} |")
        L.append("")
    L += ["## The 10 V4 songs: persistence, stability, tempo following (whole songs)", "",
          "| song | quiet passages | kept pulse / lib / grid | grid dropouts | kept pulse / lib | pulse amp ratio (quiet, median) | jumps/min | share rate within 6 % | following windows | median folded dev % | share within 4 % | corr (if tempo varies) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k in spot:
        r = by.get(k)
        if r is None:
            continue
        qp, dp, fo = r["quiet"], r["dropouts"], r["following"]
        kq = lambda rows, s: sum(x[s]["kept"] for x in rows)  # noqa: E731
        am = np.median([x["pulse_amp_ratio"] for x in qp]) if qp else float("nan")
        L.append(f"| {k[:24]} | {len(qp)} | {kq(qp, 'pulse')} / {kq(qp, 'lib')} / {kq(qp, 'grid')} | {len(dp)} | {kq(dp, 'pulse')} / {kq(dp, 'lib')} | {am:.2f} | "
                 f"{r['stability']['jumps_per_min']:.2f} | {r['stability']['share_within_6pct']:.2f} | {fo.get('windows', 0)} | {fo.get('median_abs_fold_pct', float('nan')):.1f} | "
                 f"{fo.get('share_within_4pct', float('nan')):.2f} | {fo.get('corr_log2', 'n/a') if isinstance(fo.get('corr_log2'), str) or 'corr_log2' not in fo else '%.2f' % fo['corr_log2']} |")
    L.append("")
    summ = {}
    L += ["## All songs, per dataset", "",
          "| dataset | songs | pulse BPM q5/25/50/75/95 | librosa BPM q5/25/50/75/95 | grid BPM q5/25/50/75/95 | share pulse < 80 BPM | share pulse > 150 BPM | longest gap s q50/90/max (pulse) | (librosa) | (grid) | longest gap in IOIs q50/90 (pulse / lib / grid) | regularity ms q50 (pulse / lib / grid) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ds in ("finedance", "aioz", "phantom", "motorica", "all"):
        g = [r for r in rs if ds == "all" or r["dataset"] == ds]
        if not g:
            continue
        pb = [r["whole"]["pulse"]["median_rate_bpm"] for r in g]
        tb = lambda s: [r["whole"][s]["tempo_bpm"] for r in g]  # noqa: E731
        lg = lambda s: [r["whole"][s]["longest_gap_s"] for r in g]  # noqa: E731
        li = lambda s: [r["whole"][s]["longest_gap_ioi"] for r in g]  # noqa: E731
        rg = lambda s: [r["whole"][s]["regularity_ms"] for r in g]  # noqa: E731
        s = dict(songs=len(g), pulse_bpm=q(pb), lib_bpm=q(tb("lib")), grid_bpm=q(tb("grid")), share_below_80=float(np.mean(np.array(pb) < 80)), share_above_150=float(np.mean(np.array(pb) > 150)))
        summ[ds] = s
        L.append(f"| {ds} | {len(g)} | {q(pb)} | {q(tb('lib'))} | {q(tb('grid'))} | {s['share_below_80']:.3f} | {s['share_above_150']:.3f} | {q(lg('pulse'), (50, 90, 100), 2)} | "
                 f"{q(lg('lib'), (50, 90, 100), 2)} | {q(lg('grid'), (50, 90, 100), 2)} | {q(li('pulse'), (50, 90), 2)} ; {q(li('lib'), (50, 90), 2)} ; {q(li('grid'), (50, 90), 2)} | "
                 f"{q(rg('pulse'), (50,))} / {q(rg('lib'), (50,))} / {q(rg('grid'), (50,))} |")
    L += ["", "## All songs: level against librosa and the grid (share of songs, whole-song tempo ratio pulse / other, nearest simple ratio)", "",
          "| dataset | vs | " + " | ".join(RATIO_NAMES) + " | median abs deviation from the nearest ratio |", "|---|---|" + "---|" * (len(RATIO_NAMES) + 1)]
    for ds in ("finedance", "aioz", "phantom", "motorica", "all"):
        g = [r for r in rs if ds == "all" or r["dataset"] == ds]
        for nm in ("lib", "grid"):
            lv = [r["whole"]["level_vs_" + nm]["nearest"] for r in g]
            dv = [abs(r["whole"]["level_vs_" + nm]["dev"]) for r in g if r["whole"]["level_vs_" + nm]["nearest"]]
            L.append(f"| {ds} | {nm} | " + " | ".join(f"{np.mean([x == n for x in lv]):.3f}" for n in RATIO_NAMES) + f" | {np.median(dv) * 100:.1f} % |")
            summ.setdefault(ds, {})["level_vs_" + nm] = {n: float(np.mean([x == n for x in lv])) for n in RATIO_NAMES}
    L += ["", "## All songs: persistence, stability, tempo following", "",
          "| dataset | quiet passages | kept pulse / lib / grid | grid dropouts | kept pulse / lib | pulse amp ratio in quiet q50 | jumps/min q50/90 | share rate within 6 % q50/10 | following: songs | median folded dev % (q50 over songs) | share windows within 4 % (q50 over songs) | songs with varying tempo | corr q50 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ds in ("finedance", "aioz", "phantom", "motorica", "all"):
        g = [r for r in rs if ds == "all" or r["dataset"] == ds]
        qp = [x for r in g for x in r["quiet"]]
        dp = [x for r in g for x in r["dropouts"]]
        sh = lambda rows, s: float(np.mean([x[s]["kept"] for x in rows])) if rows else float("nan")  # noqa: E731
        fo = [r["following"] for r in g if r["following"].get("windows", 0) > 0]
        co = [f["corr_log2"] for f in fo if "corr_log2" in f]
        row = dict(quiet=len(qp), quiet_kept=dict(pulse=sh(qp, "pulse"), lib=sh(qp, "lib"), grid=sh(qp, "grid")), dropouts=len(dp), dropout_kept=dict(pulse=sh(dp, "pulse"), lib=sh(dp, "lib")))
        summ.setdefault(ds, {})["persistence"] = row
        L.append(f"| {ds} | {len(qp)} | {row['quiet_kept']['pulse']:.3f} / {row['quiet_kept']['lib']:.3f} / {row['quiet_kept']['grid']:.3f} | {len(dp)} | "
                 f"{row['dropout_kept']['pulse']:.3f} / {row['dropout_kept']['lib']:.3f} | {q([x['pulse_amp_ratio'] for x in qp], (50,), 2)} | "
                 f"{q([r['stability']['jumps_per_min'] for r in g], (50, 90), 2)} | {q([r['stability']['share_within_6pct'] for r in g], (50, 10), 2)} | {len(fo)} | "
                 f"{q([f['median_abs_fold_pct'] for f in fo], (50,), 1)} | {q([f['share_within_4pct'] for f in fo], (50,), 2)} | {len(co)} | {q(co, (50,), 2)} |")
    failed = (OUT / "failed.txt").read_text().count("\n\n") if (OUT / "failed.txt").exists() else 0
    L += ["", f"Failed songs: {failed} (`pulse/failed.txt`)."]
    (HERE.parent.parent / "docs/PULSE_TABLES.md").write_text("\n".join(L) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    print("REPORT DONE", len(rs), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"scan": cmd_scan, "run": cmd_run, "report": cmd_report}[a[0]](*[int(x) for x in a[1:]])
