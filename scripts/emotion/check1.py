#!/usr/bin/env python3
"""Check 1 of docs/EMOTION.md: does the encoding hold emotion?

Fixed before any result was seen (this file was committed first):

* Splits: 5 folds by song, one seed, the same folds for every candidate
  (DEAM: shuffled songs; Emotify: shuffled within genre). Test songs never
  appear in training; the ridge penalty and, for the layer-wise MERT
  candidate, the layer are chosen by an inner 3-fold on training songs only.
* Evaluation grid: 4 s windows on a 2 s grid, only windows that fit inside the
  clip (DEAM label times 15, 17, ... s; Emotify centres 2, 4, ... s, averaged
  per clip). Every candidate is scored on the same rows.
* Timing: pooled R^2 of linear readouts of DEAM dynamic valence and arousal
  (2013/2014 label release, songs 1..2000) on held-out songs; the measure is
  the mean of the two. Within-song R^2 (song means removed) is a diagnostic.
* Feelings (Emotify, GEMS fractions of raters): mean per-clip Spearman rank
  correlation of predicted vs rated profile; nearest-neighbour agreement of
  the dominant feeling (cosine distance on training-standardised vectors,
  neighbour among the other held-out clips of the same fold).
* Geometry: mean distance between clips of different dominant feeling over mean
  distance within the same feeling (same pools and distance).
* 95 % intervals: 2000 bootstrap resamples over songs (percentile).
* Pass: beats the baseline's point estimate on timing, rank correlation and
  nearest-neighbour agreement, each with a 95 % interval that does not overlap
  the baseline's. Geometry is reported and ranked but does not gate passing.
* Pick: among passing candidates, best mean rank over the three measures
  (timing; feelings = mean of rank-correlation rank and agreement rank; geometry).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

import numpy as np
from scipy.stats import rankdata, spearmanr

import common
from common import CACHE, EVAL_STEP, N_BOOT, N_FOLDS

COMPONENTS = {
    "baseline_stems": ("baseline_stems", "plain"),
    "baseline_mix": ("baseline_mix", "plain"),
    "mert_avg": ("mert", "mean_layers"),
    "mert_layers": ("mert", "layers"),
    "clap": ("clap", "plain"),
    "essentia_effnet": ("essentia_effnet", "plain"),
    "essentia_mood": ("essentia_mood", "plain"),
}
CANDIDATES = {
    "baseline": ["baseline_stems"],
    "baseline_mix": ["baseline_mix"],
    "mert_avg": ["mert_avg"],
    "mert_best": ["mert_layers"],
    "clap": ["clap"],
    "essentia": ["essentia_effnet", "essentia_mood"],
    "baseline+mert_avg": ["baseline_stems", "mert_avg"],
    "baseline+clap": ["baseline_stems", "clap"],
    "baseline+essentia": ["baseline_stems", "essentia_effnet", "essentia_mood"],
    "baseline+all": ["baseline_stems", "mert_avg", "clap", "essentia_effnet", "essentia_mood"],
}
BASELINE = "baseline"


# ------------------------------------------------------------------ data

def _manifest(cache_name):
    return json.loads((CACHE / "emb" / cache_name / "manifest.json").read_text())


def _rows(array, manifest, centres, mode):
    k = np.rint((np.asarray(centres) - manifest["centre0"]) / manifest["hopSeconds"]).astype(int)
    if k.min() < 0 or k.max() >= len(array):
        raise ValueError("window centre outside cached range")
    x = array[k].astype(np.float32)
    return x.mean(axis=1) if mode == "mean_layers" else x


def load_component(name, deam_index, emotify_index):
    """-> (deam rows, emotify clip means) of one component for the given index lists."""
    cache_name, mode = COMPONENTS[name]
    manifest = _manifest(cache_name)
    deam = []
    for key, centres in deam_index:
        deam.append(_rows(np.load(CACHE / "emb" / cache_name / f"{key}.npy"), manifest, centres, mode))
    emo = []
    for key, centres in emotify_index:
        emo.append(_rows(np.load(CACHE / "emb" / cache_name / f"{key}.npy"), manifest, centres, mode).mean(axis=0))
    return np.concatenate(deam), np.stack(emo)


def build_index(durations):
    """Clip lists with evaluation centres and the DEAM labels at those centres."""
    val, aro = common.deam_dynamic("valence"), common.deam_dynamic("arousal")
    deam_index, y_rows, song_rows, time_rows = [], [], [], []
    for key, _ in common.deam_clips():
        sid = int(key.split("_")[1])
        if sid not in val or sid not in aro:
            continue
        centres = []
        for c in common.eval_centres(durations[key], common.DEAM_FIRST_LABEL):
            i = int(np.argmin(np.abs(val[sid][0] - c)))
            if abs(val[sid][0][i] - c) < 1e-6 and np.isfinite(val[sid][1][i]) and np.isfinite(aro[sid][1][i]):
                centres.append(c)
                y_rows.append((val[sid][1][i], aro[sid][1][i]))
                song_rows.append(sid)
                time_rows.append(c)
        if centres:
            deam_index.append((key, centres))
    profiles = common.emotify_profiles()
    emotify_index = [(key, common.eval_centres(durations[key], EVAL_STEP)) for key, _ in common.emotify_clips()]
    tids = [int(key.split("_")[1]) for key, _ in common.emotify_clips()]
    return {
        "deam_index": deam_index, "y": np.array(y_rows), "song": np.array(song_rows), "time": np.array(time_rows),
        "emotify_index": emotify_index, "tids": tids,
        "profile": np.stack([profiles[t][1] for t in tids]),
        "genre": {t: profiles[t][0] for t in tids},
    }


def clip_durations():
    """Duration per clip from the cached mix frames (20 Hz)."""
    return {p.stem: len(np.load(p)) / 20.0 for p in (CACHE / "frames_mix").glob("*.npy")}


# --------------------------------------------------------------- readouts

def select_and_fit(x_tr, y_tr, groups, layered):
    """Ridge on standardised features. `layered` x is (n, L, D): choose layer by inner CV."""
    options = range(x_tr.shape[1]) if layered else [None]
    best = None
    for o in options:
        x = x_tr[:, o] if layered else x_tr
        alpha, cost = common.choose_alpha(x, y_tr, groups, return_cost=True)
        if best is None or cost < best[0]:
            best = (cost, o, alpha)
    _, option, alpha = best
    x = x_tr[:, option] if layered else x_tr
    std = common.Standardizer().fit(x)
    model = common.ridge_fit(std(x), y_tr, alpha)
    return std, model, option, alpha


def timing_stats(x, data, folds, layered):
    """Per-song sufficient statistics of held-out DEAM predictions + chosen options."""
    song, y = data["song"], data["y"]
    pred = np.zeros_like(y)
    chosen = []
    for f in range(N_FOLDS):
        te = np.array([folds[f"deam_{s}"] == f for s in song])
        std, model, option, alpha = select_and_fit(x[~te], y[~te], song[~te], layered)
        xt = x[te][:, option] if layered else x[te]
        pred[te] = common.ridge_predict(model, std(xt))
        chosen.append((None if option is None else int(option), float(alpha)))
    songs = np.unique(song)
    stats = np.zeros((len(songs), 2, 7))
    for i, s in enumerate(songs):
        m = song == s
        for j in range(2):
            t, p = y[m, j], pred[m, j]
            stats[i, j] = [m.sum(), t.sum(), (t ** 2).sum(), ((t - p) ** 2).sum(),
                           ((t - t.mean()) ** 2).sum(), (((t - t.mean()) - (p - p.mean())) ** 2).sum(), 0]
    return songs, stats, chosen


def r2_from_stats(stats):
    """stats (..., songs, 2, 7) -> (..., 2) pooled R^2 and (..., 2) within-song R^2."""
    n, sy, syy, sse, sst_c, sse_c = (stats[..., k].sum(axis=-2) for k in range(6))
    pooled = 1 - sse / (syy - sy ** 2 / n)
    within = 1 - sse_c / sst_c
    return pooled, within


def feelings_stats(z, data, folds, layered):
    """Held-out GEMS predictions, per-clip rank correlations, NN agreement, geometry inputs."""
    tids, profile = data["tids"], data["profile"]
    fold = np.array([folds[f"emotify_{t}"] for t in tids])
    pred = np.zeros_like(profile)
    dist = np.full((len(tids), len(tids)), np.nan)
    chosen = []
    for f in range(N_FOLDS):
        te = fold == f
        groups = np.array(tids)[~te]
        std, model, option, alpha = select_and_fit(z[~te], profile[~te], groups, layered)
        zt = z[te][:, option] if layered else z[te]
        pred[te] = common.ridge_predict(model, std(zt))
        v = std(zt)
        v = v - v.mean(axis=0)
        v = v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-9)
        idx = np.where(te)[0]
        dist[np.ix_(idx, idx)] = 1 - v @ v.T
        chosen.append((None if option is None else int(option), float(alpha)))
    train_mean = np.stack([profile[fold != fold[i]].mean(axis=0) for i in range(len(tids))])
    rho = np.array([spearmanr(pred[i], profile[i])[0] for i in range(len(tids))])
    rho_c = np.array([spearmanr(pred[i] - train_mean[i], profile[i] - train_mean[i])[0] for i in range(len(tids))])
    dominant = profile.argmax(axis=1)
    agree = np.zeros(len(tids))
    for i in range(len(tids)):
        d = dist[i].copy()
        d[i] = np.inf
        d[np.isnan(d)] = np.inf
        agree[i] = float(dominant[np.argmin(d)] == dominant[i])
    return {"rho": np.nan_to_num(rho), "rho_centred": np.nan_to_num(rho_c), "agree": agree,
            "dist": dist, "fold": fold, "dominant": dominant, "chosen": chosen}


def geometry_ratio(dist, fold, dominant, weights=None):
    n = len(dominant)
    w = np.ones(n) if weights is None else weights
    pair = np.outer(w, w) * (fold[:, None] == fold[None, :]) * (1 - np.eye(n))
    same = dominant[:, None] == dominant[None, :]
    d = np.nan_to_num(dist)
    ws, wd = pair * same, pair * ~same
    if ws.sum() == 0 or wd.sum() == 0:
        return float("nan")
    return float((wd * d).sum() / wd.sum() / ((ws * d).sum() / ws.sum()))


# -------------------------------------------------------------- bootstrap

def bootstrap_timing(stats):
    idx = common.bootstrap_indices(stats.shape[0])
    pooled, within = r2_from_stats(stats[idx])
    return pooled.mean(axis=1), within.mean(axis=1)


def evaluate(name, components, data, folds, comp_cache):
    t0 = time.time()
    layered = components == ["mert_layers"]
    x_deam = np.concatenate([comp_cache[c][0] for c in components], axis=-1)
    x_emo = np.concatenate([comp_cache[c][1] for c in components], axis=-1)
    songs, stats, chosen_t = timing_stats(x_deam, data, folds, layered)
    pooled, within = r2_from_stats(stats)
    boot_pooled, boot_within = bootstrap_timing(stats)
    fe = feelings_stats(x_emo, data, folds, layered)
    n = len(fe["rho"])
    idx = common.bootstrap_indices(n)
    weights = np.stack([np.bincount(row, minlength=n) for row in idx]).astype(float)
    geo = geometry_ratio(fe["dist"], fe["fold"], fe["dominant"])
    geo_boot = np.array([geometry_ratio(fe["dist"], fe["fold"], fe["dominant"], w) for w in weights])
    result = {
        "dims": int(x_deam.shape[-1] if not layered else x_deam.shape[-1]),
        "timing": float(pooled.mean()), "timingCI": common.interval(boot_pooled),
        "timingValence": float(pooled[0]), "timingArousal": float(pooled[1]),
        "timingWithin": float(within.mean()), "timingWithinCI": common.interval(boot_within),
        "rho": float(fe["rho"].mean()), "rhoCI": common.interval(fe["rho"][idx].mean(axis=1)),
        "rhoCentred": float(fe["rho_centred"].mean()), "rhoCentredCI": common.interval(fe["rho_centred"][idx].mean(axis=1)),
        "agree": float(fe["agree"].mean()), "agreeCI": common.interval(fe["agree"][idx].mean(axis=1)),
        "geometry": geo, "geometryCI": common.interval(geo_boot[np.isfinite(geo_boot)]),
        "chosenTiming": chosen_t, "chosenFeelings": fe["chosen"],
        "seconds": round(time.time() - t0, 1),
    }
    return result


def overlaps(a_ci, b_ci):
    return not (a_ci[0] > b_ci[1] or b_ci[0] > a_ci[1])


def judge(results, baseline=BASELINE):
    """Apply the pre-declared pass and pick rules. Returns (verdicts, pick)."""
    base = results[baseline]
    verdicts = {}
    for name, r in results.items():
        if name == baseline or name == "baseline_mix":
            continue
        gates = {}
        for label, key in (("timing", "timing"), ("rho", "rho"), ("agree", "agree")):
            gates[label] = bool(r[key] > base[key] and not overlaps(r[key + "CI"], base[key + "CI"]))
        verdicts[name] = {"gates": gates, "pass": all(gates.values())}
    passing = [n for n, v in verdicts.items() if v["pass"]]
    pick = None
    if passing:
        def rank(key):
            values = [results[n][key] for n in passing]
            return dict(zip(passing, rankdata([-v for v in values])))
        rt, rr, ra, rg = rank("timing"), rank("rho"), rank("agree"), rank("geometry")
        mean_rank = {n: (rt[n] + (rr[n] + ra[n]) / 2 + rg[n]) / 3 for n in passing}
        pick = min(passing, key=lambda n: (mean_rank[n], n))
        for n in passing:
            verdicts[n]["meanRank"] = float(mean_rank[n])
    return verdicts, pick


def markdown(results, verdicts, pick, baseline_name):
    def cell(value, ci, digits=3):
        return f"{value:.{digits}f} [{ci[0]:.{digits}f}, {ci[1]:.{digits}f}]"
    lines = ["| candidate | dims | timing R² (V,A mean) | V / A | within-song R² | rank corr ρ | ρ centred | NN agreement | geometry | gates timing/ρ/NN | pass |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for name, r in results.items():
        v = verdicts.get(name)
        gates = "-" if v is None else "/".join("y" if v["gates"][k] else "n" for k in ("timing", "rho", "agree"))
        verdict = "baseline" if name == baseline_name else ("-" if v is None else ("PASS" if v["pass"] else "fail"))
        if name == pick:
            verdict += " (pick)"
        lines.append(f"| {name} | {r['dims']} | {cell(r['timing'], r['timingCI'])} | {r['timingValence']:.3f} / {r['timingArousal']:.3f} | "
                     f"{cell(r['timingWithin'], r['timingWithinCI'])} | {cell(r['rho'], r['rhoCI'])} | {cell(r['rhoCentred'], r['rhoCentredCI'])} | "
                     f"{cell(r['agree'], r['agreeCI'])} | {cell(r['geometry'], r['geometryCI'])} | {gates} | {verdict} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(common.DATA / "check1"))
    parser.add_argument("--only", nargs="*")
    parser.add_argument("--baseline", choices=("stems", "mix"), default="stems",
                        help="mix: the stem features are not available, so the mix-only features are the baseline")
    args = parser.parse_args()
    if args.baseline == "mix":
        for name, parts in CANDIDATES.items():
            CANDIDATES[name] = ["baseline_mix" if p == "baseline_stems" else p for p in parts]
        del CANDIDATES["baseline_mix"]
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} "
          f"boot={N_BOOT} folds={N_FOLDS}", flush=True)
    durations = clip_durations()
    data = build_index(durations)
    deam_songs = sorted(set(data["song"]))
    folds = common.assign_folds([f"deam_{s}" for s in deam_songs])
    folds.update(common.assign_folds([f"emotify_{t}" for t in data["tids"]],
                                     {f"emotify_{t}": data["genre"][t] for t in data["tids"]}))
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    common.write_json(out / "folds.json", folds)
    print(f"DEAM songs {len(deam_songs)} rows {len(data['y'])}; Emotify clips {len(data['tids'])}", flush=True)

    names = args.only or list(CANDIDATES)
    needed = sorted({c for n in names for c in CANDIDATES[n]})
    comp_cache = {}
    for c in needed:
        comp_cache[c] = load_component(c, data["deam_index"], data["emotify_index"])
        print("loaded", c, comp_cache[c][0].shape, comp_cache[c][1].shape, flush=True)
    results = {}
    for n in names:
        results[n] = evaluate(n, CANDIDATES[n], data, folds, comp_cache)
        r = results[n]
        print(f"{n}: timing {r['timing']:.3f} rho {r['rho']:.3f} agree {r['agree']:.3f} geo {r['geometry']:.3f} ({r['seconds']}s)", flush=True)
        common.write_json(out / "results.json", {"results": results})
    if BASELINE in results:
        verdicts, pick = judge(results)
        table = markdown(results, verdicts, pick, BASELINE)
        common.write_json(out / "results.json", {"results": results, "verdicts": verdicts, "pick": pick,
                                                 "seeds": {"folds": common.SEED_FOLDS, "bootstrap": common.SEED_BOOTSTRAP,
                                                           "inner": common.SEED_INNER}})
        (out / "table.md").write_text(table)
        print(table)
        print("PICK:", pick)


if __name__ == "__main__":
    main()
