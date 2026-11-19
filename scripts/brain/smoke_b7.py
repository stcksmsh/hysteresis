"""B7 smoke run (BRAIN_SPEC 7.3, 7.9): the B7 = B3 identity check on 10 held-out songs, and peak RAM and time per step at 8 streams x 180 s with
the projection to 8 epochs (and, for the slowdown, the same steps on B3).

  smoke_b7.py identity [--songs 10] [--double-songs 2]
  smoke_b7.py steps --model b7|b3 [--batch 8] [--grad-checkpoint] [--steps 4]      inside a memory-capped systemd-run scope (smoke_b7.sh)

Identity: B3 round-2 epoch 12 as core.Core against the same weights in Core7 (new weights at their step-0 values), whole songs, state carried in
chunks of 6,000 frames; the maximum absolute difference of every layer's mean, log-variance and error, in float32 (the training precision) and,
for the first --double-songs songs, in float64 (where the difference is rounding only). Peak RAM is the process's peak RSS (anon plus mapped files)
and, at the end, the cgroup's anon bytes from memory.stat.
"""
import argparse
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import core_b7  # noqa: E402
import train  # noqa: E402
import train_b7  # noqa: E402
import val_split  # noqa: E402

C = Path("/secondary/hyst-data/brain/corpus")
EVAL_CHUNK = 6000


def manifest():
    return [train.Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads((C / "manifest.json").read_text())]


def run_song(model, x, chunk=EVAL_CHUNK, double=False):
    state = model.init_state()
    if double:
        state = core_b7.to_double(state)
    outs = []
    with torch.no_grad():
        for a in range(0, len(x), chunk):
            xb = torch.from_numpy(x[a:a + chunk])[None]
            out, state = model(xb.double() if double else xb, state)
            outs.append([{k: o[k] for k in ("mean", "logvar", "err")} for o in out])
    return [{k: torch.cat([o[i][k] for o in outs], 1) for k in ("mean", "logvar", "err")} for i in range(4)]


def identity(a):
    mean, std = train.load_stats(C / "feature_stats.npz")
    songs = [t for t in manifest() if t.split == "heldout"][:a.songs]
    ck = torch.load(train_b7.WARM, weights_only=False)
    b3 = core.Core(phase=ck["meta"]["phase"], head_norm=ck["meta"].get("head_norm", True))
    b3.load_state_dict(ck["model"])
    b3.eval()
    b7, _ = train_b7.warm_started()
    b7.eval()
    torch.set_num_threads(8)
    res = {"epoch": ck["meta"]["epoch"], "songs": [], "max_abs_diff_float32": 0.0, "max_abs_diff_float64": 0.0}
    for n, t in enumerate(songs):
        x = train.load_inputs(t, mean, std)
        o3, o7 = run_song(b3, x), run_song(b7, x)
        d = max(float((o3[i][k] - o7[i][k]).abs().max()) for i in range(4) for k in ("mean", "logvar", "err"))
        row = {"id": t.id, "frames": len(x), "max_abs_diff_float32": d}
        if n < a.double_songs:
            b3d, b7d = core.Core(phase=b3.phase, head_norm=b3.head_norm), core_b7.Core7(phase=b3.phase, head_norm=b3.head_norm)
            b3d.load_state_dict(b3.state_dict())
            b7d.load_state_dict(b7.state_dict())
            b3d, b7d = b3d.double().eval(), b7d.double().eval()
            p3, p7 = run_song(b3d, x, double=True), run_song(b7d, x, double=True)
            row["max_abs_diff_float64"] = max(float((p3[i][k] - p7[i][k]).abs().max()) for i in range(4) for k in ("mean", "logvar", "err"))
            res["max_abs_diff_float64"] = max(res["max_abs_diff_float64"], row["max_abs_diff_float64"])
        res["songs"].append(row)
        res["max_abs_diff_float32"] = max(res["max_abs_diff_float32"], d)
        print(json.dumps(row), flush=True)
    res["pass_1e-5_float32"] = res["max_abs_diff_float32"] < 1e-5
    print(json.dumps({"identity": res}), flush=True)


def cgroup_anon():
    try:
        cg = Path("/sys/fs/cgroup") / Path("/proc/self/cgroup").read_text().strip().split("::")[-1].lstrip("/")
        return int(next(l.split()[1] for l in (cg / "memory.stat").read_text().splitlines() if l.startswith("anon ")))
    except Exception:
        return None


def steps(a):
    mean, std = train.load_stats(C / "feature_stats.npz")
    fit, val = val_split.split_tracks([t for t in manifest() if t.split == "train"], val_split.load())
    load = lambda t: train.load_inputs(t, mean, std)
    n_len = lambda t: len(np.load(t.feats, mmap_mode="r"))
    spe_fit, spe_val = train.steps_per_epoch(fit, n_len, a.batch), train.steps_per_epoch(val, n_len, a.batch)
    print(json.dumps({"model": a.model, "batch": a.batch, "chunk": train.CHUNK, "grad_checkpoint": a.grad_checkpoint, "fit_tracks": len(fit), "val_tracks": len(val),
                      "steps_per_epoch_fit": spe_fit, "steps_per_epoch_val": spe_val}), flush=True)
    torch.set_num_threads(train.THREADS)
    torch.manual_seed(train.SEED)
    model = train_b7.warm_started()[0] if a.model == "b7" else core.Core()
    model.grad_checkpoint = a.grad_checkpoint
    opt = train.make_optimizer(model)
    lr_fn = train.lr_schedule(spe_fit, train_b7.EPOCHS)
    state, times, losses = model.init_state(a.batch), [], []
    for step, b in enumerate(train.epoch_batches(fit, load, a.batch, train.SEED, 0)):
        t0 = time.perf_counter()
        if b["reset"].any():
            state = model.reset_rows(state, b["reset"])
        out, state = model(b["x"][:, :train.CHUNK], state)
        rss_fwd = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
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
        print(json.dumps({"step": step + 1, "s": round(times[-1], 1), "loss": round(losses[-1], 4), "store_columns": int(state["sk"].shape[1]) if "sk" in state else None,
                          "peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, "peak_rss_after_forward_gb": rss_fwd}), flush=True)
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
    t_step, t_val = statistics.median(times[1:] or times), statistics.median(vtimes[1:] or vtimes)
    epoch_s = spe_fit * t_step + spe_val * t_val
    print(json.dumps({"summary": True, "model": a.model, "batch": a.batch, "grad_checkpoint": a.grad_checkpoint, "train_step_s_median": t_step, "train_step_s_all": times,
                      "val_step_s_median": t_val, "epoch_h": epoch_s / 3600, "eight_epochs_h": 8 * epoch_s / 3600,
                      "peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6, "cgroup_anon_gb_at_end": (cgroup_anon() or 0) / 1e9,
                      "note": "scope peak (with file cache): systemctl --user show <unit> -p MemoryPeak"}), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("identity", "steps"))
    ap.add_argument("--model", choices=("b7", "b3"), default="b7")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--val-steps", type=int, default=3)
    ap.add_argument("--songs", type=int, default=10)
    ap.add_argument("--double-songs", type=int, default=2)
    ap.add_argument("--grad-checkpoint", action="store_true")
    a = ap.parse_args()
    identity(a) if a.mode == "identity" else steps(a)


if __name__ == "__main__":
    main()
