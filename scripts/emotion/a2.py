#!/usr/bin/env python3
"""A2 of docs/NEXT_DECODER_THEN_BRAIN.md (rule note 2026-10-29): the spread fix on `core-2b`, before and after.

Reuses check3r2.py: the corpus, folds, seeds, config (bounded map, check 2b's radius), core features, mood model,
k choice and map fit (check3.prepare), render (check3.render_map), ratings and scoring (check3r2.rating_fold,
check3.score_map). For each of the five folds and the sixth set the map is fitted once. "Before" is that map
as round 2 had it. "After" attaches quantile.QuantileMap, fitted on the pre-sigmoid values of the same training
segments (a fold's training segments for a fold, all five folds' segments for the sixth set), and renders again.
The power anchor is dropped (overseer's ruling), so "before" is not round 2's map; round 2's saved core-2b numbers are reported beside it.

Reported, before and after: DEAM/MERP rho with its gate-1 shuffle (1,000), GEMS rho, the sixth set against the dial,
failed segments, the 24 links (training and held-out r), and the share of segments within 0.05 of 0 or 1 per
dimension. The anchors (0.05, 0.95) are arguments; the one allowed later adjustment is made by the overseer.

  python a2.py [--out DIR] [--dial DIR]
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
# variant -> quantile anchors (None: no fix). "after" is round 1 (5th/95th to 0.05/0.95), "after2" is A3 round 2 (0.10/0.90,
# chosen after round 1's results). One fit per set serves all three; each is rendered with its own standardiser.
ANCHORS = {"before": None, "after": {}, "after2": dict(p_low=0.10, p_high=0.90, out_low=0.10, out_high=0.90)}
VARIANTS = tuple(ANCHORS)
POWER_ANCHOR = False    # overseer, 2026-10-29: the power anchor is dropped for core-2b (signs disagree on 3 of 3 songs); weight is free


def score_variant(per_tag, ratings, dial_rows, cfg):
    """per_tag {tag: (prep, rendered)} of one variant -> DEAM/MERP, GEMS, sixth-set dial scores and the links."""
    folds = range(common.N_FOLDS)
    take = lambda tag, r: r2.rating_fold(per_tag[tag][0], per_tag[tag][1], r)
    va = c3.score_map([take(t, ratings[t]["va"]) for t in folds], cfg.n_perm)
    gems = c3.score_map([take(t, ratings[t]["gems"]) for t in folds], cfg.n_perm, seed=c3.SEED_PERM + 50)
    d = take(c3.SIXTH, dial_rows)
    sixth = dict(c3.score_map([d], cfg.n_perm, seed=c3.SEED_PERM + 99), segments=len(d["songs"]),
                 segmentsWithoutDial=int(len(dial_rows) - len(d["songs"])))
    links = {str(t): per_tag[t][0]["links"] for t in per_tag}
    bodies = {str(t): per_tag[t][1]["bodies"] for t in per_tag}
    edge = {t: spread.edge_share(b).tolist() for t, b in bodies.items()}
    return {"va": va, "gems": gems, "sixthDial": sixth, "links": links, "edgeShare": edge,
            "failedSegments": {str(t): int((~per_tag[t][1]["ok"]).sum()) for t in per_tag}}


def run(clips, folds, surrogate, cfg, dial, out_dir=None, log=print):
    start = time.time()
    prepared, rendered = {}, {v: {} for v in VARIANTS}
    for tag in list(range(common.N_FOLDS)) + [c3.SIXTH]:
        train, test = c3.split(clips, folds, tag)
        feats, radius = c3.core_features(train, test, tag, cfg)
        prep = c3.prepare(train, test, feats, mood.SOURCE_CORE2B, None, surrogate, cfg, power_anchor=POWER_ANCHOR)
        prep["radius"], prepared[tag] = radius, (prep, test)
        log(f"tag {tag}: fitted ({time.time() - start:.0f} s), k {prep['k']}")
        for v, anchors in ANCHORS.items():
            if anchors is None:
                prep["map"].quantile = None
            else:
                prep["map"].fit_quantile(prep["lanes_tr"], **anchors)
            links = r2.link_report(prep)      # with the variant's quantile attached: held-out r of lane and body dimension
            rendered[v][tag] = (dict(prep, links=links), c3.render_map(prep, tag, "core2b", cfg))
            log(f"tag {tag}: rendered {v} ({time.time() - start:.0f} s)")
        prep["map"].quantile = None
        if out_dir:
            save_segments(pathlib.Path(out_dir), tag, rendered, prep)
    ratings = {t: r2.segment_ratings(prepared[t][1]) for t in prepared}
    dial_rows = r2.dial_ratings(prepared[c3.SIXTH][1], dial)
    result = {"anchors": {v: a if a is not None else "none" for v, a in ANCHORS.items()}, "variants": {}}
    for v in VARIANTS:
        result["variants"][v] = score_variant(rendered[v], ratings, dial_rows, cfg)
        s = result["variants"][v]
        log(f"{v}: DEAM/MERP rho {s['va']['rho']:.4f} {np.round(s['va']['rhoPerFold'], 4).tolist()} beats {s['va']['beaten']}/{s['va']['of']}; "
            f"GEMS {s['gems']['rho']:.4f}; sixth vs dial {s['sixthDial']['rhoPerFold'][0]:.4f} over {s['sixthDial']['segments']}; failed {s['failedSegments']}")
    result["round2"] = round2_reference()
    result["seconds"] = round(time.time() - start, 1)
    if out_dir:
        common.write_json(pathlib.Path(out_dir) / "a2.json", result)
    return result


def held_out_links(out_dir):
    """Held-out Pearson r of each lane and body dimension per variant, recomputed from the saved segments_*.npz
    (lanes and rendered bodies); the same quantity as check3r2.link_report's heldOutR."""
    out = {}
    for v in VARIANTS:
        out[v] = {}
        for tag in list(range(common.N_FOLDS)) + [c3.SIXTH]:
            z = np.load(pathlib.Path(out_dir) / f"segments_{tag}.npz")
            lanes, bodies = z["lanes"], z[f"{v}/bodies"]
            out[v][str(tag)] = {decoder.link_name(l): decoder._np_pearson(lanes[:, l[0]], bodies[:, decoder.DIMS.index(l[1])])
                                for l in decoder.links(True)}
    return out


def round2_reference(check_dir=r2.OUT):
    """check3r2's saved core-2b numbers (power anchor kept), the reference column beside 'before' and 'after'."""
    path = pathlib.Path(check_dir) / "results.json"
    if not path.exists():
        return None
    m = json.loads(path.read_text())["maps"]["core2b"]
    return {"va": m["va"], "gems": m["gems"], "sixthDial": m["sixthDial"],
            "links": {t: v["heldOutR"] for t, v in m["links"].items()}}


def save_segments(out, tag, rendered, prep):
    out.mkdir(parents=True, exist_ok=True)
    arrays = {"keys": np.array(prep["keys_te"]), "lanes": prep["lanes_te"]}
    for v in VARIANTS:
        for part in ("bodies", "ok", "desc", "stretch", "desc_mean", "desc_std"):
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
            log(f"{v}: links tag {tag}: held-out r {json.dumps({k: round(x, 3) for k, x in links['heldOutR'].items()})} (power->weight is not an anchor, not gated)")
        for tag, share in s["edgeShare"].items():
            log(f"{v}: tag {tag} share within 0.05 of 0 or 1, per dimension: " + ", ".join(f"{n} {x:.2f}" for n, x in zip(decoder.DIMS, share)))
    ref = result["round2"]
    if ref:
        va, g, d = ref["va"], ref["gems"], ref["sixthDial"]
        log(f"round 2 (power anchor kept, reference): DEAM/MERP mean rho {va['rho']:.4f}, per fold {np.round(va['rhoPerFold'], 4).tolist()}; GEMS {g['rho']:.4f}; "
            f"sixth set against the dial {d['rhoPerFold'][0]:.4f}; failed {sum(va['failed'])}")
        for tag, links in ref["links"].items():
            log(f"round 2: links tag {tag}: held-out r {json.dumps({k: round(x, 3) for k, x in links.items()})}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    args = parser.parse_args(argv)
    cfg = r2.config()
    render.build()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} perm={c3.SEED_PERM} std={c3.SEED_STD} "
          f"render={render.SEEDS} map={decoder.SEED_MAP}; variants {ANCHORS}", flush=True)
    clips, folds, _ = c3.load_corpus()
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    result = run(clips, folds, surrogate, cfg, dial, args.out, log=lambda s: print(s, flush=True))
    report(result)


if __name__ == "__main__":
    main()
