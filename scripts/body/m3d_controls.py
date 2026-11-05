"""M3d report-only controls (docs/BRAIN_SPEC.md 7.18 point 1; work order 7). No retraining, not a try. Provisional servo model (Feetech STS3215 12 V assumed).

Policies scored on the same 16 held-out episodes (same Gumbel noise, start poses and bar shifts), both choice modes:
  trained   try 1 checkpoint (reference, rescored here with the same procedure as the controls)
  (i)       untrained motor cortex: the initial weights of try 1 (Trainer seed 0), kappa as initialised
  (ii)      trained motor cortex, kappa forced to 0
  (iii)     untrained motor cortex, kappa fixed at the trained per-joint means (read from try1/result.json)
Observer procedure, identical for every policy and mode: a fresh observer (init key 0, 64 hidden) trained 600 Adam steps (final_observer's steps and seed 999) on
the 16 training episodes rolled out by THAT policy in THAT mode, 4 rollouts (Gumbel keys 100..103, start seed 100; the 4 stand in for try 1's last 4 epochs),
blocks from 2 s on, descriptors standardised with try 1's calibration statistics. Held-out: key 7, start seed 4242 (evaluate's defaults).
Paired difference: per-episode (a) gap of trained minus control (same episodes, same shifts); 95 % bootstrap interval of its mean (10,000 resamples).

    m3d_controls.py [--out DIR --ckpt try1/ckpt.pkl --toy toy.npz]     resume-safe: a policy with its json is skipped.
"""
import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3d_jax as J

D = Path("/secondary/hyst-data/body/m3d")
CHUNK = 8
MODES = ("argmax", "sample")


def initial_policy(seed=0):
    """The policy Trainer(seed) starts from."""
    _, k1, _, _ = jax.random.split(jax.random.PRNGKey(seed), 4)
    return J.init_policy(k1)


def with_kappa(P, kappa):
    """Copy of P whose kappa is the fixed (5,) vector (rad/s) instead of the cortex output."""
    return {**P, "kappa_fix": jnp.asarray(kappa, float)}


def paired_difference(gaps_trained, gaps_control):
    """Mean of the per-episode difference and its paired 95 % bootstrap interval."""
    d = np.asarray(gaps_trained) - np.asarray(gaps_control)
    return {"mean": float(d.mean()), "ci": list(m3d.boot_ci(d)), "per_episode": d.tolist()}


def final_observer(fns, P, toy, stats, mode, log):
    xs, ys = [], []
    idx = toy.sets["train"]
    yz = toy.yz[idx][:, m3d.VALID_FROM:].reshape(-1, 8)
    for k in range(4):
        r = m3d.rollout_hard(fns, P, toy, idx, mode, jax.random.PRNGKey(100 + k), CHUNK, 100)
        xs.append(m3d.std_desc(r["desc"], stats["dmu"], stats["dsd"])[:, m3d.VALID_FROM:].reshape(-1, J.N_DESC))
        ys.append(yz)
    x, y = np.concatenate(xs), np.concatenate(ys)
    O, l = m3d.train_observer(J.init_observer(jax.random.PRNGKey(0), 64), x, y, 600, seed=999)
    log(f"  observer ({mode}): {len(x)} blocks, train loss {l:.3f}")
    return O


def score(fns, P, toy, stats, log):
    out = {}
    for mode in MODES:
        O = final_observer(fns, P, toy, stats, mode, log)
        out[mode] = m3d.evaluate(fns, P, O, stats, toy, "held", CHUNK, log=log)[mode]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(D / "controls"))
    ap.add_argument("--ckpt", default=str(D / "try1/ckpt.pkl"))
    ap.add_argument("--toy", default=str(D / "toy.npz"))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    log = lambda s: print(f"[{time.time() - t0:7.0f}s] {s}", flush=True)
    toy = m3d.Toy(a.toy)
    ck = pickle.loads(Path(a.ckpt).read_bytes())
    stats = ck["stats"]
    trained = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    kap = json.loads((Path(a.ckpt).parent / "result.json").read_text())["result"]["argmax"]["kappa_mean"]
    log(f"trained per-joint kappa means (try1/result.json): {kap}")
    fns = m3d.make_fns(CHUNK)
    pols = {"trained": trained, "i_untrained": initial_policy(), "ii_trained_kappa0": with_kappa(trained, np.zeros(5)),
            "iii_untrained_kappa_trained_means": with_kappa(initial_policy(), kap)}
    for name, P in pols.items():
        f = out / f"{name}.json"
        if f.exists():
            continue
        log(f"policy {name}")
        f.write_text(json.dumps(score(fns, P, toy, stats, log), indent=1))
    res = {n: json.loads((out / f"{n}.json").read_text()) for n in pols}
    summary = {"kappa_trained_means": kap, "table": {}, "paired": {}}
    for n, r in res.items():
        summary["table"][n] = {m: {k: r[m][k] for k in ("a_gap_mean", "a_ci", "b_rms_nonroll", "c_mi", "c_null_mean", "c_p", "programs_used", "kappa_mean")} for m in MODES}
    for n in list(pols)[1:]:
        summary["paired"][n] = {m: paired_difference(res["trained"][m]["a_gaps"], res[n][m]["a_gaps"]) for m in MODES}
    (out / "summary.json").write_text(json.dumps(summary, indent=1))
    log("done")


if __name__ == "__main__":
    sys.exit(main())
