#!/usr/bin/env python3
"""B1 checks: gates 1-3 of docs/BRAIN_SPEC.md 2.2 in one script. Writes results.json and check_b1.log to the output directory.

  python check_b1.py [--sets ballroom,gtzan] [--out /secondary/hyst-data/brain/b1] [--workers 8] [--limit N] [--no-analyze]

THIS SCRIPT IS COMMITTED BEFORE IT IS EVER RUN ON REAL DATA. The pass rules are in scoring.py's docstring (committed with it).
Only tests/test_check_b1 run it, on synthetic clips. Each clip is cached under OUT/cache so an interrupted run resumes; delete the
cache to recompute. Per clip:
  B1 pulse        fast features -> Hopf bank -> beats, readout amplitude and frequency, meter ratio
  PLL baseline    hyst-audio's BeatTracker through crates/hyst-audio/examples/beat_pll.rs (raw times; centred times also kept)
  offline grid    scripts/analyze.py beats in /secondary/hyst-env/analyze-py (upper reference, reported only)
  gaps            for each gap length (2, 4, 8 s) and kind (silence, noise): the clip with the gap, B1 and PLL again
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from multiprocessing import Pool

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fast_features as ff  # noqa: E402
import gaps  # noqa: E402
import grfnn  # noqa: E402
import scoring  # noqa: E402
import testsets  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PLL_BIN = os.path.join(REPO, "target", "release", "examples", "beat_pll")
ANALYZE = os.path.join(REPO, "scripts", "analyze.py")
ANALYZE_PY = "/secondary/hyst-env/analyze-py/bin/python"
DEFAULT_OUT = "/secondary/hyst-data/brain/b1"
CHUNK = 24


# ----------------------------------------------------------------------------------------------- per clip

def b1_run(y):
    """Audio -> B1 outputs and the features (for the onset rule)."""
    f = ff.fast_features(y)
    p = grfnn.pulse(f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET])
    return f, p


def meter_numbers(p, ann_beats):
    """f_b (median readout frequency from 5 s), the meter ratio at f_b and at the annotated tempo, the annotated tempo."""
    f_b = float(np.median(p["readout_freq"][500:]))
    ann = scoring.tempo_hz(ann_beats[ann_beats >= scoring.TRIM_S]) if (ann_beats >= scoring.TRIM_S).sum() >= 2 else float("nan")
    out = {"f_b": f_b, "ratio_b1": scoring.meter_ratio(p["freqs"], p["amp"], f_b), "f_ann": ann}
    out["ratio_ann"] = scoring.meter_ratio(p["freqs"], p["amp"], ann) if np.isfinite(ann) else float("nan")
    return out


def write_wav(path, y):
    sf.write(path, np.clip(y, -1.0, 1.0), ff.SR, subtype="PCM_16")


def clip_job(args):
    """One clip: original + gap variants through B1. Writes the wavs the PLL and the offline grid need into tmp."""
    clip, tmp, do_gaps = args
    cid = clip["id"]
    safe = cid.replace("/", "__")
    try:
        y = ff.load_mono(clip["audio"])
    except Exception as e:  # undecodable file: reported, not scored
        return {"id": cid, "error": f"decode: {str(e)[:80]}"}
    _, p0 = b1_run(y)
    out = {"id": cid, "set": clip["set"], "style": clip["style"], "duration": len(y) / ff.SR,
           "b1": {"beats": p0["beats"].tolist()}, "meter": meter_numbers(p0, np.asarray(clip["beats"])),
           "wav": {"orig": os.path.join(tmp, f"{safe}.wav")}, "gaps": []}
    write_wav(out["wav"]["orig"], y)
    if do_gaps:
        for g in gaps.GAPS:
            for kind in gaps.KINDS:
                t0 = gaps.gap_start(cid, g, kind, len(y) / ff.SR)
                if t0 is None:
                    continue
                yg = gaps.make_gap(y, ff.SR, t0, g, kind, clip_id=cid)
                fg, pg = b1_run(yg)
                valid, stat, thr = gaps.gap_valid(pg["input"], t0, g, cid, kind)
                k0 = int(pg["readout_index"][int(round(t0 * 100)) - 1])           # the readout oscillator just before the gap
                path = os.path.join(tmp, f"{safe}.{g:g}.{kind}.wav")
                write_wav(path, yg)
                out["gaps"].append({"gap": g, "kind": kind, "start": t0, "valid": bool(valid), "stat": stat, "threshold": thr,
                                    "beats": pg["beats"].tolist(), "amp_ratio": scoring.amplitude_ratio(pg["amp"], k0, t0, t0 + g),
                                    "switches": scoring.readout_switches(pg["readout_index"], t0, t0 + g),
                                    "wav": path})
    return out


def run_pll(wavs, workers):
    """beat_pll over a list of wavs (batches in parallel); {path: {beats, beats_centred, tempo_bpm}}."""
    batches = [wavs[i::workers] for i in range(workers) if wavs[i::workers]]
    res = {}
    procs = [subprocess.Popen([PLL_BIN] + b, stdout=subprocess.PIPE, text=True) for b in batches]
    for pr in procs:
        for line in pr.stdout:
            d = json.loads(line)
            res[d["path"]] = d
        if pr.wait() != 0:
            raise RuntimeError("beat_pll failed")
    return res


def regular_grid(beats, duration):
    """The dance_memory regularised grid (constant period and phase fitted to analyze.py's beats), as beat times."""
    sys.path.insert(0, os.path.join(REPO, "scripts"))
    import dance_memory
    try:
        period, phase, _ = dance_memory.regularize_beats(beats, duration)
    except ValueError:                      # fewer than five usable beats
        return None
    return np.arange(phase % period, duration, period).tolist()


def run_analyze(path):
    """scripts/analyze.py beats of one wav (the offline analysis, upper reference)."""
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "s.json")
        subprocess.run([ANALYZE_PY, ANALYZE, path, out], check=True, capture_output=True)
        return json.load(open(out))["beats"]


# ------------------------------------------------------------------------------------- missing pulse (reported)

def missing_pulse_report():
    """Large 2015 section 4 stimulus (reported only): 8 events over 8 pulse cycles at 2 Hz; complexity level L puts L events
    half a cycle off the pulse (anti-phase). Which events move is a fixed seed (the paper's figure 6 patterns are not in the text).
    Reports the bank's amplitude at the pulse frequency against its strongest oscillator in 0.5-4 Hz, and the stimulus spectrum at the pulse."""
    from scipy.ndimage import gaussian_filter1d
    rng = np.random.default_rng(20261032)
    rows = []
    for level, n_patterns in ((0, 1), (1, 2), (2, 2), (3, 2), (4, 4)):
        for k in range(n_patterns):
            moved = set(rng.choice(8, size=level, replace=False).tolist())
            period, reps = 0.5, 10
            x = np.zeros(int(8 * period * reps * 100) + 100)
            for r in range(reps):
                for e in range(8):
                    t = (r * 8 + e) * period + (0.25 if e in moved else 0.0) + 0.25
                    x[int(round(t * 100))] = 1.0
            x = gaussian_filter1d(x, 3.0)
            x = 4.0 * x / x.max()
            p = grfnn.pulse(x, x)
            f, a = p["freqs"], p["amp"][1000:].mean(axis=0)
            band = (f >= 0.5) & (f <= 4.0)
            spec = np.abs(np.fft.rfft(x - x.mean())) / len(x)
            sf_ = np.fft.rfftfreq(len(x), 0.01)
            rows.append({"level": level, "moved": sorted(moved), "bank_amp_at_2hz": float(a[np.argmin(abs(f - 2.0))]),
                         "bank_peak_hz": float(f[band][np.argmax(a[band])]), "bank_peak_amp": float(a[band].max()),
                         "stimulus_amp_at_2hz": float(spec[np.argmin(abs(sf_ - 2.0))])})
    return rows


# ----------------------------------------------------------------------------------------------- the check

def column(rows, key):
    return np.array([r[key] for r in rows], float)


def run(clips, out_dir, workers=8, do_analyze=True, do_gaps=True, log=print):
    t_start = time.time()
    os.makedirs(os.path.join(out_dir, "cache"), exist_ok=True)
    results, skipped = [], []
    todo = []
    for c in clips:
        cache = os.path.join(out_dir, "cache", c["id"].replace("/", "__") + ".json")
        if os.path.exists(cache):
            results.append(json.load(open(cache)))
        else:
            todo.append((c, cache))
    log(f"{len(clips)} clips, {len(results)} cached, {len(todo)} to run, workers {workers}")
    for i in range(0, len(todo), CHUNK):
        batch = todo[i:i + CHUNK]
        tmp = tempfile.mkdtemp(prefix="b1_", dir=os.path.join(out_dir, "cache"))
        try:
            with Pool(workers) as pool:
                outs = pool.map(clip_job, [(c, tmp, do_gaps) for c, _ in batch], chunksize=1)
            good = [o for o in outs if "error" not in o]
            wavs = [o["wav"]["orig"] for o in good] + [g["wav"] for o in good for g in o["gaps"]]
            pll = run_pll(wavs, workers) if wavs else {}
            analyzed = {}
            if do_analyze and good:
                with Pool(workers) as pool:
                    for o, b in zip(good, pool.map(run_analyze, [o["wav"]["orig"] for o in good])):
                        analyzed[o["id"]] = b
            for (c, cache), o in zip(batch, outs):
                if "error" in o:
                    skipped.append(o)
                    json.dump(o, open(cache, "w"))
                    continue
                p = pll[o["wav"]["orig"]]
                o["pll"] = {"beats": p["beats"], "beats_centred": p["beats_centred"], "tempo_bpm": p["tempo_bpm"]}
                o["offline"] = analyzed.get(o["id"])
                o["offline_grid"] = regular_grid(o["offline"], o["duration"]) if o["offline"] else None
                o["ref"] = np.asarray(c["beats"]).tolist()
                for g in o["gaps"]:
                    q = pll[g["wav"]]
                    g["pll"] = q["beats"]
                    g["pll_centred"] = q["beats_centred"]
                    del g["wav"]
                del o["wav"]
                json.dump(o, open(cache, "w"))
                results.append(o)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        log(f"  {min(i + CHUNK, len(todo))}/{len(todo)} clips done, {time.time() - t_start:.0f} s")
    errors = {r["id"]: r for r in results + skipped if "error" in r}     # undecodable files, cached or new: reported, not scored
    results = [r for r in results if "error" not in r]
    return summarise(results, list(errors.values()), clips, t_start)


ALPHA_NOTE = ("With alpha = 0 (critical) the amplitude decays without input; with alpha > 0 the bank would sustain itself and "
              "criterion 3 would pass trivially, so the amplitude result reflects the published alpha.")


def summarise(results, skipped, clips, t_start):
    results = sorted(results, key=lambda r: r["id"])
    sets = sorted({r["set"] for r in results})
    out = {"meta": {"seeds": {"gaps": gaps.SEED, "bootstrap": scoring.BOOT_SEED, "permutation": scoring.PERM_SEED},
                    "clips": {s: sum(r["set"] == s for r in results) for s in sets}, "skipped": [s["id"] + ": " + s["error"] for s in skipped],
                    "smc": "not obtained (see /secondary/hyst-data/brain/testsets/SOURCES.md)"},
           "notes": {"alpha": ALPHA_NOTE,
                     "pll": "The PLL baseline of each gate is whichever of its raw and centred beat times scores higher on that gate's metric; both are reported."}}
    # ---- gate 1 and the reported metrics, per set; PLL = the better of raw and centred per set and metric
    g1_b1, g1_pll, variant, reported = {}, {}, {}, {}
    for s in sets:
        rows = [r for r in results if r["set"] == s]
        m_b1 = [scoring.beat_metrics(r["ref"], r["b1"]["beats"]) for r in rows]
        m_raw = [scoring.beat_metrics(r["ref"], r["pll"]["beats"]) for r in rows]
        m_cen = [scoring.beat_metrics(r["ref"], r["pll"]["beats_centred"]) for r in rows]
        g1_b1[s] = {k: column(m_b1, k) for k in ("f", "cmlt", "amlt")}
        raw = {k: column(m_raw, k) for k in ("f", "cmlt", "amlt")}
        cen = {k: column(m_cen, k) for k in ("f", "cmlt", "amlt")}
        g1_pll[s], variant[s] = {}, {}
        for k in ("f", "cmlt", "amlt"):
            variant[s][k] = "centred" if cen[k].mean() > raw[k].mean() else "raw"
            g1_pll[s][k] = cen[k] if variant[s][k] == "centred" else raw[k]
        reported[s] = {name: {"f": float(np.mean(column(m, "f"))), "cmlt": float(np.mean(column(m, "cmlt"))), "amlt": float(np.mean(column(m, "amlt"))),
                              "tempo_error_median": float(np.nanmedian(column(m, "tempo_error"))),
                              "tempo_error_mean": float(np.nanmean(column(m, "tempo_error"))),
                              "phase_ms_median": float(np.median(np.minimum(column(m, "phase_ms"), scoring.PHASE_CAP_MS)))}
                       for name, m in (("b1", m_b1), ("pll_raw", m_raw), ("pll_centred", m_cen))}
        for name, key in (("offline_analyze", "offline"), ("offline_regularised_grid", "offline_grid")):
            have = [r for r in rows if r.get(key)]
            if have:
                m = [scoring.beat_metrics(r["ref"], r[key]) for r in have]
                reported[s][name] = {"clips": len(have), "f": float(np.mean(column(m, "f"))), "cmlt": float(np.mean(column(m, "cmlt"))),
                                     "amlt": float(np.mean(column(m, "amlt")))}
    out["gate1"] = scoring.gate1(g1_b1, g1_pll)
    for key, row in out["gate1"]["rows"].items():
        set_, metric = key.split(".")
        row["pll_variant"] = variant[set_][metric]
    out["gate1_reported"] = {"metrics": reported, "pll_variant_per_set_and_metric": variant,
                             "superiority_vs_best_pll": {f"{s}.{k}": float(np.mean(g1_b1[s][k] - g1_pll[s][k])) for s in sets for k in ("f", "amlt")}}
    # ---- gate 2: verification, exclusions, switches, then the criteria
    g2, excluded, switches, rejected = {}, {}, {}, []
    for g in gaps.GAPS:
        g2[f"{g:g}s"], excluded[f"{g:g}s"], switches[f"{g:g}s"] = {}, {}, {}
        for kind in gaps.KINDS:
            e_b1, e_raw, e_cen, ratios, n_all, sw = [], [], [], [], 0, []
            for r in results:
                for v in r["gaps"]:
                    if v["gap"] != g or v["kind"] != kind:
                        continue
                    n_all += 1
                    if not v["valid"]:
                        rejected.append(f"{r['id']} {g:g}s {kind}: statistic {v['stat']:.3f} > threshold {v['threshold']:.3f}")
                        continue
                    end = v["start"] + g
                    e_b1.append(scoring.gap_end_error_ms(r["ref"], v["beats"], end))
                    e_raw.append(scoring.gap_end_error_ms(r["ref"], v["pll"], end))
                    e_cen.append(scoring.gap_end_error_ms(r["ref"], v["pll_centred"], end))
                    ratios.append(v["amp_ratio"])
                    sw.append(v["switches"])
            excluded[f"{g:g}s"][kind] = {"gaps": n_all, "excluded": n_all - len(e_b1), "rate": (n_all - len(e_b1)) / n_all if n_all else float("nan")}
            switches[f"{g:g}s"][kind] = {"gaps": len(sw), "mean": float(np.mean(sw)) if sw else float("nan"),
                                         "share_with_a_switch": float(np.mean(np.array(sw) > 0)) if sw else float("nan")}
            if e_b1:
                raw, cen = scoring.gate2(e_b1, e_raw, ratios), scoring.gate2(e_b1, e_cen, ratios)
                best = cen if cen["median_pll_ms"] < raw["median_pll_ms"] else raw
                res = dict(best)
                res["pll_variant"] = "centred" if best is cen else "raw"
                res["raw"], res["centred"] = raw, cen
                g2[f"{g:g}s"][kind] = res
    out["gate2"] = g2
    out["gate2_exclusions"] = excluded
    out["gate2_readout_switches"] = switches
    out["gate2_excluded_gaps"] = rejected
    four = [g2.get("4s", {}).get(k) for k in gaps.KINDS]
    out["gate2_pass"] = bool(all(x is not None and x["pass"] for x in four))
    # ---- gate 3 (Ballroom)
    bal = [r for r in results if r["set"] == "ballroom"]
    if bal:
        triple = np.array([r["style"] in testsets.TRIPLE_STYLES for r in bal])
        ratio_b1 = column([r["meter"] for r in bal], "ratio_b1")
        out["gate3"] = scoring.gate3(ratio_b1, triple)
        ok = np.isfinite(column([r["meter"] for r in bal], "ratio_ann"))
        out["gate3_reported"] = {"annotated_tempo": scoring.gate3(column([r["meter"] for r in bal], "ratio_ann")[ok], triple[ok]),
                                 "half_double": scoring.half_or_double_share(column([r["meter"] for r in bal], "f_b")[ok],
                                                                             column([r["meter"] for r in bal], "f_ann")[ok]),
                                 "mean_ratio_triple": float(np.mean(ratio_b1[triple])), "mean_ratio_duple": float(np.mean(ratio_b1[~triple]))}
    out["missing_pulse"] = missing_pulse_report()
    out["pass"] = bool(out["gate1"]["pass"] and out["gate2_pass"] and out.get("gate3", {}).get("pass", False))
    out["meta"]["seconds"] = round(time.time() - t_start, 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="ballroom,gtzan")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0, help="first N clips of each set (smoke runs only)")
    ap.add_argument("--no-analyze", action="store_true")
    ap.add_argument("--no-gaps", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    logf = open(os.path.join(a.out, "check_b1.log"), "a")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    if not os.path.exists(PLL_BIN):
        subprocess.run(["cargo", "build", "--release", "-p", "hyst-audio", "--example", "beat_pll"], cwd=REPO, check=True)
    clips = []
    for s in a.sets.split(","):
        c = {"ballroom": testsets.ballroom_clips, "gtzan": testsets.gtzan_clips}[s]()
        clips += c[:a.limit] if a.limit else c
    if testsets.verify_lists():
        log("hash lists do not match the files on disk: stop")
        sys.exit(1)
    result = run(clips, a.out, a.workers, not a.no_analyze, not a.no_gaps, log)
    json.dump(result, open(os.path.join(a.out, "results.json"), "w"), indent=1)
    log(result["notes"]["alpha"])
    log(f"gate1 {result['gate1']['pass']}  gate2 {result['gate2_pass']}  gate3 {result.get('gate3', {}).get('pass')}  overall {result['pass']}  ({result['meta']['seconds']} s)")


if __name__ == "__main__":
    main()
