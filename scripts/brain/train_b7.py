"""B7 training (docs/BRAIN_SPEC.md 7.2): B3 round 2's training (train.py: beta-NLL 0.5, 180 s chunks, 8 streams, validation artists, early
stopping with patience 2, hard stop) on the Core7 network, warm-started from B3 round 2 epoch 12.

Fixed here, before any result:
  warm start   the B3 round-2 weights fill every B3 parameter; the new ones (relay, skip, w_g, w_tau at zero; key / query projections and
               log_tau as in core_b7) stay at their init, so step 0 is B3 (checked in smoke_b7.py). The optimiser and its state are new.
  schedule     train.py's: 200 warm-up steps to LR 1e-3, then cosine per epoch to 0.1 LR over the 8 epochs (the B3 round-2 values).
  epochs       up to 8, patience 2, 24 h of wall time (training and validation), the best validation beta-NLL epoch is best.pt.
Outputs: OUT/ (default /secondary/hyst-data/brain/b7/ckpt/phase/): epoch_NNN.pt, best.pt, last.pt, warm_start.json.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import core_b7  # noqa: E402
import train  # noqa: E402
import val_split  # noqa: E402

EPOCHS = 8
CAP_H = 24.0
WARM = Path("/secondary/hyst-data/brain/b3r2/ckpt/phase/best.pt")


def warm_started(path=WARM, **kw):
    """A Core7 holding the B3 checkpoint's weights; the only missing keys are the new B7 ones."""
    ck = torch.load(path, weights_only=False)
    meta = ck["meta"]
    model = core_b7.Core7(phase=meta["phase"], head_norm=meta.get("head_norm", True), **kw)
    r = model.load_state_dict(ck["model"], strict=False)
    new = {n for n, _ in model.named_parameters() if n.split(".")[0] in ("key_proj", "query_proj", "log_tau", "relay", "skip", "w_g", "w_tau")}
    if r.unexpected_keys or set(r.missing_keys) != new:
        raise ValueError(f"warm start: unexpected {r.unexpected_keys}, missing {sorted(set(r.missing_keys) ^ new)}")
    return model, {"warm_start": str(path), "epoch": meta["epoch"], "best_score": meta.get("best_score")}


def load_model7(path):
    """Checkpoint -> Core7 (eval mode) and its meta."""
    ck = torch.load(path, weights_only=False)
    model = core_b7.Core7(phase=ck["meta"]["phase"], head_norm=ck["meta"].get("head_norm", True))
    model.load_state_dict(ck["model"])
    return model.eval(), ck["meta"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="B7 training: train_b7.py --manifest M.json --stats S.npz --out DIR [--batch 8] [--grad-checkpoint]")
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=EPOCHS)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--cap-hours", type=float, default=CAP_H)
    ap.add_argument("--val-artists", default=str(val_split.ARTISTS_JSON))
    ap.add_argument("--warm", default=str(WARM))
    ap.add_argument("--grad-checkpoint", action="store_true")
    ap.add_argument("--no-resume", action="store_true")
    args = ap.parse_args(argv)
    mean, std = train.load_stats(args.stats)
    tracks = [train.Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads(Path(args.manifest).read_text())]
    trn, val = val_split.split_tracks([t for t in tracks if t.split == "train"], val_split.load(args.val_artists))
    torch.manual_seed(train.SEED)
    model, warm = warm_started(args.warm)
    model.grad_checkpoint = args.grad_checkpoint
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "warm_start.json").write_text(json.dumps(warm))
    print(f"{len(trn)} fit tracks, {len(val)} validation tracks (the held-out side is not read); warm start {warm}; {model.n_params()} parameters", flush=True)
    meta = train.fit(model, trn, val, lambda t: train.load_inputs(t, mean, std), args.out, args.epochs, batch=args.batch, cap_s=args.cap_hours * 3600,
                     load_len=lambda t: len(np.load(t.feats, mmap_mode="r")), resume=not args.no_resume)
    print(json.dumps({k: meta[k] for k in ("epoch", "step", "wall_s", "stopped_by_cap", "cut", "stopped_early", "best_epoch", "params")}))


if __name__ == "__main__":
    main()
