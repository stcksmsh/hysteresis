#!/usr/bin/env python3
"""Check 3 of docs/EMOTION.md stage 3 / docs/NEXT_DECODER_THEN_BRAIN.md D2, as made operational by the
overseer's note ("check 3 made operational", 2026-10-28) and the user's note (anchors).

Written and committed before any result it scores; when committed it has never been run on real data.

What is scored
  Segments   8 s windows (16 steps of the 0.5 s grid), non-overlapping from the start of each clip, a trailing
             partial window dropped, from DEAM 2013/14, Emotify, the 43 MERP songs and the user's 3 songs.
             A segment's mood is the mean of the lanes over its window.
  Folds      the five folds by song of check1b.py (DEAM, Emotify, MERP as there). The user's 3 songs are a
             sixth set: never in any training set, scored beside the five folds, never in their mean.
  Mood       mindState lanes (mood.py): mood.energy (ridge direction on DEAM + MERP arousal), mood.power (ridge
             direction on Emotify "power"), mood.rest (PCA of what is left, k rest lanes), 8 s causal smoothing,
             fixed 0..1 scaling; everything fitted on the training folds only.
  Motion     the decoded 15-dim body vector rendered by body.rs with 3 fixed seeds (render.SEEDS), each clip on
             the existing stretch ladder; the segment's descriptors are the mean of the 3 clips' 37
             descriptors, standardised with the mean and standard deviation of the rendered training segments
             (1,000 random training segments of the same map and fold). A segment whose body is still
             infeasible for any of the 3 seeds after the ladder is a failed segment: left out of that map's
             distances, counted, reported.
  Distances  Euclidean on the mood lanes standardised on the training segments, and on the standardised
             descriptors. Spearman rank correlation of the two upper triangles (rsa.py) per held-out fold,
             then the mean over the five folds.
  Gates      1. Shuffle: the observed mean over folds beats 99 % of 1,000 permuted means (each fold's pairing of
                segments permuted, seeded; pass if at least 990 of the 1,000 are below the observed value).
             2. Baseline: the same map fitted to the 49-dim baseline encoding (same lane construction on its
                first 49 columns, same anchors, its own k and standardisers); pass if the lower end of the
                95 % bootstrap interval (2,000 resamples over held-out songs, rsa.weighted_rhos) of the
                difference (decoder minus baseline) of the mean over folds is above 0.
             3. Energy sign: Pearson r of mood.energy (final model, smoothed lane) with the user's pass A
                energy dial, 0.5 s step means, masked spans left out, positive on each of the 3 songs.
  Reported   not gated: the library lookup (decoder.Library, stage-1 lanes) and core-2b as the mood source (the
             same map and k selection on mind.run_plain features, radius as chosen in check2b), each with its
             per-fold values and its own shuffle count; the power anchor's sign against the pass B heavy/dark
             axis on each song (the anchor is dropped, a refit without it, if the sign disagrees on 2 of 3);
             each anchor's strength on held-out songs (lane against labels, lane against its body dimensions);
             the share of failed segments per map; the sixth set's values.
  Order      A fold's lanes, map and k use that fold's training clips only. k (rest lanes) is chosen from
             (2, 4, 8, 16) by 3 inner folds over the training songs (surrogate representational similarity on the
             held-out inner fold). The final model for the sixth set and the energy sign is fitted on all five
             folds' clips.
  Saved      every held-out segment's mood, body vector, descriptors and stretches (segments_*.npz) so the
             overseer can recompute every number.

Points the notes leave open and this file fixes (listed in the handoff):
 1 Folds: gate 1 and 2 use the five folds; the sixth set is reported with its own shuffle count.
 2 Standardisation of descriptors: per map and fold, on 1,000 rendered random training segments (the library
   lookup: on all training segments, they are the 8 region renders).
 3 The baseline map's mood distances are those of its own lanes (energy, power, rest of the 49-dim encoding).
 4 Failed segments leave only that map's distance matrices; the bootstrap weights are per song, shared by both
   maps, ranks stay those of the full held-out fold.
 5 The energy sign uses the smoothed, unscaled lane of the final model; steps touching a mask or beyond the
   recording are left out (check1b._dial_steps). The power sign: r(mood.power, heavy) > 0 agrees.
 6 core-2b: ear PCA 64 and the spectral radius per fold as in check2b (radius read from check2b's results file for the
   same folds when present, else selected by check2b.select_radius); state PCA 64; features = state and ear scores.
 7 Surrogate: surrogate.py (20,000 uniform bodies, 3 seeds, 16,000 for training, held-out R^2 reported).

  python check3.py [--out DIR] [--dial DIR] [--no-core]
Reads the dial files only in main(), only when it runs.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
from dataclasses import dataclass, field

import numpy as np

import check1b as c1
import common
import decoder
import mind
import mood
import render
import rsa

SEGMENT_STEPS = 16                       # 8 s of the 0.5 s grid
SIXTH = common.N_FOLDS                   # fold index of the user's songs
N_PERM = 1000
STD_SEGMENTS = 1000
BASELINE_COLUMNS = 49
SEED_STD = 20261034
SEED_PERM = 20261035
CHECK2B_RESULTS = common.DATA / "check2b" / "results.json"
SURROGATE = common.DATA / "check3" / "surrogate.pt"
MAPS = ("decoder", "baseline49", "library", "core2b")


@dataclass
class Config:
    surrogate_path: pathlib.Path = SURROGATE
    core: bool = True
    n_perm: int = N_PERM
    n_boot: int = common.N_BOOT
    std_segments: int = STD_SEGMENTS
    fit: dict = field(default_factory=dict)             # decoder.fit_map arguments (tests shorten them)
    k_grid: tuple = decoder.K_GRID
    baseline_columns: int = BASELINE_COLUMNS            # the first columns of the stage-1 encoding are the 49-dim baseline
    renderer: object = render.render
    radius: dict = field(default_factory=dict)          # fold tag -> spectral radius, core-2b


# --------------------------------------------------------------------------- segments

def segment_table(clips):
    """[(clip index, first step)] of the whole 8 s windows of every clip."""
    return [(i, s) for i, c in enumerate(clips) for s in range(0, (len(c.x) // SEGMENT_STEPS) * SEGMENT_STEPS, SEGMENT_STEPS)]


def segment_lanes(model, feats, clips):
    """(n segments, 2 + k) mean lanes per window, and the clip key of each segment."""
    out, keys = [], []
    for c in clips:
        n = len(feats[c.key]) // SEGMENT_STEPS
        lanes = model.lanes(feats[c.key])[:n * SEGMENT_STEPS]
        out.append(lanes.reshape(n, SEGMENT_STEPS, -1).mean(axis=1))
        keys += [c.key] * n
    return (np.concatenate(out) if out else np.zeros((0, 2 + model.k))), keys


# --------------------------------------------------------------------------- fitting

def arousal_rows(train, feats):
    xs = [feats[c.key][c.rows] for c in train if c.ds in ("deam", "merp")]
    ys = [c.y[c.rows, 1] for c in train if c.ds in ("deam", "merp")]
    groups = [np.full(len(c.rows), i) for i, c in enumerate(c for c in train if c.ds in ("deam", "merp"))]
    x, y, g = np.concatenate(xs), np.concatenate(ys), np.concatenate(groups)
    keep = np.isfinite(y)
    return x[keep], y[keep], g[keep]


def power_rows(train, feats):
    emo = [c for c in train if c.ds == "emotify"]
    return (np.stack([feats[c.key][c.rows].mean(axis=0) for c in emo]),
            np.array([c.profile[common.GEMS.index("power")] for c in emo]))


def fit_mood(train, feats, source, columns=None):
    return mood.fit([feats[c.key] for c in train], arousal_rows(train, feats), power_rows(train, feats), source, columns)


def core_features(train, test, tag, cfg):
    """core-2b features of every train and test clip, everything fitted on `train` (check2b settings)."""
    import check2b
    clips = train + test
    ear = mind.fit_projector([c.x for c in train], mind.EAR_PCA)
    radius = cfg.radius.get(tag)
    if radius is None:
        radius = check2b.select_radius(train, ear, check2b.Config2b())[0]
    model = mind.MindModel(ear, radius, mind.SEED_CORE, mind.UNITS, mind.STATE_PCA, mind.REHEARSAL_PCA).fit_state(train)
    out = model.run_plain(clips)
    return {c.key: check2b.core_features(out, c) for c in clips}, radius


def prepare(train, test, feats, source, columns, surrogate, cfg, power_anchor=True):
    """Everything one map needs, from the training clips only: lanes, k, the fitted map."""
    model = fit_mood(train, feats, source, columns)
    lanes_tr, keys_tr = segment_lanes(model, feats, train)
    k, scores = decoder.choose_k(lanes_tr, keys_tr, surrogate, power_anchor, grid=cfg.k_grid, **cfg.fit)
    model = model.with_k(k)
    lanes_tr, lanes_te = lanes_tr[:, :2 + k], segment_lanes(model, feats, test)
    fitted = decoder.fit_map(lanes_tr, surrogate, power_anchor, **cfg.fit)
    return {"model": model, "k": k, "kScores": scores, "map": fitted, "lanes_tr": lanes_tr,
            "lanes_te": lanes_te[0], "keys_tr": keys_tr, "keys_te": lanes_te[1]}


def render_map(prep, tag, name, cfg):
    """Render the held-out segments and a random subset of training segments for the standardiser."""
    rng = np.random.default_rng([SEED_STD, tag, MAPS.index(name)])
    idx = np.sort(rng.permutation(len(prep["lanes_tr"]))[:cfg.std_segments])
    bodies_te = prep["map"].bodies(prep["lanes_te"])
    bodies_std = prep["map"].bodies(prep["lanes_tr"][idx])
    both = cfg.renderer(np.concatenate([bodies_te, bodies_std]))
    n = len(bodies_te)
    take = lambda a: (a[:n], a[n:])
    (ok_te, ok_std), (desc_te, desc_std), (str_te, _) = take(both["ok"]), take(both["desc"]), take(both["stretch"])
    return {"bodies": bodies_te, "ok": ok_te, "desc": desc_te, "stretch": str_te,
            "desc_mean": desc_std[ok_std].mean(axis=0), "desc_std": np.maximum(desc_std[ok_std].std(axis=0), 1e-8),
            "std_failed": int((~ok_std).sum()), "seconds": both["seconds"]}


def library_map(prep, tag, cfg, regions):
    """The baseline lookup on the decoder's stage-1 lanes: region bodies rendered once (`regions` holds them)."""
    bodies, ref_desc, region_desc = regions
    m = prep["map"]
    ref_mean, ref_std = ref_desc.mean(axis=0), np.maximum(ref_desc.std(axis=0), 1e-8)
    z_tr, z_te = m.standardised(prep["lanes_tr"]), m.standardised(prep["lanes_te"])
    lib = decoder.Library(bodies).fit(z_tr, (region_desc - ref_mean) / ref_std)
    train_desc = region_desc[lib.regions(z_tr)]
    region_te = lib.regions(z_te)
    return {"bodies": bodies[region_te], "ok": np.ones(len(z_te), bool), "desc": region_desc[region_te],
            "stretch": np.full((len(z_te), len(render.SEEDS)), np.nan),
            "desc_mean": train_desc.mean(axis=0), "desc_std": np.maximum(train_desc.std(axis=0), 1e-8),
            "std_failed": 0, "seconds": 0.0, "assignment": lib.assignment.tolist(), "assignmentScore": lib.score,
            "regionOfSegment": region_te}


def region_renders(cfg):
    bodies, ref = decoder.load_regions()
    out = cfg.renderer(bodies)
    if not out["ok"].all():
        raise RuntimeError("a region of the body study no longer renders")
    return bodies, ref, out["desc"]


# --------------------------------------------------------------------------- scoring

def map_fold(prep, rendered):
    """Mood and motion of the segments that rendered, ready for rsa: standardised on the training segments."""
    m, ok = prep["map"], rendered["ok"]
    z = m.standardised(prep["lanes_te"])[ok]
    desc_z = (rendered["desc"][ok] - rendered["desc_mean"]) / rendered["desc_std"]
    return {"z": z, "desc_z": desc_z, "songs": [k for k, o in zip(prep["keys_te"], ok) if o],
            "total": int(len(ok)), "failed": int((~ok).sum())}


def shuffle_passes(beaten, n_perm):
    """The observed value beats 99 % of the permuted means."""
    return beaten * 100 >= 99 * n_perm


def score_map(folds, n_perm, seed=SEED_PERM, keep=False):
    """Per-fold rho, their mean, 1,000 permuted means and how many of them the observed mean beats."""
    rhos, perms, kept = [], [], []
    for f, fold in enumerate(folds):
        a, b = rsa.rank_matrix(fold["z"]), rsa.rank_matrix(fold["desc_z"])
        rhos.append(rsa.rho(a, b))
        perms.append(rsa.permutation_rhos(a, b, n_perm, seed + f))
        if keep:
            kept.append((a, b))
    observed, null = float(np.mean(rhos)), np.mean(perms, axis=0)
    beaten = int((null < observed).sum())
    result = {"rhoPerFold": rhos, "rho": observed, "permutedMean": float(null.mean()), "permutedMax": float(null.max()),
              "beaten": beaten, "of": int(n_perm), "pass": shuffle_passes(beaten, n_perm),
              "failed": [f["failed"] for f in folds], "total": [f["total"] for f in folds]}
    return (result, kept) if keep else result


def bootstrap_difference(dec_folds, dec_mats, base_folds, base_mats, n_boot):
    """95 % interval of (decoder - baseline) of the mean-over-folds rho, resampling held-out songs."""
    songs = sorted({s for fold in dec_folds + base_folds for s in fold["songs"]})
    index = {s: i for i, s in enumerate(songs)}
    draws = common.bootstrap_indices(len(songs), n_boot)
    counts = np.stack([np.bincount(row, minlength=len(songs)) for row in draws], axis=1).astype(np.float64)

    def mean_rho(folds, mats):
        per = [rsa.weighted_rhos(a, b, counts[[index[s] for s in fold["songs"]]]) for fold, (a, b) in zip(folds, mats)]
        return np.mean(per, axis=0)

    diff = mean_rho(dec_folds, dec_mats) - mean_rho(base_folds, base_mats)
    lo, hi = common.interval(diff[np.isfinite(diff)])
    return {"difference": [lo, hi], "mean": float(np.nanmean(diff)), "resamples": int(n_boot), "songs": len(songs),
            "pass": bool(lo > 0)}


# ------------------------------------------------------------------- dial and anchors

def finite_corr(a, b):
    return c1.dial_correlation(a, b)


def dial_checks(lanes, dial, songs):
    """lanes {song key: (T, 2 + k) smoothed unscaled lanes of the final model}. Energy sign (gate 3) and the
    power sign against pass B (reported)."""
    energy, power = {}, {}
    for key in songs:
        d = dial[key]
        steps = len(lanes[key])
        r, n = finite_corr(lanes[key][:, 0], c1._dial_steps(d["energy10"], steps, d["masks"]))
        energy[key] = {"r": r, "steps": n, "positive": bool(r > 0)}
        if "heavy10" in d:
            r, n = finite_corr(lanes[key][:, 1], c1._dial_steps(d["heavy10"], steps, []))
            light, _ = finite_corr(lanes[key][:, 1], c1._dial_steps(d["light10"], steps, []))
            power[key] = {"rHeavy": r, "rLight": light, "steps": n, "agrees": bool(r > 0)}
        else:
            power[key] = {"note": "no pass B"}
    agree = sum(1 for v in power.values() if v.get("agrees"))
    disagree = sum(1 for v in power.values() if v.get("agrees") is False)
    return {"energy": energy, "energyPass": bool(len(energy) == len(songs) and all(v["positive"] for v in energy.values())),
            "power": power, "powerAgree": agree, "powerDisagree": disagree, "powerAnchorDropped": bool(disagree >= 2)}


def pearson(a, b):
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    ok = np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 3 or a[ok].std() == 0 or b[ok].std() == 0:
        return float("nan")
    return float(np.corrcoef(a[ok], b[ok])[0, 1])


def anchor_strength(prep, rendered, test, feats):
    """Reported: the lanes against the labels they were fitted on, and against their body dimensions (held-out)."""
    model = prep["model"]
    lab = [c for c in test if c.ds in ("deam", "merp")]
    lane_e = np.concatenate([model.smoothed(feats[c.key])[c.rows, 0] for c in lab]) if lab else np.zeros(0)
    arousal = np.concatenate([c.y[c.rows, 1] for c in lab]) if lab else np.zeros(0)
    emo = [c for c in test if c.ds == "emotify"]
    lane_p = [model.smoothed(feats[c.key])[c.rows, 1].mean() for c in emo]
    power = [c.profile[common.GEMS.index("power")] for c in emo]
    lanes, bodies = prep["lanes_te"], rendered["bodies"]
    dim = lambda name: bodies[:, decoder.DIMS.index(name)]
    return {"energyLaneVsArousal": pearson(lane_e, arousal), "powerLaneVsPower": pearson(lane_p, power),
            "energyLaneVsBody": {n: pearson(lanes[:, 0], dim(n)) for n in decoder.ANCHORS[decoder.ENERGY_LANE]},
            "powerLaneVsBody": {n: pearson(lanes[:, 1], dim(n)) for n in decoder.ANCHORS[decoder.POWER_LANE]}}


# ---------------------------------------------------------------------------- the run

def split(clips, folds, f):
    """Training and test clips of fold f: the user's songs (ds 'song') are never trained on."""
    real = [c for c in clips if c.ds != "song"]
    if f == SIXTH:
        return real, [c for c in clips if c.ds == "song"]
    return [c for c in real if folds[c.key] != f], [c for c in real if folds[c.key] == f]


def run_tag(clips, folds, tag, surrogate, cfg, regions, log=print):
    """One fold (or the sixth set): all maps. -> {map name: (prep, rendered, folddata)}, features, test."""
    train, test = split(clips, folds, tag)
    stage1 = {c.key: c.x for c in clips}
    out = {}
    prep = prepare(train, test, stage1, mood.SOURCE_STAGE1, None, surrogate, cfg)
    out["decoder"] = (prep, render_map(prep, tag, "decoder", cfg), stage1, test)
    out["library"] = (prep, library_map(prep, tag, cfg, regions), stage1, test)
    base = prepare(train, test, stage1, mood.SOURCE_BASELINE49, cfg.baseline_columns, surrogate, cfg)
    out["baseline49"] = (base, render_map(base, tag, "baseline49", cfg), stage1, test)
    if cfg.core:
        feats, radius = core_features(train, test, tag, cfg)
        cprep = prepare(train, test, feats, mood.SOURCE_CORE2B, None, surrogate, cfg)
        cprep["radius"] = radius
        out["core2b"] = (cprep, render_map(cprep, tag, "core2b", cfg), feats, test)
    log(f"tag {tag}: {len(test)} clips, {len(prep['lanes_te'])} segments, k decoder {prep['k']}, baseline {base['k']}")
    return out


def run(clips, folds, surrogate, cfg, dial=None, out_dir=None, log=print):
    start = time.time()
    regions = region_renders(cfg)
    per_tag = {}
    for tag in list(range(common.N_FOLDS)) + [SIXTH]:
        per_tag[tag] = run_tag(clips, folds, tag, surrogate, cfg, regions, log)
        log(f"tag {tag} done ({time.time() - start:.0f} s)")
        if out_dir:
            save_segments(pathlib.Path(out_dir), tag, per_tag[tag])
    results = {"maps": {}, "k": {}, "seconds": 0.0}
    names = [n for n in MAPS if n in per_tag[0]]
    mats = {}
    for name in names:
        data = [map_fold(per_tag[t][name][0], per_tag[t][name][1]) for t in range(common.N_FOLDS)]
        if name in ("decoder", "baseline49"):
            scored, kept = score_map(data, cfg.n_perm, keep=True)
            mats[name] = (data, kept)
        else:
            scored = score_map(data, cfg.n_perm)
        sixth = score_map([map_fold(per_tag[SIXTH][name][0], per_tag[SIXTH][name][1])], cfg.n_perm, seed=SEED_PERM + 99)
        results["maps"][name] = dict(scored, sixth=sixth,
                                     failedShare=float(sum(scored["failed"]) / max(sum(scored["total"]), 1)))
        results["k"][name] = [per_tag[t][name][0]["k"] for t in range(common.N_FOLDS + 1)]
        log(f"{name}: rho {scored['rho']:.4f} (per fold {np.round(scored['rhoPerFold'], 4).tolist()}), beats {scored['beaten']}/{scored['of']} "
            f"permuted means, failed {results['maps'][name]['failedShare']:.4f}")
    boot = bootstrap_difference(mats["decoder"][0], mats["decoder"][1], mats["baseline49"][0], mats["baseline49"][1], cfg.n_boot)
    results["baselineBootstrap"] = boot
    results["anchors"] = {name: {str(t): anchor_strength(per_tag[t][name][0], per_tag[t][name][1], per_tag[t][name][3], per_tag[t][name][2])
                                 for t in range(common.N_FOLDS)} for name in names if name != "library"}
    if dial is not None:
        final = per_tag[SIXTH]["decoder"]
        songs = [c.key for c in final[3]]
        lanes = {c.key: final[0]["model"].smoothed(final[2][c.key]) for c in final[3]}
        results["dial"] = dial_checks(lanes, dial, songs)
    results["pass"] = {"shuffle": results["maps"]["decoder"]["pass"], "baseline": boot["pass"],
                       "energySign": results["dial"]["energyPass"] if dial is not None else None}
    results["check3"] = bool(all(v is True for v in results["pass"].values()))
    results["seconds"] = round(time.time() - start, 1)
    if out_dir:
        out = pathlib.Path(out_dir)
        common.write_json(out / "results.json", results)
        per_tag[SIXTH]["decoder"][0]["model"].save(out / "mood_model_stage1.npz")
    return results


def save_segments(out, tag, maps):
    """Every held-out segment's mood, body vector, descriptors and stretches, per map, so every number can be recomputed."""
    out.mkdir(parents=True, exist_ok=True)
    arrays = {}
    for name, (prep, rendered, _, _) in maps.items():
        arrays[f"{name}/lanes"] = prep["lanes_te"]
        arrays[f"{name}/keys"] = np.array(prep["keys_te"])
        for part in ("bodies", "ok", "desc", "stretch", "desc_mean", "desc_std"):
            arrays[f"{name}/{part}"] = rendered[part]
    np.savez_compressed(out / f"segments_{tag}.npz", **arrays)


# ---------------------------------------------------------------------------- report

def report(results, log=print):
    for name, m in results["maps"].items():
        gate = " (gate 1)" if name == "decoder" else " (reported)"
        log(f"{name}{gate}: mean rho {m['rho']:.4f}, per fold {np.round(m['rhoPerFold'], 4).tolist()}; beats {m['beaten']} of {m['of']} permuted means "
            f"(permuted mean {m['permutedMean']:.4f}, max {m['permutedMax']:.4f}) -> {'PASS' if m['pass'] else 'FAIL'}; "
            f"failed segments {sum(m['failed'])} of {sum(m['total'])}; sixth set rho {m['sixth']['rhoPerFold'][0]:.4f}, "
            f"beats {m['sixth']['beaten']} of {m['sixth']['of']}")
    b = results["baselineBootstrap"]
    log(f"gate 2 decoder minus baseline49: mean {b['mean']:.4f}, 95 % interval [{b['difference'][0]:.4f}, {b['difference'][1]:.4f}] over {b['songs']} songs -> "
        f"{'PASS' if b['pass'] else 'FAIL'}")
    if "dial" in results:
        d = results["dial"]
        for key, v in d["energy"].items():
            log(f"gate 3 energy sign {key}: r {v['r']:.3f} over {v['steps']} steps -> {'positive' if v['positive'] else 'NOT positive'}")
        log(f"gate 3: {'PASS' if d['energyPass'] else 'FAIL'}")
        for key, v in d["power"].items():
            log(f"power sign {key} (reported): " + (f"r heavy {v['rHeavy']:.3f}, r light {v['rLight']:.3f}, {'agrees' if v['agrees'] else 'disagrees'}" if "rHeavy" in v else v["note"]))
        log(f"power anchor: agrees on {d['powerAgree']}, disagrees on {d['powerDisagree']} -> {'DROP' if d['powerAnchorDropped'] else 'keep'}")
    log("anchor strength per fold (reported): " + json.dumps(results["anchors"]["decoder"]))
    log("CHECK 3: " + ("PASS" if results["check3"] else "FAIL") + "  " + json.dumps(results["pass"]))


def load_corpus():
    world = c1.load_real()
    clips = world.deam + world.emotify + world.merp + world.songs
    folds = dict(world.folds)
    folds.update({c.key: SIXTH for c in world.songs})
    return clips, folds, world


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(common.DATA / "check3"))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    parser.add_argument("--no-core", action="store_true")
    args = parser.parse_args(argv)
    cfg = Config(core=not args.no_core)
    if CHECK2B_RESULTS.exists():
        chosen = json.loads(CHECK2B_RESULTS.read_text())["chosen"]
        cfg.radius = {**{f: chosen[str(f)]["radius"] for f in range(common.N_FOLDS)}, SIXTH: chosen["all"]["radius"]}
    render.build()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} perm={SEED_PERM} std={SEED_STD} "
          f"render={render.SEEDS} map={decoder.SEED_MAP}", flush=True)
    clips, folds, world = load_corpus()
    print(f"DEAM {len(world.deam)}, Emotify {len(world.emotify)}, MERP {len(world.merp)}, songs {len(world.songs)}; "
          f"{len(segment_table(clips))} segments", flush=True)
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    surrogate = decoder.Surrogate.load(cfg.surrogate_path)
    results = run(clips, folds, surrogate, cfg, dial, args.out, log=lambda s: print(s, flush=True))
    report(results)


if __name__ == "__main__":
    main()
