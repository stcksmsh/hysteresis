"""The spread requirement A3 of docs/NEXT_DECODER_THEN_BRAIN.md (rule note 2026-10-29), fixed before results.

Region of a phrase: its body is rendered by body.rs with the 3 check-3 seeds (render.render), the mean of the
37 descriptors is ranked against the r6 sweep (midrank, `body_regions::rank`: (below + half the equal) / N per
descriptor), and the region is the nearest, in Euclidean distance, of the 8 region positions (the mean of a
region's 12 clips' midrank vectors, r6/regions.json "m"). The distance to it is reported.

Rules, per song, on the phrase bodies:
  1  the phrases visit at least 2 regions;
  2  no two songs share their most-visited region (a tie for most visited counts as sharing when the tied sets meet);
  3  for each of the 15 dimensions, the share of phrases with the value within 0.05 of 0 or 1 is at most 20 %.
A phrase whose body still fails the stretch ladder has no descriptors, so no region: it is counted, and left
out of the region counts only (rule 3 reads every phrase's body).
"""
from __future__ import annotations

import json
import pathlib

import numpy as np

import render

STUDY = pathlib.Path("/secondary/hyst-data/bodystudy/r6")
MIN_REGIONS = 2
EDGE = 0.05
MAX_SHARE = 0.20


def load_study(study=STUDY):
    """-> (sorted sweep columns (37, N), region positions (8, 37))."""
    study = pathlib.Path(study)
    sweep = json.loads((study / "sweep.json").read_text())["clips"]
    regions = json.loads((study / "regions.json").read_text())
    sorted_cols = np.sort(np.array([c["desc"] for c in sweep], dtype=np.float64), axis=0).T
    return sorted_cols, np.array(regions["m"], dtype=np.float64)


def midrank(sorted_cols, desc):
    """(n, 37) descriptors -> (n, 37) midranks: (number of sweep values below + half the number equal) / N."""
    desc = np.asarray(desc, dtype=np.float64)
    n = sorted_cols.shape[1]
    out = np.empty_like(desc)
    for k, col in enumerate(sorted_cols):
        below = np.searchsorted(col, desc[:, k], side="left")
        equal = np.searchsorted(col, desc[:, k], side="right") - below
        out[:, k] = (below + equal / 2.0) / n
    return out


def assign(ranks, positions):
    """Nearest region position (first on a tie) and the distance to it, per row of `ranks`."""
    dist = np.linalg.norm(ranks[:, None, :] - positions[None, :, :], axis=2)
    nearest = dist.argmin(axis=1)
    return nearest, dist[np.arange(len(ranks)), nearest]


def regions_of(bodies, study, renderer=render.render):
    """bodies (n, 15) -> dict(ok, region (n,) int with -1 where not ok, distance (n,) with NaN, ranks (n, 37))."""
    sorted_cols, positions = study
    out = renderer(bodies)
    ok = out["ok"]
    region, distance = np.full(len(bodies), -1), np.full(len(bodies), np.nan)
    ranks = np.full((len(bodies), sorted_cols.shape[0]), np.nan)
    if ok.any():
        ranks[ok] = midrank(sorted_cols, out["desc"][ok])
        region[ok], distance[ok] = assign(ranks[ok], positions)
    return {"ok": ok, "region": region, "distance": distance, "ranks": ranks, "stretch": out["stretch"]}


def top_regions(regions, n_regions=8):
    """(counts, the tied most-visited regions) of one song's phrase regions (-1 = failed, not counted)."""
    counts = np.bincount(regions[regions >= 0], minlength=n_regions)
    return counts, [int(r) for r in np.flatnonzero(counts == counts.max())] if counts.max() > 0 else []


def edge_share(bodies, edge=EDGE):
    """(15,) share of the rows with the value within `edge` of 0 or 1."""
    bodies = np.asarray(bodies, dtype=np.float64)
    return ((bodies <= edge) | (bodies >= 1.0 - edge)).mean(axis=0)


def score(songs, n_regions=8):
    """songs {key: dict(region (n,) ints, -1 = failed; bodies (n, 15))} -> the three rules and the numbers behind them."""
    per = {}
    for key, s in songs.items():
        region = np.asarray(s["region"])
        counts, top = top_regions(region, n_regions)
        share = edge_share(s["bodies"])
        per[key] = {"phrases": int(len(region)), "failed": int((region < 0).sum()), "counts": counts.tolist(),
                    "visited": int((counts > 0).sum()), "mostVisited": top, "edgeShare": share.tolist(),
                    "dimensionsOver": [int(i) for i in np.flatnonzero(share > MAX_SHARE)]}
    keys = list(per)
    shared = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if set(per[a]["mostVisited"]) & set(per[b]["mostVisited"])]
    rule1 = {k: v["visited"] >= MIN_REGIONS for k, v in per.items()}
    rule3 = {k: not v["dimensionsOver"] for k, v in per.items()}
    return {"songs": per, "rule1": rule1, "rule2SharedPairs": shared, "rule2": not shared, "rule3": rule3,
            "pass": bool(all(rule1.values()) and not shared and all(rule3.values()))}
