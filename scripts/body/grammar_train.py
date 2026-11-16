"""WO45 training of A (docs/A_RULES.md sections 2-4). Brain env.

    grammar_train.py train SEED [THREADS] [--timing N] [--epochs N]    resumable per epoch; out grammar/runs/seed<SEED>/ (ckpt.pt, best.pt, log.json, done.json)
--timing N: N training steps and one validation pass, prints seconds per step, extrapolated epoch time and peak memory, writes nothing else (no checkpoint).
"""
import json
import os
import resource
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grammar_data as GD  # noqa: E402
import grammar_model as GM  # noqa: E402

G = GD.G
LAMBDA = 1.0                 # weight of the auxiliary control loss (fixed, docs/A_RULES.md 3)
P_DROP, P_CORR, P_NOISE = 0.15, 0.10, 0.10
BATCH, LR, WD, CLIP = 64, 1e-3, 0.01, 1.0
PATIENCE, EPOCH_CAP = 5, 40
HEADS = ("code1", "code2", "vigour", "posture1", "posture2")


class Data:
    """windows of one split as tensors; controls standardised (undefined entries -> 0, flags untouched)"""

    def __init__(self, split, stats, vocab, sel=None):
        z = GD.load(split)
        use = [GD.DS.index(d) for d in os.environ.get("HYST_A_DATASETS", ",".join(GD.DS)).split(",")]      # per-dataset switch, all on by default
        keep = np.isin(z["dsid"], use)
        z = {k: v[keep] for k, v in z.items()}
        if sel is not None:
            z = {k: v[sel(z)] for k, v in z.items()}
        self.z = z
        self.n = len(z["code1"])
        L = lambda a: torch.from_numpy(np.asarray(a).astype(np.int64))
        self.c1, self.c2, self.v, self.p1, self.p2 = L(z["code1"]), L(z["code2"]), L(z["vbin"]), L(z["p1"]), L(z["p2"])
        ctl = z["ctl"].astype(np.float64)
        self.valid = torch.from_numpy(valid_dims(ctl))
        gm, gs = stats["global_mean"], np.maximum(stats["global_sd"], 1e-3)
        cn = (ctl - gm) / gs
        cn[..., 15:] = ctl[..., 15:]
        cn = np.where(self.valid.numpy(), cn, 0.0)
        cn[..., 15:] = ctl[..., 15:]
        self.cn = torch.from_numpy(cn.astype(np.float32))
        self.ds, self.copy = L(z["dsid"]), L(z["copy"])
        self.genre = L([vocab["genres"].index(g) for g in z["genre"]])
        self.w = torch.from_numpy(z["weight"].astype(np.float32))


def valid_dims(ctl):
    """(..., 18) raw controls -> bool (..., 18): entries that count in the auxiliary loss (flags never do)"""
    v = GD.valid_mask(ctl)
    v[..., 15:] = False
    return v


def norm_means(stats):
    """per-code control means in standardised units (K, 18) for the four sources"""
    gm, gs = stats["global_mean"], np.maximum(stats["global_sd"], 1e-3)
    return {k: torch.from_numpy(((stats[f"{k}_mean"] - gm) / gs).astype(np.float32)) for k in ("c1", "c2", "p1", "p2")}


def noisy(prev, gen):
    r = lambda x, n: torch.where(torch.rand(x.shape, generator=gen) < P_NOISE, torch.randint(0, n, x.shape, generator=gen), x)
    return (r(prev[0], GM.K_CODE), r(prev[1], GM.K_CODE), r(prev[2], GM.N_VIG), r(prev[3], GM.N_POST), r(prev[4], GM.N_POST))


def run_batch(model, d, idx, means, pool, gen=None, train=True, controls=True):
    """teacher-forced pass over the 40 tokens of the windows `idx` -> dict of weighted mean CE per head, aux, and the weight sum"""
    B = len(idx)
    cn = d.cn[idx]
    ctl, present = (GM.corrupt_controls(cn, pool, P_DROP, P_CORR, gen) if train else (cn, torch.ones(B, GM.N_TOKENS)))
    if not controls:
        present = torch.zeros(B, GM.N_TOKENS)
    valid = d.valid[idx] & (present[..., None] > 0)
    if train:                                                                      # the flags travel with a corrupted vector: validity follows the fed flags
        valid = valid_from_fed(ctl) & (present[..., None] > 0)
    style = model.style_vec(d.ds[idx], d.copy[idx], d.genre[idx])
    feat = model.ctl_feat(ctl, present)
    st = model.zero_state(style)
    prev = None
    ce = {h: [] for h in HEADS}
    aux = []
    for k in range(GM.N_TOKENS):
        fed = prev if (prev is None or not train) else noisy(prev, gen)
        f, st = model.step(st, feat[:, k], style, fed)
        c1, c2, v, p1, p2 = d.c1[idx, k], d.c2[idx, k], d.v[idx, k], d.p1[idx, k], d.p2[idx, k]
        lg = model.heads(f, c1, p1)
        for h, (l, y) in zip(HEADS, ((lg["c1"], c1), (lg["c2"], c2), (lg["v"], v), (lg["p1"], p1), (lg["p2"], p2))):
            ce[h].append(F.cross_entropy(l, y, reduction="none"))
        ex = [GM.expected_controls(lg[s], means[m]) for s, m in (("c1", "c1"), ("c2", "c2"), ("p1", "p1"), ("p2", "p2"))]
        aux.append(GM.aux_loss(ex, ctl[:, k], valid[:, k], torch.ones(GM.CD), present[:, k]))
        prev = (c1, c2, v, p1, p2)
    w = d.w[idx]
    ws = w.sum()
    out = {h: (torch.stack(x, 1).mean(1) * w).sum() / ws for h, x in ce.items()}
    out["aux"] = (torch.stack(aux, 1).mean(1) * w).sum() / ws
    return out, ws


def valid_from_fed(ctl):
    """validity of a (possibly corrupted) standardised control tensor from its own flag dims (15 sharp_ok, 16 dir_ok, 17 acc_ok); always-defined dims 0, 1, 14"""
    v = torch.zeros(ctl.shape, dtype=torch.bool)
    v[..., [0, 1, 14]] = True
    v[..., 10] = ctl[..., 15] > 0
    v[..., 11:14] = (ctl[..., 16] > 0)[..., None]
    v[..., 2:10] = (ctl[..., 17] > 0)[..., None]
    return v


def total(o):
    return sum(o[h] for h in HEADS)


@torch.no_grad()
def evaluate(model, d, means, controls=True, idx=None, bs=256):
    model.eval()
    idx = torch.arange(d.n) if idx is None else idx
    acc, wsum = {h: 0.0 for h in HEADS + ("aux",)}, 0.0
    for a in range(0, len(idx), bs):
        o, ws = run_batch(model, d, idx[a:a + bs], means, None, train=False, controls=controls)
        for k in acc:
            acc[k] += float(o[k]) * float(ws)
        wsum += float(ws)
    model.train()
    r = {k: v / wsum for k, v in acc.items()}
    r["total"] = sum(r[h] for h in HEADS)
    return r


def build(seed):
    torch.manual_seed(seed)
    voc = json.loads((G / "vocab.json").read_text())
    return GM.Grammar(n_genre=len(voc["genres"])), voc


def train(seed, threads=2, timing=0, epochs=EPOCH_CAP):
    torch.set_num_threads(threads)
    stats = dict(np.load(G / "stats.npz"))
    model, voc = build(seed)
    tr, va = Data("train", stats, voc), Data("validation", stats, voc)
    means = norm_means(stats)
    pool = tr.cn.reshape(-1, GM.CD)
    sub = torch.from_numpy(np.random.default_rng(seed).choice(tr.n, min(1500, tr.n), replace=False))
    out = G / "runs" / f"seed{seed}"
    out.mkdir(parents=True, exist_ok=True)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WD)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, factor=0.5, patience=1)
    ep0, best, bad, log = 0, 1e9, 0, []
    if not timing and (out / "ckpt.pt").exists():
        ck = torch.load(out / "ckpt.pt")
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        sched.load_state_dict(ck["sched"])
        ep0, best, bad, log = ck["epoch"], ck["best"], ck["bad"], ck["log"]
        print("resumed after epoch", ep0, flush=True)
    steps_done = 0
    for ep in range(ep0, epochs):
        gen = torch.Generator().manual_seed(seed * 1000 + ep)
        perm = torch.randperm(tr.n, generator=gen)
        t0 = time.time()
        run = {h: 0.0 for h in HEADS + ("aux",)}
        rw = 0.0
        for a in range(0, tr.n, BATCH):
            idx = perm[a:a + BATCH]
            o, ws = run_batch(model, tr, idx, means, pool, gen)
            loss = total(o) + LAMBDA * o["aux"]
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP)
            opt.step()
            for k in run:
                run[k] += float(o[k]) * float(ws)
            rw += float(ws)
            steps_done += 1
            if timing and steps_done == timing:
                dt = (time.time() - t0) / steps_done
                t1 = time.time()
                evaluate(model, va, means, idx=torch.arange(min(va.n, 512)))
                tv = (time.time() - t1) / min(va.n, 512)
                spe = int(np.ceil(tr.n / BATCH))
                est = spe * dt + tv * va.n + 1.0 * tv * len(sub)
                print("TIMING", json.dumps(dict(seed=seed, threads=threads, sec_per_step=dt, steps_per_epoch=spe, val_sec_per_window=tv, epoch_sec_est=est,
                                                 peak_rss_gb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, train_windows=tr.n, val_windows=va.n)), flush=True)
                return
        trn = {k: v / rw for k, v in run.items()}
        ev_tr, ev_va, ev_nc = evaluate(model, tr, means, idx=sub), evaluate(model, va, means), evaluate(model, va, means, controls=False)
        rec = dict(epoch=ep + 1, sec=time.time() - t0, lr=opt.param_groups[0]["lr"], train_noisy=trn, train_eval_subset=ev_tr, val=ev_va, val_no_controls=ev_nc,
                   gap={h: ev_va[h] - ev_tr[h] for h in HEADS + ("aux", "total")})
        log.append(rec)
        sched.step(ev_va["total"])
        improved = ev_va["total"] < best - 1e-4
        if improved:
            best, bad = ev_va["total"], 0
            torch.save(model.state_dict(), out / "best.pt")
        else:
            bad += 1
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), sched=sched.state_dict(), epoch=ep + 1, best=best, bad=bad, log=log), str(out / "ckpt.pt") + ".tmp")
        Path(str(out / "ckpt.pt") + ".tmp").replace(out / "ckpt.pt")
        (out / "log.json").write_text(json.dumps(log, indent=1))
        print(f"epoch {ep + 1} {rec['sec']:.0f}s lr {rec['lr']:.1e} train_noisy {sum(trn[h] for h in HEADS):.3f} aux {trn['aux']:.3f} | val {ev_va['total']:.3f} (no controls {ev_nc['total']:.3f}) aux {ev_va['aux']:.3f} "
              + " ".join(f"{h} {ev_va[h]:.2f}" for h in HEADS) + (" *" if improved else ""), flush=True)
        if bad >= PATIENCE:
            break
    (out / "done.json").write_text(json.dumps(dict(seed=seed, epochs=len(log), best_val_total=best, early_stopped=bad >= PATIENCE)))
    print("TRAIN DONE", seed, len(log), best, flush=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    assert a[0] == "train"
    opt_ = lambda f, dflt: int(a[a.index(f) + 1]) if f in a else dflt
    train(int(a[1]), int(a[2]) if len(a) > 2 and a[2].isdigit() else 2, timing=opt_("--timing", 0), epochs=opt_("--epochs", EPOCH_CAP))
