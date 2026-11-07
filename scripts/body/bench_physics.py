"""Z5 benchmark: physics steps per second of the M0 arm for N parallel environments (docs/BODY_BRAIN_PLAN.md §4 Z5; job contract of scripts/compute).

    python bench_physics.py --out DIR [--envs 1,64,512,1024,4096] [--seconds 60] [--steps 500]

Per N: MuJoCo CPU (mujoco.rollout, all cores) and MJX (JAX, vmap + scan, whatever device JAX has: CPU here, GPU on Kaggle if the wheel is there). One physics step = 2 ms
of arm time. Each timing is a rollout of --steps steps from the neutral pose with random targets held; MJX's compile is excluded (first call), the median of the
repeats is reported; a config stops repeating at --seconds/len(envs)... of wall time. Writes results.json and progress.json to --out.
"""
import argparse
import json
import os
import statistics
import time
from pathlib import Path

import mujoco
import numpy as np
from mujoco import rollout

import make_arm as M


def cpu_run(model, n, steps, rng, budget_s, nthread):
    datas = [mujoco.MjData(model) for _ in range(nthread)]
    spec = mujoco.mjtState.mjSTATE_FULLPHYSICS
    d0 = mujoco.MjData(model)
    d0.qpos[:] = np.radians(M.NEUTRAL_DEG)
    s0 = np.zeros(mujoco.mj_stateSize(model, spec))
    mujoco.mj_getState(model, d0, s0, spec)
    init = np.tile(s0, (n, 1))
    ctrl = np.repeat(np.radians(M.NEUTRAL_DEG)[None, None] + rng.uniform(-0.3, 0.3, (n, 1, 5)), steps, axis=1)
    times, t_end = [], time.perf_counter() + budget_s
    while not times or (time.perf_counter() < t_end and len(times) < 5):
        t0 = time.perf_counter()
        rollout.rollout(model, datas, init, ctrl)
        times.append(time.perf_counter() - t0)
    return n * steps / statistics.median(times), len(times)


def mjx_run(model, n, steps, rng, budget_s):
    import jax
    from mujoco import mjx
    mx = mjx.put_model(model)
    q0 = np.radians(M.NEUTRAL_DEG)
    base = mjx.make_data(model).replace(qpos=jax.numpy.asarray(q0))
    ctrl = jax.numpy.asarray(q0[None] + rng.uniform(-0.3, 0.3, (n, 5)))

    def one(c):
        d = base.replace(ctrl=c)
        d, _ = jax.lax.scan(lambda d, _: (mjx.step(mx, d), None), d, None, length=steps)
        return d.qpos

    f = jax.jit(jax.vmap(one))
    f(ctrl).block_until_ready()          # compile
    times, t_end = [], time.perf_counter() + budget_s
    while not times or (time.perf_counter() < t_end and len(times) < 5):
        t0 = time.perf_counter()
        f(ctrl).block_until_ready()
        times.append(time.perf_counter() - t0)
    return n * steps / statistics.median(times), len(times), str(jax.devices()[0])


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--envs", default="1,64,512,1024,4096")
    ap.add_argument("--seconds", type=float, default=60.0, help="wall budget per backend per N")
    ap.add_argument("--steps", type=int, default=500)
    ap.add_argument("--no-mjx", action="store_true")
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    model = mujoco.MjModel.from_xml_string(M.final_xml())
    rng = np.random.default_rng(0)
    nthread = os.cpu_count() or 1
    rows = []
    for n in (int(x) for x in a.envs.split(",")):
        row = {"envs": n}
        row["mujoco_cpu_steps_per_s"], row["mujoco_cpu_repeats"] = cpu_run(model, n, a.steps, rng, a.seconds, min(nthread, n))
        row["mujoco_cpu_threads"] = min(nthread, n)
        if not a.no_mjx:
            try:
                row["mjx_steps_per_s"], row["mjx_repeats"], row["mjx_device"] = mjx_run(model, n, a.steps, rng, a.seconds)
            except Exception as e:      # noqa: BLE001  (e.g. out of memory at 4096, or no JAX)
                row["mjx_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        rows.append(row)
        print(json.dumps(row), flush=True)
        (out / "progress.json").write_text(json.dumps({"envs": n, "time": time.time()}))
        (out / "results.json").write_text(json.dumps({"cpu_count": nthread, "mujoco": mujoco.__version__, "steps_per_rollout": a.steps,
                                                      "timestep_s": M.TIMESTEP, "rows": rows}, indent=1))


if __name__ == "__main__":
    main()
