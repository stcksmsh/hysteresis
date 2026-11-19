"""K5 speed check (work order 9, BRAIN_SPEC 7.20 point 1): JAX backend, MJX import, and the speed of M3e training on REAL K5 windows, on the laptop and on Kaggle (job file
scripts/compute/jobs/k5_bench.json). Provisional servo model (Feetech STS3215 12 V assumed). One arm. Does not train K5.

    k5_bench.py pack --out DIR [--k5 K5DIR]     a small dataset folder (name hyst-k5: splits.json / windows.json restricted to the windows used, their lanes, cb_r2.npz, HYST_DATASET.json)
    k5_bench.py run  --out DIR [--k5 DIR] [--cb FILE] [--rounds 3] [--es 16,64,256]

`run` measures: (1) one K5 round = m3e.Trainer.run_epoch on 16 real windows (the training unit; first call includes compilation and is reported separately; the median of the
rest is used); (2) gradient steps per second of the M3e loss on one 8-block chunk at E = 16 (the K5 batch), 64 and 256 windows (capacity only: a larger batch is not the K5
recipe); (3) hard-rollout seconds per window for evaluation; (4) the fresh-observer fit. Projection: one pass = 977 rounds, plus 5 validations (217 + 16 windows each) and the K5 check
(3 policies x (4 x 16 + 1,071) windows, argmax; sampled doubles it). Results in OUT/results.json.
"""
import argparse
import json
import os
import platform
import shutil
import statistics
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
N_PACK_TRAIN, N_PACK_CHECK = 64, 64


def pack(out, k5):
    import k5_train as T
    out, k5 = Path(out), Path(k5)
    w = json.loads((k5 / "windows.json").read_text())
    order = T.train_order(w["train"])[:N_PACK_TRAIN]
    chk = [r for r in w["check"]][:N_PACK_CHECK]
    sp = json.loads((k5 / "splits.json").read_text())
    for split, ids in (("train", sorted({s for s, _ in order})), ("check", sorted({r[0] for r in chk}))):
        (out / "lanes" / split).mkdir(parents=True, exist_ok=True)
        for sid in ids:
            shutil.copy(k5 / "lanes" / split / f"{sid}.npz", out / "lanes" / split / f"{sid}.npz")
    (out / "windows.json").write_text(json.dumps({"train": [list(x) for x in order], "check": chk}))
    (out / "splits.json").write_text(json.dumps({"train": {"ids": sorted({s for s, _ in order})}, "check": {"ids": sorted({r[0] for r in chk})}, "val": {"ids": []}}))
    shutil.copy("/secondary/hyst-data/body/m3e/cb_r2.npz", out / "cb_r2.npz")
    (out / "HYST_DATASET.json").write_text(json.dumps({"name": "hyst-k5", "note": "bench subset: real K5 lanes of the songs of 64 training and 64 check windows"}))
    print(out, sum(f.stat().st_size for f in out.rglob("*") if f.is_file()), "bytes")


def timed(f, *a):
    t = time.time()
    r = f(*a)
    return r, time.time() - t


def run(out, k5, cb, rounds, es):
    import jax
    import jax.numpy as jnp
    import k5_train as T
    import m3d
    import m3d_jax as J
    import m3e
    import m3e_jax as M
    out, k5 = Path(out), Path(k5)
    out.mkdir(parents=True, exist_ok=True)
    res = {"host": platform.node(), "python": sys.version.split()[0], "jax": jax.__version__, "backend": jax.default_backend(), "devices": [str(d) for d in jax.devices()],
           "cpu_count": os.cpu_count(), "x64": bool(jax.config.jax_enable_x64)}
    import mujoco
    from mujoco import mjx
    res["mujoco"], res["mjx_import"] = mujoco.__version__, True
    print(json.dumps(res), flush=True)
    w = json.loads((k5 / "windows.json").read_text())
    order = T.train_order(w["train"])
    C = M.load_cb(cb)
    obs_w = T.obs_windows(order)
    calib = T.build_toy(k5, "train", obs_w)
    tr = m3e.Trainer(calib, C, T.LAM, T.LR, 977, 8, dopamine=True, log=lambda s: None)
    tr.toy, tr.groups = calib, {"A": np.arange(0, 8), "B": np.arange(8, 16)}
    _, res["calibrate_s"] = timed(tr.calibrate)
    print("calibrated", res["calibrate_s"], flush=True)
    secs = []
    for r in range(rounds):
        wins = order[16 * r:16 * (r + 1)]
        toy = T.build_toy(k5, "train", wins)
        tr.toy, tr.groups = toy, {"A": np.arange(0, 8), "B": np.arange(8, 16)}
        _, s = timed(tr.run_epoch)
        secs.append(s)
        print(f"round {r}: {s:.1f} s", flush=True)
        res["round_s_all"] = secs
        (out / "results.json").write_text(json.dumps(res, indent=1))
    res["round_s_first_incl_compile"] = secs[0]
    res["round_s"] = statistics.median(secs[1:]) if len(secs) > 1 else secs[0]
    # gradient steps on one chunk, E windows (the 16 real windows tiled)
    toy = T.build_toy(k5, "train", order[:16])
    S = tr.stats
    grads = {}
    for E in es:
        try:
            idx = np.arange(E) % 16
            inps = toy.inputs(idx, jax.random.PRNGKey(0))
            yz = jnp.asarray(toy.yz[idx])
            carry = jax.vmap(lambda q: M.init_carry(q, C))(jnp.asarray(m3d.start_poses(E, 100)))
            args = lambda c0: (tr.P, tr.obs["A"][0], tr.obs["A"][1], carry, m3d.take(inps, c0, c0 + 8), yz[:, c0:c0 + 8], m3e.valid_mask(c0, 8, E), 0.5, tr.lam, tr.e0, S["dmu"], S["dsd"], S["imu"], S["isd"])
            (l, _), g = tr.fns["loss"](*args(16))
            jax.block_until_ready(g)
            ts = []
            for _ in range(3):
                t = time.time()
                (l, _), g = tr.fns["loss"](*args(16))
                jax.block_until_ready(g)
                ts.append(time.time() - t)
            grads[E] = {"s_per_step": statistics.median(ts), "steps_per_s": 1 / statistics.median(ts), "window_blocks_per_s": E * 8 / statistics.median(ts)}
        except Exception as e:                                   # out of memory at a large batch is a result
            grads[E] = {"error": str(e)[:200]}
        print("grad", E, grads[E], flush=True)
    res["grad_step"] = grads
    # evaluation rollouts and the observer fit
    chk = [(r[0], r[2]) for r in w["check"]][:64]
    combo = T.combine(T.build_toy(k5, "train", obs_w), T.build_toy(k5, "check", chk))
    key = jax.random.PRNGKey(7)
    T.rollout_batched(tr.fns, C, tr.P, combo, combo.sets["eval"], "argmax", key, 4242)
    _, t_roll = timed(T.rollout_batched, tr.fns, C, tr.P, combo, combo.sets["eval"], "argmax", key, 4242)
    res["eval_s_per_window"] = t_roll / len(chk)
    rolls = [T.rollout_batched(tr.fns, C, tr.P, combo, combo.sets["train"], "argmax", jax.random.PRNGKey(100 + k), 100) for k in range(4)]
    _, res["observer_fit_s"] = timed(m3e.fresh_observers, rolls, combo.yz[combo.sets["train"]], S)
    n_check, n_val, n_obs = 1071, 217, 4 * 16
    pol = lambda n_eval: (n_obs + n_eval) * res["eval_s_per_window"] + res["observer_fit_s"]
    res["projection_h"] = {"pass_training": 977 * res["round_s"] / 3600, "validations_5": 5 * pol(n_val) / 3600, "check_argmax_3_policies": 3 * pol(n_check) / 3600}
    res["projection_h"]["one_try_pass_plus_check"] = sum(res["projection_h"].values())
    (out / "results.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res["projection_h"]), flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("pack", "run"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--k5", default="/secondary/hyst-data/body/k5")
    ap.add_argument("--cb")
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--es", default="16", help="gradient-step batch sizes; large ones can exhaust memory (on the CPU that kills the process)")
    a = ap.parse_args()
    if a.what == "pack":
        pack(a.out, a.k5)
    else:
        run(a.out, a.k5, a.cb or str(Path(a.k5) / "cb_r2.npz"), a.rounds, [int(x) for x in a.es.split(',')])


if __name__ == "__main__":
    main()
