"""M3 step benchmark (report only; work order 2 phase 3). One step = one 2 s block (200 frames at 100 Hz) for E environments:
  physics   E arms x 200 control steps (MuJoCo CPU, pattern generators, random commands), over a pool of worker processes
  cortex    B7 epoch 6 twin pass (moving + still rows, batch 2E) with the proprioceptive relays, forward with autograd (gradient checkpointing on)
  relay     backward of the surprisal sum into the relays only (cortex frozen)
  policy    basal ganglia (8 programs, Go/NoGo) + motor cortex + critic: forward and backward of a PPO-style loss on E x 20 samples (10 Hz)
Features are synthetic standardised noise (cost does not depend on content). Reports seconds per step and seconds of wall time per hour of simulated
experience summed over environments (step_s * 3600 / (2 E)), and peak RSS (a fresh process per E: run once per E).
    python bench_m3.py --out DIR --envs 64 [--device auto|cpu|cuda] [--threads 12] [--steps 3] [--procs 12]
Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import argparse
import json
import resource
import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

import m3_cortex as M

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402

BLOCK = 200
_W = {}


def _phys(args):
    """Worker: advance each env in `ids` by one block with fresh random commands every 10 steps (envs persist in the worker between calls)."""
    ids, seed = args
    import arm_sim
    import babble
    import cpg
    rng = np.random.default_rng(seed)
    obs = np.empty((len(ids), BLOCK, 15), np.float32)
    for j, e in enumerate(ids):
        if e not in _W:
            _W[e] = (arm_sim.ArmSim(), cpg.CPG())
        sim, gen = _W[e]
        u = babble.ou_commands(rng, BLOCK // 10 + 1)
        for k in range(BLOCK):
            if k % 10 == 0:
                gen.command(*babble.to_command(u[k // 10]))
            p = sim.step(gen.step())
            obs[j, k] = np.concatenate([p["pos_deg"], p["vel_deg_s"], p["load_nm"]])
    return obs


class Policy(nn.Module):
    """Basal ganglia (striatum scores Go - NoGo per program), motor cortex (continuous modulation) and critic on pooled cortex + body input."""

    def __init__(self, din, k=8, hid=256):
        super().__init__()
        self.go, self.nogo = nn.Sequential(nn.Linear(din, hid), nn.Tanh(), nn.Linear(hid, k)), nn.Sequential(nn.Linear(din, hid), nn.Tanh(), nn.Linear(hid, k))
        self.mc = nn.Sequential(nn.Linear(din, hid), nn.Tanh(), nn.Linear(hid, 40))      # 20 modulation means + 20 log stds
        self.critic = nn.Sequential(nn.Linear(din, hid), nn.Tanh(), nn.Linear(hid, 1))

    def forward(self, x):
        return self.go(x) - self.nogo(x), self.mc(x), self.critic(x)[..., 0]


def run(a):
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)
    dev = a.device if a.device != "auto" else ("cuda" if torch.cuda.is_available() else "cpu")
    E = a.envs
    wrapped = M.Cortex(M.core_b7.Core7(skip_taps=10, hippocampus=False) if a.fresh else M.load_epoch())      # --fresh: the cost does not depend on the weights
    wrapped.freeze_cortex()
    wrapped.core.grad_checkpoint = True
    for p in wrapped.prop.parameters():
        nn.init.normal_(p, std=0.01)          # a non-zero relay costs the same as a zero one; the benchmark uses non-zero so no shortcut is possible
    core.use_device(wrapped, dev)
    din = 2 * core.D + M.P + 1
    pol = Policy(din).to(dev)
    opt = torch.optim.Adam(list(wrapped.prop.parameters()) + list(pol.parameters()), 1e-4)
    rng = np.random.default_rng(0)
    pool = Pool(a.procs) if a.procs > 1 else None
    chunks = [list(range(i, E, a.procs)) for i in range(a.procs)] if pool else [list(range(E))]
    rows = []
    for step in range(a.steps + 1):
        t = {}
        t0 = time.perf_counter()
        res = (pool.map(_phys, [(c, int(rng.integers(1 << 30))) for c in chunks if c]) if pool else [_phys((chunks[0], 0))])
        obs = np.concatenate(res)
        t["physics"] = time.perf_counter() - t0
        f = torch.randn(E, BLOCK, core.N_IN, device=dev)
        prop = torch.from_numpy(np.concatenate([(obs - obs.mean((0, 1))) / (obs.std((0, 1)) + 1e-6), np.zeros_like(obs)], -1)).float().to(dev)
        still = torch.zeros_like(prop)
        f2, p2 = torch.cat([f, f]), torch.cat([prop, still])
        if dev == "cuda":
            torch.cuda.synchronize()
        t0 = time.perf_counter()
        out, _ = wrapped(f2, p2, wrapped.core.init_state(2 * E))
        s = M.row_surprisal(out, f2)
        gain = (s[E:] - s[:E]).sum()                       # S_still - S_moving, summed: the quantity the reward is built from
        if dev == "cuda":
            torch.cuda.synchronize()
        t["cortex_twin_forward"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        feat = torch.cat([out[2]["x"], out[3]["x"]], -1)[:E].detach()                                    # pooled-state input for the policy
        feat = torch.cat([feat.reshape(E, 20, 10, -1).mean(2), prop[:E].reshape(E, 20, 10, -1).mean(2), s[:E].detach().reshape(E, 20, 10).mean(2)[..., None]], -1)
        opt.zero_grad()
        s[:E].sum().backward()                             # relay backward (cortex frozen): through all four layers into the proprioceptive relays
        if dev == "cuda":
            torch.cuda.synchronize()
        t["relay_backward"] = time.perf_counter() - t0
        t0 = time.perf_counter()
        logits, mc, v = pol(feat.reshape(E * 20, din))
        ratio = torch.exp(torch.log_softmax(logits, -1).max(-1).values - 0.0)
        loss = -(ratio * v.detach()).mean() + (v - v.detach() - 1.0).pow(2).mean() + mc.pow(2).mean() * 1e-3
        loss.backward()
        opt.step()
        if dev == "cuda":
            torch.cuda.synchronize()
        t["policy_fwd_bwd"] = time.perf_counter() - t0
        t["total"] = sum(t.values())
        rows.append(t)
        print(json.dumps({"step": step, **{k: round(v, 3) for k, v in t.items()}}), flush=True)
        del out
    if pool:
        pool.close()
    keep = rows[1:]
    med = {k: statistics.median(r[k] for r in keep) for k in keep[0]}
    res = {"envs": E, "device": dev, "threads": a.threads, "procs": a.procs, "steps_timed": len(keep), "median_s": med,
           "sim_seconds_per_step": 2 * E, "wall_s_per_sim_hour": med["total"] * 3600 / (2 * E),
           "peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6}
    if dev == "cuda":
        res["peak_cuda_gb"] = torch.cuda.max_memory_allocated() / 1e9
    print(json.dumps(res), flush=True)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    (Path(a.out) / f"m3_bench_{E}_{dev}.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--data")           # accepted and unused (job contract)
    ap.add_argument("--envs", type=int, required=True)
    ap.add_argument("--device", default="auto")
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--procs", type=int, default=12)
    ap.add_argument("--steps", type=int, default=3)
    ap.add_argument("--fresh", action="store_true")
    run(ap.parse_args())
