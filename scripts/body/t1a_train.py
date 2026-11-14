"""WO38 T1a training loop and timing run (rules docs/T1A_RULES.md sections 4 and 6). Brain env, 8 threads.

    t1a_train.py time           each K for 40 steps on the real train set -> t1a/timing.json (seconds per step / epoch, memory)
    t1a_train.py train K [THREADS]   full training of one size, checkpoint each epoch, resumable -> t1a/k<K>/{best.pt,ckpt.pt,log.json,done.json}
"""
import json
import math
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1a_data as DD  # noqa: E402
import t1a_model as M  # noqa: E402

OUT = DD.OUT
BATCH, EPOCH_CAP, PATIENCE = 16, 40, 5
LR0, LR1 = 2e-3, 1e-4
SEEDS = dict(shuffle=34001, init=34002, reset=34003)
SIZES = (128, 256, 512, 1024)


def rss_anon_mb():
    for line in open("/proc/self/status"):
        if line.startswith("RssAnon"):
            return int(line.split()[1]) / 1024


def lr_at(step, total):
    return LR1 + 0.5 * (LR0 - LR1) * (1 + math.cos(math.pi * min(step / max(total, 1), 1.0)))


def loss_fn(model, wb, wt, gen):
    o = model(wb, gen)
    err = (o["recon"] - wb).pow(2).mean((1, 2))                                  # per window, scaled units
    return ((err + M.COMMIT * o["commit"]) * wt).sum() / wt.sum(), err, o


@torch.no_grad()
def evaluate(model, data, sd, bs=64):
    """validation pass: weighted / unweighted reconstruction error, per-source error, code usage (share of codes that are the nearest code of >= 1 chunk), per-source usage"""
    model.eval()
    g = torch.from_numpy(data["g"] / sd)
    w, src = torch.from_numpy(data["w"]), data["src"]
    errs, idxs = [], []
    for i in range(0, len(g), bs):
        o = model(g[i:i + bs])
        errs.append((o["recon"] - g[i:i + bs]).pow(2).mean((1, 2)))
        idxs.append(o["idx"].reshape(-1, M.WIN_CH))
    err, idx = torch.cat(errs), torch.cat(idxs)
    res = dict(err_weighted=float((err * w).sum() / w.sum()), err_unweighted=float(err.mean()), code_usage=float(len(idx.unique()) / model.vq.k))
    for s, n in ((0, "finedance"), (1, "aioz")):
        m = torch.from_numpy(src == s)
        if m.any():
            res[f"err_{n}"] = float(err[m].mean())
            res[f"code_usage_{n}"] = float(len(idx[m].unique()) / model.vq.k)
    return res


def make(k):
    torch.manual_seed(SEEDS["init"])
    return M.VQAE(k)


def epoch(model, opt, g, w, sd, step0, total, rng, gen):
    model.train()
    order = rng.permutation(len(g))
    steps = 0
    for i in range(0, len(order), BATCH):
        b = order[i:i + BATCH]
        for pg in opt.param_groups:
            pg["lr"] = lr_at(step0 + steps, total)
        loss, _, o = loss_fn(model, torch.from_numpy(g[b] / sd), torch.from_numpy(w[b]), gen)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        steps += 1
        if (step0 + steps) % M.RESET_EVERY == 0:
            model.vq.reset_dead(model.enc(M.vigour(torch.from_numpy(g[b] / sd).reshape(-1, M.CH, 5))[2]).detach(), gen)
    return steps


def cmd_time():
    torch.set_num_threads(8)
    tr, va, sd = DD.load("train"), DD.load("validation"), DD.scale()
    n_train, n_val = len(tr["g"]), len(va["g"])
    spe = math.ceil(n_train / BATCH)
    out = dict(train_windows=n_train, validation_windows=n_val, steps_per_epoch=spe, epoch_cap=EPOCH_CAP, steps=40, threads=8, per_k={})
    for k in SIZES:
        model, rng, gen = make(k), np.random.default_rng(SEEDS["shuffle"]), torch.Generator().manual_seed(SEEDS["reset"])
        opt = torch.optim.Adam(model.parameters(), lr=LR0, betas=(0.9, 0.99))
        model.train()
        order = rng.permutation(n_train)
        t0 = time.time()
        for s in range(40):
            b = order[s * BATCH:(s + 1) * BATCH]
            loss, _, _ = loss_fn(model, torch.from_numpy(tr["g"][b] / sd), torch.from_numpy(tr["w"][b]), gen)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            if s == 9:
                t10 = time.time()
        per_step = (time.time() - t10) / 30                                      # steps 10..39 (the first ten include warm-up)
        t1 = time.time()
        ev = evaluate(model, {k_: v[:160] for k_, v in va.items()}, sd)              # 160 validation windows
        per_val = (time.time() - t1) / 160 * n_val
        out["per_k"][str(k)] = dict(seconds_per_step=per_step, seconds_per_epoch_train=per_step * spe, seconds_validation_pass=per_val, seconds_per_epoch=per_step * spe + per_val,
                                    projected_hours_to_cap=(per_step * spe + per_val) * EPOCH_CAP / 3600, rss_anon_mb=rss_anon_mb(), ru_maxrss_mb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
                                    loss_after_40_steps=float(loss), val_err_160=ev["err_weighted"])
        print(k, json.dumps(out["per_k"][str(k)]), flush=True)
    out["projected_hours_all_four_to_cap"] = sum(v["projected_hours_to_cap"] for v in out["per_k"].values())
    OUT.mkdir(exist_ok=True)
    (OUT / "timing.json").write_text(json.dumps(out, indent=1))
    print("projected hours, all four to the epoch cap:", round(out["projected_hours_all_four_to_cap"], 2))


def cmd_train(k, threads=8):
    """full training of one size; threads stated by the caller. Checkpoints every epoch (ckpt.pt, atomic) and resumes from it; done.json marks the end (cap or early stop)."""
    torch.set_num_threads(threads)
    k = int(k)
    tr, va, sd = DD.load("train"), DD.load("validation"), DD.scale()
    d = OUT / f"k{k}"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "done.json").exists():
        print(k, "done already")
        return
    model, rng, gen = make(k), np.random.default_rng(SEEDS["shuffle"]), torch.Generator().manual_seed(SEEDS["reset"])
    opt = torch.optim.Adam(model.parameters(), lr=LR0, betas=(0.9, 0.99))
    spe, step, best, bad, log, ep0 = math.ceil(len(tr["g"]) / BATCH), 0, float("inf"), 0, [], 0
    if (d / "ckpt.pt").exists():
        c = torch.load(d / "ckpt.pt", weights_only=False)
        model.load_state_dict(c["model"])
        opt.load_state_dict(c["opt"])
        rng.bit_generator.state, gen = c["rng"], gen
        gen.set_state(c["gen"])
        step, best, bad, log, ep0 = c["step"], c["best"], c["bad"], c["log"], c["epoch"] + 1
        print(k, "resumed after epoch", c["epoch"], flush=True)
    stopped = "cap"
    for ep in range(ep0, EPOCH_CAP):
        t0 = time.time()
        step += epoch(model, opt, tr["g"], tr["w"], sd, step, spe * EPOCH_CAP, rng, gen)
        ev = evaluate(model, va, sd)
        log.append(dict(epoch=ep, seconds=time.time() - t0, threads=threads, **ev))
        print(k, log[-1], flush=True)
        if ev["err_weighted"] < best:
            best, bad = ev["err_weighted"], 0
            torch.save(model.state_dict(), d / "best.pt")
        else:
            bad += 1
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), rng=rng.bit_generator.state, gen=gen.get_state(), step=step, best=best, bad=bad, log=log, epoch=ep), d / "ckpt.tmp")
        (d / "ckpt.tmp").replace(d / "ckpt.pt")
        (d / "log.json").write_text(json.dumps(log, indent=1))
        if bad >= PATIENCE:
            stopped = "early_stop"
            break
    (d / "done.json").write_text(json.dumps(dict(stopped=stopped, epochs=len(log), best_err_weighted=best, threads=threads)))


if __name__ == "__main__":
    a = sys.argv[1:]
    cmd_time() if a[0] == "time" else cmd_train(a[1], int(a[2]) if len(a) > 2 else 8)
