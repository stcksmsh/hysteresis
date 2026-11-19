"""Check K1 (docs/BODY_BRAIN_PLAN.md §5, BRAIN_SPEC §7.13 D3). Committed before the model is trained.

    /secondary/hyst-env/brain/bin/python check_m1.py BUNDLE.pt HELD.npz V47.npz OUT.json

Claim if it passes: "It predicts where its own arm will be a moment from now." Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor
inertia, damping 1.5, acceleration share 0.25): the claim is about this simulated arm.

Scores (cerebellum.evaluate): per unit (trajectory / segment), mean over scored steps and the 15 proprioceptive dimensions, at +10, +50, +100 ms,
of the Gaussian NLL and the MSE of the predicted change, in standardised units; scored steps = chunk step >= 20 (GRU warm-up) with k + 10 < T.
Persistence = zero change with a constant per-dimension variance fitted on the training babbling; ridge = alpha 1.0 on the same inputs, same variance rule.

The two sets are scored separately.
  * held-out babbling: 120 independent 60 s trajectories (own seed, own start pose); units = trajectories; bootstrap over trajectories.
  * v47: 78 whole 60 s segments of the 18 arm trajectories (3 danced songs x 6 hexagon arms) replayed in physics as servo targets; two-level
    bootstrap, arms within song then segments within arm, the 3 songs held fixed; the statistic is the mean over songs of the song mean.
    The interval is conditional on these three songs, and arms in unison or mirrored formations are near-duplicates.
  10,000 resamples, 95 % percentile interval, fixed seed.

For each set and each horizon:
  NLL condition: the lower end of the interval of (baseline NLL - model NLL) is above 0, for persistence and for ridge.
  MSE condition: the model's mean MSE is at least 5 % below the lower of the two baselines' mean MSE (point estimate on the set; interval reported).
K1 passes only if every condition holds on both sets at all three horizons (+10, +50, +100 ms).
"""
import json
import sys

import numpy as np
import torch

import cerebellum as C

RESAMPLES = 10000
SEED = 20261104
NAMES = ("model", "ridge", "persistence")


def unit_scores(net, st, ridge, pvar, npz):
    d = np.load(npz)
    X, (Y, V) = C.features(d["obs"], d["tgt"], st), C.labels(d["obs"], st)
    return C.evaluate(net, X, Y, V, ridge, pvar), d



def boot_babbling(arrs, rng):
    n = len(next(iter(arrs.values())))
    idx = rng.integers(0, n, (RESAMPLES, n))
    return {k: v[idx].mean(1) for k, v in arrs.items()}


def boot_v47(arrs, meta, rng):
    """Songs fixed; per song resample its arms with replacement, then each chosen arm's segments with replacement; statistic = mean over songs."""
    out = {k: np.zeros((RESAMPLES,) + v.shape[1:]) for k, v in arrs.items()}
    songs = sorted(set(meta[:, 0]))
    for s in songs:
        arms = sorted(set(meta[meta[:, 0] == s, 1]))
        segs = {a: np.where((meta[:, 0] == s) & (meta[:, 1] == a))[0] for a in arms}
        acc = {k: np.zeros((RESAMPLES,) + v.shape[1:]) for k, v in arrs.items()}
        for r in range(RESAMPLES):
            chosen = rng.choice(arms, len(arms))
            per_arm = []
            for a in chosen:
                idx = rng.choice(segs[a], len(segs[a]))
                per_arm.append({k: v[idx].mean(0) for k, v in arrs.items()})
            for k in arrs:
                acc[k][r] = np.mean([p[k] for p in per_arm], 0)
        for k in arrs:
            out[k] += acc[k] / len(songs)
    return out


def verdict(ev, boot, point):
    """ev: evaluate() output. Returns per-horizon dict and overall bool."""
    res, ok = {}, True
    for h, name in enumerate(C.HNAMES):
        r = {}
        for base in ("persistence", "ridge"):
            d = boot[f"{base}_nll"][:, h] - boot["model_nll"][:, h]
            lo, hi = float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))
            r[f"nll_gain_vs_{base}"] = {"mean": float(point[f"{base}_nll"][h] - point["model_nll"][h]), "lo": lo, "hi": hi, "pass": lo > 0}
        base_mse = {b: point[f"{b}_mse"][h] for b in ("persistence", "ridge")}
        best = min(base_mse, key=base_mse.get)
        red = 1 - point["model_mse"][h] / base_mse[best]
        rb = 1 - boot["model_mse"][:, h] / np.minimum(boot["persistence_mse"][:, h], boot["ridge_mse"][:, h])
        r["mse"] = {"model": float(point["model_mse"][h]), "persistence": float(base_mse["persistence"]), "ridge": float(base_mse["ridge"]),
                    "better_baseline": best, "reduction": float(red), "reduction_lo": float(np.percentile(rb, 2.5)),
                    "reduction_hi": float(np.percentile(rb, 97.5)), "pass": bool(red >= 0.05)}
        r["pass"] = all(r[k]["pass"] for k in ("nll_gain_vs_persistence", "nll_gain_vs_ridge", "mse"))
        ok &= r["pass"]
        res[name] = r
    return res, bool(ok)


def run(bundle, held, v47, out):
    torch.set_num_threads(12)
    net, st, ridge, pvar = C.load_bundle(bundle)
    rng = np.random.default_rng(SEED)
    report, allok = {}, True
    for label, path in (("held_out_babbling", held), ("v47", v47)):
        ev, d = unit_scores(net, st, ridge, pvar, path)
        arrs = {f"{n}_{m}": ev[n][m] for n in NAMES for m in ("nll", "mse")}
        point = {k: v.mean(0) if label == "held_out_babbling" else None for k, v in arrs.items()}
        if label == "held_out_babbling":
            boot = boot_babbling(arrs, rng)
        else:
            meta = d["meta"]
            boot = boot_v47(arrs, meta, rng)
            point = {k: np.mean([v[meta[:, 0] == s].mean(0) for s in sorted(set(meta[:, 0]))], 0) for k, v in arrs.items()}
        res, ok = verdict(ev, boot, point)
        report[label] = {"units": int(len(next(iter(arrs.values())))), "horizons": res, "pass": ok,
                         "mean_nll": {n: point[f"{n}_nll"].tolist() for n in NAMES}, "mean_mse": {n: point[f"{n}_mse"].tolist() for n in NAMES}}
        allok &= ok
    report["K1_pass"] = bool(allok)
    report["resamples"], report["seed"] = RESAMPLES, SEED
    json.dump(report, open(out, "w"), indent=1)
    print(json.dumps({k: (v if k == "K1_pass" else {"pass": v["pass"], "mean_nll": v["mean_nll"], "mean_mse": v["mean_mse"]})
                      for k, v in report.items() if k in ("K1_pass", "held_out_babbling", "v47")}, indent=1))
    return report


if __name__ == "__main__":
    run(*sys.argv[1:5])
