"""WO9 Part 1 (BRAIN_SPEC 7.20 point 4): the frozen K1 round-2 cerebellum (JAX port) run CONTINUOUSLY over full 60 s episodes. Provisional servo model (Feetech STS3215 12 V assumed).

    m3e_cb60.py [--try /secondary/hyst-data/body/m3e/try1 --out /secondary/hyst-data/body/m3e/cb60]

(1) The 16 held-out toy episodes in the closed loop exactly as M3e runs it: try 1 policy, argmax, m3e.rollout (the cerebellum's state is carried over all 120 blocks).
(2) The 2 v47 60 s trajectories of parity/traj.npz (index 8, 9), replayed in ArmSim (build_v47.replay, as the M1 set did), the cerebellum run open-loop on them.
Error = what M3e feeds the cortex: the +10 ms prediction error of the 10 position/velocity dims, as mean squared error (standardised units) and Gaussian NLL, per 5 s bin.
Statistics over the 16 episodes: mean and 95 % bootstrap interval (10,000 resamples) of each bin; per-episode least-squares slope of the 12 bin values against time, in
units per 10 s, mean and bootstrap interval; difference of the last 10 s (bins 11-12) minus the first 10 s (bins 1-2), mean and interval.
Rule, fixed before the run: the error "grows" if the slope interval lies above 0 or the last-minus-first interval lies above 0, in the squared error or in the NLL.
Writes OUT/cb60.json and OUT/verdict.json ({"grows": bool}); the chain stops before Part 2 when it grows.
"""
import argparse
import json
import pickle
import sys
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import build_v47
import m3d
import m3e
import m3e_jax as M

PARITY = "/secondary/hyst-data/body/parity/traj.npz"
BIN_BLOCKS = 10                          # 5 s


def bins(x, per):
    """(..., n) per-step/per-block values -> (..., n // per) bin means."""
    n = x.shape[-1] // per
    return x[..., :n * per].reshape(*x.shape[:-1], n, per).mean(-1)


def stats(b, resamples=10000, seed=0):
    """b (E, 12) per-episode bin values -> dict of mean/CI per bin, slope per 10 s, last-minus-first."""
    rng = np.random.default_rng(seed)
    E, nb = b.shape
    t = np.arange(nb) * 5.0 + 2.5
    slope = ((b - b.mean(1, keepdims=True)) * (t - t.mean())).sum(1) / ((t - t.mean()) ** 2).sum() * 10.0
    diff = b[:, -2:].mean(1) - b[:, :2].mean(1)
    ci = lambda v: [float(np.percentile(v[rng.integers(0, E, (resamples, E))].mean(1), q)) for q in (2.5, 97.5)]
    return {"bin_mean": b.mean(0).tolist(), "bin_ci": [ci(b[:, i]) for i in range(nb)], "slope_per_10s": float(slope.mean()), "slope_ci": ci(slope),
            "last10_minus_first10": float(diff.mean()), "diff_ci": ci(diff)}


def v47_series(C, q_idx):
    """Cerebellum error series (per 100 Hz step) on a v47 trajectory replayed in physics, run open-loop. -> (sq, nll) each (6000,)."""
    d = np.load(PARITY, allow_pickle=True)
    tgt = d["tgt"][q_idx].astype(float)
    obs, _ = build_v47.replay(tgt)
    obs = obs.astype(float)

    def f(c, x):
        s, prev, p1, lv1 = c
        o, t = x
        s, mean, lv = M.cb_step(C, s, o, t)
        e = ((o - prev) / C["dsd"][0] - p1)[:10]
        nll = (0.5 * (lv1[:10] + e ** 2 / jnp.exp(lv1[:10]) + np.log(2 * np.pi))).mean()
        return (s, o, mean[0], lv[0]), ((e ** 2).mean(), nll)
    _, (sq, nll) = jax.lax.scan(f, (M.cb_init(tgt[0]), jnp.asarray(obs[0]), jnp.zeros(15), jnp.zeros(15)), (jnp.asarray(obs), jnp.asarray(tgt)))
    return np.asarray(sq), np.asarray(nll)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--try", dest="tdir", default="/secondary/hyst-data/body/m3e/try1")
    ap.add_argument("--out", default="/secondary/hyst-data/body/m3e/cb60")
    ap.add_argument("--toy", default="/secondary/hyst-data/body/m3d/toy.npz")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    toy = m3e.ToyE(a.toy)
    C = M.load_cb()
    ck = pickle.loads((Path(a.tdir) / "ckpt.pkl").read_bytes())
    P = jax.tree_util.tree_map(jnp.asarray, ck["P"])
    fns = m3e.make_fns(C)
    r = m3e.rollout(fns, C, P, toy, toy.sets["held"], "argmax", jax.random.PRNGKey(7), 8, 4242)
    res = {"held_closed_loop": {k: stats(bins(r[k], BIN_BLOCKS)) for k in ("cb_sq", "cb_nll")}, "bins_s": 5}
    # the training distribution's own level for reference: the first-bin mean is the comparison
    res["v47_open_loop"] = {}
    for i, name in ((8, "v47-0"), (9, "v47-2")):
        sq, nll = v47_series(C, i)
        res["v47_open_loop"][name] = {"cb_sq_bins": bins(sq, 500).tolist(), "cb_nll_bins": bins(nll, 500).tolist()}
    grows = any(res["held_closed_loop"][k][s][0] > 0 for k in ("cb_sq", "cb_nll") for s in ("slope_ci", "diff_ci"))
    res["grows"] = bool(grows)
    (out / "cb60.json").write_text(json.dumps(res, indent=1))
    (out / "verdict.json").write_text(json.dumps({"grows": bool(grows)}))
    for k in ("cb_sq", "cb_nll"):
        s = res["held_closed_loop"][k]
        print(k, "bins", np.round(s["bin_mean"], 4).tolist(), "slope/10s", round(s["slope_per_10s"], 5), np.round(s["slope_ci"], 5).tolist(), "last-first", round(s["last10_minus_first10"], 5), np.round(s["diff_ci"], 5).tolist())
    for n, v in res["v47_open_loop"].items():
        print(n, "sq", np.round(v["cb_sq_bins"], 4).tolist(), "nll", np.round(v["cb_nll_bins"], 3).tolist())
    print("grows:", grows)


if __name__ == "__main__":
    sys.exit(main())
