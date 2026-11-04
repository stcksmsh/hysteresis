"""Z5 benchmark: B7 cost per audio hour (docs/BODY_BRAIN_PLAN.md §4 Z5). Job contract of scripts/compute: --out DIR (results.json, progress.json); --data is accepted and unused
(synthetic standardised features: the cost does not depend on the content).

Per variant, in its own process (so the peak memory is that variant's own):
  train_ckpt     forward + backward + optimiser step, gradient checkpointing on   (what training uses)
  train_nockpt   the same, checkpointing off
  forward        forward only, no grad
A step is batch 8 x 180 s = 0.4 audio hours. Step 0 (warm-up) is dropped; the median of the others is reported. Model: Core7, 10-tap skip, no hippocampus, fresh init
(the B7 training configuration; the warm-start weights do not change the cost). Threads: --threads (8 locally, spec §0; on Kaggle pass the core count).
    python bench_b7.py --out DIR [--data DIR] [--device auto|cpu|cuda] [--threads 8] [--steps 4] [--minutes 20]
"""
import argparse
import json
import os
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import core_b7  # noqa: E402
import train  # noqa: E402

VARIANTS = ("forward", "train_ckpt", "train_nockpt")      # the one that may run out of memory last
BATCH = 8


def run_variant(a):
    torch.set_num_threads(a.threads)
    torch.manual_seed(0)
    model = core_b7.Core7(skip_taps=10, hippocampus=False)
    model.grad_checkpoint = a.variant == "train_ckpt"
    core.use_device(model, a.device)
    dev = next(model.parameters()).device
    rng = np.random.default_rng(0)
    opt = train.make_optimizer(model) if a.variant != "forward" else None
    state, times = model.init_state(BATCH), []
    if dev.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    deadline = time.perf_counter() + a.budget_s
    for step in range(a.steps + 1):
        x = torch.from_numpy(rng.standard_normal((BATCH, train.CHUNK + train.LOOK, core.N_IN)).astype(np.float32)).to(dev)
        nvalid = torch.full((BATCH,), train.CHUNK + train.LOOK, dtype=torch.long, device=dev)
        t0 = time.perf_counter()
        with torch.set_grad_enabled(opt is not None):
            out, state = model(x[:, :train.CHUNK], state)
            if opt is not None:
                sums, _, _, counts = train.chunk_terms(out, x, nvalid, beta=train.BETA)
                loss = sum(s / max(float(c), 1.0) for s, c in zip(sums, counts))
        if opt is not None:
            opt.zero_grad()
            loss.backward()
            opt.step()
            model.clamp_modes()
        del out
        state = model.detach_state(state)
        if dev.type == "cuda":
            torch.cuda.synchronize()
        times.append(time.perf_counter() - t0)
        print(json.dumps({"variant": a.variant, "step": step, "s": round(times[-1], 2)}), flush=True)
        (Path(a.out) / "progress.json").write_text(json.dumps({"variant": a.variant, "step": step, "time": time.time()}))
        if time.perf_counter() > deadline and step >= 1:
            break
    med = statistics.median(times[1:])
    hours = BATCH * train.CHUNK / 100 / 3600
    res = {"variant": a.variant, "steps_timed": len(times) - 1, "s_per_step_median": med, "audio_hours_per_step": hours,
           "s_per_audio_hour": med / hours, "peak_rss_gb": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6}
    if dev.type == "cuda":
        res["peak_cuda_gb"] = torch.cuda.max_memory_allocated() / 1e9
    print(json.dumps(res), flush=True)
    (Path(a.out) / f"variant_{a.variant}.json").write_text(json.dumps(res))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default="")
    ap.add_argument("--device", default="auto", help="auto = cuda if there is one, else cpu")
    ap.add_argument("--threads", type=int, default=min(8, os.cpu_count() or 1), help="8 on the laptop (spec section 0); the core count on a smaller host")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--minutes", type=float, default=20, help="total wall budget; each variant gets a third (after its first two steps)")
    ap.add_argument("--variant", choices=VARIANTS, help="internal: run one variant in this process")
    a = ap.parse_args(argv)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    if a.device == "auto":
        a.device = "cuda" if torch.cuda.is_available() else "cpu"
        sys.argv += ["--device", a.device]
    a.budget_s = a.minutes * 60 / len(VARIANTS)
    if a.variant:
        return run_variant(a)
    args = [x for x in sys.argv[1:]]
    for v in VARIANTS:
        r = subprocess.run([sys.executable, "-u", __file__, *args, "--variant", v])
        if r.returncode:
            print(json.dumps({"variant": v, "failed": r.returncode}), flush=True)
    rows = {v: json.loads((Path(a.out) / f"variant_{v}.json").read_text()) for v in VARIANTS if (Path(a.out) / f"variant_{v}.json").exists()}
    info = {"device": a.device, "threads": a.threads, "cpu_count": os.cpu_count(), "torch": torch.__version__,
            "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None, "batch": BATCH, "chunk_frames": train.CHUNK}
    (Path(a.out) / "results.json").write_text(json.dumps({"info": info, "variants": rows}, indent=1))
    print(json.dumps({"info": info, "variants": rows}), flush=True)


if __name__ == "__main__":
    main()
