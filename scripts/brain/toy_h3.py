"""H3 toy (docs/BRAIN_SPEC.md 7.15): T1a + T1b of 7.10 R3 on designs A, B, C, same toy settings and evaluation as toy_h2.py.
  toy_h3.py --design A|B|C [--k 64] [--tau 0.05] [--lr 0.05] [--blend-steps 400] [--a0 8] [--b0 0.5] [--cortex-steps 1500] [--threads 2] [--tag try1]
Stage 1 (once per design, then reused from <h3 dir>/cortex_<design>.pt): the toy cortex is trained exactly as in H2's toy with the hippocampus off
(Core7 at small width, hippocampus=False, toy_b7.fit, beta-NLL, lr 3e-3, seed 0, 1,500 steps planned, flat-loss stop), then frozen.
Stage 2: Core7H3 (H2's code and store, retrieval_on False) loads that cortex; only blend_a and blend_b train (beta-NLL of the blended prediction, same data).
JSON on stdout; exit 1 on fail.
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
import hippo_h2  # noqa: E402
import hippo_h3  # noqa: E402
import toy_b7  # noqa: E402

DIR = Path("/secondary/hyst-data/brain/h3")


def batch(design):
    return lambda rng: np.stack([toy_b7.pad46(toy_b7.t1_train_sequence(rng, design)[:, :core.FEAT]) for _ in range(8)])


def cortex(design, steps, log=print):
    """Stage 1 model (hippocampus off), trained once per design and cached."""
    path = DIR / f"cortex_{design}.pt"
    model = core_b7.Core7(seed=0, phase=False, hippocampus=False)
    if path.exists():
        model.load_state_dict(torch.load(path))
        log(f"cortex {design}: loaded {path}")
        return model.eval()
    toy_b7.fit(model, batch(design), steps, log=log, deadline_s=3 * 3600)
    DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), path)
    return model.eval()


def run(design, k, tau, lr, blend_steps, a0, b0, cortex_steps, log=print):
    with toy_b7.small():
        base = cortex(design, cortex_steps, log)
        m = hippo_h3.Core7H3(seed=0, phase=False, k_sparse=k, tau=tau, a_init=a0, b_init=b0)
        missing = m.load_state_dict({n: v for n, v in base.state_dict().items() if n != "hippo_flag"}, strict=False)
        assert set(missing.missing_keys) <= {"blend_a", "blend_b", "dg_proj", "hippo_flag"} and not missing.unexpected_keys, missing
        m.freeze_all_but_blend()
        cortex_only = toy_b7.t1_eval(_with(m, 0.0, 1e3), design, n=16)["ratio_repeat_over_first"]
        _with(m, a0, b0)
        pre = toy_b7.t1_eval(m, design, n=8)
        toy_b7.fit(m, batch(design), blend_steps, lr=lr, log=log, deadline_s=3 * 3600, flat_s=600)
        res = toy_b7.t1_eval(m, design)
        res.update(design=design, k=k, tau=tau, lr=lr, blend_steps=blend_steps, a_init=a0, b_init=b0, cortex_steps=cortex_steps,
                   a=[float(x) for x in m.blend_a], b=[float(x) for x in m.blend_b], ratio_cortex_only=cortex_only,
                   untrained_blend={x: pre[x] for x in ("ratio_repeat_over_first", "source_share_in_first_S", "recognition_repeat_median", "recognition_pre_repeat_p95", "T1a_pass")})
    return res


def _with(m, a, b):
    with torch.no_grad():
        m.blend_a.fill_(a)
        m.blend_b.fill_(b)
    return m


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="A")
    ap.add_argument("--k", type=int, default=hippo_h2.K_SPARSE)
    ap.add_argument("--tau", type=float, default=hippo_h2.TAU_H2)
    ap.add_argument("--lr", type=float, default=0.05)
    ap.add_argument("--blend-steps", type=int, default=400)
    ap.add_argument("--a0", type=float, default=hippo_h3.A_INIT)
    ap.add_argument("--b0", type=float, default=hippo_h3.B_INIT)
    ap.add_argument("--cortex-steps", type=int, default=1500)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args(argv)
    toy_b7.THREADS = a.threads
    torch.set_num_threads(a.threads)
    r = run(a.design, a.k, a.tau, a.lr, a.blend_steps, a.a0, a.b0, a.cortex_steps)
    print(json.dumps({"t1": r}), flush=True)
    sys.exit(0 if r["T1b_pass"] and r["T1a_pass"] else 1)


if __name__ == "__main__":
    main()
