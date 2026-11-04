"""M3c driver (toy only; see tm3c.py). Provisional servo model (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).

    run_tm3c.py calib --out DIR --bundle M1.pt [--iters 15]       standardisation constants, initial observer, LP0, E0 -> DIR/calib.{json,pt} (DIR/cortex.pt = the T-M3 cortex)
    run_tm3c.py train --out DIR --bundle M1.pt --name N --lam L --beta B --csw C --ent W --iters I [--threads 2] [--seed S] [--lr LR] [--H H] [--no-policy]
--no-policy keeps the initial random policy and trains only the observer (the diagnosis: can the observer beat the control on random movement?).
Every setting is written to DIR/<name>.settings.json before the first iteration; policy and observer are saved before evaluation.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

import m3_cortex as M
import tm3
import tm3_world as W
import tm3c


def load_cortex(out):
    cx = M.Cortex(W.make_cortex(0))
    cx.core.load_state_dict(torch.load(Path(out) / "cortex.pt"))
    cx.freeze_cortex()
    return cx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("calib", "train"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--bundle", required=True)
    ap.add_argument("--name", default="run")
    ap.add_argument("--iters", type=int, default=30)
    ap.add_argument("--lam", type=float, default=0.0)
    ap.add_argument("--beta", type=float, default=0.0)
    ap.add_argument("--csw", type=float, default=0.0)
    ap.add_argument("--ent", type=float, default=0.01)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--E", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--H", type=int, default=300)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--eval-eps", type=int, default=8)
    ap.add_argument("--eval-secs", type=float, default=90.0)
    ap.add_argument("--no-policy", action="store_true")
    a = ap.parse_args()
    torch.set_num_threads(a.threads)
    out = Path(a.out)
    log = lambda s: print(s, flush=True)
    cortex = load_cortex(out)
    cfg = tm3.Config(beta=a.beta, lam=a.lam, csw=a.csw, E=a.E, H=a.H, iters=a.iters, seed=a.seed, lr=a.lr, ent=a.ent)
    if a.cmd == "calib":
        run = tm3c.RunC(cfg, cortex, a.bundle)
        cal = tm3c.calibrate(run, a.iters, log=log)
        (out / "calib.json").write_text(json.dumps(cal, indent=1))
        torch.save({"obs": run.obs.state_dict(), "cb": run.cb.net.state_dict()}, out / "calib.pt")
        log(json.dumps({k: v for k, v in cal.items() if k != "stats"}))
        return
    cal = json.loads((out / "calib.json").read_text())
    ck = torch.load(out / "calib.pt")
    (out / f"{a.name}.settings.json").write_text(json.dumps({"config": cfg.__dict__, "calibration": {k: v for k, v in cal.items() if k != "stats"}, "bundle": a.bundle,
                                                              "torch_threads": a.threads, "no_policy": a.no_policy}, indent=1))
    run = tm3c.RunC(cfg, cortex, a.bundle, cal)
    run.cb.net.load_state_dict(ck["cb"])
    run.obs.load_state_dict(ck["obs"])
    run.stats = {k: np.array(v) for k, v in cal["stats"].items()}
    t0 = time.time()
    for i in range(a.iters):
        info = tm3c.run_iteration(run, learn_policy=not a.no_policy)
        log(f"{a.name} it {i + 1}/{a.iters} t {time.time() - t0:.0f}s " + json.dumps({k: (round(v, 4) if isinstance(v, float) else v) for k, v in info.items()}))
    torch.save({"policy": run.pol.state_dict(), "observer": run.obs.state_dict(), "cb": run.cb.net.state_dict(), "stats": cal["stats"]}, out / f"{a.name}.pt")
    res = tm3c.evaluate(run, n_ep=a.eval_eps, secs=a.eval_secs)
    res.update({"name": a.name, "config": cfg.__dict__, "train_seconds": time.time() - t0})
    (out / f"{a.name}.result.json").write_text(json.dumps(res, indent=1))
    log(json.dumps({k: v for k, v in res.items() if k not in ("config", "a_per_episode", "partner")}))


if __name__ == "__main__":
    main()
