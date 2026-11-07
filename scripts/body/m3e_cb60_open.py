"""WO9 Part 1, open-loop drift check (overseer's request): the K1 round-2 cerebellum (JAX port) on 60 s babbling trajectories from its own training distribution
(held2h.npz: held out of its training, obs and tgt exactly as the M1 set), run (a) continuously over the 6,000 steps and (b) with the GRU state zeroed every 200 steps
(its training chunk length; the input ring of past targets is NOT reset). Error = the +10 ms prediction error of the 10 position/velocity dims, as in M3e: squared
error and Gaussian NLL, per 5 s bin (500 steps).
Warm-up exclusion, the same set of steps in both runs: the first 20 steps of every 200-step window (k % 200 < 20; the 20 steps the model was trained to ignore; this also drops k = 0).
Per bin: mean over the retained steps (450 of 500), per trajectory. Statistics over the trajectories: bin mean with 95 % bootstrap interval, and the paired difference
continuous - reset per bin (mean and 95 % bootstrap interval, 10,000 resamples), and the slope of that difference over the 12 bins (per 10 s, mean and interval).

    m3e_cb60_open.py [--n 32] [--first 0]
"""
import argparse
import json
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import m3e_jax as M

HELD = "/secondary/hyst-data/body/held2h.npz"
OUT = Path("/secondary/hyst-data/body/m3e/cb60")


def run(C, obs, tgt, reset_every):
    """(6000, 15), (6000, 5) -> per-step squared error (10 dims mean) and NLL, each (6000,)."""
    ks = jnp.arange(obs.shape[0])

    def f(c, x):
        s, prev, p1, lv1 = c
        o, t, k = x
        if reset_every:
            s = {**s, "h": s["h"] * (1.0 - (k % reset_every == 0))}
        s, mean, lv = M.cb_step(C, s, o, t)
        e = ((o - prev) / C["dsd"][0] - p1)[:10]
        nll = (0.5 * (lv1[:10] + e ** 2 / jnp.exp(lv1[:10]) + np.log(2 * np.pi))).mean()
        return (s, o, mean[0], lv[0]), ((e ** 2).mean(), nll)
    _, out = jax.lax.scan(f, (M.cb_init(tgt[0]), obs[0], jnp.zeros(15), jnp.zeros(15)), (obs, tgt, ks))
    return out


def boot(v, resamples=10000, seed=0):
    rng = np.random.default_rng(seed)
    n = len(v)
    b = v[rng.integers(0, n, (resamples, n))].mean(1)
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=32)
    ap.add_argument("--first", type=int, default=0)
    a = ap.parse_args()
    C = M.load_cb()
    d = np.load(HELD)
    idx = np.arange(a.first, a.first + a.n)
    obs, tgt = jnp.asarray(d["obs"][idx], float), jnp.asarray(d["tgt"][idx], float)
    keep = (np.arange(6000) % 200) >= 20
    res = {"n_trajectories": int(a.n), "indices": idx.tolist(), "excluded": "first 20 steps of every 200-step window, both runs", "bin_steps": 500}
    series = {}
    for name, re in (("continuous", None), ("reset_every_200", 200)):
        sq, nll = jax.jit(jax.vmap(lambda o, t: run(C, o, t, re)))(obs, tgt)
        series[name] = {"sq": np.asarray(sq), "nll": np.asarray(nll)}
    for m in ("sq", "nll"):
        res[m] = {}
        binned = {}
        for name, s in series.items():
            x = s[m]
            binned[name] = np.stack([(x[:, i * 500:(i + 1) * 500] * keep[i * 500:(i + 1) * 500]).sum(1) / keep[i * 500:(i + 1) * 500].sum() for i in range(12)], 1)      # (n, 12)
            res[m][name] = {"bin_mean": binned[name].mean(0).tolist(), "bin_ci": [boot(binned[name][:, i]) for i in range(12)]}
        diff = binned["continuous"] - binned["reset_every_200"]
        t = np.arange(12) * 5.0 + 2.5
        slope = ((diff - diff.mean(1, keepdims=True)) * (t - t.mean())).sum(1) / ((t - t.mean()) ** 2).sum() * 10.0
        res[m]["diff_continuous_minus_reset"] = {"bin_mean": diff.mean(0).tolist(), "bin_ci": [boot(diff[:, i]) for i in range(12)], "slope_per_10s": float(slope.mean()), "slope_ci": boot(slope)}
        late = binned["continuous"][:, 6:].mean(1) - binned["continuous"][:, 1:6].mean(1)
        late_r = binned["reset_every_200"][:, 6:].mean(1) - binned["reset_every_200"][:, 1:6].mean(1)
        res[m]["late_minus_early"] = {"note": "mean of bins 7-12 minus mean of bins 2-6", "continuous": float(late.mean()), "continuous_ci": boot(late), "reset": float(late_r.mean()), "reset_ci": boot(late_r),
                                      "continuous_minus_reset": float((late - late_r).mean()), "continuous_minus_reset_ci": boot(late - late_r)}
    (OUT / "open_loop_drift.json").write_text(json.dumps(res, indent=1))
    for m in ("sq", "nll"):
        r = res[m]
        print(m, "continuous", np.round(r["continuous"]["bin_mean"], 4).tolist())
        print(m, "reset     ", np.round(r["reset_every_200"]["bin_mean"], 4).tolist())
        print(m, "diff      ", np.round(r["diff_continuous_minus_reset"]["bin_mean"], 4).tolist(), "slope/10s", round(r["diff_continuous_minus_reset"]["slope_per_10s"], 5), np.round(r["diff_continuous_minus_reset"]["slope_ci"], 5).tolist())
        print(m, "late-early", {k: (np.round(v, 5).tolist() if not isinstance(v, str) else v) for k, v in r["late_minus_early"].items()})


if __name__ == "__main__":
    sys.exit(main())
