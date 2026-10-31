"""B3 training (docs/BRAIN_SPEC.md 4.1, 4.2): the B2 core, trained on corpus features. Code only; no real run yet.

Fixed here, before any result (the spec is silent on all of these):
  chunks     60 s (CHUNK frames). B parallel streams; each stream plays one song at a time, chunk after chunk, state carried
             and detached at each chunk edge. A new song resets that stream's state. A song's last chunk is zero-padded and
             masked. Each chunk comes with LOOK = 1600 frames of lookahead features, used only to build targets.
  loss       per layer, Gaussian NLL of the layer's head against the mean of the standardised features over [t+h, t+2h),
             averaged over the features and over every (stream, frame) whose whole target window lies inside the song;
             summed over the 4 layers with equal weight. Frames before that window exists carry no loss.
  optimiser  AdamW, betas (0.9, 0.99), weight decay 0.01 on matrices only; mode parameters (theta, nu_log) at 0.1 x lr, no decay;
             gradient norm clipped at 1.0; lr = LR, linear warm-up over WARMUP steps, then cosine per epoch from LR to 0.1 LR over
             `epochs`. The learning rate is a function of (epoch, step) only, so a resumed run follows the same schedule.
  clamp      core.clamp_modes() after every step.
  order      songs shuffled per epoch with numpy seed SEED + epoch; model init seed core.SEED.
  checkpoint last.pt (and epoch_NNN.pt) after every epoch, written atomically; resume = continue after the last finished epoch.
  cap        CAP_S = 3 x 10 h of training wall time, counted across resumes. At the cap the run saves and stops (stopped_by_cap).
  log        per epoch: train and held-out NLL per layer (nats per feature, mean over frames), wall seconds.
"""
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2  # noqa: E402
import core  # noqa: E402

SEED = 20261031
CHUNK = 6000
LOOK = 2 * core.HORIZONS[-1]
CAP_S = 3 * 10 * 3600
LR = 1e-3
WARMUP = 200
CLIP_NORM = 1.0
THREADS = 8


@dataclass
class Track:
    id: str
    feats: str        # .npy, raw fast features (T, 44)
    beats: str        # .json with "beats" (grid beats, seconds)
    split: str        # "train" or "heldout"


def load_stats(path):
    """(mean, std) from a stats npz; the corpus builder's file calls the SD `sd`, prep_corpus's smoke file `std`."""
    z = np.load(path)
    return z["mean"], z["std"] if "std" in z.files else z["sd"]


def load_inputs(track, mean, std):
    """Track -> (T, 46) float32 core input (standardised, clipped features + grid phase)."""
    feats = np.load(track.feats).astype(np.float32)
    return b2.build_inputs(feats, json.loads(Path(track.beats).read_text())["beats"], mean, std)


# ---- batching ---------------------------------------------------------------------------------------------------

def epoch_batches(tracks, load, batch, seed, epoch, chunk=None):
    """Yield dicts per step: x (B, chunk + LOOK, 46), nvalid (B,) frames left in the song from the chunk start,
    reset (B,) bool (a song starts in this row). Rows without a song are all zero with nvalid 0."""
    chunk = chunk or CHUNK
    order = list(np.random.default_rng(seed + epoch).permutation(len(tracks)))
    slots = [None] * batch    # [inputs, pos]

    def refill(i):
        slots[i] = [load(tracks[order.pop(0)]), 0] if order else None

    for i in range(batch):
        refill(i)
    while any(s is not None for s in slots):
        x = np.zeros((batch, chunk + LOOK, core.N_IN), np.float32)
        nvalid, reset = np.zeros(batch, np.int64), np.zeros(batch, bool)
        for i, s in enumerate(slots):
            if s is None:
                continue
            inp, pos = s
            seg = inp[pos:pos + chunk + LOOK]
            x[i, :len(seg)] = seg
            nvalid[i], reset[i] = len(inp) - pos, pos == 0
            s[1] = pos + chunk
        yield {"x": torch.from_numpy(x), "nvalid": torch.from_numpy(nvalid), "reset": torch.from_numpy(reset)}
        for i, s in enumerate(slots):
            if s is not None and s[1] >= len(s[0]):
                refill(i)


# ---- loss ---------------------------------------------------------------------------------------------------------

def chunk_nll(out, x, nvalid, chunk=None):
    """Per-layer NLL sums over valid (row, frame) pairs, and the counts. out: core.forward output on x[:, :chunk]."""
    chunk = chunk or CHUNK
    B = x.shape[0]
    feats = x[..., :core.FEAT]
    cs = torch.cat([torch.zeros(B, 1, core.FEAT), feats.cumsum(1)], 1)
    t = torch.arange(chunk)
    sums, counts = [], []
    for o, hz in zip(out, core.HORIZONS):
        end = torch.clamp(t + 2 * hz, max=cs.shape[1] - 1)
        y = (cs[:, end] - cs[:, t + hz]) / hz
        valid = (t[None] + 2 * hz <= nvalid[:, None]).float()
        lv = o["logvar"]
        e = 0.5 * (lv + (y - o["mean"]) ** 2 * torch.exp(-lv) + math.log(2 * math.pi)).mean(-1)
        sums.append((e * valid).sum())
        counts.append(valid.sum())
    return sums, counts


def run_epoch(model, tracks, load, batch, seed, epoch, opt=None, lr_fn=None, step0=0, deadline=None, log=None, heartbeat_s=600):
    """One pass over `tracks`. With `opt` it trains; without, it evaluates (no grad). Returns (per-layer NLL, steps, hit_deadline)."""
    state = model.init_state(batch)
    tot, cnt, step, hit = np.zeros(4), np.zeros(4), step0, False
    t_start = t_beat = time.perf_counter()
    for b in epoch_batches(tracks, load, batch, seed, epoch):
        if b["reset"].any():
            state = model.reset_rows(state, b["reset"])
        x = b["x"]
        with torch.set_grad_enabled(opt is not None):
            out, state = model(x[:, :CHUNK], state)
            sums, counts = chunk_nll(out, x, b["nvalid"])
            n = [max(float(c), 1.0) for c in counts]
            loss = sum(s / c for s, c in zip(sums, n))
        if opt is not None:
            for g in opt.param_groups:
                g["lr"] = lr_fn(step) * g["lr_mult"]
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), CLIP_NORM)
            opt.step()
            model.clamp_modes()
        state = model.detach_state(state)
        tot += [s.item() for s in sums]
        cnt += [c.item() for c in counts]
        step += 1
        if log is not None and time.perf_counter() - t_beat >= heartbeat_s:
            t_beat = time.perf_counter()
            log(json.dumps({"heartbeat": True, "epoch": epoch + 1, "step": step, "mean_loss_so_far": float((tot / np.maximum(cnt, 1)).sum()),
                            "wall_s": t_beat - t_start}))
        if deadline is not None and time.perf_counter() >= deadline:
            hit = True
            break
    return tot / np.maximum(cnt, 1.0), step, hit


# ---- optimiser and schedule ---------------------------------------------------------------------------------------

def make_optimizer(model):
    modes = [p for n, p in model.named_parameters() if n.endswith(("theta", "nu_log"))]
    decay = [p for n, p in model.named_parameters() if p.ndim >= 2]
    other = [p for n, p in model.named_parameters() if p.ndim < 2 and not n.endswith(("theta", "nu_log"))]
    groups = [{"params": decay, "weight_decay": 0.01, "lr_mult": 1.0},
              {"params": other, "weight_decay": 0.0, "lr_mult": 1.0},
              {"params": modes, "weight_decay": 0.0, "lr_mult": 0.1}]
    return torch.optim.AdamW(groups, lr=LR, betas=(0.9, 0.99))


def lr_schedule(steps_per_epoch, epochs):
    def fn(step):
        epoch = step // max(steps_per_epoch, 1)
        cosine = 0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(epoch, epochs) / max(epochs, 1)))
        return LR * min(1.0, (step + 1) / WARMUP) * cosine
    return fn


def steps_per_epoch(tracks, load_len, batch):
    """Number of steps one epoch takes, without loading audio: load_len(track) -> frames. Same slot logic as epoch_batches."""
    lens = list(load_len(t) for t in tracks)
    slots = [None] * batch
    q = list(range(len(lens)))
    for i in range(batch):
        slots[i] = [lens[q.pop(0)], 0] if q else None
    n = 0
    while any(s is not None for s in slots):
        n += 1
        for i, s in enumerate(slots):
            if s is not None:
                s[1] += CHUNK
                if s[1] >= s[0]:
                    slots[i] = [lens[q.pop(0)], 0] if q else None
    return n


# ---- checkpoints and the training loop -------------------------------------------------------------------------------

def save_ckpt(path, model, opt, meta):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    torch.save({"model": model.state_dict(), "opt": opt.state_dict(), "meta": meta}, tmp)
    os.replace(tmp, path)


def fit(model, train, heldout, load, out_dir, epochs, batch=8, cap_s=CAP_S, seed=SEED, steps_per_ep=None, log=lambda s: print(s, flush=True),
        load_len=None, resume=True):
    """Train for `epochs` epochs (resuming from out_dir/last.pt when present). Returns the meta dict of the last checkpoint."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(THREADS)
    opt = make_optimizer(model)
    meta = {"epoch": 0, "step": 0, "wall_s": 0.0, "log": [], "stopped_by_cap": False, "phase": model.phase, "head_norm": model.head_norm, "epochs": epochs,
            "batch": batch, "seed": seed, "model_seed": core.SEED, "params": model.n_params()}
    last = out_dir / "last.pt"
    if resume and last.exists():
        ck = torch.load(last, weights_only=False)
        model.load_state_dict(ck["model"])
        opt.load_state_dict(ck["opt"])
        meta = ck["meta"]
        log(f"resumed after epoch {meta['epoch']}, wall {meta['wall_s']:.0f} s")
    if steps_per_ep is None:
        steps_per_ep = steps_per_epoch(train, load_len, batch) if load_len else 1
    lr_fn = lr_schedule(steps_per_ep, epochs)
    while meta["epoch"] < epochs and not meta["stopped_by_cap"]:
        e = meta["epoch"]
        t0 = time.perf_counter()
        remaining = cap_s - meta["wall_s"]
        train_nll, step, hit = run_epoch(model, train, load, batch, seed, e, opt, lr_fn, meta["step"], deadline=t0 + remaining, log=log)
        wall = time.perf_counter() - t0
        meta["wall_s"] += wall
        meta["step"] = step
        if hit:
            meta["stopped_by_cap"] = True
            log(f"cap reached in epoch {e}: saving and stopping")
        else:
            model.eval()
            held_nll = run_epoch(model, heldout, load, batch, seed, e)[0] if heldout else np.full(4, np.nan)
            meta["epoch"] = e + 1
            meta["log"].append({"epoch": e + 1, "train_nll": [float(v) for v in train_nll], "heldout_nll": [float(v) for v in held_nll],
                                "wall_s": wall})
            log(json.dumps(meta["log"][-1]))
        save_ckpt(out_dir / "last.pt", model, opt, meta)
        if not hit:
            save_ckpt(out_dir / f"epoch_{meta['epoch']:03d}.pt", model, opt, meta)
    return meta


def load_model(path):
    """Checkpoint -> Core (eval mode) and its meta."""
    ck = torch.load(path, weights_only=False)
    model = core.Core(phase=ck["meta"]["phase"], head_norm=ck["meta"].get("head_norm", True))
    model.load_state_dict(ck["model"])
    return model.eval(), ck["meta"]


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="B3 training: train.py --manifest M.json --stats S.npz --out DIR --epochs N [--no-phase] [--batch 8]")
    ap.add_argument("--manifest", required=True, help="JSON list of {id, audio, feats, beats, split} (prep_corpus.py)")
    ap.add_argument("--stats", required=True, help="npz with mean and std of the training-side fast features")
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, required=True)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--no-phase", action="store_true", help="ablation: the two grid-phase inputs are zeroed")
    ap.add_argument("--cap-hours", type=float, default=CAP_S / 3600, help="wall-clock cap in training hours (default 3 x 10)")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args(argv)
    mean, std = load_stats(args.stats)
    tracks = [Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads(Path(args.manifest).read_text())]
    trn, ho = [t for t in tracks if t.split == "train"], [t for t in tracks if t.split == "heldout"]
    torch.manual_seed(SEED)
    no_grid = count_no_grid(tracks)
    print(f"{len(no_grid)} of {len(tracks)} tracks have fewer than 2 grid beats and get zero phase columns: {no_grid}", flush=True)
    model = core.Core(phase=not args.no_phase)
    meta = fit(model, trn, ho, lambda t: load_inputs(t, mean, std), args.out, args.epochs, batch=args.batch,
               cap_s=args.cap_hours * 3600, load_len=lambda t: len(np.load(t.feats, mmap_mode="r")), resume=not args.no_resume)
    print(json.dumps({k: meta[k] for k in ("epoch", "step", "wall_s", "stopped_by_cap", "params")}))


def count_no_grid(tracks):
    """Tracks whose offline grid has fewer than 2 beats; they train with zero phase columns."""
    return [t.id for t in tracks if len(json.loads(Path(t.beats).read_text())["beats"]) < 2]


if __name__ == "__main__":
    main()
