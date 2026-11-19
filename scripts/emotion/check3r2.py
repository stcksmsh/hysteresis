#!/usr/bin/env python3
"""Check 3, round 2 (docs/NEXT_DECODER_THEN_BRAIN.md, "Rule note (user, 2026-10-28, after D2-2 ...)").

Round 1 (check3.py at fd3fbfe, results ac08509) stands as run: gate 2 FAIL. This file reuses check3.py for everything the
note does not change (segments, folds, mood lanes, k grid, seeds, surrogate, rendering, descriptors, shuffle, bootstrap,
dial checks) and changes only what the note says. Written and committed before anything is computed against the new
reference; when committed it has never been run on real data.

What changes
  Reference  one common yardstick for every map: human ratings of the held-out segments.
             DEAM + MERP: the mean valence and arousal over the labelled steps inside the 8 s window (a window with no
             labelled step is left out). Emotify: the clip's nine GEMS profile, same for each of its segments
             (separate score). The user's 3 songs (sixth set): the dial, three numbers per 0.5 s step (pass A energy,
             pass B light, pass B heavy), mean over the window's steps that are not masked or missing; a window missing
             any of the three is left out.
  Distances  Euclidean on the ratings against Euclidean on the standardised body descriptors (standardised as in round 1),
             Spearman per held-out fold, mean over the five folds (rsa.py, check3.score_map).
  Gate 1     decoder, DEAM/MERP ratings: the mean over folds beats 99 % of 1,000 within-fold shuffles (990 of 1,000).
  Gate 2     decoder minus baseline49, DEAM/MERP ratings, mean over folds: the 95 % bootstrap interval (2,000 resamples
             over held-out songs, check3.bootstrap_difference) lies above 0.
  Gate 3     energy sign on the user's 3 songs against pass A, unchanged.
  Reported   not gated: library lookup and core-2b scored against the same ratings; the GEMS score of every map (per fold,
             shuffle count); the sixth set against the dial (per map, shuffle count); the power anchor's sign against
             pass B (check3.dial_checks); the achieved train and held-out r of every anchored link per map and fold.
  Anchors    baseline49 and core-2b get the same two anchors as the decoder, fitted the same way on the same folds
             (the shared Map class and check3.prepare do this).
  Size       the one change to the maps: each anchored link (mood.energy -> body energy, size, time; mood.power ->
             weight) must reach a Pearson r of at least 0.5 between the lane and the decoded body dimension. Enforced in
             fitting for every map (decoder.fit_map_bounded): the map is fitted as in round 1; a link whose r on the
             training segments is below 0.5 + 0.05 gets a lower bound on its weight, stepped up the grid (0.5, 1, 2, 4, 8,
             16) with a refit until it holds or the grid ends. Training segments only; the held-out r is reported.

Points this file fixes where the note is silent (listed in the handoff, to be ruled on)
 1 The margin of 0.05 above 0.5 on the training segments (the note says r >= 0.5 held out).
 2 A rating needs at least one labelled step in the window (DEAM labels come every 2 s from 15 s, MERP every 0.5 s).
 3 The k of the rest lanes is chosen as in round 1, by the unbounded fit, so the lanes are round 1's lanes; the bound
   applies to the final map fit only.
 4 DEAM and MERP segments of one fold are pooled in one score (as the note's "DEAM/MERP"); the ratings are not
   standardised (both axes are -1..1, GEMS are fractions).
 5 The sixth set's dial score pools the three songs' segments; pass B of a song with no pass B leaves its segments out.
 6 Segments that failed to render leave that map's matrices, as in round 1 (round 1: 0 failed).

  python check3r2.py [--out DIR] [--dial DIR] [--no-core]
Reads the dial files only in main(), only when it runs.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np

import check1b as c1
import check3 as c3
import common
import decoder
import mind
import render

OUT = common.DATA / "check3r2"
GEMS = len(common.GEMS)


# ------------------------------------------------------------------------- ratings

def segment_ratings(clips):
    """Ratings of the whole 8 s windows of `clips`, in segment order (as check3.segment_lanes).
    -> dict(va (n, 2), gems (n, 9)), NaN where a segment has no such rating."""
    va, gems = [], []
    for c in clips:
        for s in range(0, (len(c.x) // c3.SEGMENT_STEPS) * c3.SEGMENT_STEPS, c3.SEGMENT_STEPS):
            row_va, row_gems = np.full(2, np.nan), np.full(GEMS, np.nan)
            if c.ds in ("deam", "merp") and c.y is not None:
                y = c.y[s:s + c3.SEGMENT_STEPS]
                have = np.isfinite(y).all(axis=1)
                if have.any():
                    row_va = y[have].mean(axis=0)
            elif c.ds == "emotify":
                row_gems = np.asarray(c.profile, dtype=np.float64)
            va.append(row_va)
            gems.append(row_gems)
    return {"va": np.array(va).reshape(-1, 2), "gems": np.array(gems).reshape(-1, GEMS)}


def dial_ratings(clips, dial):
    """(n, 3) pass A energy, pass B light, pass B heavy per window of the user's songs; NaN rows where any is missing."""
    rows = []
    for c in clips:
        d, steps = dial[c.key], len(c.x)
        series = [c1._dial_steps(d["energy10"], steps, d["masks"])]
        for name in ("light10", "heavy10"):
            series.append(c1._dial_steps(d[name], steps, []) if name in d else np.full(steps, np.nan))
        for s in range(0, (steps // c3.SEGMENT_STEPS) * c3.SEGMENT_STEPS, c3.SEGMENT_STEPS):
            row = np.array([_mean_finite(x[s:s + c3.SEGMENT_STEPS]) for x in series])
            rows.append(row if np.isfinite(row).all() else np.full(3, np.nan))
    return np.array(rows).reshape(-1, 3)


def _mean_finite(x):
    x = x[np.isfinite(x)]
    return float(x.mean()) if len(x) else float("nan")


def rating_fold(prep, rendered, ratings):
    """The segments of one map and fold that rendered and have a rating, ready for rsa; the ratings are the distances' space."""
    has = np.isfinite(ratings).all(axis=1)
    keep = rendered["ok"] & has
    desc_z = (rendered["desc"][keep] - rendered["desc_mean"]) / rendered["desc_std"]
    return {"z": ratings[keep], "desc_z": desc_z, "songs": [k for k, o in zip(prep["keys_te"], keep) if o],
            "total": int(has.sum()), "failed": int((has & ~rendered["ok"]).sum())}


# --------------------------------------------------------------------------- scoring

def score_r2(per_tag, cfg, dial=None, log=print):
    """Gate 1, gate 2 and the reported scores from the fitted and rendered maps of check3.compute_tags."""
    folds = range(common.N_FOLDS)
    names = [n for n in c3.MAPS if n in per_tag[0]]
    ratings = {t: segment_ratings(per_tag[t]["decoder"][3]) for t in per_tag}
    sixth_dial = dial_ratings(per_tag[c3.SIXTH]["decoder"][3], dial) if dial is not None else None
    result = {"maps": {}}
    mats = {}
    for name in names:
        va = [rating_fold(per_tag[t][name][0], per_tag[t][name][1], ratings[t]["va"]) for t in folds]
        if name in ("decoder", "baseline49"):
            scored, kept = c3.score_map(va, cfg.n_perm, keep=True)
            mats[name] = (va, kept)
        else:
            scored = c3.score_map(va, cfg.n_perm)
        gems = [rating_fold(per_tag[t][name][0], per_tag[t][name][1], ratings[t]["gems"]) for t in folds]
        entry = {"va": scored, "gems": c3.score_map(gems, cfg.n_perm, seed=c3.SEED_PERM + 50),
                 "links": {} if name == "library" else {str(t): link_report(per_tag[t][name][0]) for t in per_tag}}
        if sixth_dial is not None:
            d = rating_fold(per_tag[c3.SIXTH][name][0], per_tag[c3.SIXTH][name][1], sixth_dial)
            entry["sixthDial"] = dict(c3.score_map([d], cfg.n_perm, seed=c3.SEED_PERM + 99), segments=len(d["songs"]),
                                      segmentsWithoutDial=int(len(sixth_dial) - len(d["songs"])))
        result["maps"][name] = entry
        log(f"{name}: DEAM/MERP rho {scored['rho']:.4f} (per fold {np.round(scored['rhoPerFold'], 4).tolist()}), beats {scored['beaten']}/{scored['of']}; "
            f"GEMS rho {entry['gems']['rho']:.4f}, beats {entry['gems']['beaten']}/{entry['gems']['of']}")
    result["bootstrap"] = c3.bootstrap_difference(mats["decoder"][0], mats["decoder"][1], mats["baseline49"][0], mats["baseline49"][1], cfg.n_boot)
    result["ratedSegments"] = {"va": [m["total"] for m in mats["decoder"][0]],
                               "gems": [int(np.isfinite(ratings[t]["gems"]).all(axis=1).sum()) for t in folds]}
    return result


def link_report(prep):
    """Bounds, training r and held-out r of each anchored link of a map (the library has no map of its own)."""
    held = decoder.link_r(prep["map"], prep["lanes_te"])
    return dict(prep["links"] or {}, heldOutR=held)


def run(clips, folds, surrogate, cfg, dial=None, out_dir=None, log=print):
    start = time.time()
    per_tag = c3.compute_tags(clips, folds, surrogate, cfg, out_dir, log, start)
    result = score_r2(per_tag, cfg, dial, log)
    if dial is not None:
        final = per_tag[c3.SIXTH]["decoder"]
        lanes = {c.key: final[0]["model"].smoothed(final[2][c.key]) for c in final[3]}
        result["dial"] = c3.dial_checks(lanes, dial, [c.key for c in final[3]])
    result["pass"] = {"shuffle": result["maps"]["decoder"]["va"]["pass"], "baseline": result["bootstrap"]["pass"],
                      "energySign": result["dial"]["energyPass"] if dial is not None else None}
    result["check3r2"] = bool(all(v is True for v in result["pass"].values()))
    result["seconds"] = round(time.time() - start, 1)
    if out_dir:
        out = pathlib.Path(out_dir)
        save_ratings(out, per_tag, dial)
        common.write_json(out / "results.json", result)
        per_tag[c3.SIXTH]["decoder"][0]["model"].save(out / "mood_model_stage1.npz")
    return result


def save_ratings(out, per_tag, dial):
    """The ratings used for every segment of each fold (same order as segments_*.npz), so every number can be recomputed."""
    for tag, maps in per_tag.items():
        test = maps["decoder"][3]
        r = segment_ratings(test)
        arrays = {"va": r["va"], "gems": r["gems"]}
        if tag == c3.SIXTH and dial is not None:
            arrays["dial"] = dial_ratings(test, dial)
        np.savez_compressed(out / f"ratings_{tag}.npz", **arrays)


# ---------------------------------------------------------------------------- report

def report(result, log=print):
    for name, m in result["maps"].items():
        v, g = m["va"], m["gems"]
        gate = " (gate 1)" if name == "decoder" else " (reported)"
        log(f"{name}{gate}: DEAM/MERP mean rho {v['rho']:.4f}, per fold {np.round(v['rhoPerFold'], 4).tolist()}; beats {v['beaten']} of {v['of']} permuted means "
            f"(permuted max {v['permutedMax']:.4f}) -> {'PASS' if v['pass'] else 'FAIL'}; rated segments {sum(v['total'])}, failed {sum(v['failed'])}")
        log(f"{name} GEMS (reported): mean rho {g['rho']:.4f}, per fold {np.round(g['rhoPerFold'], 4).tolist()}; beats {g['beaten']} of {g['of']}")
        if "sixthDial" in m:
            d = m["sixthDial"]
            log(f"{name} sixth set against the dial (reported): rho {d['rhoPerFold'][0]:.4f} over {d['segments']} segments, beats {d['beaten']} of {d['of']}")
    b = result["bootstrap"]
    log(f"gate 2 decoder minus baseline49 (DEAM/MERP): mean {b['mean']:.4f}, 95 % interval [{b['difference'][0]:.4f}, {b['difference'][1]:.4f}] over {b['songs']} songs -> "
        f"{'PASS' if b['pass'] else 'FAIL'}")
    for name, m in result["maps"].items():
        for tag, links in m["links"].items():
            if links.get("trainR") is None:
                continue
            log(f"links {name} tag {tag}: bounds {json.dumps(links['bounds'])}, met {links['met']}, attempts {links['attempts']}, "
                f"train r {json.dumps({k: round(v, 3) for k, v in links['trainR'].items()})}, held-out r {json.dumps({k: round(v, 3) for k, v in links['heldOutR'].items()})}")
    if "dial" in result:
        d = result["dial"]
        for key, v in d["energy"].items():
            log(f"gate 3 energy sign {key}: r {v['r']:.3f} over {v['steps']} steps -> {'positive' if v['positive'] else 'NOT positive'}")
        log(f"gate 3: {'PASS' if d['energyPass'] else 'FAIL'}")
        for key, v in d["power"].items():
            log(f"power sign {key} (reported): " + (f"r heavy {v['rHeavy']:.3f}, r light {v['rLight']:.3f}, {'agrees' if v['agrees'] else 'disagrees'}" if "rHeavy" in v else v["note"]))
        log(f"power anchor: agrees on {d['powerAgree']}, disagrees on {d['powerDisagree']} -> {'DROP' if d['powerAnchorDropped'] else 'keep'}")
    log("CHECK 3 ROUND 2: " + ("PASS" if result["check3r2"] else "FAIL") + "  " + json.dumps(result["pass"]))


def config(no_core=False):
    """The round-2 settings: bounded map, check 2b's spectral radius per fold when its results file exists."""
    cfg = c3.Config(core=not no_core, bound=True)
    if c3.CHECK2B_RESULTS.exists():
        chosen = json.loads(c3.CHECK2B_RESULTS.read_text())["chosen"]
        cfg.radius = {**{f: chosen[str(f)]["radius"] for f in range(common.N_FOLDS)}, c3.SIXTH: chosen["all"]["radius"]}
    return cfg


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    parser.add_argument("--no-core", action="store_true")
    args = parser.parse_args(argv)
    cfg = config(args.no_core)
    render.build()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} perm={c3.SEED_PERM} std={c3.SEED_STD} "
          f"render={render.SEEDS} map={decoder.SEED_MAP}; link target {decoder.LINK_TARGET} margin {decoder.LINK_MARGIN} grid {decoder.BOUND_GRID}", flush=True)
    clips, folds, world = c3.load_corpus()
    print(f"DEAM {len(world.deam)}, Emotify {len(world.emotify)}, MERP {len(world.merp)}, songs {len(world.songs)}; "
          f"{len(c3.segment_table(clips))} segments", flush=True)
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    result = run(clips, folds, surrogate, cfg, dial, args.out, log=lambda s: print(s, flush=True))
    report(result)


if __name__ == "__main__":
    main()
