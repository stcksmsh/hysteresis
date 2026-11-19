"""WO6 diagnostic (BRAIN_SPEC 7.17 point 1): top-k used, replay vs oracle error inside the repeat, and the cortex-only control of H3 vs H4. Nothing trained.
  diag_h4.py [--window 100] [--threads 3]   JSON lines on stdout"""
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
import hippo_h4  # noqa: E402
import toy_b7  # noqa: E402
import toy_h3  # noqa: E402


def load(cls, design, **kw):
    base = toy_h3.cortex(design, 1500, print)
    m = cls(seed=0, phase=False, k_sparse=hippo_h2.K_SPARSE, tau=hippo_h2.TAU_H2, **kw)
    miss = m.load_state_dict({n: v for n, v in base.state_dict().items() if n != "hippo_flag"}, strict=False)
    assert not miss.unexpected_keys
    for p in m.parameters():
        p.requires_grad_(False)
    return m


def replay_errors(m, design, n=32, seed=991):
    """Per layer L1-L3: mean squared error over the frames u in [s2+200, s2+S) (as mean w), prediction made at s = u - 2h + 1, for the cortex, the retrieval
    replay and the oracle replay, on the frames where both replays had a source."""
    rng = np.random.default_rng(seed)
    acc = [{"c": [], "r": [], "o": []} for _ in range(3)]
    shapes = {}
    orig = m.read

    def spy(*a, **k):
        r = orig(*a, **k)
        if r[3] is not None and m.oracle is None:
            shapes["weights_B_k"] = list(r[3].shape)
        shapes["replay_B_BLOCK_horizons_feat"] = list(r[0].shape)
        return r
    m.read = spy
    for _ in range(n):
        x, (s1, s2) = toy_b7.t1_sequence(rng, design)
        xt = torch.from_numpy(x)[None]
        m.oracle = None
        with torch.no_grad():
            out, _ = m(xt, m.init_state(1))
        has_r = (out[0]["hippo"]["source_t"] >= 0)[0]
        rep_r = out[0]["replay_true"][0]
        m.oracle = lambda n0, s1=s1, s2=s2: torch.where(n0 >= s2, s1 + (n0 - s2), -torch.ones_like(n0))
        with torch.no_grad():
            outo, _ = m(xt, m.init_state(1))
        m.oracle = None
        has_o = (outo[0]["hippo"]["source_t"] >= 0)[0]
        rep_o = outo[0]["replay_true"][0]
        for i, hz in enumerate(core.HORIZONS[:3]):
            mu, err = out[i]["mean_c"][0], out[i]["err_c"][0]
            T = mu.shape[0]
            u = torch.arange(s2 + 200, min(s2 + toy_b7.T1_S, T))
            s = u - 2 * hz + 1
            ok = has_r[s] & has_o[s]
            u, s = u[ok], s[ok]
            ec = err[u]
            eh = ec + (mu[s] - rep_r[s, i])
            eo = ec + (mu[s] - rep_o[s, i])
            acc[i]["c"].append((ec ** 2).mean(-1))
            acc[i]["r"].append((eh ** 2).mean(-1))
            acc[i]["o"].append((eo ** 2).mean(-1))
    m.read = orig
    res = {}
    for i, k in enumerate(("L1", "L2", "L3")):
        c, r, o = (torch.cat(acc[i][x]) for x in "cro")
        res[k] = {"cortex_mse": float(c.mean()), "replay_mse": float(r.mean()), "oracle_replay_mse": float(o.mean()), "frames": int(len(c))}
    return res, shapes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=100)
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--design", default="A,B,C")
    a = ap.parse_args(argv)
    toy_b7.THREADS = a.threads
    torch.set_num_threads(a.threads)
    print(json.dumps({"TOP_K": core_b7.TOP_K, "K_SPARSE": hippo_h2.K_SPARSE}), flush=True)
    for d in a.design.split(","):
        with toy_b7.small():
            m4 = load(hippo_h4.Core7H4, d, window=a.window)
            m4.arbitrate = False
            ctl4 = toy_b7.t1_eval(m4, d, n=16)["ratio_repeat_over_first"]
            m4.arbitrate = True
            errs, shapes = replay_errors(m4, d)
            m3 = load(hippo_h3.Core7H3, d)
            ctl = {}
            for name, (aa, bb) in {"h3_as_run_a0_b1e3": (0.0, 1e3), "h3_true_w0_a1_b1e3": (1.0, 1e3)}.items():
                with torch.no_grad():
                    m3.blend_a.fill_(aa)
                    m3.blend_b.fill_(bb)
                    w = float(torch.sigmoid(m3.blend_a[0] * (0.8 - m3.blend_b[0])))
                ctl[name] = {"ratio": toy_b7.t1_eval(m3, d, n=16)["ratio_repeat_over_first"], "w_at_rec_0.8": w}
        print(json.dumps({"design": d, "h4_arbitrate_off_ratio": ctl4, "h3_controls": ctl, "errors_in_repeat": errs, "shapes": shapes}), flush=True)


if __name__ == "__main__":
    main()
