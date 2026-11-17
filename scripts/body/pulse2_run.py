"""WO51 pulse v2: run on every song + numeric check v1 vs v2 (docs/PULSE2_RULES.md sections 5-6). Brain env.
    pulse2_run.py run [P]     whole-song causal pulse v2 + per-song check, P processes, resumable -> pulse2/songs/<key>.{npz,json}; errors -> pulse2/failed.txt
    pulse2_run.py report      v1 vs v2 aggregates -> pulse2/summary.json, docs/PULSE2_TABLES.md
v1's per-song values are read from pulse/songs/<key>.json (read-only). Reuses pulse_run's check (section 5 of docs/PULSE_RULES.md).
"""
import json
import multiprocessing as mp
import sys
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "brain"))
import pulse_run as R  # noqa: E402

B = R.B
V1 = B / "pulse"
OUT = B / "pulse2"
MIN_SONG_S = 12.0                                       # 7.79 Q4: songs under 12 s are left out of every summary
# passage rules (docs/PULSE2_RULES.md section 6)
PER_WIN_S, PER_LAG = 6.0, (0.25, 2.0)                    # low-band periodicity: centred 6 s window, lags 0.25-2 s
BEATLESS_TH, BEAT_TH, BEATLESS_MIN_S, START_S = 0.3, 0.5, 4, 10
VIEW_KEYS = (V1 / "flash/key.json", V1 / "flash2/key.json")


def periodicity(flux_low, rate=100):
    """per second s (frames [100 s, 100 s + 100)): max over lags 0.25-2 s of the autocorrelation (normalised at lag 0) of the mean-removed
    30-200 Hz flux in the 6 s window centred on s + 0.5 s; 0 where the window has no variance. -> (seconds,)"""
    x = np.asarray(flux_low, float)
    n = len(x) // rate
    h = int(PER_WIN_S * rate / 2)
    l0, l1 = int(PER_LAG[0] * rate), int(PER_LAG[1] * rate)
    out = np.zeros(n)
    for s in range(n):
        c = s * rate + rate // 2
        w = x[max(c - h, 0):c + h]
        w = w - w.mean()
        e = float(w @ w)
        if e <= 1e-12 or len(w) <= l1:
            continue
        ac = np.correlate(w, w, "full")[len(w) - 1:]
        out[s] = float(ac[l0:l1 + 1].max() / e)
    return out


def passages(rms, flux_low, grid, dur_s):
    """-> per-second labels: 'silence' (v1 quiet passages), 'dropout' (v1 grid dropouts), 'beatless', 'beat', or '' (other / first 10 s)"""
    n = int(dur_s)
    lab = np.array([""] * n, dtype=object)
    per = periodicity(flux_low)[:n]
    sil = np.zeros(n, bool)
    for a, b in R.quiet_passages(rms):
        sil[int(a):int(np.ceil(b))] = True
    drp = np.zeros(n, bool)
    for a, b in R.grid_dropouts(grid):
        drp[int(a):int(np.ceil(b))] = True
    low = (per < BEATLESS_TH) & ~sil
    bl = np.zeros(n, bool)
    i = 0
    while i < n:
        if low[i]:
            j = i
            while j < n and low[j]:
                j += 1
            if j - i >= BEATLESS_MIN_S and i >= START_S:
                bl[i:j] = True
            i = j
        else:
            i += 1
    idx = np.arange(n)
    lab[(idx >= START_S) & (per >= BEAT_TH) & ~sil & ~drp & ~bl] = "beat"
    lab[bl] = "beatless"
    lab[drp & ~sil] = "dropout"
    lab[sil] = "silence"
    return lab, per


def conf_by_passage(conf, lab):
    out = {}
    for t in ("silence", "beatless", "dropout", "beat"):
        sec = np.flatnonzero(lab == t)
        if not len(sec):
            continue
        fr = (sec[:, None] * 100 + np.arange(100)[None]).ravel()
        fr = fr[fr < len(conf)]
        out[t] = dict(seconds=int(len(sec)), median_conf=float(np.median(conf[fr])), share_below_half=float(np.mean(conf[fr] < 0.5)))
    return out


def run_one(a):
    ds, key, wav = a
    dst = OUT / "songs" / f"{key}.json"
    if dst.exists():
        return key, "skip"
    try:
        import fast_features as ff
        import pulse2_lib as P2
        F = ff.fast_features(ff.load_mono(wav))
        r = P2.pulse(F)
        r["f_max"] = P2.P1.f_max()
        sw = np.array([[s[0], s[1], s[2], int(s[3])] for s in r["switches"]], np.int32).reshape(-1, 4)
        np.savez_compressed(OUT / "songs" / f"{key}.npz", period=r["period"].astype(np.float32), rate=r["rate"].astype(np.float32), phase=r["phase"].astype(np.float32),
                            conf=r["conf"].astype(np.float32), freq=r["freq"].astype(np.float32), sel=r["sel"].astype(np.int16), amp=r["amp"].astype(np.float32),
                            prom=r["prom"].astype(np.float32), coh=r["coh"].astype(np.float32), novelty=r["novelty"].astype(np.float32),
                            events=r["events"], event_conf=r["event_conf"].astype(np.float32), boundaries=r["boundaries"], switches=sw, f_max=r["f_max"], rms=F[:, 41])
        lib = R.load_beats(B / "beatv/librosa" / f"{key}.json")
        grid = R.load_beats(R.grid_path(key))
        c = R.check_song(key, r, F[:, 41], lib, grid, R.excerpts().get(key))
        c["dataset"] = ds
        dur_min = len(r["rate"]) / 100 / 60
        c["stability"]["rule_switches"] = len(r["switches"])
        c["stability"]["rule_switches_near_boundary"] = int(sum(s[3] for s in r["switches"]))
        c["stability"]["rule_switches_per_min"] = len(r["switches"]) / dur_min
        c["stability"]["boundaries_per_min"] = len(r["boundaries"]) / dur_min
        lab, per = passages(F[:, 41], F[:, 32], grid, len(r["rate"]) / 100)
        c["confidence"] = dict(median=float(np.median(r["conf"])), by_passage=conf_by_passage(r["conf"], lab))
        c["events"] = [round(float(e), 4) for e in r["events"]]
        c["event_conf"] = [round(float(e), 3) for e in r["event_conf"]]
        tmp = dst.with_suffix(".tmp")
        tmp.write_text(json.dumps(c))
        tmp.replace(dst)
        return key, f"{len(r['events'])} events, {c['whole']['pulse']['tempo_bpm']:.1f} bpm, {len(r['switches'])} switches"
    except Exception as e:  # noqa: BLE001
        with open(OUT / "failed.txt", "a") as f:
            f.write(f"{key}\t{type(e).__name__}: {e}\n{traceback.format_exc()}\n")
        return key, f"FAILED {type(e).__name__}: {e}"


def view_excerpts():
    """the 20 viewing excerpts: (check, song, dataset, start) from the two flash keys, one per song"""
    out = []
    for i, p in enumerate(VIEW_KEYS, 1):
        seen = set()
        for v in json.loads(p.read_text())["items"].values():
            if v["song"] not in seen:
                seen.add(v["song"])
                out.append(dict(check=f"flash{'' if i == 1 else 2}", song=v["song"], dataset=v["dataset"], start_s=float(v["start_s"])))
    return out


def cmd_run(procs=6):
    (OUT / "songs").mkdir(parents=True, exist_ok=True)
    jobs = R.songs()
    first = {s["song"] for s in view_excerpts()}
    jobs.sort(key=lambda j: j[1] not in first)
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (k, msg) in enumerate(pool.imap_unordered(run_one, jobs)):
            if i % 25 == 0 or "FAILED" in msg or k in first:
                print(i, "/", len(jobs), k, msg, flush=True)
    print("PULSE2 RUN DONE", len(jobs), flush=True)


# ---------------- report ----------------
q = R.q
DSS = ("finedance", "aioz", "phantom", "motorica", "all")


def cmd_report():
    v2 = {r["key"]: r for r in (json.loads(p.read_text()) for p in sorted((OUT / "songs").glob("*.json")))}
    v1 = {k: json.loads((V1 / "songs" / f"{k}.json").read_text()) for k in v2}
    keep = [k for k in v2 if v2[k]["duration_s"] >= MIN_SONG_S]
    short = len(v2) - len(keep)
    L = ["# Pulse v2 numeric check tables (WO51, docs/PULSE2_RULES.md section 6)", "",
         f"Songs run: {len(v2)}; in the summaries: {len(keep)} (songs under {MIN_SONG_S:.0f} s left out: {short}). Per-song values: "
         "`/secondary/hyst-data/body/pulse2/songs/<key>.json` (v2), `/secondary/hyst-data/body/pulse/songs/<key>.json` (v1).", ""]
    summ = dict(songs=len(v2), in_summary=len(keep), short_excluded=short)
    # 1 headline
    L += ["## 1. v1 vs v2, all songs (>= 12 s)", "",
          "| dataset | songs | level switches/min q50/q90 v1 | v2 | v2 rule switches/min q50/q90 (near a boundary, share) | share rate within 6 % q50 v1 / v2 | 3:2 share vs librosa v1 / v2 | vs grid v1 / v2 | level 1 vs librosa v1 / v2 | 1/2 + 2 v1 / v2 | pulse BPM q5/50/95 v1 | v2 | longest gap in IOIs q50/q90 v1 | v2 | regularity ms q50 v1 / v2 | quiet kept v1 / v2 | dropouts kept v1 / v2 | folded dev % q50 v1 / v2 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for ds in DSS:
        ks = [k for k in keep if ds == "all" or v2[k]["dataset"] == ds]
        if not ks:
            continue
        g = lambda V, f: [f(V[k]) for k in ks]  # noqa: E731
        lv = lambda V, nm, names: float(np.mean([V[k]["whole"]["level_vs_" + nm]["nearest"] in names for k in ks]))  # noqa: E731
        kept = lambda V, part: (lambda rows: float(np.mean([x["pulse"]["kept"] for x in rows])) if rows else float("nan"))([x for k in ks for x in V[k][part]])  # noqa: E731
        fo = lambda V: [V[k]["following"]["median_abs_fold_pct"] for k in ks if V[k]["following"].get("windows", 0) > 0]  # noqa: E731
        near = sum(v2[k]["stability"]["rule_switches_near_boundary"] for k in ks) / max(sum(v2[k]["stability"]["rule_switches"] for k in ks), 1)
        row = dict(songs=len(ks),
                   jumps_per_min=dict(v1=[float(np.percentile(g(v1, lambda r: r["stability"]["jumps_per_min"]), p)) for p in (50, 90)],
                                      v2=[float(np.percentile(g(v2, lambda r: r["stability"]["jumps_per_min"]), p)) for p in (50, 90)]),
                   rule_switches_per_min_v2=[float(np.percentile(g(v2, lambda r: r["stability"]["rule_switches_per_min"]), p)) for p in (50, 90)],
                   share_near_boundary=near,
                   share_32_lib=dict(v1=lv(v1, "lib", ("2/3", "3/2")), v2=lv(v2, "lib", ("2/3", "3/2"))),
                   share_32_grid=dict(v1=lv(v1, "grid", ("2/3", "3/2")), v2=lv(v2, "grid", ("2/3", "3/2"))),
                   level_dist_lib=dict(v1={n: lv(v1, "lib", (n,)) for n in R.RATIO_NAMES}, v2={n: lv(v2, "lib", (n,)) for n in R.RATIO_NAMES}),
                   quiet_kept=dict(v1=kept(v1, "quiet"), v2=kept(v2, "quiet")), dropout_kept=dict(v1=kept(v1, "dropouts"), v2=kept(v2, "dropouts")))
        summ.setdefault(ds, {})["headline"] = row
        L.append(f"| {ds} | {len(ks)} | {q(g(v1, lambda r: r['stability']['jumps_per_min']), (50, 90), 2)} | {q(g(v2, lambda r: r['stability']['jumps_per_min']), (50, 90), 2)} | "
                 f"{q(g(v2, lambda r: r['stability']['rule_switches_per_min']), (50, 90), 2)} ({near:.2f}) | "
                 f"{q(g(v1, lambda r: r['stability']['share_within_6pct']), (50,), 2)} / {q(g(v2, lambda r: r['stability']['share_within_6pct']), (50,), 2)} | "
                 f"{row['share_32_lib']['v1']:.3f} / {row['share_32_lib']['v2']:.3f} | {row['share_32_grid']['v1']:.3f} / {row['share_32_grid']['v2']:.3f} | "
                 f"{lv(v1, 'lib', ('1',)):.3f} / {lv(v2, 'lib', ('1',)):.3f} | {lv(v1, 'lib', ('1/2', '2')):.3f} / {lv(v2, 'lib', ('1/2', '2')):.3f} | "
                 f"{q(g(v1, lambda r: r['whole']['pulse']['median_rate_bpm']), (5, 50, 95))} | {q(g(v2, lambda r: r['whole']['pulse']['median_rate_bpm']), (5, 50, 95))} | "
                 f"{q(g(v1, lambda r: r['whole']['pulse']['longest_gap_ioi']), (50, 90), 2)} | {q(g(v2, lambda r: r['whole']['pulse']['longest_gap_ioi']), (50, 90), 2)} | "
                 f"{q(g(v1, lambda r: r['whole']['pulse']['regularity_ms']), (50,))} / {q(g(v2, lambda r: r['whole']['pulse']['regularity_ms']), (50,))} | "
                 f"{row['quiet_kept']['v1']:.3f} / {row['quiet_kept']['v2']:.3f} | {row['dropout_kept']['v1']:.3f} / {row['dropout_kept']['v2']:.3f} | "
                 f"{q(fo(v1), (50,), 1)} / {q(fo(v2), (50,), 1)} |")
    L += ["", "## 2. Level against librosa, all songs (>= 12 s), share of songs (v1 / v2)", "", "| " + " | ".join(R.RATIO_NAMES) + " |", "|" + "---|" * len(R.RATIO_NAMES)]
    ld = summ["all"]["headline"]["level_dist_lib"]
    L.append("| " + " | ".join(f"{ld['v1'][n]:.3f} / {ld['v2'][n]:.3f}" for n in R.RATIO_NAMES) + " |")
    # 3 confidence by passage
    L += ["", "## 3. Confidence by passage type (v2; per song median over the passage's frames)", "",
          "| dataset | type | songs | seconds | median over songs | q25 / q75 over songs | share of frames below 0.5 (median over songs) | paired: beat minus type, median over songs |",
          "|---|---|---|---|---|---|---|---|"]
    for ds in DSS:
        ks = [k for k in keep if ds == "all" or v2[k]["dataset"] == ds]
        for t in ("beat", "silence", "beatless", "dropout"):
            rows = [(k, v2[k]["confidence"]["by_passage"][t]) for k in ks if t in v2[k]["confidence"]["by_passage"]]
            if not rows:
                continue
            m = [x["median_conf"] for _, x in rows]
            pair = [v2[k]["confidence"]["by_passage"]["beat"]["median_conf"] - x["median_conf"] for k, x in rows if "beat" in v2[k]["confidence"]["by_passage"]] if t != "beat" else []
            summ.setdefault(ds, {}).setdefault("confidence", {})[t] = dict(songs=len(rows), seconds=int(sum(x["seconds"] for _, x in rows)), median=float(np.median(m)),
                                                                            paired_beat_minus=float(np.median(pair)) if pair else None)
            L.append(f"| {ds} | {t} | {len(rows)} | {sum(x['seconds'] for _, x in rows)} | {np.median(m):.3f} | {q(m, (25, 75), 3)} | "
                     f"{np.median([x['share_below_half'] for _, x in rows]):.3f} | {('%.3f (%d songs)' % (np.median(pair), len(pair))) if pair else 'n/a'} |")
    # 4 the 20 viewing excerpts
    L += ["", "## 4. The 20 viewing excerpts (30 s; tempo from events inside the window)", "",
          "| check | song | start s | librosa BPM | v1 BPM | v1/lib (level) | v2 BPM | v2/lib (level) | v2 median confidence | v2 rule switches in excerpt |", "|---|---|---|---|---|---|---|---|---|---|"]
    ex_rows = []
    for e in view_excerpts():
        k, lo = e["song"], e["start_s"]
        hi = lo + R.EX_LEN
        lib = R.load_beats(B / "beatv/librosa" / f"{k}.json")
        lt = R.series_stats(lib, lo, hi)["tempo_bpm"]
        t1 = R.series_stats(np.array(v1[k]["events"]), lo, hi)["tempo_bpm"]
        t2 = R.series_stats(np.array(v2[k]["events"]), lo, hi)["tempo_bpm"]
        z = np.load(OUT / "songs" / f"{k}.npz")
        mc = float(np.median(z["conf"][int(lo * 100):int(hi * 100)]))
        nsw = int(np.sum((z["switches"][:, 0] >= lo * 100) & (z["switches"][:, 0] < hi * 100))) if len(z["switches"]) else 0
        row = dict(e, lib_bpm=lt, v1_bpm=t1, v2_bpm=t2, v1_ratio=t1 / lt, v2_ratio=t2 / lt, v1_level=R.level(t1 / lt)[0], v2_level=R.level(t2 / lt)[0], v2_median_conf=mc, v2_switches=nsw)
        ex_rows.append(row)
        L.append(f"| {e['check']} | {k[:26]} | {lo:.0f} | {lt:.1f} | {t1:.1f} | {t1 / lt:.3f} ({row['v1_level']}) | {t2:.1f} | {t2 / lt:.3f} ({row['v2_level']}) | {mc:.2f} | {nsw} |")
    summ["view_excerpts"] = ex_rows
    failed = (OUT / "failed.txt").read_text().count("\n\n") if (OUT / "failed.txt").exists() else 0
    L += ["", f"Failed songs: {failed} (`pulse2/failed.txt`)."]
    (HERE.parent.parent / "docs/PULSE2_TABLES.md").write_text("\n".join(L) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summ, indent=1))
    print("REPORT DONE", len(v2), flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"run": cmd_run, "report": cmd_report}[a[0]](*[int(x) for x in a[1:]])
