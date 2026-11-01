"""B7 toy tests T1 (recall) and T2 (relay), BRAIN_SPEC 7.3 as ruled in 7.10 (R3, R4). Engineering go/no-go, not claim gates. CLI:
  toy_b7.py t1 --design A|B|C [--steps N] [--oracle] [--aux W]      T1a and T1b on one design (JSON on stdout)
  toy_b7.py t2 [--steps 2000] [--taps 10]                           T2
T3 is test_core_b7.py (TestModulationT3). Exit code 1 on fail.

Fixed here, before any result (7.10 is silent on all of these; also in B7_NOTES.md):
  model       Core7 at reduced width (D 32, N 32, HID 64 via `small()`; same code, same bands), no grid phase, random init (seed 0), trained with
              train.py's beta-NLL (beta 0.5, 4 layers), AdamW as train.make_optimizer, lr 3e-3 after 20 warm-up steps, clip 1, clamp_modes, 4 threads.
  designs     A: features independent N(0, 1) per 0.1 s (10 frames) block ("iid noise"). B: independent N(0, 1) levels held for 2 s, feature 0 a ramp
              clock inside each 2 s. C: smooth, independent AR(1) per feature, a = 0.995 (tau 2 s), unit variance.
  sequences   Eval (the spec's): 80 s; S = 16 s at a random 2 s-grid start in [6 s, 16 s); the sequence repeats S exactly after a 30 s gap (start + 46 s);
              all else fresh. Train: 64 s, four 16 s passages P0 P1 P0 P1 (half of it exact repeat at a 16 s gap), 8 per step.
  T1a         During the repeat's blocks (2 s blocks that lie inside the repeat, from the second one on: the first block has no history of the
              repeat), the share whose top-1 source (the entry's frame) lies inside the first S span [s1, s1 + 16 s] must be >= 0.5, pooled over the 32 eval
              draws; and the median recognition over the repeat's frames must exceed the 95th percentile of the recognition over the frames before the
              repeat from 17 s on (pooled).
  T1b         "prediction error" = mean over L1, L2 and L3 (the layers whose target windows fit inside the passage; L4's 8 s window does not) of the
              squared error of the predicted mean on frames whose prediction was made and whose target window ended inside the passage (t >= start + 2h),
              pooled over the eval draws; first occurrence = S the first time, repeat = the second time. Ratio repeat / first <= 0.5.
  oracle      the same toy with the read replaced by the true source pointer (core_b7 `oracle`): replay of the true source, weight 1. T1a is not asked.
  aux         optional auxiliary loss, weight W: the squared error between the replay of each layer's horizon and that layer's true target, on
              frames that have a source (so retrieval learns directly).
  T2 data     44 independent AR(4) series per sequence (the same AR(4) for all 44, poles at radius 0.96 with angles in [0.3, 2.0] rad), unit variance,
              40 s, train 8 per step, eval 24 draws. Compare: MSE of L1's mean (+100 ms) against a ridge AR (last 16 frames of the 44 features -> the
              44 target means, fitted on 200 fresh train sequences, alpha on 50 more). Pass: model <= 1.05 x ridge. Reported: relay off.
"""
import argparse
import contextlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core  # noqa: E402
import core_b7  # noqa: E402
import train  # noqa: E402

T1_T, T1_GAP, T1_S = 8000, 3000, 1600
T2_T = 4000
SEG = 200
THREADS = 4
torch.set_num_threads(THREADS)


@contextlib.contextmanager
def small(D=32, N=32, HID=64):
    old = (core.D, core.N, core.HID)
    core.D, core.N, core.HID = D, N, HID
    try:
        yield
    finally:
        core.D, core.N, core.HID = old


# ---- data -----------------------------------------------------------------------------------------------------------

def passage(rng, T, design):
    """(T, 44) float32 features of one of the three designs."""
    if design == "A":
        return np.repeat(rng.standard_normal((T // 10, core.FEAT)), 10, 0).astype(np.float32)
    if design == "B":
        x = np.repeat(rng.standard_normal((T // SEG, core.FEAT)), SEG, 0).astype(np.float32)
        x[:, 0] = np.tile(np.linspace(-1.0, 1.0, SEG, dtype=np.float32), T // SEG)
        return x
    a = 0.995
    e = rng.standard_normal((T + 1000, core.FEAT)) * math.sqrt(1 - a * a)
    x = np.zeros_like(e)
    for t in range(1, len(x)):
        x[t] = a * x[t - 1] + e[t]
    return x[1000:].astype(np.float32)


def pad46(x):
    return np.concatenate([x, np.zeros((len(x), 2), np.float32)], 1)


def t1_sequence(rng, design):
    """The spec's eval draw -> x (T, 46), (s1, s2): the starts of S and of its repeat, in frames."""
    x = passage(rng, T1_T, design)
    s1 = int(rng.integers(3, 8)) * SEG
    s2 = s1 + T1_S + T1_GAP
    x[s2:s2 + T1_S] = x[s1:s1 + T1_S]
    return pad46(x), (s1, s2)


def t1_train_sequence(rng, design):
    """Training draw: four 16 s passages P0 P1 P0 P1 (half of it exact repeat, gap 16 s), 64 s."""
    p = [passage(rng, T1_S, design) for _ in range(2)]
    return pad46(np.concatenate([p[0], p[1], p[0], p[1]]))


def train_oracle(n0):
    """True source pointer of the training draw: frame n0 - 3200 once the repeat has begun."""
    return torch.where(n0 >= 2 * T1_S, n0 - 2 * T1_S, -torch.ones_like(n0))


def ar4_coeffs(seed=7):
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0.3, 2.0, 2)
    poly = np.poly(np.concatenate([0.96 * np.exp(1j * ang), 0.96 * np.exp(-1j * ang)]))    # x_t = -sum c_k x_{t-k} + e_t
    return -poly[1:].real.astype(np.float64)


def t2_sequence(rng, a=None):
    a = ar4_coeffs() if a is None else a
    e = rng.standard_normal((T2_T + 500, core.FEAT))
    x = np.zeros_like(e)
    for t in range(4, len(x)):
        x[t] = a[0] * x[t - 1] + a[1] * x[t - 2] + a[2] * x[t - 3] + a[3] * x[t - 4] + e[t]
    x = x[500:]
    return pad46((x / x.std()).astype(np.float32))


# ---- training and scoring -------------------------------------------------------------------------------------------

def aux_loss(out, x):
    """Squared error between each layer's replay and that layer's true target window mean, on frames with a source (replay not all zero)."""
    B, T = out[0]["mean"].shape[:2]
    cs = torch.cat([torch.zeros(B, 1, core.FEAT), x[..., :core.FEAT].cumsum(1)], 1)
    t = torch.arange(T)
    rep = out[0]["replay"]
    tot = 0.0
    for i, hz in enumerate(core.HORIZONS):
        end = torch.clamp(t + 2 * hz, max=cs.shape[1] - 1)
        y = (cs[:, end] - cs[:, t + hz]) / hz
        has = (rep[:, :, i].abs().sum(-1) > 0).float() * (t[None] + 2 * hz <= T).float()
        tot = tot + (((rep[:, :, i] - y) ** 2).mean(-1) * has).sum() / has.sum().clamp(min=1)
    return tot


def fit(model, make_batch, steps, lr=3e-3, log=print, seed=0, aux=0.0, oracle=None, deadline_s=None, flat_s=300):
    """Brief training on beta-NLL (+ aux * the replay loss). make_batch(rng) -> x (B, T, 46). Stops at deadline_s, or when the loss has not
    improved for flat_s seconds (a run with a flat loss is killed)."""
    torch.set_num_threads(THREADS)
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    opt = train.make_optimizer(model)
    model.train()
    model.oracle = oracle
    t0 = t_best = time.time()
    best = 1e9
    ema = None
    for step in range(steps):
        x = torch.from_numpy(make_batch(rng))
        B, T = x.shape[0], x.shape[1]
        xp = torch.cat([x, torch.zeros(B, train.LOOK, core.N_IN)], 1)
        out, _ = model(x, model.init_state(B), return_replay=aux > 0)
        sums, _, _, counts = train.chunk_terms(out, xp, torch.full((B,), T), chunk=T, beta=train.BETA)
        loss = sum(s / max(float(c), 1.0) for s, c in zip(sums, counts))
        if aux > 0:
            loss = loss + aux * aux_loss(out, x)
        for g in opt.param_groups:
            g["lr"] = lr * min(1.0, (step + 1) / 20) * g["lr_mult"]
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), train.CLIP_NORM)
        opt.step()
        model.clamp_modes()
        v = float(loss.detach())
        ema = v if ema is None else 0.9 * ema + 0.1 * v
        if ema < best - 1e-3:
            best, t_best = ema, time.time()
        if step % 25 == 0 or step == steps - 1:
            log(f"step {step} loss {v:.3f} ema {ema:.3f} {time.time() - t0:.0f}s")
        if deadline_s and time.time() - t0 > deadline_s:
            log("deadline")
            break
        if time.time() - t_best > flat_s and step > 50:
            log("flat loss: stopped")
            break
    model.oracle = None
    return model.eval()


def t1_eval(model, design, n=32, seed=991, oracle=False):
    rng = np.random.default_rng(seed)
    res = {"first": [[] for _ in range(4)], "repeat": [[] for _ in range(4)]}
    rec_rep, rec_pre, hits, blocks = [], [], 0, 0
    for _ in range(n):
        x, (s1, s2) = t1_sequence(rng, design)
        model.oracle = (lambda n0, s1=s1, s2=s2: torch.where(n0 >= s2, s1 + (n0 - s2), -torch.ones_like(n0))) if oracle else None
        with torch.no_grad():
            out, _ = model(torch.from_numpy(x)[None], model.init_state(1))
        for i, h in enumerate(core.HORIZONS[:3]):
            for k, s in (("first", s1), ("repeat", s2)):
                res[k][i].append(float((out[i]["err"][:, s + 2 * h:s + T1_S] ** 2).mean()))
        r = out[0]["hippo"]["recognition"][0].numpy()
        src = out[0]["hippo"]["source_t"][0].numpy()
        rec_rep.append(r[s2:s2 + T1_S])
        rec_pre.append(r[1700:s2])
        for b in range(s2 + 200, s2 + T1_S, 200):
            blocks += 1
            hits += int(src[b] >= 0 and s1 <= src[b] * 100 <= s1 + T1_S)
    model.oracle = None
    mse = {k: [float(np.mean(v)) for v in res[k]] for k in res}
    first, rep = sum(mse["first"]), sum(mse["repeat"])
    share = hits / max(blocks, 1)
    p95 = float(np.percentile(np.concatenate(rec_pre), 95))
    med = float(np.median(np.concatenate(rec_rep)))
    return {"design": design, "oracle": oracle, "mse_first_L1L2L3": mse["first"], "mse_repeat_L1L2L3": mse["repeat"], "ratio_repeat_over_first": rep / first,
            "T1b_pass": bool(rep <= 0.5 * first), "source_share_in_first_S": share, "recognition_repeat_median": med, "recognition_pre_repeat_p95": p95,
            "T1a_pass": bool(share >= 0.5 and med > p95)}


def t1(design, steps=400, oracle=False, aux=0.0, log=print, deadline_s=1100):
    with small():
        model = core_b7.Core7(seed=0, phase=False)
        pre = None if oracle else t1_eval(model, design, n=8)
        fit(model, lambda rng: np.stack([pad46(t1_train_sequence(rng, design)[:, :core.FEAT]) for _ in range(8)]), steps, log=log, aux=aux,
            oracle=train_oracle if oracle else None, deadline_s=deadline_s)
        res = t1_eval(model, design, oracle=oracle)
        res["untrained_T1a"] = None if pre is None else {k: pre[k] for k in ("source_share_in_first_S", "recognition_repeat_median", "recognition_pre_repeat_p95", "T1a_pass")}
        res["steps_arg"], res["aux"] = steps, aux
        if not oracle:
            model.retrieval_on = False
            res["ratio_retrieval_off"] = t1_eval(model, design, n=16)["ratio_repeat_over_first"]
    return res


def ridge_ar_mse(train_x, val_x, test_x, lags=16, alphas=(1e-3, 1e-2, 1e-1, 1.0, 10.0)):
    """Ridge from the last `lags` frames of the 44 features to the +100 ms target means; MSE on test_x (pooled)."""
    def rows(x):
        z, h = x[:, :core.FEAT], core.HORIZONS[0]
        T = len(z)
        t = np.arange(lags - 1, T - 2 * h + 1)
        X = np.stack([z[t - j] for j in range(lags)], 1).reshape(len(t), -1)
        cs = np.concatenate([np.zeros((1, core.FEAT)), np.cumsum(z.astype(np.float64), 0)])
        Y = (cs[t + 2 * h] - cs[t + h]) / h
        return X.astype(np.float64), Y
    def stack(xs):
        r = [rows(x) for x in xs]
        return np.concatenate([a for a, _ in r]), np.concatenate([b for _, b in r])
    (Xt, Yt), (Xv, Yv), (Xs, Ys) = stack(train_x), stack(val_x), stack(test_x)
    G, C = Xt.T @ Xt, Xt.T @ Yt
    best = min(alphas, key=lambda al: ((Xv @ np.linalg.solve(G + al * len(Xt) * np.eye(len(G)), C) - Yv) ** 2).mean())
    W = np.linalg.solve(G + best * len(Xt) * np.eye(len(G)), C)
    return float(((Xs @ W - Ys) ** 2).mean()), best


def t2_eval(model, test_x):
    num, den = 0.0, 0
    with torch.no_grad():
        for x in test_x:
            out, _ = model(torch.from_numpy(x)[None], model.init_state(1))
            h = core.HORIZONS[0]
            z = x[:, :core.FEAT]
            cs = np.concatenate([np.zeros((1, core.FEAT)), np.cumsum(z.astype(np.float64), 0)])
            t = np.arange(15, len(z) - 2 * h + 1)
            y = (cs[t + 2 * h] - cs[t + h]) / h
            p = out[0]["mean"][0].numpy()[t]
            num += float(((y - p) ** 2).sum())
            den += y.size
    return num / den


def t2(steps=2000, taps=1, log=print, deadline_s=3300):
    a = ar4_coeffs()
    with small():
        model = core_b7.Core7(seed=0, phase=False, skip_taps=taps)
        fit(model, lambda rng: np.stack([t2_sequence(rng, a) for _ in range(8)]), steps, log=log, deadline_s=deadline_s, flat_s=900)
        rng = np.random.default_rng(555)
        tr, va = [t2_sequence(rng, a) for _ in range(200)], [t2_sequence(rng, a) for _ in range(50)]
        test = [t2_sequence(np.random.default_rng(900 + k), a) for k in range(24)]
        ridge, alpha = ridge_ar_mse(tr, va, test)
        mse = t2_eval(model, test)
        model.relay_on = False
        mse_off = t2_eval(model, test)
    return {"taps": taps, "model_mse": mse, "ridge_ar_mse": ridge, "ridge_alpha": alpha, "ratio": mse / ridge, "relay_off_mse": mse_off,
            "relay_off_ratio": mse_off / ridge, "pass": bool(mse <= 1.05 * ridge)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("which", choices=("t1", "t2"))
    ap.add_argument("--design", default="A")
    ap.add_argument("--steps", type=int, default=400)
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--aux", type=float, default=0.0)
    ap.add_argument("--taps", type=int, default=1)
    ap.add_argument("--deadline", type=float, default=1100)
    a = ap.parse_args(argv)
    if a.which == "t1":
        r = t1(a.design, a.steps, a.oracle, a.aux, deadline_s=a.deadline)
        ok = r["T1b_pass"] and (a.oracle or r["T1a_pass"])
    else:
        r = t2(a.steps, a.taps, deadline_s=a.deadline)
        ok = r["pass"]
    print(json.dumps({a.which: r}), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
