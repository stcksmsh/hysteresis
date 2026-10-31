"""B3 training (docs/BRAIN_SPEC.md 4.1, 4.2, 4.7): the B2 core, trained on corpus features.

Round 2 (4.7) changes, on top of round 1 below: chunks of 180 s with the gradient through the whole chunk; loss = beta-NLL, beta 0.5
(Seitzer et al. 2022; B3_NOTES.md), surprisal and every check keep the plain Gaussian NLL; up to 12 epochs with early stopping
(patience 2) on the validation beta-NLL summed over the 4 layers, the validation set being 10 % of the training artists
(val_split.py, val_artists.json); every epoch's checkpoint is kept and the best is copied to best.pt (the earlier epoch on a tie);
hard stop at 20 h of wall time (training and validation), recorded in the meta of best.pt as cut; optional gradient checkpointing.
The held-out artists are not read by training at all. Where "60 s", "8 epochs" or "3 x 10 h" appear below, read the round-2 values.

Round 1 text:

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
import val_split  # noqa: E402

SEED = 20261031
CHUNK = 18000
LOOK = 2 * core.HORIZONS[-1]
CAP_S = 20 * 3600
BETA = 0.5
EPOCHS = 12
PATIENCE = 2
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

def chunk_terms(out, x, nvalid, chunk=None, beta=0.0):
    """Per-layer sums over valid (row, frame) pairs of the beta-NLL, the plain NLL and the MSE, and the counts.
    out: core.forward output on x[:, :chunk]. beta-NLL (Seitzer et al. 2022, eq. 7): the per-feature Gaussian NLL times the stopped-gradient
    variance ** beta, then the mean over features; beta = 0 is the plain NLL."""
    chunk = chunk or CHUNK
    B = x.shape[0]
    feats = x[..., :core.FEAT]
    cs = torch.cat([torch.zeros(B, 1, core.FEAT), feats.cumsum(1)], 1)
    t = torch.arange(chunk)
    sums, plain, mse, counts = [], [], [], []
    for o, hz in zip(out, core.HORIZONS):
        end = torch.clamp(t + 2 * hz, max=cs.shape[1] - 1)
        y = (cs[:, end] - cs[:, t + hz]) / hz
        valid = (t[None] + 2 * hz <= nvalid[:, None]).float()
        lv = o["logvar"]
        e = 0.5 * (lv + (y - o["mean"]) ** 2 * torch.exp(-lv) + math.log(2 * math.pi))
        w = e * torch.exp(beta * lv).detach() if beta > 0 else e
        sums.append((w.mean(-1) * valid).sum())
        plain.append((e.mean(-1) * valid).sum())
        mse.append((((y - o["mean"]) ** 2).mean(-1) * valid).sum())
        counts.append(valid.sum())
    return sums, plain, mse, counts


def chunk_nll(out, x, nvalid, chunk=None):
    """Plain NLL sums per layer and the counts (chunk_terms at beta 0)."""
    sums, _, _, counts = chunk_terms(out, x, nvalid, chunk)
    return sums, counts


def run_epoch(model, tracks, load, batch, seed, epoch, opt=None, lr_fn=None, step0=0, deadline=None, log=None, heartbeat_s=600, beta=BETA):
    """One pass over `tracks`. With `opt` it trains on the beta-NLL; without, it evaluates (no grad).
    Returns ({"beta_nll", "nll", "mse"}: per-layer means over valid frames, steps, hit_deadline)."""
    state = model.init_state(batch)
    tot, cnt, step, hit = np.zeros((3, 4)), np.zeros(4), step0, False
    t_start = t_beat = time.perf_counter()
    for b in epoch_batches(tracks, load, batch, seed, epoch):
        if b["reset"].any():
            state = model.reset_rows(state, b["reset"])
        x = b["x"]
        with torch.set_grad_enabled(opt is not None):
            out, state = model(x[:, :CHUNK], state)
            sums, plain, mse, counts = chunk_terms(out, x, b["nvalid"], beta=beta)
            del out
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
        tot += [[s.item() for s in v] for v in (sums, plain, mse)]
        cnt += [c.item() for c in counts]
        step += 1
        if log is not None and time.perf_counter() - t_beat >= heartbeat_s:
            t_beat = time.perf_counter()
            log(json.dumps({"heartbeat": True, "epoch": epoch + 1, "step": step, "mean_loss_so_far": float((tot[0] / np.maximum(cnt, 1)).sum()),
                            "wall_s": t_beat - t_start}))
        if deadline is not None and time.perf_counter() >= deadline:
            hit = True
            break
    mean = tot / np.maximum(cnt, 1.0)
    return {"beta_nll": mean[0], "nll": mean[1], "mse": mean[2]}, step, hit


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


def early_stop_step(meta, epoch, score, patience=PATIENCE):
    """Record validation `score` (lower is better) of finished `epoch` in meta. -> (is_best, stop). A tie keeps the earlier epoch."""
    is_best = meta["best_score"] is None or score < meta["best_score"]
    if is_best:
        meta["best_score"], meta["best_epoch"], meta["bad_epochs"] = float(score), epoch, 0
    else:
        meta["bad_epochs"] += 1
    return is_best, meta["bad_epochs"] >= patience


def mark_cut(path, wall_s):
    """Record in the meta of the best checkpoint that the run was cut by the wall-time cap. -> False if there is no best checkpoint yet."""
    path = Path(path)
    if not path.exists():
        return False
    ck = torch.load(path, weights_only=False)
    ck["meta"].update(cut=True, stopped_by_cap=True, wall_s=wall_s)
    tmp = path.with_suffix(".tmp")
    torch.save(ck, tmp)
    os.replace(tmp, path)
    return True


def fit(model, train, val, load, out_dir, epochs=EPOCHS, batch=8, cap_s=CAP_S, seed=SEED, steps_per_ep=None, log=lambda s: print(s, flush=True),
        load_len=None, resume=True, beta=BETA, patience=PATIENCE):
    """Train for up to `epochs` epochs on the beta-NLL (resuming from out_dir/last.pt when present), validating on `val` after each.
    Early stop after `patience` epochs without a lower validation beta-NLL (summed over the 4 layers). Every epoch is saved as epoch_NNN.pt, the best
    one also as best.pt. At `cap_s` of wall time (training and validation) it saves and stops; best.pt then says cut. Returns the last meta."""
    if not val:
        raise ValueError("fit needs validation tracks")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(THREADS)
    opt = make_optimizer(model)
    meta = {"epoch": 0, "step": 0, "wall_s": 0.0, "log": [], "stopped_by_cap": False, "cut": False, "stopped_early": False,
            "best_score": None, "best_epoch": 0, "bad_epochs": 0, "phase": model.phase, "head_norm": model.head_norm, "epochs": epochs,
            "batch": batch, "chunk": CHUNK, "beta": beta, "patience": patience, "grad_checkpoint": model.grad_checkpoint,
            "seed": seed, "model_seed": core.SEED, "params": model.n_params()}
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
    while meta["epoch"] < epochs and not meta["stopped_by_cap"] and not meta["stopped_early"]:
        e = meta["epoch"]
        t0 = time.perf_counter()
        stats, step, hit = run_epoch(model, train, load, batch, seed, e, opt, lr_fn, meta["step"], deadline=t0 + cap_s - meta["wall_s"], log=log, beta=beta)
        meta["step"] = step
        if hit:
            meta["wall_s"] += time.perf_counter() - t0
            meta["stopped_by_cap"] = meta["cut"] = True
            log(f"cap reached in epoch {e + 1}: saving and stopping")
        else:
            model.eval()
            vstats = run_epoch(model, val, load, batch, seed, e, log=log, beta=beta)[0]
            wall = time.perf_counter() - t0
            meta["wall_s"] += wall
            meta["epoch"] = e + 1
            score = float(vstats["beta_nll"].sum())
            is_best, stop = early_stop_step(meta, e + 1, score, patience)
            meta["log"].append({"epoch": e + 1, "wall_s": wall, "val_score": score, "best": is_best,
                                **{f"train_{k}": [float(v) for v in a] for k, a in stats.items()},
                                **{f"val_{k}": [float(v) for v in a] for k, a in vstats.items()}})
            log(json.dumps(meta["log"][-1]))
            save_ckpt(out_dir / f"epoch_{e + 1:03d}.pt", model, opt, meta)
            if is_best:
                save_ckpt(out_dir / "best.pt", model, opt, meta)
            if stop:
                meta["stopped_early"] = True
                log(f"early stop after epoch {e + 1}: best epoch {meta['best_epoch']}")
            elif meta["wall_s"] >= cap_s:
                meta["stopped_by_cap"] = meta["cut"] = True
                log(f"cap reached after epoch {e + 1}")
        if meta["cut"] and not mark_cut(out_dir / "best.pt", meta["wall_s"]):
            log("cut before the first finished epoch: there is no best checkpoint")
        save_ckpt(out_dir / "last.pt", model, opt, meta)
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
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--no-phase", action="store_true", help="ablation: the two grid-phase inputs are zeroed")
    ap.add_argument("--cap-hours", type=float, default=CAP_S / 3600, help="hard stop in wall hours, training and validation (default 20)")
    ap.add_argument("--val-artists", default=str(val_split.ARTISTS_JSON), help="JSON from val_split.py: the validation track ids")
    ap.add_argument("--grad-checkpoint", action="store_true", help="recompute each layer in the backward pass (less memory, same maths)")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args(argv)
    mean, std = load_stats(args.stats)
    tracks = [Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads(Path(args.manifest).read_text())]
    trn, val = val_split.split_tracks([t for t in tracks if t.split == "train"], val_split.load(args.val_artists))
    torch.manual_seed(SEED)
    no_grid = count_no_grid(tracks)
    print(f"{len(no_grid)} of {len(tracks)} tracks have fewer than 2 grid beats and get zero phase columns: {no_grid}", flush=True)
    model = core.Core(phase=not args.no_phase)
    model.grad_checkpoint = args.grad_checkpoint
    print(f"{len(trn)} fit tracks, {len(val)} validation tracks (the held-out side is not read)", flush=True)
    meta = fit(model, trn, val, lambda t: load_inputs(t, mean, std), args.out, args.epochs, batch=args.batch,
               cap_s=args.cap_hours * 3600, load_len=lambda t: len(np.load(t.feats, mmap_mode="r")), resume=not args.no_resume)
    print(json.dumps({k: meta[k] for k in ("epoch", "step", "wall_s", "stopped_by_cap", "cut", "stopped_early", "best_epoch", "params")}))


def count_no_grid(tracks):
    """Tracks whose offline grid has fewer than 2 beats; they train with zero phase columns."""
    return [t.id for t in tracks if len(json.loads(Path(t.beats).read_text())["beats"]) < 2]


if __name__ == "__main__":
    main()
