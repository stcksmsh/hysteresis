#!/usr/bin/env python3
"""A2 of docs/NEXT_DECODER_THEN_BRAIN.md (rule note 2026-10-29): the spread fix on `core-2b`, before and after.

Reuses check3r2.py: the corpus, folds, seeds, config (bounded map, check 2b's radius), core features, mood model,
k choice and map fit (check3.prepare), render (check3.render_map), ratings and scoring (check3r2.rating_fold,
check3.score_map). For each of the five folds and the sixth set the map is fitted once. "Before" is that map
as round 2 had it. "After" attaches quantile.QuantileMap, fitted on the pre-sigmoid values of the same training
segments (a fold's training segments for a fold, all five folds' segments for the sixth set), and renders again.
Nothing else changes, so "before" must reproduce check3r2's core-2b numbers (compared in the result, `reproduces`).

Reported, before and after: DEAM/MERP rho with its gate-1 shuffle (1,000), GEMS rho, the sixth set against the dial,
failed segments, the 24 links (training and held-out r), and the share of segments within 0.05 of 0 or 1 per
dimension. The anchors (0.05, 0.95) are arguments; the one allowed later adjustment is made by the overseer.

  python a2.py [--out DIR] [--dial DIR] [--anchor 0.05]
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time

import numpy as np

import check1b as c1
import check3 as c3
import check3r2 as r2
import common
import decoder
import mood
import render
import spread

OUT = common.DATA / "a2"
VARIANTS = ("before", "after")


def score_variant(per_tag, ratings, dial_rows, cfg):
    """per_tag {tag: (prep, rendered)} of one variant -> DEAM/MERP, GEMS, sixth-set dial scores and the links."""
    folds = range(common.N_FOLDS)
    take = lambda tag, r: r2.rating_fold(per_tag[tag][0], per_tag[tag][1], r)
    va = c3.score_map([take(t, ratings[t]["va"]) for t in folds], cfg.n_perm)
    gems = c3.score_map([take(t, ratings[t]["gems"]) for t in folds], cfg.n_perm, seed=c3.SEED_PERM + 50)
    d = take(c3.SIXTH, dial_rows)
    sixth = dict(c3.score_map([d], cfg.n_perm, seed=c3.SEED_PERM + 99), segments=len(d["songs"]),
                 segmentsWithoutDial=int(len(dial_rows) - len(d["songs"])))
    links = {str(t): r2.link_report(per_tag[t][0]) for t in per_tag}
    bodies = {str(t): per_tag[t][1]["bodies"] for t in per_tag}
    edge = {t: spread.edge_share(b).tolist() for t, b in bodies.items()}
    return {"va": va, "gems": gems, "sixthDial": sixth, "links": links, "edgeShare": edge,
            "failedSegments": {str(t): int((~per_tag[t][1]["ok"]).sum()) for t in per_tag}}


def run(clips, folds, surrogate, cfg, dial, out_dir=None, log=print, anchors=None):
    start = time.time()
    anchors = anchors or {}
    prepared, rendered = {}, {v: {} for v in VARIANTS}
    for tag in list(range(common.N_FOLDS)) + [c3.SIXTH]:
        train, test = c3.split(clips, folds, tag)
        feats, radius = c3.core_features(train, test, tag, cfg)
        prep = c3.prepare(train, test, feats, mood.SOURCE_CORE2B, None, surrogate, cfg)
        prep["radius"], prepared[tag] = radius, (prep, test)
        log(f"tag {tag}: fitted ({time.time() - start:.0f} s), k {prep['k']}")
        before_links = r2.link_report(prep)
        rendered["before"][tag] = (dict(prep, links=before_links), c3.render_map(prep, tag, "core2b", cfg))
        log(f"tag {tag}: rendered before ({time.time() - start:.0f} s)")
        prep["map"].fit_quantile(prep["lanes_tr"], **anchors)
        rendered["after"][tag] = (dict(prep, links=r2.link_report(prep)), c3.render_map(prep, tag, "core2b", cfg))
        prep["map"].quantile = None
        log(f"tag {tag}: rendered after ({time.time() - start:.0f} s)")
        if out_dir:
            save_segments(pathlib.Path(out_dir), tag, rendered, prep, anchors)
    ratings = {t: r2.segment_ratings(prepared[t][1]) for t in prepared}
    dial_rows = r2.dial_ratings(prepared[c3.SIXTH][1], dial)
    result = {"anchors": anchors or "default 0.05/0.95", "variants": {}}
    for v in VARIANTS:
        result["variants"][v] = score_variant(rendered[v], ratings, dial_rows, cfg)
        s = result["variants"][v]
        log(f"{v}: DEAM/MERP rho {s['va']['rho']:.4f} {np.round(s['va']['rhoPerFold'], 4).tolist()} beats {s['va']['beaten']}/{s['va']['of']}; "
            f"GEMS {s['gems']['rho']:.4f}; sixth vs dial {s['sixthDial']['rhoPerFold'][0]:.4f} over {s['sixthDial']['segments']}; failed {s['failedSegments']}")
    result["reproduces"] = reproduces(result["variants"]["before"])
    result["seconds"] = round(time.time() - start, 1)
    if out_dir:
        common.write_json(pathlib.Path(out_dir) / "a2.json", result)
    return result


def reproduces(before, check_dir=r2.OUT):
    """The 'before' numbers against check3r2's results.json for core2b (largest absolute differences)."""
    path = pathlib.Path(check_dir) / "results.json"
    if not path.exists():
        return None
    m = json.loads(path.read_text())["maps"]["core2b"]
    diff = lambda a, b: float(np.max(np.abs(np.asarray(a, dtype=np.float64) - np.asarray(b, dtype=np.float64))))
    links = max(diff([v for _, v in sorted(before["links"][t]["heldOutR"].items())], [v for _, v in sorted(m["links"][t]["heldOutR"].items())])
                for t in before["links"])
    return {"vaRhoPerFold": diff(before["va"]["rhoPerFold"], m["va"]["rhoPerFold"]), "gemsRho": diff(before["gems"]["rho"], m["gems"]["rho"]),
            "sixthDialRho": diff(before["sixthDial"]["rhoPerFold"], m["sixthDial"]["rhoPerFold"]), "heldOutLinkR": links}


def save_segments(out, tag, rendered, prep, anchors):
    out.mkdir(parents=True, exist_ok=True)
    arrays = {"keys": np.array(prep["keys_te"]), "lanes": prep["lanes_te"]}
    for v in VARIANTS:
        for part in ("bodies", "ok", "desc", "stretch"):
            arrays[f"{v}/{part}"] = rendered[v][tag][1][part]
    np.savez_compressed(out / f"segments_{tag}.npz", **arrays)


def report(result, log=print):
    for v in VARIANTS:
        s = result["variants"][v]
        va, g, d = s["va"], s["gems"], s["sixthDial"]
        log(f"{v}: DEAM/MERP mean rho {va['rho']:.4f}, per fold {np.round(va['rhoPerFold'], 4).tolist()}; beats {va['beaten']} of {va['of']} permuted means "
            f"(permuted max {va['permutedMax']:.4f}) -> {'PASS' if va['pass'] else 'FAIL'}; rated {sum(va['total'])}, failed {sum(va['failed'])}")
        log(f"{v}: GEMS mean rho {g['rho']:.4f}, per fold {np.round(g['rhoPerFold'], 4).tolist()}; sixth set against the dial rho {d['rhoPerFold'][0]:.4f} "
            f"over {d['segments']} segments, beats {d['beaten']} of {d['of']}")
        log(f"{v}: failed segments (all, per tag) {s['failedSegments']}")
        for tag, links in s["links"].items():
            log(f"{v}: links tag {tag}: held-out r {json.dumps({k: round(x, 3) for k, x in links['heldOutR'].items()})}")
        for tag, share in s["edgeShare"].items():
            log(f"{v}: tag {tag} share within 0.05 of 0 or 1, per dimension: " + ", ".join(f"{n} {x:.2f}" for n, x in zip(decoder.DIMS, share)))
    log(f"before against check3r2's saved core2b (largest absolute differences): {json.dumps(result['reproduces'])}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    parser.add_argument("--anchor", type=float, default=None, help="p_low = out_low = ANCHOR, p_high = out_high = 1 - ANCHOR (the allowed adjustment)")
    args = parser.parse_args(argv)
    cfg = r2.config()
    anchors = {} if args.anchor is None else dict(p_low=args.anchor, p_high=1 - args.anchor, out_low=args.anchor, out_high=1 - args.anchor)
    render.build()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} perm={c3.SEED_PERM} std={c3.SEED_STD} "
          f"render={render.SEEDS} map={decoder.SEED_MAP}; anchors {anchors or 'default'}", flush=True)
    clips, folds, _ = c3.load_corpus()
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    result = run(clips, folds, surrogate, cfg, dial, args.out, log=lambda s: print(s, flush=True), anchors=anchors)
    report(result)


if __name__ == "__main__":
    main()
