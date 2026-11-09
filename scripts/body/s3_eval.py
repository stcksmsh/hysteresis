"""Stage 3 bar evaluation (work order 26A; docs/STAGE3_RULES_DATA_EVAL.md section 4; BRAIN_SPEC 7.39.4). Brain env (numpy, scipy, sklearn, librosa). Imports s0_measure / hf_share / arm_sim, edits nothing. One arm.

    s3_eval.py --policy best.pkl --out DIR [--rollouts DIR] [--check-dir DIR] [--ref-bars pass2/bars.json] [--body-python PY]
Missing parts are produced by the existing scripts in the BODY env (`--body-python`, default /secondary/hyst-env/body/bin/python, 6 threads, taskset 6-11 by the caller):
    rollouts of the 357 check songs   s0_roll.py --policy P --out ROLLOUTS      (skipped if ROLLOUTS holds all 357 npz)
    (a) and (f) parts                 k5p2_eval.py check / songs --policy P --out CHECK_DIR   (skipped if CHECK_DIR/check.json and CHECK_DIR/songs/*.json exist; then `summary` too)
Writes OUT/bars.json: every bar's value and pass/fail, the per-joint limit report, report-only lines.
"""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hf_share  # noqa: E402
import s0_measure as S  # noqa: E402

K5 = Path("/secondary/hyst-data/body/k5")
S3 = Path("/secondary/hyst-data/body/s3")
CORPUS = Path("/secondary/hyst-data/brain/corpus")
HZ = 50
CLIP_ROWS = S.CLIP_S * HZ          # 30 s
STRIDE_ROWS = 2 * CLIP_ROWS        # 30 s clip + 30 s gap
CELLS_SECONDS = 120
BARS = {"b": 0.75, "c": 2.0, "d": 1.5, "e_share": 0.70, "e_deg": 8.0}


# ---------------------------------------------------------------------------------------------------------------- clips
def interleaved_clips(q):
    """Clips of 30 s starting at 0, 60, 120, ... s (a 30 s gap between consecutive clips), wholly inside the song -> (train = 1st, 3rd, ..., test = 2nd, 4th, ...)."""
    cl = [q[s:s + CLIP_ROWS] for s in range(0, len(q) - CLIP_ROWS + 1, STRIDE_ROWS)]
    return cl[0::2], cl[1::2]


def pair_2afc_interleaved(qa, qb, rng=None, n_shuffle=0, min_clips=2):
    """s0_measure.pair_2afc with the interleaved split (7.36.3). -> dict(acc, shuffled) or None."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    (a0, a1), (b0, b1) = interleaved_clips(qa), interleaved_clips(qb)
    if min(len(a0), len(a1), len(b0), len(b1)) < min_clips:
        return None
    n0, n1 = min(len(a0), len(b0)), min(len(a1), len(b1))
    tr, te = a0[:n0] + b0[:n0], a1[:n1] + b1[:n1]
    ytr = np.r_[np.zeros(n0), np.ones(n0)]
    yte = np.r_[np.zeros(n1), np.ones(n1)]
    vocab = sorted({tuple(k) for c in tr for k in S.cells(S.hand(c), S.CELL_CLIP).tolist()})
    Xtr = np.stack([S.clip_features(c, vocab) for c in tr])
    Xte = np.stack([S.clip_features(c, vocab) for c in te])
    sc = StandardScaler().fit(Xtr)
    Xtr, Xte = sc.transform(Xtr), sc.transform(Xte)

    def acc(y):
        return float((LogisticRegression(C=1.0, max_iter=2000).fit(Xtr, y).predict(Xte) == yte).mean())

    return {"acc": acc(ytr), "shuffled": [acc(rng.permutation(ytr)) for _ in range(n_shuffle)]}


def bar_b(Q, pairs, n_shuffle=5, seed=0):
    rng = np.random.default_rng(seed)
    accs, shuf = [], []
    for a, b, *_ in pairs:
        r = pair_2afc_interleaved(Q[a], Q[b], rng, n_shuffle)
        if r:
            accs.append(r["acc"])
            shuf.append(float(np.mean(r["shuffled"])) if r["shuffled"] else np.nan)
    if not accs:
        return {"n_pairs": 0, "pass": None}
    out = S.boot_mean(accs, seed=seed)
    out["n_pairs"] = len(accs)
    out["shuffled_control"] = S.boot_mean([s for s in shuf if s == s], seed=seed) if n_shuffle else None
    out["bar"], out["pass"] = BARS["b"], bool(out["mean"] >= BARS["b"])
    return out


def share_dict(q_list, size=S.CELL):
    h = np.concatenate([S.hand(c) for c in q_list])
    u, n = np.unique(S.cells(h, size), axis=0, return_counts=True)
    return {tuple(k): v / len(h) for k, v in zip(u.tolist(), n)}


def bar_c(Q):
    ids = sorted(Q)
    D = {s: S.cell_dist(Q[s]) for s in ids}
    between = S.js_between(D, ids)
    within = []
    for s in ids:
        tr, te = interleaved_clips(Q[s])
        if tr and te:
            within.append(S.js_dist(share_dict(tr), share_dict(te)))
    mb, mw = float(np.median(between)), float(np.median(within)) if within else None
    ratio = mb / mw if mw else None
    return {"between_median": mb, "within_median": mw, "ratio": ratio, "n_pairs": int(len(between)), "n_within_songs": len(within), "bar": BARS["c"], "pass": None if ratio is None else bool(ratio >= BARS["c"])}


def bar_d(Q, ref_median=None):
    n = CELLS_SECONDS * HZ
    cnt = {s: len(S.cell_dist(q[:n])) for s, q in Q.items() if len(q) >= n}
    med = float(np.median(list(cnt.values()))) if cnt else None
    out = {"median_cells_120s": med, "n_songs": len(cnt), "mean": float(np.mean(list(cnt.values()))) if cnt else None, "reference_median": ref_median, "bar_factor": BARS["d"]}
    out["ratio_to_reference"] = med / ref_median if (ref_median and med is not None) else None
    out["pass"] = None if out["ratio_to_reference"] is None else bool(out["ratio_to_reference"] >= BARS["d"])
    return out


def bar_e(Q):
    sd = {s: float(np.std(q[:, 1])) for s, q in Q.items()}
    share = float(np.mean([v >= BARS["e_deg"] for v in sd.values()]))
    return {"share_ge_8deg": share, "median_sd_deg": float(np.median(list(sd.values()))), "mean_sd_deg": float(np.mean(list(sd.values()))), "n_songs": len(sd), "bar": BARS["e_share"], "pass": bool(share >= BARS["e_share"])}


# ---------------------------------------------------------------------------------------------------------------- limit report
def limit_report(q, hz=HZ):
    """q (n, 5) deg at hz -> per joint p99 and max of |speed| (deg/s) and |acceleration| (deg/s^2) by central differences (np.gradient), and as a share of arm_sim.LIM_V / LIM_A. Flags, not failures."""
    import arm_sim
    v = np.gradient(q, axis=0) * hz
    a = np.gradient(v, axis=0) * hz
    out = {}
    for j, nm in enumerate(("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")):
        sv, sa = np.abs(v[:, j]), np.abs(a[:, j])
        out[nm] = {"speed_p99": float(np.percentile(sv, 99)), "speed_max": float(sv.max()), "speed_limit": float(arm_sim.LIM_V[j]), "speed_max_over_limit": float(sv.max() / arm_sim.LIM_V[j]),
                   "speed_p99_over_limit": float(np.percentile(sv, 99) / arm_sim.LIM_V[j]),
                   "acc_p99": float(np.percentile(sa, 99)), "acc_max": float(sa.max()), "acc_limit": float(arm_sim.LIM_A[j]), "acc_max_over_limit": float(sa.max() / arm_sim.LIM_A[j]),
                   "acc_p99_over_limit": float(np.percentile(sa, 99) / arm_sim.LIM_A[j]),
                   "flag_speed": bool(sv.max() > arm_sim.LIM_V[j]), "flag_acc": bool(sa.max() > arm_sim.LIM_A[j])}
    return out


# ---------------------------------------------------------------------------------------------------------------- report-only
def program_usage(P):
    cnt = np.zeros(8)
    for p in P.values():
        cnt += np.bincount(np.asarray(p, int), minlength=8)[:8]
    pr = cnt / cnt.sum()
    return {"counts": cnt.tolist(), "used": int((cnt > 0).sum()), "top_share": float(pr.max()), "entropy_bits": float(-(pr[pr > 0] * np.log2(pr[pr > 0])).sum())}


def low_band_flux(song):
    """Audio low-band flux (rules amendment 2026-11-09): librosa STFT of the mono 22,050 Hz audio (n_fft 2048, hop 512), magnitude in the 50-200 Hz bins, half-wave-rectified frame-to-frame difference summed over the bins, mean over frames."""
    import librosa
    y, sr = librosa.load(CORPUS / "audio" / f"{song}.mp3", sr=22050, mono=True)
    m = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    f = librosa.fft_frequencies(sr=sr, n_fft=2048)
    band = m[(f >= 50) & (f <= 200)]
    return float(np.maximum(np.diff(band, axis=1), 0).sum(0).mean())


def burger(Q, flux_cache):
    ids = sorted(Q)
    pulse = {}
    for s in ids:
        y = np.load(K5 / "lanes" / "check" / f"{s}.npz")["y"]
        pulse[s] = float((y[:, 2] ** 2 + y[:, 3] ** 2).mean())
    fx = {}
    cache = json.loads(flux_cache.read_text()) if flux_cache.exists() else {}
    for s in ids:
        if s not in cache:
            cache[s] = low_band_flux(s)
        fx[s] = cache[s]
    flux_cache.write_text(json.dumps(cache))
    sh = [float(np.std(Q[s][:, 1])) for s in ids]
    wb = [float(np.std(Q[s][:, 3])) for s in ids]
    r1 = spearmanr(sh, [pulse[s] for s in ids])
    r2 = spearmanr(wb, [fx[s] for s in ids])
    return {"shoulder_sd_vs_pulse_clarity_B7_proxy": {"spearman": float(r1.statistic), "p": float(r1.pvalue), "n": len(ids)},
            "wrist_bend_sd_vs_audio_low_band_flux": {"spearman": float(r2.statistic), "p": float(r2.pvalue), "n": len(ids)}}


# ---------------------------------------------------------------------------------------------------------------- inputs
def load_rollouts(d, ids):
    Q, P = {}, {}
    for s in ids:
        f = Path(d) / f"{s}.npz"
        if f.exists():
            z = np.load(f)
            Q[s], P[s] = z["rows50"].astype(float), z["prog"]
    return Q, P


def run_body(py, args, log):
    log("running: " + " ".join(args))
    subprocess.run([py, "-u", *args], check=True, cwd=HERE, env={**__import__("os").environ, "JAX_PLATFORMS": "cpu"})


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rollouts", help="dir of <id>.npz (rows50, prog); default OUT/rollouts")
    ap.add_argument("--check-dir", help="k5p2_eval out dir (check.json, songs/); default OUT/check")
    ap.add_argument("--ref-bars", help="the pass2 reference bars.json (for bar (d)); absent = this run is the reference")
    ap.add_argument("--body-python", default="/secondary/hyst-env/body/bin/python")
    ap.add_argument("--max-songs", type=int, help="test only")
    a = ap.parse_args()
    log = lambda s: print(s, flush=True)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    roll = Path(a.rollouts) if a.rollouts else out / "rollouts"
    chk = Path(a.check_dir) if a.check_dir else out / "check"
    ids = json.loads((K5 / "splits.json").read_text())["check"]["ids"]
    ids = ids[:a.max_songs] if a.max_songs else ids
    if not all((roll / f"{s}.npz").exists() for s in ids):
        run_body(a.body_python, ["s0_roll.py", "--policy", a.policy, "--out", str(roll)] + (["--songs", ",".join(ids)] if a.max_songs else []), log)
    if not (chk / "check.json").exists() and not a.max_songs:
        run_body(a.body_python, ["k5p2_eval.py", "check", "--policy", a.policy, "--out", str(chk)], log)
    if not list((chk / "songs").glob("*.json")) and not a.max_songs:
        run_body(a.body_python, ["k5p2_eval.py", "songs", "--policy", a.policy, "--out", str(chk)], log)
    if not (chk / "summary.json").exists() and (chk / "check.json").exists():
        run_body(a.body_python, ["k5p2_eval.py", "summary", "--out", str(chk)], log)
    Q, P = load_rollouts(roll, ids)
    art = {f"{int(r['id']):06d}": r["artist_id"] for r in csv.DictReader(open(CORPUS / "final_corpus.csv"))}
    tr_file = S3 / "tempo_rms.json"
    if tr_file.exists():
        tempo = {s: v["bpm"] for s, v in json.loads(tr_file.read_text()).items()}
        tsrc = str(tr_file)
    else:
        tempo = json.loads(Path("/secondary/hyst-data/body/s0/tempo.json").read_text())["tempo"]
        tsrc = "s0/tempo.json"
    eligible = [s for s in Q if all(len(c) >= 2 for c in interleaved_clips(Q[s]))]
    pairs = S.tempo_pairs(tempo, art, eligible)
    ref_med = None
    if a.ref_bars:
        ref_med = json.loads(Path(a.ref_bars).read_text())["d"]["median_cells_120s"]
    res = {"policy": a.policy, "n_songs": len(Q), "tempo_source": tsrc, "n_eligible_ge2_clips_per_role": len(eligible), "n_tempo_pairs": len(pairs)}
    res["b"] = bar_b(Q, pairs)
    log(f"b: {res['b']}")
    res["c"] = bar_c(Q)
    log(f"c: {res['c']}")
    res["d"] = bar_d(Q, ref_med)
    log(f"d: {res['d']}")
    res["e"] = bar_e(Q)
    log(f"e: {res['e']}")
    # (a), (f) from the k5p2_eval parts
    if (chk / "check.json").exists():
        c = json.loads((chk / "check.json").read_text())["modes"]["argmax"]
        res["a"] = {"ext_a": c["ext"]["trained"]["a_song_mean"], "ext_a_ci": c["ext"]["trained"]["a_ci"], "paired_vs_untrained": c["ext"]["paired_vs_untrained"], "beats_untrained": c["ext"]["beats_untrained"], "pass": c["k5_pass"]}
        res["kappa0_control"] = {d: c[d]["paired_vs_trained_kappa0"] for d in ("ext", "int")}
    songs = {p.stem: json.loads(p.read_text()) for p in sorted((chk / "songs").glob("*.json"))} if (chk / "songs").exists() else {}
    if songs:
        f = {"songs": {}, "limit_report": {}}
        for n, s in songs.items():
            v = s["eprime_vs_v47"]
            f["songs"][n] = {"check_csv_accepted": s["check_csv"]["accepted"], "e1": v["e1"], "e1_limit": v["e1_limit"], "e1_pass": v["e1_pass"], "e2": v["e2"], "e2_limit": v["e2_limit"], "e2_pass": v["e2_pass"]}
            csvs = list((chk / "songs").glob(f"{n}.*.csv"))
            if csvs:
                f["limit_report"][n] = limit_report(hf_share.read_csv(csvs[0])[0])
        f["pass"] = bool(all(x["check_csv_accepted"] and x["e1_pass"] and x["e2_pass"] for x in f["songs"].values()))
        f["limit_flags"] = {n: [f"{j}:{k}" for j, d in r.items() for k in ("flag_speed", "flag_acc") if d[k]] for n, r in f["limit_report"].items()}
        res["f"] = f
    pq = {}
    for s, q in Q.items():
        pq[s] = limit_report(q)
    res["limit_report_heldout_rollouts_pooled"] = {j: {k: float(np.max([pq[s][j][k] for s in pq])) for k in ("speed_max", "acc_max", "speed_max_over_limit", "acc_max_over_limit")} |
                                                   {k: float(np.median([pq[s][j][k] for s in pq])) for k in ("speed_p99", "acc_p99")} for j in next(iter(pq.values()))}
    res["programs"] = program_usage(P)
    res["decoding_D"] = {"fast": None, "slow": None, "note": "not in a pass2-format pickle; Stage 3 trainer's pickle may carry it"}
    pk = None
    try:
        import pickle
        d = pickle.loads(Path(a.policy).read_bytes())
        pk = d.get("D") or (d.get("trainer") or {}).get("D")
    except Exception:  # noqa: BLE001
        pass
    if pk:
        res["decoding_D"] = pk
    res["burger_contrasts"] = burger(Q, out / "low_band_flux.json")
    flags = [res[k]["pass"] for k in ("a", "b", "c", "d", "e", "f") if k in res]
    res["all_bars_pass"] = None if any(x is None for x in flags) or len(flags) < 6 else bool(all(flags))
    (out / "bars.json").write_text(json.dumps(res, indent=1, default=float))
    log("all_bars_pass: " + str(res["all_bars_pass"]))


if __name__ == "__main__":
    main()
