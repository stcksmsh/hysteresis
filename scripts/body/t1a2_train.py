"""WO39 T1a2 training (rules docs/T1A2_RULES.md). Brain env.

    t1a2_train.py weights               write t1a2/weights.json (the AIOZ 50 % cap factor from the train split)
    t1a2_train.py train A|B THREADS     full training, checkpoint each epoch (ckpt.pt), resumable, done.json at the end -> t1a2/run<A|B>/
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1a_data as DD  # noqa: E402
import t1a_model as M  # noqa: E402
import t1a_train as TR  # noqa: E402
import t1a2_model as M2  # noqa: E402

OUT = Path("/secondary/hyst-data/body/t1a2")
BATCH, EPOCH_CAP, PATIENCE = 16, 80, 5
COMMIT, VEL, ACC = 0.02, 1.0, 1.0                                        # Bailando's config (rules 2)
SEEDS = TR.SEEDS
K = 1024


def cap_factor(d):
    """f such that sum(AIOZ weight x f x chunks) = sum(FineDance weight x chunks) on the train windows (the 50 % cap, 7.61.7)"""
    fd, az = float(d["w"][d["src"] == 0].sum()), float(d["w"][d["src"] == 1].sum())
    return fd / az


def load(split, f):
    d = DD.load(split)
    d["w"] = np.where(d["src"] == 1, d["w"] * f, d["w"]).astype(np.float32)
    return d


def bailando_loss(recon, w):
    """per window: L1 + vel x L1 of first differences + acc x L1 of second differences (the code quoted in the rules), means over time and joints; (B,)"""
    l1 = (recon - w).abs().mean((1, 2))
    v = ((recon[:, 1:] - recon[:, :-1]) - (w[:, 1:] - w[:, :-1])).abs().mean((1, 2))
    a = ((recon[:, 2:] + recon[:, :-2] - 2 * recon[:, 1:-1]) - (w[:, 2:] + w[:, :-2] - 2 * w[:, 1:-1])).abs().mean((1, 2))
    return l1 + VEL * v + ACC * a


@torch.no_grad()
def evaluate(model, data, sd, bs=64):
    """weighted / unweighted MSE (scaled units, the T1a metric), per-source MSE, code usage (Run B: stage 1 and 2)"""
    model.eval()
    g, w, src = torch.from_numpy(data["g"] / sd), torch.from_numpy(data["w"]), data["src"]
    errs, i1, i2 = [], [], []
    for i in range(0, len(g), bs):
        o = model(g[i:i + bs])
        errs.append((o["recon"] - g[i:i + bs]).pow(2).mean((1, 2)))
        idx = o["idx"] if model.residual else (o["idx"], None)
        i1.append(idx[0].reshape(-1, M.WIN_CH))
        if model.residual:
            i2.append(idx[1].reshape(-1, M.WIN_CH))
    err, i1 = torch.cat(errs), torch.cat(i1)
    res = dict(err_weighted=float((err * w).sum() / w.sum()), err_unweighted=float(err.mean()), code_usage=float(len(i1.unique()) / model.k))
    if model.residual:
        i2 = torch.cat(i2)
        res["code_usage_stage2"] = float(len(i2.unique()) / model.k)
    for s, n in ((0, "finedance"), (1, "aioz")):
        m = torch.from_numpy(src == s)
        if m.any():
            res[f"err_{n}"] = float(err[m].mean())
            res[f"code_usage_{n}"] = float(len(i1[m].unique()) / model.k)
    return res


def make(run):
    torch.manual_seed(SEEDS["init"])
    return M2.VQAE2(K, residual=(run == "B"))


def epoch(model, opt, g, w, sd, step0, total, rng, gen):
    model.train()
    order = rng.permutation(len(g))
    steps = 0
    for i in range(0, len(order), BATCH):
        b = order[i:i + BATCH]
        for pg in opt.param_groups:
            pg["lr"] = TR.lr_at(step0 + steps, total)
        x, wt = torch.from_numpy(g[b] / sd), torch.from_numpy(w[b])
        o = model(x, gen)
        loss = (bailando_loss(o["recon"], x) * wt).sum() / wt.sum() + COMMIT * o["commit"]
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step()
        steps += 1
        if (step0 + steps) % M.RESET_EVERY == 0:
            with torch.no_grad():
                z = model.enc(M.vigour(x.reshape(-1, M.CH, 5))[2])
                model.vq.reset_dead(z, gen)
    return steps


def cmd_weights():
    OUT.mkdir(parents=True, exist_ok=True)
    f = cap_factor(DD.load("train"))
    (OUT / "weights.json").write_text(json.dumps(dict(aioz_factor=f, rule="7.61.3 applies: AIOZ capped at 50 % of total train weight")))
    print("aioz factor", f)


def cmd_train(run, threads):
    torch.set_num_threads(threads)
    f = json.loads((OUT / "weights.json").read_text())["aioz_factor"]
    tr, va, sd = load("train", f), load("validation", f), DD.scale()
    d = OUT / f"run{run}"
    d.mkdir(parents=True, exist_ok=True)
    if (d / "done.json").exists():
        print(run, "done already")
        return
    model, rng, gen = make(run), np.random.default_rng(SEEDS["shuffle"]), torch.Generator().manual_seed(SEEDS["reset"])
    opt = torch.optim.Adam(model.parameters(), lr=TR.LR0, betas=(0.9, 0.99))
    spe, step, best, bad, log, ep0 = math.ceil(len(tr["g"]) / BATCH), 0, float("inf"), 0, [], 0
    if (d / "ckpt.pt").exists():
        c = torch.load(d / "ckpt.pt", weights_only=False)
        model.load_state_dict(c["model"])
        opt.load_state_dict(c["opt"])
        rng.bit_generator.state = c["rng"]
        gen.set_state(c["gen"])
        step, best, bad, log, ep0 = c["step"], c["best"], c["bad"], c["log"], c["epoch"] + 1
        print(run, "resumed after epoch", c["epoch"], flush=True)
    stopped = "cap"
    for ep in range(ep0, EPOCH_CAP):
        t0 = time.time()
        step += epoch(model, opt, tr["g"], tr["w"], sd, step, spe * EPOCH_CAP, rng, gen)
        ev = evaluate(model, va, sd)
        log.append(dict(epoch=ep, seconds=time.time() - t0, threads=threads, **ev))
        print(run, log[-1], flush=True)
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
    cmd_weights() if a[0] == "weights" else cmd_train(a[1], int(a[2]))
