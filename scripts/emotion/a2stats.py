#!/usr/bin/env python3
"""Statistics for A3 round 2 (docs/NEXT_DECODER_THEN_BRAIN.md, "A3 round 2"), reported and not gated.

  mood_distances   the 3 songs' mood vectors before the map: distances between song means and between phrases of
                   two songs, and within a song, in units of the corpus SD per lane (all lanes).
  paired bootstrap 95 % intervals of the difference of the rank correlation of two variants of the same segments,
                   2,000 resamples, fixed seed.
                     sixth set  segments resampled within each song (blocked by song), the same draw for both variants;
                                ranks stay those of the full set (rsa.weighted_rhos), as check3.bootstrap_difference.
                     DEAM/MERP  check3.bootstrap_difference over held-out songs, as check3r2 does.
                   Variants come from a2.py's segments_*.npz (before, after, after2) and check3r2's saved core-2b.

  python a2stats.py [--a2 DIR] [--check3r2 DIR] [--out FILE]
"""
from __future__ import annotations

import argparse
import itertools
import json
import pathlib

import numpy as np

import check3 as c3
import check3r2 as r2
import common
import rsa

N_BOOT = 2000


# ------------------------------------------------------------------------ mood vectors

def _spread(d):
    """Median and quartiles of a set of distances."""
    q1, med, q3 = np.percentile(d, [25, 50, 75])
    return {"median": float(med), "q1": float(q1), "q3": float(q3), "n": int(len(d))}


def mood_distances(corpus, phrases):
    """corpus (n, d) lanes of the public segments; phrases {song: (m, d) phrase-mean lanes}. All distances Euclidean in
    units of the corpus SD per lane. -> dict(sd, means, meanDistance {pair}, phraseDistance {pair}, within {song}, corpusPairs)."""
    corpus = np.asarray(corpus, dtype=np.float64)
    sd = corpus.std(axis=0)
    z = {k: np.asarray(v, dtype=np.float64) / sd for k, v in phrases.items()}
    dist = lambda a, b: np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    out = {"sd": sd.tolist(), "means": {k: v.mean(axis=0).tolist() for k, v in z.items()}, "meanDistance": {}, "phraseDistance": {}, "within": {}}
    for a, b in itertools.combinations(z, 2):
        out["meanDistance"][f"{a}|{b}"] = float(np.linalg.norm(z[a].mean(axis=0) - z[b].mean(axis=0)))
        out["phraseDistance"][f"{a}|{b}"] = _spread(dist(z[a], z[b]).ravel())
    for k, v in z.items():
        iu = np.triu_indices(len(v), 1)
        out["within"][k] = dict(_spread(dist(v, v)[iu]), toSongMean=_spread(np.linalg.norm(v - v.mean(axis=0), axis=1)))
    c = corpus / sd
    idx = np.random.default_rng(0).permutation(len(c))[:1500]
    out["corpusPairs"] = _spread(dist(c[idx], c[idx])[np.triu_indices(len(idx), 1)])
    return out


# --------------------------------------------------------------------------- bootstrap

def within_song_counts(songs, n_boot=N_BOOT, seed=common.SEED_BOOTSTRAP):
    """(n, n_boot) segment draw counts: for each resample, every song's segments are drawn with replacement within that song."""
    songs = np.asarray(songs)
    rng = np.random.default_rng(seed)
    counts = np.zeros((len(songs), n_boot))
    for s in sorted(set(songs.tolist())):
        idx = np.flatnonzero(songs == s)
        draws = rng.integers(0, len(idx), size=(n_boot, len(idx)))
        for r in range(n_boot):
            counts[idx, r] = np.bincount(draws[r], minlength=len(idx))
    return counts


def paired_sixth(variants, songs, n_boot=N_BOOT):
    """variants {name: (rating_rank (n, n), desc_rank (n, n), keep (n,) bool)} over the same n segments; `songs` (n,) the song of
    each. -> {name: rho on the full set} and the resampled rho per variant (n_boot,), drawn on the same counts."""
    counts = within_song_counts(songs, n_boot)
    full, boot = {}, {}
    for name, (a, b, keep) in variants.items():
        full[name] = rsa.rho(a, b)
        boot[name] = rsa.weighted_rhos(a, b, counts[keep])
    return full, boot


def difference(boot_a, boot_b):
    """Later minus earlier: mean and 95 % interval of boot_b - boot_a over the resamples that are defined."""
    d = boot_b - boot_a
    d = d[np.isfinite(d)]
    lo, hi = common.interval(d)
    return {"mean": float(d.mean()), "interval": [float(lo), float(hi)], "resamples": int(len(d))}


# --------------------------------------------------------------------------- loading

def _variant(npz, prefix, ratings):
    """Rating-based fold data of one variant of one set from a saved segments file: as check3r2.rating_fold."""
    ok = npz[f"{prefix}ok"]
    has = np.isfinite(ratings).all(axis=1)
    keep = ok & has
    desc_z = (npz[f"{prefix}desc"][keep] - npz[f"{prefix}desc_mean"]) / npz[f"{prefix}desc_std"]
    keys = np.asarray(npz["keys"] if "keys" in npz.files else npz[f"{prefix}keys"])
    return {"z": ratings[keep], "desc_z": desc_z, "songs": [str(k) for k in keys[keep]], "keep": keep, "has": has}


def build(a2_dir, check_dir):
    """-> {variant: {tag: fold data}}. 'round2' is check3r2's core-2b (power anchor kept, no fix); 'before' is power dropped, no fix;
    'after' round 1 (0.05/0.95); 'after2' round 2 (0.10/0.90)."""
    a2_dir, check_dir = pathlib.Path(a2_dir), pathlib.Path(check_dir)
    out = {"round2": {}, "before": {}, "after": {}, "after2": {}}
    for tag in list(range(common.N_FOLDS)) + [c3.SIXTH]:
        rat = np.load(check_dir / f"ratings_{tag}.npz")
        ratings = rat["dial"] if tag == c3.SIXTH else rat["va"]
        out["round2"][tag] = _variant(np.load(check_dir / f"segments_{tag}.npz"), "core2b/", ratings)
        mine = np.load(a2_dir / f"segments_{tag}.npz")
        for v in ("before", "after", "after2"):
            out[v][tag] = _variant(mine, f"{v}/", ratings)
    return out


def run(a2_dir, check_dir, n_boot=N_BOOT, log=print):
    data = build(a2_dir, check_dir)
    names = ("round2", "before", "after", "after2")
    pairs = [("round2", "before"), ("before", "after"), ("before", "after2"), ("after", "after2"), ("round2", "after2")]
    result = {"sixthDial": {"rho": {}, "differences": {}}, "deamMerp": {"rho": {}, "differences": {}}, "resamples": n_boot,
              "note": "later minus earlier; round2 = check3r2 core-2b (power kept, no fix), before = power dropped, after = + fix 0.05/0.95, after2 = + fix 0.10/0.90"}
    sixth = {n: data[n][c3.SIXTH] for n in names}
    has = sixth["before"]["has"]
    songs_all = np.array([k for k, h in zip(np.load(pathlib.Path(a2_dir) / f"segments_{c3.SIXTH}.npz")["keys"], has) if h])
    variants = {}
    for n in names:
        d = sixth[n]
        keep_in_has = d["keep"][has]
        variants[n] = (rsa.rank_matrix(d["z"]), rsa.rank_matrix(d["desc_z"]), keep_in_has)
    full, boot = paired_sixth(variants, songs_all, n_boot)
    result["sixthDial"]["rho"] = full
    for a, b in pairs:
        result["sixthDial"]["differences"][f"{b} - {a}"] = difference(boot[a], boot[b])
    folds = {n: [data[n][t] for t in range(common.N_FOLDS)] for n in names}
    mats = {n: [(rsa.rank_matrix(f["z"]), rsa.rank_matrix(f["desc_z"])) for f in folds[n]] for n in names}
    for n in names:
        result["deamMerp"]["rho"][n] = float(np.mean([rsa.rho(a, b) for a, b in mats[n]]))
    for a, b in pairs:
        r = c3.bootstrap_difference(folds[b], mats[b], folds[a], mats[a], n_boot)
        result["deamMerp"]["differences"][f"{b} - {a}"] = {"mean": r["mean"], "interval": r["difference"], "songs": r["songs"]}
    for part in ("sixthDial", "deamMerp"):
        log(f"{part} rho: " + json.dumps({k: round(v, 4) for k, v in result[part]["rho"].items()}))
        for k, v in result[part]["differences"].items():
            log(f"  {k}: mean {v['mean']:+.4f}, 95 % interval [{v['interval'][0]:+.4f}, {v['interval'][1]:+.4f}]")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a2", default=str(common.DATA / "a2b"))
    parser.add_argument("--check3r2", default=str(r2.OUT))
    parser.add_argument("--out", default=str(common.DATA / "a2b" / "stats.json"))
    args = parser.parse_args(argv)
    result = run(args.a2, args.check3r2)
    common.write_json(pathlib.Path(args.out), result)


if __name__ == "__main__":
    main()
