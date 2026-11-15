"""WO41 T1b training (docs/T1B_RULES.md section 4). Brain env.

    t1b_train.py norm                          cortex column mean/sd from the train split -> t1b/cortex_norm.npz
    t1b_train.py train SEED THREADS [--max-epochs N] [--songs N]   -> t1b/e1/seed<SEED>/ (ckpt.pt each epoch, atomic, resumable; log.json; best.pt; done.json)
    t1b_train.py time THREADS                  a few windows, prints seconds per window and peak memory (timing for the estimate)
A song is one T0 FineDance sequence (fd_NNN): 4 copies (V1, V2, V1m, V2m) share its music. Slots: SLOTS songs advance in lockstep, one 60 s window per optimiser step.
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t1b_model as M  # noqa: E402

OUT = Path(os.environ.get("HYST_T1B", "/secondary/hyst-data/body/t1b"))
COPIES = ("V1", "V2", "V1m", "V2m")
WIN_FR, WIN_TOK, WIN_ST = 6000, 120, 3000
SLOTS, CLIP_X = 4, 5.0
SEEDS = (41101, 41102, 41103)
NOISE_P, LR, WD, CLIP_G, PATIENCE, MAXEP = 0.10, 1e-3, 0.01, 1.0, 5, 60
N_POST = (256,)                                                                   # entries per posture stage; set by the ruling (rules note section 2)


def song_index():
    """-> {key: dict(split, tok=[per copy dict], n)} for every song with 4 token files and a cortex file"""
    out = {}
    for p in sorted((OUT / "tokens").glob("fd_*__V1.npz")):
        key = p.stem.split("__")[0]
        if not (OUT / "cortex" / f"{key}.npy").exists():
            continue
        out[key] = dict(split=str(np.load(p)["split"]))
    return out


def load_tokens(key):
    cs = []
    for c in COPIES:
        z = np.load(OUT / "tokens" / f"{key}__{c}.npz")
        pe = z["pent"].astype(np.int64)
        cs.append(dict(c1=z["code1"].astype(np.int64), c2=z["code2"].astype(np.int64), v=z["vbin"].astype(np.int64), p=pe.reshape(len(pe), -1), ok=z["ok"].astype(bool), w=float(z["weight"])))
    n = min(len(c["c1"]) for c in cs)
    return cs, n


def cmd_norm():
    idx = song_index()
    s = s2 = None
    n = 0
    for k, d in idx.items():
        if d["split"] != "train":
            continue
        x = np.load(OUT / "cortex" / f"{k}.npy", mmap_mode="r")[::10].astype(np.float64)
        s = x.sum(0) if s is None else s + x.sum(0)
        s2 = (x ** 2).sum(0) if s2 is None else s2 + (x ** 2).sum(0)
        n += len(x)
    mu = s / n
    sd = np.sqrt(np.maximum(s2 / n - mu ** 2, 1e-12))
    np.savez(OUT / "cortex_norm.npz", mu=mu.astype(np.float32), sd=np.maximum(sd, 1e-3).astype(np.float32), n_frames_every10th=n)
    print("norm", n)


class Song:
    def __init__(self, key, norm):
        self.key, self.norm = key, norm
        self.x = np.load(OUT / "cortex" / f"{key}.npy", mmap_mode="r")
        self.cs, self.n = load_tokens(key)
        self.n = min(self.n, int(len(self.x) / 50))                              # tokens whose chunk starts after the audio has ended are dropped (sync check: fd_043, fd_059 have 18-20 s less audio than motion)
        self.nwin = -(-self.n // WIN_TOK)

    def window(self, w):
        """-> x (3000, 2105) 50 Hz standardised float32, tokens (4 copies) c1, c2, v (4, 120), p (4, 120, S), mask (4, 120) float weights"""
        a = self.x[w * WIN_FR:(w + 1) * WIN_FR].astype(np.float32)
        a = np.clip((a - self.norm[0]) / self.norm[1], -CLIP_X, CLIP_X)
        if len(a) < WIN_FR:
            a = np.concatenate([a, np.zeros((WIN_FR - len(a), a.shape[1]), np.float32)])
        x = a.reshape(WIN_ST, 2, -1).mean(1)
        t = slice(w * WIN_TOK, min(self.n, (w + 1) * WIN_TOK))
        m = t.stop - t.start
        pad = lambda arr: np.concatenate([arr[t], np.zeros((WIN_TOK - m,) + arr.shape[1:], arr.dtype)])
        tok = {k: np.stack([pad(c[k]) for c in self.cs]) for k in ("c1", "c2", "v", "p")}
        wt = np.stack([pad(c["ok"].astype(np.float32)) * c["w"] for c in self.cs])
        return x, tok, wt


def load_norm():
    z = np.load(OUT / "cortex_norm.npz")
    return z["mu"], z["sd"]


def queues(keys, rng, slots=SLOTS):
    """greedy balance of songs (by window count) over slots"""
    ks = [keys[i] for i in rng.permutation(len(keys))]
    q, load = [[] for _ in range(slots)], [0] * slots
    for k in ks:
        i = int(np.argmin(load))
        q[i].append(k)
        load[i] += 1                                                              # window counts are not known here; equal song counts is the rule
    return q


class Runner:
    """lockstep window steps over SLOTS songs; one optimiser step per window step when `opt` is given"""

    def __init__(self, model, songs, norm):
        self.m, self.songs, self.norm = model, songs, norm

    def run(self, q, opt=None, noise_p=0.0, gen=None, clip=CLIP_G):
        m, B = self.m, len(q)
        pl = m.planner
        cur = [None] * B                                                          # (Song, next window)
        qi = [0] * B
        lh = torch.zeros(B, M.NR + M.NA)
        ps = pl.zero_state(B * 4)
        tail = torch.zeros(B, 25, M.NR + M.NA)
        prev = None
        tot = dict(code=0.0, vig=0.0, post=0.0)
        wsum = 0.0
        nstep = 0
        while True:
            start = torch.zeros(B, dtype=torch.bool)
            for b in range(B):
                if (cur[b] is None or cur[b][1] >= cur[b][0].nwin) and qi[b] < len(q[b]):
                    cur[b] = (self.songs(q[b][qi[b]]), 0)
                    qi[b] += 1
                    start[b] = True
                elif cur[b] is not None and cur[b][1] >= cur[b][0].nwin:
                    cur[b] = None
            act = [b for b in range(B) if cur[b] is not None]
            if not act:
                break
            xs = torch.zeros(B, WIN_ST, M.WIDTH)
            toks = {k: torch.zeros((B * 4, WIN_TOK) + (() if k != "p" else (len(N_POST),)), dtype=torch.long) for k in ("c1", "c2", "v", "p")}
            wt = torch.zeros(B * 4, WIN_TOK)
            for b in act:
                s, w = cur[b]
                x, tok, ww = s.window(w)
                xs[b] = torch.from_numpy(x)
                for k in toks:
                    toks[k][4 * b:4 * b + 4] = torch.from_numpy(tok[k])
                wt[4 * b:4 * b + 4] = torch.from_numpy(ww)
                cur[b] = (s, w + 1)
            for b in range(B):
                if b not in act:
                    start[b] = True                                               # an idle slot stays in the start state
            if start.any():
                lh = lh.clone(); lh[start] = 0
                tail = tail.clone(); tail[start] = 0
                rows = start.repeat_interleave(4)
                pl.reset_rows(ps, rows)
                if prev is not None:
                    ok = prev[4].clone(); ok[rows] = False
                    prev = prev[:4] + (ok,)
            with torch.set_grad_enabled(opt is not None):
                st, lh = m.listener(xs, lh)
                cat = torch.cat([tail, st], 1)
                idx = torch.arange(WIN_TOK) * 25 + 12                             # token i reads step 25 i - 13 of the window = index 25 i + 12 of [tail, states]
                lis = cat[:, idx].repeat_interleave(4, 0)
                ce, ps, prev = M.run_window(m, lis, toks, ps, prev, noise_p, gen)
                den = wt.sum().clamp_min(1e-9)
                parts = {k: (v * wt).sum() / den for k, v in ce.items()}
                loss = sum(parts.values())
                if opt is not None and wt.sum() > 0:
                    opt.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(m.parameters(), clip)
                    opt.step()
            lh, tail = lh.detach(), st[:, -25:].detach()
            ps = {k: v.detach() for k, v in ps.items()}
            prev = tuple(t.detach() for t in prev)
            for k in tot:
                tot[k] += float(parts[k].detach()) * float(wt.sum())
            wsum += float(wt.sum())
            nstep += 1
        return {k: v / max(wsum, 1e-9) for k, v in tot.items()}, nstep


def total(d):
    return sum(d.values())


def make_model(seed):
    torch.manual_seed(seed)
    return M.Model(n_post=N_POST)


def cmd_train(seed, threads, max_epochs=MAXEP, nsongs=None):
    torch.set_num_threads(threads)
    d = OUT / "e1" / f"seed{seed}"
    d.mkdir(parents=True, exist_ok=True)
    idx = song_index()
    norm = load_norm()
    songs = lambda k: Song(k, norm)
    tr = sorted(k for k, v in idx.items() if v["split"] == "train")[:nsongs]
    va = sorted(k for k, v in idx.items() if v["split"] == "validation")[:nsongs]
    tr_eval = tr[::max(1, len(tr) // 16)][:16]
    model = make_model(seed)
    opt = torch.optim.AdamW(model.parameters(), LR, weight_decay=WD)
    rng = np.random.default_rng(seed)
    gen = torch.Generator().manual_seed(seed + 7)
    log, best, bad, ep0, lr_bad = [], 1e9, 0, 0, 0
    if (d / "ckpt.pt").exists():
        c = torch.load(d / "ckpt.pt", weights_only=False)
        model.load_state_dict(c["model"]); opt.load_state_dict(c["opt"]); rng.bit_generator.state = c["rng"]; gen.set_state(c["gen"])
        log, best, bad, ep0, lr_bad = c["log"], c["best"], c["bad"], c["epoch"] + 1, c["lr_bad"]
    R = Runner(model, songs, norm)
    for ep in range(ep0, max_epochs):
        t0 = time.time()
        model.train()
        trl, nst = R.run(queues(tr, rng), opt, NOISE_P, gen)
        model.eval()
        tre, _ = R.run(queues(tr_eval, np.random.default_rng(0)))
        val, _ = R.run(queues(va, np.random.default_rng(0)))
        rec = dict(epoch=ep, train_noisy=trl, train_eval=tre, val=val, gap=total(val) - total(tre), lr=opt.param_groups[0]["lr"], steps=nst, secs=time.time() - t0)
        log.append(rec)
        print(json.dumps(rec), flush=True)
        if total(val) < best - 1e-4:
            best, bad, lr_bad = total(val), 0, 0
            torch.save(model.state_dict(), d / "best.pt")
        else:
            bad += 1
            lr_bad += 1
            if lr_bad >= 2:
                for g in opt.param_groups:
                    g["lr"] *= 0.5
                lr_bad = 0
        torch.save(dict(model=model.state_dict(), opt=opt.state_dict(), rng=rng.bit_generator.state, gen=gen.get_state(), best=best, bad=bad, log=log, epoch=ep, lr_bad=lr_bad), d / "ckpt.tmp")
        (d / "ckpt.tmp").replace(d / "ckpt.pt")
        (d / "log.json").write_text(json.dumps(log, indent=1))
        if bad >= PATIENCE:
            break
    (d / "done.json").write_text(json.dumps(dict(epochs=len(log), best_val=best, stopped="early_stop" if bad >= PATIENCE else "cap", seed=seed, threads=threads)))


def cmd_time(threads):
    import resource
    torch.set_num_threads(threads)
    idx = song_index()
    norm = load_norm()
    keys = sorted(k for k, v in idx.items() if v["split"] == "train")[:SLOTS]
    model = make_model(SEEDS[0]).train()
    opt = torch.optim.AdamW(model.parameters(), LR, weight_decay=WD)
    R = Runner(model, lambda k: Song(k, norm), norm)
    t0 = time.time()
    _, n = R.run([[k] for k in keys], opt, NOISE_P, torch.Generator().manual_seed(1))
    dt = time.time() - t0
    print(json.dumps(dict(window_steps=n, secs=dt, secs_per_step=dt / n, peak_rss_gb=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6)))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "norm":
        cmd_norm()
    elif a[0] == "time":
        cmd_time(int(a[1]))
    else:
        kw = {}
        if "--max-epochs" in a:
            kw["max_epochs"] = int(a[a.index("--max-epochs") + 1])
        if "--songs" in a:
            kw["nsongs"] = int(a[a.index("--songs") + 1])
        cmd_train(int(a[1]), int(a[2]), **kw)
