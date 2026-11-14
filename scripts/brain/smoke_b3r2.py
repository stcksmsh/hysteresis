"""B3 round 2 smoke run (BRAIN_SPEC 4.7, "Memory and time"): a few real training steps and validation steps at one setting, then the projection of
12 epochs. Peak RAM is read from the memory-capped scope (`systemctl --user show <unit> -p MemoryPeak`), not from here.

  smoke_b3r2.py --batch 8 [--grad-checkpoint] [--steps 8]      inside:  systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0 --unit=...
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import train  # noqa: E402
import val_split  # noqa: E402

C = Path("/secondary/hyst-data/brain/corpus")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--val-steps", type=int, default=3)
    ap.add_argument("--grad-checkpoint", action="store_true")
    a = ap.parse_args()
    mean, std = train.load_stats(C / "feature_stats.npz")
    tracks = [train.Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads((C / "manifest.json").read_text())]
    fit, val = val_split.split_tracks([t for t in tracks if t.split == "train"], val_split.load())
    load = lambda t: train.load_inputs(t, mean, std)
    n_len = lambda t: len(np.load(t.feats, mmap_mode="r"))
    spe_fit, spe_val = train.steps_per_epoch(fit, n_len, a.batch), train.steps_per_epoch(val, n_len, a.batch)
    print(json.dumps({"batch": a.batch, "chunk": train.CHUNK, "grad_checkpoint": a.grad_checkpoint, "fit_tracks": len(fit), "val_tracks": len(val),
                      "steps_per_epoch_fit": spe_fit, "steps_per_epoch_val": spe_val}), flush=True)
    torch.set_num_threads(train.THREADS)
    torch.manual_seed(train.SEED)
    model = core.Core()
    model.grad_checkpoint = a.grad_checkpoint
    opt = train.make_optimizer(model)
    lr_fn = train.lr_schedule(spe_fit, train.EPOCHS)
    state, times, losses = model.init_state(a.batch), [], []
    for step, b in enumerate(train.epoch_batches(fit, load, a.batch, train.SEED, 0)):
        t0 = time.perf_counter()
        if b["reset"].any():
            state = model.reset_rows(state, b["reset"])
        out, state = model(b["x"][:, :train.CHUNK], state)
        sums, _, _, counts = train.chunk_terms(out, b["x"], b["nvalid"], beta=train.BETA)
        del out
        loss = sum(s / max(float(c), 1.0) for s, c in zip(sums, counts))
        for g in opt.param_groups:
            g["lr"] = lr_fn(step) * g["lr_mult"]
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), train.CLIP_NORM)
        opt.step()
        model.clamp_modes()
        state = model.detach_state(state)
        times.append(time.perf_counter() - t0)
        losses.append(float(loss))
        print(json.dumps({"step": step + 1, "s": round(times[-1], 1), "loss": round(losses[-1], 4)}), flush=True)
        if step + 1 >= a.steps:
            break
    model.eval()
    vtimes = []
    state = model.init_state(a.batch)
    with torch.no_grad():
        for step, b in enumerate(train.epoch_batches(val, load, a.batch, train.SEED, 0)):
            t0 = time.perf_counter()
            if b["reset"].any():
                state = model.reset_rows(state, b["reset"])
            out, state = model(b["x"][:, :train.CHUNK], state)
            train.chunk_terms(out, b["x"], b["nvalid"], beta=train.BETA)
            del out
            state = model.detach_state(state)
            vtimes.append(time.perf_counter() - t0)
            print(json.dumps({"val_step": step + 1, "s": round(vtimes[-1], 1)}), flush=True)
            if step + 1 >= a.val_steps:
                break
    # the first step also pays for allocator warm-up: the projection uses the median of the steps after it
    t_step, t_val = statistics.median(times[1:] or times), statistics.median(vtimes[1:] or vtimes)
    epoch_s = spe_fit * t_step + spe_val * t_val
    print(json.dumps({"summary": True, "batch": a.batch, "grad_checkpoint": a.grad_checkpoint, "train_step_s_median": t_step, "train_step_s_all": times,
                      "val_step_s_median": t_val, "epoch_h": epoch_s / 3600, "twelve_epochs_h": 12 * epoch_s / 3600,
                      "note": "peak RAM: systemctl --user show <unit> -p MemoryPeak"}), flush=True)


if __name__ == "__main__":
    main()
