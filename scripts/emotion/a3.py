#!/usr/bin/env python3
"""A3 of docs/NEXT_DECODER_THEN_BRAIN.md (rule note 2026-10-29): the spread check on the user's 3 songs, core-2b bodies.

  fit     the sixth-set core-2b exactly as a2.py / check3.run_tag do it (check3r2's settings; trained on all five
          folds' clips, never on the user's songs): core features, mood model, k, bounded map. The spread fix is
          quantile.QuantileMap on the pre-sigmoid values of those training segments.
  write   per song: the emotion sidecar plus `mindState` from the core-2b model (source "core-2b-smooth8"), then the
          `bodyTrack` sidecar for the map without the fix ("before", D3-style) and with it ("after"), by bodytrack.write.
  score   spread.regions_of on each phrase body (render.render, 3 check-3 seeds), spread.score for the three rules.
          "Before" is reported, not gated.

  python a3.py [--out DIR] [--anchor 0.05]
Writes OUT/a3/{before,after}/<song>.sidecar.json, mind-<song>.json, OUT/a3.json (the rules, per-phrase regions and distances).
"""
from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

import bodytrack
import check1b as c1
import check3 as c3
import check3r2 as r2
import common
import a2stats
import decoder
import mindstate
import mood
import render
import spread

OUT = common.DATA / "a2"


def phrase_bodies(sidecar_path):
    """-> (n, 15) bodies of `bodyTrack.phrases` of a sidecar, in the Rust reader's rounding."""
    track = json.loads(pathlib.Path(sidecar_path).read_text())["bodyTrack"]
    return np.array([p["body"] for p in track["phrases"]], dtype=np.float64)


def fit_final(clips, folds, surrogate, cfg, anchors, log=print):
    """-> (prep of the sixth set, features of every clip). prep["map"] has no quantile; the caller's `fixed` copy has."""
    train, test = c3.split(clips, folds, c3.SIXTH)
    feats, radius = c3.core_features(train, test, c3.SIXTH, cfg)
    prep = c3.prepare(train, test, feats, mood.SOURCE_CORE2B, None, surrogate, cfg, power_anchor=False)   # a2.POWER_ANCHOR
    log(f"core-2b sixth set: radius {radius}, k {prep['k']}, bounds {json.dumps(prep['links']['bounds'])}, met {prep['links']['met']}")
    return prep, feats


def write_sidecars(prep, feats, anchors, out, music_arm=c1.MUSIC_ARM):
    """The mind and bodyTrack sidecars of the 3 songs for both variants; -> {variant: {song key: sidecar path}}."""
    out = pathlib.Path(out)
    paths = {"before": {}, "after": {}}
    for variant in paths:
        folder = out / variant
        folder.mkdir(parents=True, exist_ok=True)
        fitted = prep["map"]
        fitted.quantile = None
        if variant == "after":
            fitted.fit_quantile(prep["lanes_tr"], **anchors)
        bodytrack.save_map(folder / "core2b.map.npz", fitted, f"core-2b-final-{variant}")
        fitted.quantile = None
        prep["model"].save(folder / "core2b.model.npz")
        for key, _, _, stem in c1.SONGS:
            emotion = json.loads((pathlib.Path(music_arm) / f"{stem}.emotion.sidecar.json").read_text())
            steps = len(emotion["emotionEncoding"]["steps"])
            if len(feats[key]) != steps:
                raise ValueError(f"{key}: core features have {len(feats[key])} steps, the sidecar {steps}")
            mind_path = folder / f"mind-{key}.json"
            mind_path.write_text(json.dumps(dict(emotion, mindState=mindstate.mind_state_field(prep["model"], feats[key])), separators=(",", ":")))
            sidecar = folder / f"{key}.sidecar.json"
            bodytrack.write(pathlib.Path(music_arm) / f"{stem}.notes.sidecar.json", mind_path, folder / "core2b.map.npz", sidecar)
            paths[variant][key] = sidecar
    return paths


def score_variant(paths, study):
    """-> (spread.score result, {song: per-phrase dict}) for one variant's sidecars."""
    songs, detail = {}, {}
    for key, path in paths.items():
        bodies = phrase_bodies(path)
        found = spread.regions_of(bodies, study)
        songs[key] = {"region": found["region"], "bodies": bodies}
        detail[key] = {"region": found["region"].tolist(), "distance": found["distance"].tolist(), "ok": found["ok"].tolist(),
                       "stretch": np.round(found["stretch"], 4).tolist()}
    return spread.score(songs), detail


def diagnostics(prep, anchors, paths, study, renderer=render.render):
    """Reported, not gated (A3 round 2), on the "after" map: (a) the region of the body made from the corpus-median mood vector
    and the region histogram of all public-corpus training segments through the sixth-set map (rendered here, 3 seeds);
    (b) the 3 songs' mood distances before the map, in corpus SD per lane."""
    fitted = prep["map"]
    fitted.fit_quantile(prep["lanes_tr"], **anchors)
    median = np.median(prep["lanes_tr"], axis=0)
    one = spread.regions_of(fitted.bodies(median[None]), study, renderer)
    every = spread.regions_of(fitted.bodies(prep["lanes_tr"]), study, renderer)
    fitted.quantile = None
    counts = np.bincount(every["region"][every["region"] >= 0], minlength=len(study[1]))
    phrases = {}
    for key, path in paths.items():
        sidecar = json.loads(pathlib.Path(path).read_text())
        mind = json.loads((pathlib.Path(path).parent / f"mind-{key}.json").read_text())["mindState"]
        spans = [(p["start"], p["end"]) for p in sidecar["bodyTrack"]["phrases"]]
        phrases[key] = bodytrack.phrase_lanes(bodytrack.lane_matrix(mind), mind["hopSeconds"], spans)
    return {"medianMood": median.tolist(), "medianRegion": int(one["region"][0]), "medianDistance": float(one["distance"][0]), "medianOk": bool(one["ok"][0]),
            "corpusSegments": int(len(prep["lanes_tr"])), "corpusRegionCounts": counts.tolist(), "corpusFailed": int((~every["ok"]).sum()),
            "moodDistances": a2stats.mood_distances(prep["lanes_tr"], phrases)}


def report(result, log=print):
    for variant, r in result["variants"].items():
        log(f"{variant} ({'gated' if variant == 'after' else 'reported, not gated'}): rule 1 {r['rule1']}, rule 2 {r['rule2']} (shared pairs {r['rule2SharedPairs']}), "
            f"rule 3 {r['rule3']}; all rules {'PASS' if r['pass'] else 'FAIL'}")
        for key, s in r["songs"].items():
            over = {decoder.DIMS[i]: round(s["edgeShare"][i], 3) for i in s["dimensionsOver"]}
            dist = np.array(result["detail"][variant][key]["distance"])
            log(f"  {variant} {key}: {s['phrases']} phrases, failed {s['failed']}, region counts {s['counts']}, visited {s['visited']}, most visited {s['mostVisited']}, "
                f"distance to region mean {np.nanmean(dist):.3f} (max {np.nanmax(dist):.3f}); dimensions over 20 %: {over or 'none'}")
            log("    share within 0.05 of 0 or 1: " + ", ".join(f"{n} {x:.2f}" for n, x in zip(decoder.DIMS, s["edgeShare"])))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--tag", default="a3", help="folder and result name under --out")
    parser.add_argument("--anchor", type=float, default=None, help="the 5th/95th percentiles go to ANCHOR / 1 - ANCHOR (A3 round 2: 0.10)")
    args = parser.parse_args(argv)
    cfg = r2.config()
    anchors = {} if args.anchor is None else dict(out_low=args.anchor, out_high=1 - args.anchor)
    render.build()
    clips, folds, _ = c3.load_corpus()
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    prep, feats = fit_final(clips, folds, surrogate, cfg, anchors, log=lambda s: print(s, flush=True))
    out = pathlib.Path(args.out) / args.tag
    paths = write_sidecars(prep, feats, anchors, out)
    study = spread.load_study()
    result = {"anchors": anchors or "default 0.05/0.95", "variants": {}, "detail": {}}
    for variant in paths:
        result["variants"][variant], result["detail"][variant] = score_variant(paths[variant], study)
    result["diagnostics"] = diagnostics(prep, anchors, paths["after"], study)
    common.write_json(pathlib.Path(args.out) / f"{args.tag}.json", result)
    report(result)
    d = result["diagnostics"]
    print(f"diagnostics: corpus-median mood {np.round(d['medianMood'], 3).tolist()} -> region {d['medianRegion']} (distance {d['medianDistance']:.3f}); "
          f"corpus {d['corpusSegments']} segments, region counts {d['corpusRegionCounts']}, failed {d['corpusFailed']}")
    print(json.dumps(d["moodDistances"], indent=1))


if __name__ == "__main__":
    main()
