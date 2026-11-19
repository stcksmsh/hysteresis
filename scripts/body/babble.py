"""M1 babbling data (docs/BODY_BRAIN_PLAN.md §5, D1/D3 of BRAIN_SPEC §7.13).

M2 commands (freq, amp, centre, lag per joint) are Ornstein-Uhlenbeck processes (time constant 1 s, sampled at the 10 Hz command rate, stationary
N(0,1) squashed to the full command range by the normal CDF) -> CPG -> ArmSim. Every trajectory has its own seed and its own start pose.
Logged at 100 Hz: obs (15) = proprioception [pos_deg(5), vel_deg_s(5), load_nm(5)] as returned by `ArmSim.step` (state of the previous
step), and tgt (5) = the generator's servo target sent at that step (before the sim's rate limiter; the cerebellum's "command", ruling D1).
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).

    python babble.py OUT.npz --n 60 --seed0 1000 [--secs 60] [--procs 12]
"""
import argparse
import math
from multiprocessing import Pool

import numpy as np
from scipy.special import ndtr

import arm_sim
import cpg
from make_arm import NEUTRAL_DEG

OU_TAU = 1.0
CMD_DT = 0.1
SEED_STRIDE = 1_000_003


def ou_commands(rng, n):
    """(n, 4, 5) commands [freq, amp_frac, centre_frac, lag_frac] in [0, 1], one row per 0.1 s; OU latent, tau 1 s, stationary start."""
    a = math.exp(-CMD_DT / OU_TAU)
    x = rng.standard_normal(20)
    out = np.empty((n, 20))
    for i in range(n):
        out[i] = x
        x = a * x + math.sqrt(1 - a * a) * rng.standard_normal(20)
    return ndtr(out).reshape(n, 4, 5)


def to_command(u):
    """u (4, 5) in [0, 1] -> (freq, amp, centre, lag) in the CPG's command ranges (amp relative to the room left at that centre)."""
    centre = cpg.LO + u[2] * (cpg.HI - cpg.LO)
    a_max = np.where(cpg.BEND, cpg.HI - np.abs(centre), cpg.AMP_CAP_CONTINUOUS)
    return cpg.F_MIN + u[0] * (cpg.F_MAX - cpg.F_MIN), u[1] * a_max, centre, u[3] * cpg.LAG_MAX


def trajectory(seed, secs=60.0):
    rng = np.random.default_rng(seed)
    start = rng.uniform(cpg.LO, cpg.HI) * 0.5 + np.array(NEUTRAL_DEG) * 0.5          # own start pose, inside the ranges
    sim, gen = arm_sim.ArmSim(), cpg.CPG()
    sim.reset(start)
    gen.reset(start)
    n = round(secs * 100)
    u = ou_commands(rng, n // 10 + 1)
    obs, tgt = np.empty((n, 15), np.float32), np.empty((n, 5), np.float32)
    for k in range(n):
        if k % 10 == 0:
            gen.command(*to_command(u[k // 10]))
        t = gen.step()
        p = sim.step(t)
        obs[k] = np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]])
        tgt[k] = t
    return obs, tgt


def _job(args):
    return trajectory(*args)


def generate(n, seed0, secs=60.0, procs=12):
    """-> obs (n, T, 15), tgt (n, T, 5); trajectory i uses seed seed0 + i * SEED_STRIDE."""
    jobs = [(seed0 + i * SEED_STRIDE, secs) for i in range(n)]
    if procs <= 1:
        res = [_job(j) for j in jobs]
    else:
        with Pool(procs) as p:
            res = p.map(_job, jobs, chunksize=1)
    return np.stack([r[0] for r in res]), np.stack([r[1] for r in res])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--seed0", type=int, required=True)
    ap.add_argument("--secs", type=float, default=60.0)
    ap.add_argument("--procs", type=int, default=12)
    a = ap.parse_args()
    o, t = generate(a.n, a.seed0, a.secs, a.procs)
    np.savez(a.out, obs=o, tgt=t, seed0=a.seed0, secs=a.secs)
    print(a.out, o.shape, t.shape)
