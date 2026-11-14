"""H4 toy (docs/BRAIN_SPEC.md 7.16 point 3): T1a + T1b of 7.10 R3 on designs A, B, C, same toy and evaluation as toy_h3.py / toy_h2.py. Nothing is trained.
  toy_h4.py [--window 100] [--k 64] [--tau 0.05] [--threads 3] [--tag try1]     all three designs, JSON lines on stdout
The toy cortex is H3's: trained as in H2's toy with the hippocampus off, then frozen (/secondary/hyst-data/brain/h3/cortex_<design>.pt, loaded; trained by
toy_h3.cortex if absent). Reported per design: T1a, T1b (ratio repeat / first over L1-L3), the cortex-only ratio (arbitration off), mean w per layer inside the
repeat and outside it. The oracle is H2's (same toy, same evaluation), not rerun.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import hippo_h2  # noqa: E402
import hippo_h4  # noqa: E402
import toy_b7  # noqa: E402
import toy_h3  # noqa: E402


def mean_w(m, design, n=16, seed=991):
    """Mean w per layer over the repeat's frames (from its 2nd second on) and over the frames outside it from 17 s on."""
    rng = np.random.default_rng(seed)
    inside, outside = [], []
    for _ in range(n):
        x, (s1, s2) = toy_b7.t1_sequence(rng, design)
        with torch.no_grad():
            out, _ = m(torch.from_numpy(x)[None], m.init_state(1))
        w = torch.stack([o["w"][0, :, 0] for o in out], 1).numpy()                 # (T, 4)
        T = len(w)
        mask = np.zeros(T, bool)
        mask[s2 + 200:s2 + toy_b7.T1_S] = True
        out_mask = np.zeros(T, bool)
        out_mask[1700:] = True
        out_mask &= ~np.isin(np.arange(T), np.arange(s2, s2 + toy_b7.T1_S))
        inside.append(w[mask])
        outside.append(w[out_mask])
    return [float(v) for v in np.concatenate(inside).mean(0)], [float(v) for v in np.concatenate(outside).mean(0)]


def run(design, window, k, tau, log=print):
    with toy_b7.small():
        base = toy_h3.cortex(design, 1500, log)
        m = hippo_h4.Core7H4(seed=0, phase=False, k_sparse=k, tau=tau, window=window)
        miss = m.load_state_dict({n: v for n, v in base.state_dict().items() if n != "hippo_flag"}, strict=False)
        assert set(miss.missing_keys) <= {"dg_proj", "hippo_flag"} and not miss.unexpected_keys, miss
        m.freeze_all()
        m.arbitrate = False
        cortex_only = toy_b7.t1_eval(m, design, n=16)["ratio_repeat_over_first"]
        m.arbitrate = True
        res = toy_b7.t1_eval(m, design)
        res["mean_w_repeat"], res["mean_w_outside"] = mean_w(m, design)
        res.update(design=design, window=window, k=k, tau=tau, ratio_cortex_only=cortex_only)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=hippo_h4.WINDOW)
    ap.add_argument("--k", type=int, default=hippo_h2.K_SPARSE)
    ap.add_argument("--tau", type=float, default=hippo_h2.TAU_H2)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--design", default="A,B,C")
    a = ap.parse_args(argv)
    toy_b7.THREADS = a.threads
    torch.set_num_threads(a.threads)
    ok = True
    for d in a.design.split(","):
        r = run(d, a.window, a.k, a.tau)
        print(json.dumps({"t1": r}), flush=True)
        ok &= bool(r["T1b_pass"] and r["T1a_pass"])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
