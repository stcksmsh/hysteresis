#!/usr/bin/env python3
"""Check 2b of docs/NEXT_BODY_THEN_MIND.md ("Round 1 result and step 2b"): does the round-1 core without any
rehearsal follow feeling inside a song better than stage 1's memoryless encoding once both get the same
smoothing and delay?

Written and committed before it ran; it has never been run on real data when committed. The rules are those of
the note. In short:

Core: round 1's reservoir (mind.py) with no rehearsal pass and no rehearsal input; ridge readouts on the mind
state PCA 64 concatenated with the ear PCA 64. Reference: stage 1's pick (2,665 per 0.5 s) read by a memoryless
ridge. Both prediction series go through a causal exponential smoother with time constant tau, then a delay L
(smoothing.py); tau in {0, 0.5, 1, 2, 4, 8, 16, 32} s, L in {0, 0.5, ..., 4} s, chosen per outer fold by inner-fold
within-song arousal r on the training songs only, separately for the core and the reference. Folds, seeds,
bootstrap, MERP labels and the 43 songs, the radius grid and the DEAM-only gate-2 readouts as in check1b.py.
  A1 (diagnostic) within-song arousal r, core against the smoothed reference, DEAM and MERP each: the core's
     lower 95 % bound above the smoothed reference's upper bound.
  A2 (diagnostic) as round-1 gate 2.      A3 (diagnostic) as round-1 gate 3, on the core.
  B  (the decision) on the three songs, readouts fitted on all DEAM and the 43 MERP songs, tau and L chosen by inner
     folds over those songs: Pearson r of the arousal readout with the user's pass A (round-1 gate 5 handling),
     core against smoothed reference, core ahead on at least 2 of 3. Also reported: the plain reference, the core
     before smoothing, round 1's numbers, round 1's two fixed tests for the new core, pass B.
Outcome: A1 and B pass -> the step-2b core is the stage-3 encoding; A1 fails -> the stage-1 encoding with the chosen
smoothing; A1 passes and B fails -> the user decides. One run.

Points the note leaves open and this file fixes (listed in the handoff, to be ruled on):
 1 The smoother starts at the first prediction and the first L seconds of the delayed series repeat its first value;
   it runs over the whole step series of a song, read at the scored rows. The chosen tau, L apply to valence too.
 2 Order of choices inside a fold: spectral radius first, by inner-fold within-song arousal r of the core without
   smoothing (mean of the DEAM and MERP means, as in check1b); then tau and L for the core and for the reference by
   the same score with the smoothing applied. Inner-fold ridges reuse the penalty chosen on the whole training fold.
 3 A2 and A3 use the core's unsmoothed predictions. A3 shuffles the steps (ear input and labels together, the
   history scrambled) and the readout still receives the step's own ear scores.
 4 Gate B uses the smoothed core and smoothed reference chosen on all DEAM + MERP songs. Round 1's numbers are read
   from CHECK1B_RESULTS when that file exists.
 5 Valence, A1 and pass B use the same tau and L as arousal.

  python check2b.py [--out DIR] [--dial DIR]
Reads the dial files only in main(), only when it runs.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import time
import zlib
from dataclasses import dataclass

import numpy as np

import check1b as c1
import common
import mind
import smoothing
from check1b import Ridge, boot_mean, within_r

CHECK1B_RESULTS = common.DATA / "check1b" / "results.json"


@dataclass
class Config2b(c1.Config):
    taus: tuple = smoothing.TAUS
    lags: tuple = smoothing.LAGS


# ------------------------------------------------------------------ features

def core_features(out, clip):
    """Readout input of the step-2b core: mind state PCA 64 and ear PCA 64, side by side."""
    return np.concatenate([out[clip.key]["state"], out[clip.key]["ear"]], axis=1)


def _rows(clips, source):
    """(X, Y, groups) of the labelled rows; source(clip) -> (T, d)."""
    ids = {c.key: i for i, c in enumerate(clips)}
    xs, ys, gs = [], [], []
    for c in clips:
        xs.append(source(c)[c.rows])
        ys.append(c.y[c.rows])
        gs.append(np.full(len(c.rows), ids[c.key]))
    return np.concatenate(xs), np.concatenate(ys), np.concatenate(gs)


def _inner_split(clips):
    rng = np.random.default_rng(common.SEED_INNER)
    which = dict(zip(rng.permutation([c.key for c in clips]), np.arange(len(clips)) % 3))
    return [([c for c in clips if which[c.key] != k], [c for c in clips if which[c.key] == k]) for k in range(3)]


def _score(per_ds):
    """The inner-fold criterion: mean of the DEAM and MERP means of within-song arousal r."""
    return float(np.mean([np.mean(v) if v else 0.0 for v in per_ds.values()]))


def inner_predictions(labelled, source, alpha):
    """Held-out (inner fold) predictions at every step of every labelled training song."""
    pred = {}
    for tr, va in _inner_split(labelled):
        ridge = Ridge(*_rows(tr, source), alpha=alpha)
        for c in va:
            pred[c.key] = ridge(source(c))
    return pred


def choose_smoothing(labelled, pred, cfg):
    """(tau, L, score) maximising the inner-fold score; ties go to smaller tau, then smaller L."""
    best = None
    for tau in cfg.taus:
        for lag in cfg.lags:
            per_ds = {"deam": [], "merp": []}
            for c in labelled:
                r = within_r(smoothing.smooth_delay(pred[c.key][:, 1], tau, lag)[c.rows], c.y[c.rows, 1])
                if np.isfinite(r):
                    per_ds[c.ds].append(r)
            score = _score(per_ds)
            if best is None or score > best[2]:
                best = (tau, lag, score)
    return best


def select_radius(train, ear, cfg):
    labelled = [c for c in train if c.ds in ("deam", "merp")]
    splits = _inner_split(labelled)
    scores = {}
    for radius in cfg.sr_grid:
        model = mind.MindModel(ear, radius, mind.SEED_CORE, cfg.units, cfg.state_k, cfg.rehearsal_k).fit_state(train)
        out = model.run_plain(labelled)
        source = lambda c, out=out: core_features(out, c)
        per_ds = {"deam": [], "merp": []}
        for tr, va in splits:
            ridge = Ridge(*_rows(tr, source))
            for c in va:
                r = within_r(ridge(source(c)[c.rows])[:, 1], c.y[c.rows, 1])
                if np.isfinite(r):
                    per_ds[c.ds].append(r)
        scores[radius] = _score(per_ds)
    return max(cfg.sr_grid, key=lambda r: (scores[r], -r)), scores


def fit_2b(train, cfg):
    """Everything fitted on `train` clips only: ear PCA, radius, state PCA, ridge readouts, tau and L."""
    ear = mind.fit_projector([c.x for c in train], cfg.ear_k)
    radius, scores = select_radius(train, ear, cfg)
    model = mind.MindModel(ear, radius, mind.SEED_CORE, cfg.units, cfg.state_k, cfg.rehearsal_k).fit_state(train)
    out = model.run_plain(train)
    lab = [c for c in train if c.ds in ("deam", "merp")]
    deam = [c for c in train if c.ds == "deam"]
    emo = [c for c in train if c.ds == "emotify"]
    core_src, ref_src = (lambda c: core_features(out, c)), (lambda c: c.x)
    emo_y = np.stack([c.profile for c in emo])
    emo_g = np.arange(len(emo))
    readouts = {
        "va_core": Ridge(*_rows(lab, core_src)), "va_ref": Ridge(*_rows(lab, ref_src)),
        "va_core_deam": Ridge(*_rows(deam, core_src)), "va_ref_deam": Ridge(*_rows(deam, ref_src)),
        "gems_core": Ridge(np.stack([core_src(c)[c.rows].mean(axis=0) for c in emo]), emo_y, emo_g),
        "gems_ref": Ridge(np.stack([c.x[c.rows].mean(axis=0) for c in emo]), emo_y, emo_g),
    }
    chosen = {}
    for name, source in (("core", core_src), ("ref", ref_src)):
        pred = inner_predictions(lab, source, readouts["va_" + name].alpha)
        chosen[name] = choose_smoothing(lab, pred, cfg)
    return {"model": model, "readouts": readouts, "radius": radius, "radiusScores": scores,
            "smoothing": {k: {"tau": v[0], "lag": v[1], "innerScore": v[2]} for k, v in chosen.items()}}


def predict(fit, clips):
    """Held-out predictions at every step. -> {key: {...}}; Emotify entries hold the 9-vector of the clip mean."""
    out = fit["model"].run_plain(clips)
    r, s = fit["readouts"], fit["smoothing"]
    result = {}
    for c in clips:
        feats = core_features(out, c)
        entry = {}
        if c.ds in ("deam", "merp", "song"):
            entry["core"], entry["ref"] = r["va_core"](feats), r["va_ref"](c.x)
            for name in ("core", "ref"):
                entry[name + "_s"] = smoothing.smooth_delay(entry[name], s[name]["tau"], s[name]["lag"])
        if c.ds == "deam":
            entry["core_deam"], entry["ref_deam"] = r["va_core_deam"](feats), r["va_ref_deam"](c.x)
        if c.ds in ("emotify", "song"):
            rows = c.rows if c.ds == "emotify" and c.rows is not None else slice(None)
            if c.ds == "emotify":
                entry["gems_core"] = r["gems_core"](feats[rows].mean(axis=0, keepdims=True))[0]
                entry["gems_ref"] = r["gems_ref"](c.x[rows].mean(axis=0, keepdims=True))[0]
            else:
                entry["gems_core"] = r["gems_core"](feats)
        result[c.key] = entry
    return result


def shuffled_predictions(fit, labelled):
    """A3: unsmoothed core predictions at the scored rows after one seeded shuffle per song."""
    orders = {c.key: np.random.default_rng([mind.SEED_SHUFFLE, zlib.crc32(c.key.encode())]).permutation(len(c.x)) for c in labelled}
    out = fit["model"].run_plain(labelled, orders)
    pred = {}
    for c in labelled:
        inverse = np.argsort(orders[c.key])
        pred[c.key] = fit["readouts"]["va_core"](core_features(out, c)[inverse[c.rows]])
    return pred


# ----------------------------------------------------------------------- gates

def gate_a1(collected, world, cfg):
    result = {}
    for ds, clips in (("deam", world.deam), ("merp", world.merp)):
        rows = np.array([[within_r(collected[c.key][m][c.rows, j], c.y[c.rows, j])
                          for j in (1, 0) for m in ("core_s", "ref_s", "core", "ref")] for c in clips])
        keep = np.isfinite(rows).all(axis=1)
        stats = [boot_mean(rows[keep, i], cfg.n_boot) for i in range(8)]
        names = ("core_smoothed", "reference_smoothed", "core", "reference")
        result[ds] = {"songs": int(keep.sum()), "songsDropped": int((~keep).sum()),
                      "arousal": dict(zip(names, stats[:4])), "valence": dict(zip(names, stats[4:])),
                      "pass": bool(stats[0][0] > stats[1][0] and stats[0][1][0] > stats[1][1][1])}
    result["pass"] = bool(result["deam"]["pass"] and result["merp"]["pass"])
    return result


def gate_a2(collected, world, cfg):
    rows = {}
    for c in world.deam:
        rows[c.key] = {"core_deam": collected[c.key]["core_deam"][c.rows], "ref_deam": collected[c.key]["ref_deam"][c.rows]}
    for c in world.emotify:
        rows[c.key] = {"core": collected[c.key]["gems_core"], "ref": collected[c.key]["gems_ref"]}
    result = c1.gate2(rows, world, cfg)
    result["reference"] = c1.gate2_reference(rows, world)
    return result


def gate_a3(collected, shuffled, world, cfg):
    rows = {c.key: {"core": collected[c.key]["core"][c.rows]} for c in world.deam + world.merp}
    return c1.gate3(rows, shuffled, world, cfg)


def gate_b(song_pred, dial, world, round1):
    """The decision. c1.gate5 with the smoothed core and the smoothed reference; extras beside it."""
    song_out = {k: {"va_core": p["core_s"], "va_ref": p["ref_s"], "gems_core": p["gems_core"]} for k, p in song_pred.items()}
    result = c1.gate5(song_out, dial, world)
    by_key = {c.key: c for c in world.songs}
    for key, entry in result["songs"].items():
        if "core" not in entry:
            continue
        steps = len(by_key[key].x)
        dial_steps = c1._dial_steps(dial[key]["energy10"], steps, dial[key]["masks"])
        entry["coreUnsmoothed"] = c1.dial_correlation(song_pred[key]["core"][:, 1], dial_steps)[0]
        entry["referencePlain"] = c1.dial_correlation(song_pred[key]["ref"][:, 1], dial_steps)[0]
        if round1:
            entry["round1Core"] = round1["gate5"]["songs"][key]["core"]
            entry["round1Reference"] = round1["gate5"]["songs"][key]["reference"]
    result["round1"] = bool(round1)
    return result


# ------------------------------------------------------------------ the check

def outcome(a1, b):
    if a1 and b:
        return "A1 and B pass: the step-2b core is the encoding for stage 3"
    if not a1:
        return "A1 fails: the stage-1 encoding with the chosen smoothing is the encoding for stage 3, memory claim dropped"
    return "A1 passes and B fails: report, the user decides"


def run(world, dial, cfg, out_dir=None, round1=None, log=print):
    start = time.time()
    clips = world.deam + world.emotify + world.merp
    collected, shuffled, chosen = {}, {}, {}
    for f in range(common.N_FOLDS):
        train = [c for c in clips if world.folds[c.key] != f]
        test = [c for c in clips if world.folds[c.key] == f]
        fit = fit_2b(train, cfg)
        collected.update(predict(fit, test))
        shuffled.update(shuffled_predictions(fit, [c for c in test if c.ds in ("deam", "merp")]))
        chosen[str(f)] = {"radius": fit["radius"], "radiusScores": {str(k): v for k, v in fit["radiusScores"].items()},
                          "smoothing": fit["smoothing"]}
        log(f"fold {f}: radius {fit['radius']}, core tau/L {fit['smoothing']['core']['tau']}/{fit['smoothing']['core']['lag']}, "
            f"reference tau/L {fit['smoothing']['ref']['tau']}/{fit['smoothing']['ref']['lag']} ({time.time() - start:.0f}s)")
    fit = fit_2b(clips, cfg)
    chosen["all"] = {"radius": fit["radius"], "radiusScores": {str(k): v for k, v in fit["radiusScores"].items()},
                     "smoothing": fit["smoothing"]}
    log(f"final model: radius {fit['radius']}, core tau/L {fit['smoothing']['core']['tau']}/{fit['smoothing']['core']['lag']}, "
        f"reference tau/L {fit['smoothing']['ref']['tau']}/{fit['smoothing']['ref']['lag']}")
    song_pred = predict(fit, world.songs)

    results = {"A1": gate_a1(collected, world, cfg), "A2": gate_a2(collected, world, cfg),
               "A3": gate_a3(collected, shuffled, world, cfg), "B": gate_b(song_pred, dial, world, round1)}
    results["pass"] = {"A1": results["A1"]["pass"], "B": results["B"]["dial"]["pass"]}
    a1, b = results["A1"]["pass"], results["B"]["dial"]["pass"]
    results["outcome"] = outcome(a1, b)
    results["chosen"] = chosen
    results["world"] = {"deam": len(world.deam), "emotify": len(world.emotify), "merp": len(world.merp), **world.info}
    results["seconds"] = round(time.time() - start, 1)
    if out_dir:
        out = pathlib.Path(out_dir)
        common.write_json(out / "results.json", results)
        common.write_json(out / "folds.json", world.folds)
        save_predictions(out, world, collected, song_pred, dial)
    return results


def save_predictions(out, world, collected, song_pred, dial):
    """Per-song predictions so every gate can be recomputed without rerunning: held-out folds and the three songs."""
    held = {}
    for c in world.deam + world.merp:
        p = collected[c.key]
        held[f"{c.key}/rows"], held[f"{c.key}/y"] = c.rows, c.y
        for name in ("core", "core_s", "ref", "ref_s"):
            held[f"{c.key}/{name}"] = p[name].astype(np.float32)
    np.savez_compressed(out / "predictions_heldout.npz", **held)
    songs = {}
    for c in world.songs:
        p = song_pred[c.key]
        for name in ("core", "core_s", "ref", "ref_s", "gems_core"):
            songs[f"{c.key}/{name}"] = p[name].astype(np.float32)
        if "energy10" in dial[c.key]:
            songs[f"{c.key}/dial_steps"] = c1._dial_steps(dial[c.key]["energy10"], len(c.x), dial[c.key]["masks"])
    np.savez_compressed(out / "predictions_songs.npz", **songs)


def report(results, log=print):
    def ci(v):
        return f"{v[0]:.3f} [{v[1][0]:.3f}, {v[1][1]:.3f}]"
    a1 = results["A1"]
    for ds in ("deam", "merp"):
        d = a1[ds]
        log(f"A1 {ds}: {d['songs']} songs ({d['songsDropped']} dropped); within-song arousal r core smoothed {ci(d['arousal']['core_smoothed'])}, "
            f"reference smoothed {ci(d['arousal']['reference_smoothed'])}; core unsmoothed {ci(d['arousal']['core'])}, "
            f"reference plain {ci(d['arousal']['reference'])}; valence core smoothed {ci(d['valence']['core_smoothed'])}, "
            f"reference smoothed {ci(d['valence']['reference_smoothed'])} -> {'PASS' if d['pass'] else 'FAIL'}")
    log(f"A1: {'PASS' if a1['pass'] else 'FAIL'}")
    g2 = results["A2"]
    log(f"A2 timing R2 {g2['timing']['value']:.3f} [{g2['timing']['ci'][0]:.3f}, {g2['timing']['ci'][1]:.3f}] vs stage 1 lower bound "
        f"{g2['timing']['stage1'][1]} -> {'PASS' if g2['timing']['pass'] else 'FAIL'}; Emotify rank corr {g2['rho']['value']:.3f} "
        f"[{g2['rho']['ci'][0]:.3f}, {g2['rho']['ci'][1]:.3f}] vs {g2['rho']['stage1'][1]} -> {'PASS' if g2['rho']['pass'] else 'FAIL'}; "
        f"reference here: timing {g2['reference']['timing']:.3f}, rank corr {g2['reference']['rho']:.3f}")
    log(f"A2: {'PASS' if g2['pass'] else 'FAIL'}")
    g3 = results["A3"]
    for ds in ("deam", "merp"):
        d = g3[ds]
        log(f"A3 {ds}: {d['songs']} songs; r {ci(d['rOriginal'])} -> shuffled {ci(d['rShuffled'])} -> {'PASS' if d['pass'] else 'FAIL'}")
    log(f"A3: {'PASS' if g3['pass'] else 'FAIL'}")
    b = results["B"]
    for key, e in b["songs"].items():
        if "core" not in e:
            log(f"B {e['title']}: {e.get('note')}")
            continue
        extra = f"; round 1 core {e['round1Core']:.3f}, reference {e['round1Reference']:.3f}" if "round1Core" in e else ""
        log(f"B {e['title']}: {e['steps']} steps, r core smoothed {e['core']:.3f}, reference smoothed {e['reference']:.3f}; "
            f"core unsmoothed {e['coreUnsmoothed']:.3f}, reference plain {e['referencePlain']:.3f}{extra}")
        if "passB" in e:
            log("  pass B (reported): " + ", ".join(f"{k} {v:.3f}" for k, v in e["passB"].items()))
    fy, pr = b["fiveYears"], b["presence"]
    log(f"fixed tests (reported): Five Years opening {fy['opening']:.3f} climax {fy['climax']:.3f}; Presence sadness rank {pr['sadnessRank']} of 9, "
        f"span {pr['sadnessSpan']:.3f}, rest {pr['sadnessRest']:.3f}")
    log(f"B: core ahead on {b['dial']['wins']} of 3 -> {'PASS' if b['dial']['pass'] else 'FAIL'}")
    log(f"OUTCOME: {results['outcome']}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(common.DATA / "check2b"))
    parser.add_argument("--dial", default=str(common.DATA / "dial"))
    args = parser.parse_args(argv)
    cfg = Config2b()
    print(f"seeds: folds={common.SEED_FOLDS} bootstrap={common.SEED_BOOTSTRAP} inner={common.SEED_INNER} core={mind.SEED_CORE} "
          f"shuffle={mind.SEED_SHUFFLE}; tau {cfg.taus}, L {cfg.lags}", flush=True)
    world = c1.load_real()
    print(f"DEAM {len(world.deam)}, Emotify {len(world.emotify)}, MERP {len(world.merp)} clips", flush=True)
    dial = c1.load_dial(pathlib.Path(args.dial) / "dial2.json", pathlib.Path(args.dial) / "dial-ic-try1.json")
    round1 = json.loads(CHECK1B_RESULTS.read_text()) if CHECK1B_RESULTS.exists() else None
    pathlib.Path(args.out).mkdir(parents=True, exist_ok=True)
    results = run(world, dial, cfg, args.out, round1, log=lambda s: print(s, flush=True))
    report(results)


if __name__ == "__main__":
    main()
