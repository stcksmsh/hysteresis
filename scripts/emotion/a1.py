#!/usr/bin/env python3
"""A1 of docs/NEXT_DECODER_THEN_BRAIN.md (rule note 2026-10-29): the anchors of `core-2b`, report only, no new fit of a map.

  1  The 24 held-out links of core-2b (five folds plus the sixth set; energy to energy, size, time; power to
     weight) as round 2 saved them in check3r2's results.json, each against the 0.5 of the anchor spec.
  2  For core-2b's own lanes on the user's 3 songs: Pearson r of mood.energy with dial pass A, and of
     mood.power with pass B heavy (and light), by check3.dial_checks, the code check3r2.run uses for the
     stage-1 lanes. The lanes are those of the sixth-set core-2b model: `c3.core_features` and `c3.fit_mood`
     on all five folds' clips with check3r2's settings (the same function calls as check3.run_tag; the map and
     k are not needed, the first two lanes do not depend on k). The power drop rule: sign disagrees on 2 of 3 songs.

  python a1.py [--out DIR] [--check3r2 DIR] [--dial DIR]
Reads the dial files only in main(), only through check1b.load_dial.
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
import mood

OUT = common.DATA / "a2"
THRESHOLD = 0.5
LINKS = ("energy->energy", "energy->size", "energy->time", "power->weight")


def link_table(results):
    """check3r2's results.json -> {tag: {link: held-out r}} for core-2b, the count that reach 0.5 and the misses."""
    table = {tag: {k: float(v) for k, v in links["heldOutR"].items()} for tag, links in results["maps"]["core2b"]["links"].items()}
    misses = [(tag, link, r) for tag, row in table.items() for link, r in row.items() if not r >= THRESHOLD]
    return {"table": table, "reach": sum(len(row) for row in table.values()) - len(misses), "of": sum(len(row) for row in table.values()),
            "misses": misses}


def core_final(clips, folds, cfg):
    """The sixth set's core-2b: (train clips, test clips, features of every clip, spectral radius, mood model with every rest lane)."""
    train, test = c3.split(clips, folds, c3.SIXTH)
    feats, radius = c3.core_features(train, test, c3.SIXTH, cfg)
    return train, test, feats, radius, c3.fit_mood(train, feats, mood.SOURCE_CORE2B)


def dial_report(model, feats, test, dial):
    """check3.dial_checks on core-2b's smoothed, unscaled lanes of the user's songs."""
    lanes = {c.key: model.smoothed(feats[c.key]) for c in test}
    return c3.dial_checks(lanes, dial, [c.key for c in test])


def reproduces(model, feats, test, check_dir):
    """Largest absolute difference of the first two scaled segment lanes against check3r2's saved sixth-set core-2b lanes."""
    saved = np.load(pathlib.Path(check_dir) / f"segments_{c3.SIXTH}.npz")["core2b/lanes"]
    lanes, _ = c3.segment_lanes(model.with_k(saved.shape[1] - 2), feats, test)
    return float(np.abs(lanes - saved).max()) if lanes.shape == saved.shape else None


def report(links, dial, log=print):
    log(f"core-2b links reaching held-out r {THRESHOLD}: {links['reach']} of {links['of']}")
    for tag, row in links["table"].items():
        log(f"  {'sixth set' if int(tag) == c3.SIXTH else 'fold ' + tag}: " + ", ".join(f"{k} {row[k]:.3f}" for k in LINKS))
    for tag, link, r in links["misses"]:
        log(f"  MISS {'sixth set' if int(tag) == c3.SIXTH else 'fold ' + tag} {link} {r:.3f}")
    for key, v in dial["energy"].items():
        log(f"core-2b mood.energy against pass A, {key}: r {v['r']:.3f} over {v['steps']} steps -> {'positive' if v['positive'] else 'NOT positive'}")
    for key, v in dial["power"].items():
        log(f"core-2b mood.power against pass B, {key}: " + (f"r heavy {v['rHeavy']:.3f}, r light {v['rLight']:.3f}, {'agrees' if v['agrees'] else 'disagrees'}" if "rHeavy" in v else v["note"]))
    log(f"power anchor: agrees on {dial['powerAgree']}, disagrees on {dial['powerDisagree']} -> {'DROP' if dial['powerAnchorDropped'] else 'keep'}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--check3r2", default=str(r2.OUT))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    args = parser.parse_args(argv)
    start = time.time()
    links = link_table(json.loads((pathlib.Path(args.check3r2) / "results.json").read_text()))
    cfg = r2.config()
    clips, folds, _ = c3.load_corpus()
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    _, test, feats, radius, model = core_final(clips, folds, cfg)
    result = {"links": links, "dial": dial_report(model, feats, test, dial), "radius": radius,
              "lanesMaxAbsDiffToCheck3r2": reproduces(model, feats, test, args.check3r2), "seconds": round(time.time() - start, 1)}
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    common.write_json(pathlib.Path(args.out) / "a1.json", result)
    report(links, result["dial"])
    print(f"sixth-set lanes against check3r2's saved ones: largest absolute difference {result['lanesMaxAbsDiffToCheck3r2']}; {result['seconds']} s")


if __name__ == "__main__":
    main()
