"""H2 toy (docs/BODY_BRAIN_PLAN.md 4): the T1a + T1b bar of toy_b7.py (BRAIN_SPEC 7.10 R3), same three designs, same toy settings as H1.
  toy_h2.py MODE --design A|B|C [--steps N] [--k 64] [--tau 0.05] [--threads 2]
MODE: h2 (fixed sparse random code, hippo_h2.py), frozen (H1 architecture with its key / query projection and tau frozen at init: the untrained-H1
baseline, relay trained), oracle (toy_b7's oracle run, true pointer). JSON on stdout; exit 1 on fail (oracle: T1b only).
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
import toy_b7  # noqa: E402


def run(mode, design, steps, k=hippo_h2.K_SPARSE, tau=hippo_h2.TAU_H2, deadline_s=3 * 3600, log=print, seed=0):
    with toy_b7.small():
        if mode == "h2":
            model = hippo_h2.Core7H2(seed=0, phase=False, k_sparse=k, tau=tau)
        else:
            model = core_b7.Core7(seed=0, phase=False)
            if mode == "frozen":
                for p in (model.key_proj.weight, model.query_proj.weight, model.log_tau):
                    p.requires_grad_(False)
        pre = toy_b7.t1_eval(model, design, n=8) if mode != "oracle" else None
        toy_b7.fit(model, lambda rng: np.stack([toy_b7.pad46(toy_b7.t1_train_sequence(rng, design)[:, :core.FEAT]) for _ in range(8)]), steps, log=log,
                   oracle=toy_b7.train_oracle if mode == "oracle" else None, deadline_s=deadline_s, seed=seed)
        res = toy_b7.t1_eval(model, design, oracle=mode == "oracle")
        res["mode"], res["steps_arg"], res["k"], res["tau"] = mode, steps, k, tau
        res["untrained_T1a"] = None if pre is None else {x: pre[x] for x in ("source_share_in_first_S", "recognition_repeat_median", "recognition_pre_repeat_p95", "T1a_pass")}
        if mode != "oracle":
            model.retrieval_on = False
            res["ratio_retrieval_off"] = toy_b7.t1_eval(model, design, n=16)["ratio_repeat_over_first"]
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("h2", "frozen", "oracle"))
    ap.add_argument("--design", default="A")
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--k", type=int, default=hippo_h2.K_SPARSE)
    ap.add_argument("--tau", type=float, default=hippo_h2.TAU_H2)
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args(argv)
    toy_b7.THREADS = a.threads
    torch.set_num_threads(a.threads)
    r = run(a.mode, a.design, a.steps, a.k, a.tau)
    print(json.dumps({"t1": r}), flush=True)
    sys.exit(0 if r["T1b_pass"] and (a.mode == "oracle" or r["T1a_pass"]) else 1)


if __name__ == "__main__":
    main()
