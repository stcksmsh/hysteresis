"""WO46 part 2: realised whole-sequence trajectories (docs/METRIC_RULES.md section 2). Body env.   metric_sim.py [PROCS]
Same chain as controls_run.sim_file (guard, spinal, limiter/servo, v2p body) but ONE pass over the whole sequence instead of 20 s windows. V1 and V2 copies only (mirrors excluded).
-> /secondary/hyst-data/body/metric/q50/<dataset>/<name>.npz: q50 (n, 5) float32 50 Hz, lamp (n, 3) float32, win_pass (the T0 gate per 20 s window), split, group. Resumable."""
import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
B = Path("/secondary/hyst-data/body")
OUT = B / "metric" / "q50"
ROOTS = {"finedance": B / "t0/seq/finedance", "aioz": B / "t0/seq/aioz", "phantom": B / "t0_phantom/seq", "motorica": B / "t0_motorica/seq"}
PRE = 150


def sim_file(args):
    try:
        return _sim_file(args)
    except Exception as e:                                                     # logged with the name, run goes on
        with open(OUT.parent / "sim_failed.txt", "a") as f:
            f.write(f"{args[0]} {args[1].name} {type(e).__name__}: {e}\n")
        return args[1].name, -1.0


def _sim_file(args):
    ds, path = args
    dst = OUT / ds / path.name
    if dst.exists():
        return path.name, 0.0
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    RR.patch_gates()                                                           # 1.5 s warm-up (not 10 s) and the v2p body, as controls_run.sim_file
    import m3f_report as R
    t0 = time.time()
    z = np.load(path)
    var = path.stem.split("__")[1][:2]
    K = RT.to_commands(np.zeros((1, 5)), var)[0]
    tg = z["targets"].astype(float)
    pre = np.repeat(tg[:1], PRE, 0)
    sh = np.zeros(5)
    sh[[0, 4]] = (tg[0] - K)[[0, 4]]
    G, _ = P.guard(np.concatenate([pre, tg]) - sh)
    q50, _ = FX.simulate_goals(M.spinal(G))
    q50 = np.asarray(q50, float)
    if q50.ndim != 2 or q50.shape[1] != 5 or len(q50) < 100:
        raise ValueError(f"simulate_goals returned shape {q50.shape} for targets {tg.shape}")
    lamp = R.fk_points(q50)[:, 5]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.npz")
    np.savez_compressed(tmp, q50=q50.astype(np.float32), lamp=lamp.astype(np.float32), win_pass=z["win_pass"], split=str(z["split"]), group=str(z["group"]))
    tmp.replace(dst)
    return path.name, time.time() - t0


def main(procs=6):
    jobs = [(ds, p) for ds in ROOTS for p in sorted(ROOTS[ds].glob("*.npz")) if p.stem.split("__")[1] in ("V1", "V2")]
    t0 = time.time()
    with mp.get_context("spawn").Pool(procs) as pool:
        for i, (name, s) in enumerate(pool.imap_unordered(sim_file, jobs, chunksize=2)):
            if i % 100 == 0:
                print(f"{i}/{len(jobs)} {time.time() - t0:.0f}s last {name} {s:.1f}s", flush=True)
    print("SIM DONE", len(jobs), f"{time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 6)
