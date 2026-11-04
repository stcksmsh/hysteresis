"""T-M3 driver (toy only; see tm3.py). Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).

    run_tm3.py pretrain --out DIR [--steps 300]                       reduced cortex on the synthetic stream, frozen -> DIR/cortex.pt
    run_tm3.py calib    --out DIR --bundle M1.pt [--iters 15]         initialisation reference (R0, LP0, E0, SYNC0) -> DIR/calib.json
    run_tm3.py train    --out DIR --bundle M1.pt --name N --beta B --lam L --csw C [--gamma G --sync] --iters I [--threads 2] [--seed S]
Every setting is written to DIR/<name>.settings.json before the first iteration.
"""
import argparse
import json
import time
from pathlib import Path

import torch

import tm3
import tm3_world as W
import m3_cortex as M


def load_cortex(out):
    cx = M.Cortex(W.make_cortex(0))
    cx.core.load_state_dict(torch.load(Path(out) / "cortex.pt"))
    cx.freeze_cortex()
    return cx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("pretrain", "calib", "train"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--bundle")
    ap.add_argument("--name", default="run")
    ap.add_argument("--steps", type=int, default=300)
    ap.add_argument("--iters", type=int, default=100)
    ap.add_argument("--beta", type=float, default=0.0)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--csw", type=float, default=0.0)
    ap.add_argument("--gamma", type=float, default=0.0)
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--E", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--H", type=int, default=300)
    ap.add_argument("--threads", type=int, default=12)
    ap.add_argument("--eval-eps", type=int, default=16)
    ap.add_argument("--eval-secs", type=float, default=120.0)
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = lambda s: print(s, flush=True)
    if a.cmd == "pretrain":
        cx = W.pretrain_cortex(W.make_cortex(0), steps=a.steps, log=log)
        torch.save(cx.state_dict(), out / "cortex.pt")
        return
    cortex = load_cortex(out)
    cfg = tm3.Config(beta=a.beta, lam=a.lam, csw=a.csw, gamma_sync=a.gamma, sync=a.sync, E=a.E, H=a.H, iters=a.iters, seed=a.seed, lr=a.lr, ent=a.ent)
    if a.cmd == "calib":
        run = tm3.Run(cfg, cortex, a.bundle)
        cal = tm3.calibrate(run, a.iters, log)
        (out / "calib.json").write_text(json.dumps(cal, indent=1))
        torch.save({"relay": cortex.prop.state_dict(), "cb": run.cb.net.state_dict()}, out / "calib.pt")
        log(json.dumps(cal))
        return
    cal = json.loads((out / "calib.json").read_text())
    ck = torch.load(out / "calib.pt")
    cortex.prop.load_state_dict(ck["relay"])
    (out / f"{a.name}.settings.json").write_text(json.dumps({"config": cfg.__dict__, "calibration": cal, "bundle": a.bundle, "torch_threads": a.threads}, indent=1))
    run = tm3.Run(cfg, cortex, a.bundle, cal)
    run.cb.net.load_state_dict(ck["cb"])
    t0 = time.time()
    for i in range(a.iters):
        info, _ = tm3.iteration(run)
        log(f"{a.name} it {i + 1}/{a.iters} t {time.time() - t0:.0f}s " + json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in info.items()}))
    res = tm3.evaluate(run, n_ep=a.eval_eps, secs=a.eval_secs)
    res.update({"name": a.name, "config": cfg.__dict__, "train_seconds": time.time() - t0})
    (out / f"{a.name}.result.json").write_text(json.dumps(res, indent=1))
    torch.save({"policy": run.pol.state_dict(), "relay": cortex.prop.state_dict()}, out / f"{a.name}.pt")
    log(json.dumps({k: v for k, v in res.items() if k not in ("config",)}))


if __name__ == "__main__":
    main()
