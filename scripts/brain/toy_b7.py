"""B7 toy tests T1 (recall) and T2 (relay), BRAIN_SPEC 7.3. Engineering go/no-go, not claim gates: `python toy_b7.py [t1] [t2]` prints the numbers as
JSON and exits 1 if one fails. T3 is test_core_b7.py (TestModulationT3).

Fixed here, before any result (the spec is silent on all of these; also in B7_NOTES.md):
  model       Core7 at reduced width (D 32, N 32, HID 64 via `small()`; same code, same bands), no grid phase, random init (seed 0), trained with
              train.py's beta-NLL (beta 0.5, 4 layers), AdamW as train.make_optimizer, lr 2e-3 after 20 warm-up steps, clip 1, clamp_modes.
  T1 data     80 s sequences (8,000 frames) of 44 features that are independent N(0, 1) levels held for 2 s (200 frames, on a 2 s grid). The store
              returns the mean of the features over the next 2 s, so the data must carry its information at that scale: with independent values
              per 0.1 s the 2 s mean is about 0 and there is nothing to recall (a first version of this test used that and learned nothing).
              Passage S = 8 segments (16 s) at a random segment start in [6 s, 16 s); the sequence repeats it exactly after a 30 s gap
              (start + 46 s, on the grid); all else is fresh levels. Eval: 32 draws from another seed. Training draws have more recall in them
              (t1_train_sequence: four 16 s passages P0 P1 P0 P1, so half of it is exact repeat at a 16 s gap), 8 per step, fresh draws, lr 3e-3. Two
              earlier versions did not learn: (1) independent values per 0.1 s, whose 2 s mean is about 0; (2) 2 s levels without a clock channel
              and with one repeat per draw, where the offset in the segment, which the stored mix depends on, was not visible. Feature 0 is a
              clock: a ramp from -1 to 1 in every 2 s segment.
  T1 error    "prediction error" = mean over L1 and L2 (the layers whose target windows lie inside the 2 s the store returns) of the squared error
              of the predicted mean, over frames whose prediction was made and whose target window ended inside the passage (t >= start + 2h),
              pooled over the eval draws. First occurrence = S the first time, repeat = the second time. Pass: repeat <= 0.5 x first.
              Reported too: the same for L3, L4 and the plain NLL of L1 + L2.
  T1 recogn.  Median recognition over the repeat's frames, against the 95th percentile of the recognition over the frames before the repeat
              from 8 s on (pooled over the eval draws; frames after the repeat are left out: the state still carries the passage there). Pass: median > p95.
  T2 data     44 independent AR(4) series per sequence (the same AR(4) for all 44 features, poles at radius 0.96 with random angles, seeded and
              fixed), unit-variance innovations, rescaled to unit variance. 40 s sequences, train 8 per step, eval 24 draws.
  T2 compare  MSE of L1's mean (+100 ms: the mean of [t + 10, t + 20)), pooled, against a ridge AR (the last 16 frames of the 44 features -> the 44
              target means, one ridge fitted on 200 fresh train sequences, alpha chosen on 50 more of them), both at frames where the target exists.
              Pass: model MSE <= 1.05 x ridge MSE. Reported: with the relay off (same weights).
"""
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

BLK = 10
T1_T, T1_GAP, T1_S = 8000, 3000, 1600
T2_T = 4000


@contextlib.contextmanager
def small(D=32, N=32, HID=64):
    old = (core.D, core.N, core.HID)
    core.D, core.N, core.HID = D, N, HID
    try:
        yield
    finally:
        core.D, core.N, core.HID = old


# ---- data -----------------------------------------------------------------------------------------------------------

SEG = 200


def noise_blocks(rng, T):
    """Levels held for SEG frames; feature 0 is a clock instead: a ramp from -1 to 1 inside every segment, so the offset in the segment is visible
    (the stored 2 s mean mixes this segment and the next one by that offset)."""
    x = np.repeat(rng.standard_normal((T // SEG, core.FEAT)), SEG, 0).astype(np.float32)
    x[:, 0] = np.tile(np.linspace(-1.0, 1.0, SEG, dtype=np.float32), T // SEG)
    return x


def t1_sequence(rng):
    """-> x (T, 46), (s1, s2): the starts of S and of its repeat, in frames."""
    x = noise_blocks(rng, T1_T)
    s1 = int(rng.integers(3, 8)) * SEG
    s2 = s1 + T1_S + T1_GAP
    x[s2:s2 + T1_S] = x[s1:s1 + T1_S]
    return np.concatenate([x, np.zeros((T1_T, 2), np.float32)], 1), (s1, s2)


AR4_POLES = None


def t1_train_sequence(rng):
    """Training draw with more recall to learn from: four 16 s passages P0 P1 P0 P1, so half of it is exact repeat (gap 16 s), 64 s. The eval draws (t1_sequence) are the spec's 16 s repeat after a 30 s gap."""
    p = [noise_blocks(rng, T1_S) for _ in range(2)]
    x = np.concatenate([p[0], p[1], p[0], p[1]])
    return np.concatenate([x, np.zeros((len(x), 2), np.float32)], 1)


def ar4_coeffs(seed=7):
    rng = np.random.default_rng(seed)
    ang = rng.uniform(0.05, 1.2, 2)
    poly = np.poly(np.concatenate([0.96 * np.exp(1j * ang), 0.96 * np.exp(-1j * ang)]))    # 1 + c1 z + ... ; x_t = -sum c_k x_{t-k} + e_t
    return -poly[1:].real.astype(np.float64)


def t2_sequence(rng, a=None):
    a = ar4_coeffs() if a is None else a
    e = rng.standard_normal((T2_T + 500, core.FEAT))
    x = np.zeros_like(e)
    for t in range(4, len(x)):
        x[t] = a[0] * x[t - 1] + a[1] * x[t - 2] + a[2] * x[t - 3] + a[3] * x[t - 4] + e[t]
    x = x[500:]
    x = x / x.std()
    return np.concatenate([x, np.zeros((len(x), 2))], 1).astype(np.float32)


# ---- training and scoring -------------------------------------------------------------------------------------------

def fit(model, make_batch, steps, lr=2e-3, log=print, seed=0):
    """Brief training on beta-NLL. make_batch(rng) -> x (B, T, 46)."""
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    opt = train.make_optimizer(model)
    model.train()
    t0 = time.time()
    for step in range(steps):
        x = torch.from_numpy(make_batch(rng))
        B, T = x.shape[0], x.shape[1]
        xp = torch.cat([x, torch.zeros(B, train.LOOK, core.N_IN)], 1)
        out, _ = model(x, model.init_state(B))
        sums, _, _, counts = train.chunk_terms(out, xp, torch.full((B,), T), chunk=T, beta=train.BETA)
        loss = sum(s / max(float(c), 1.0) for s, c in zip(sums, counts))
        for g in opt.param_groups:
            g["lr"] = lr * min(1.0, (step + 1) / 20) * g["lr_mult"]
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), train.CLIP_NORM)
        opt.step()
        model.clamp_modes()
        if step % 25 == 0 or step == steps - 1:
            log(f"step {step} loss {float(loss):.3f} {time.time() - t0:.0f}s")
    return model.eval()


def sq_err(out, i, lo, hi):
    """Squared error of the mean (over features) of layer i's predictions, frames [lo, hi) (err already is window - prediction)."""
    return (out[i]["err"][:, lo:hi] ** 2).mean(-1)


def t1_eval(model, n=32, seed=991):
    rng = np.random.default_rng(seed)
    res = {"first": [[] for _ in range(4)], "repeat": [[] for _ in range(4)]}
    rec_rep, rec_other = [], []
    nll12 = {"first": [], "repeat": []}
    with torch.no_grad():
        for _ in range(n):
            x, (s1, s2) = t1_sequence(rng)
            out, _ = model(torch.from_numpy(x)[None], model.init_state(1))
            for i, h in enumerate(core.HORIZONS):
                for k, s in (("first", s1), ("repeat", s2)):
                    res[k][i].append(float(sq_err(out, i, s + 2 * h, s + T1_S).mean()))
            for k, s in (("first", s1), ("repeat", s2)):
                v = 0.0
                for i in (0, 1):
                    h = core.HORIZONS[i]
                    lv = torch.cat([torch.zeros(1, 2 * h - 1, core.FEAT), out[i]["logvar"]], 1)[:, :T1_T]      # prediction made 2h-1 frames earlier
                    e = 0.5 * (lv + out[i]["err"] ** 2 * torch.exp(-lv) + math.log(2 * math.pi)).mean(-1)
                    v += float(e[:, s + 2 * h:s + T1_S].mean())
                nll12[k].append(v)
            r = out[0]["hippo"]["recognition"][0].numpy()
            rec_rep.append(r[s2:s2 + T1_S])
            mask = np.ones(T1_T, bool)
            mask[:800] = False
            mask[s2:] = False                      # frames before the repeat only: after it the state still carries the passage (hangover)
            rec_other.append(r[mask])
    mse = {k: [float(np.mean(v)) for v in res[k]] for k in res}
    first12, rep12 = mse["first"][0] + mse["first"][1], mse["repeat"][0] + mse["repeat"][1]
    p95 = float(np.percentile(np.concatenate(rec_other), 95))
    med = float(np.median(np.concatenate(rec_rep)))
    return {"mse_first_per_layer": mse["first"], "mse_repeat_per_layer": mse["repeat"], "mse_L1L2_first": first12, "mse_L1L2_repeat": rep12,
            "repeat_over_first": rep12 / first12, "nll_L1L2_first": float(np.mean(nll12["first"])), "nll_L1L2_repeat": float(np.mean(nll12["repeat"])),
            "recognition_repeat_median": med, "recognition_other_p95": p95,
            "pass_error": bool(rep12 <= 0.5 * first12), "pass_recognition": bool(med > p95), "pass": bool(rep12 <= 0.5 * first12 and med > p95)}


def t1(steps=400, log=print):
    with small():
        model = core_b7.Core7(seed=0, phase=False)
        fit(model, lambda rng: np.stack([t1_train_sequence(rng) for _ in range(8)]), steps, lr=3e-3, log=log)
        res = t1_eval(model)
        model.retrieval_on = False
        res["repeat_over_first_retrieval_off"] = t1_eval(model, n=16)["repeat_over_first"]
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


def t2(steps=600, log=print):
    a = ar4_coeffs()
    with small():
        model = core_b7.Core7(seed=0, phase=False)
        fit(model, lambda rng: np.stack([t2_sequence(rng, a) for _ in range(8)]), steps, log=log)
        rng = np.random.default_rng(555)
        tr, va = [t2_sequence(rng, a) for _ in range(200)], [t2_sequence(rng, a) for _ in range(50)]
        test = [t2_sequence(np.random.default_rng(900 + k), a) for k in range(24)]
        ridge, alpha = ridge_ar_mse(tr, va, test)
        mse = t2_eval(model, test)
        model.relay_on = False
        mse_off = t2_eval(model, test)
    return {"model_mse": mse, "ridge_ar_mse": ridge, "ridge_alpha": alpha, "ratio": mse / ridge, "relay_off_mse": mse_off, "relay_off_ratio": mse_off / ridge,
            "pass": bool(mse <= 1.05 * ridge)}


def main(argv=None):
    which = (argv if argv is not None else sys.argv[1:]) or ["t1", "t2"]
    ok = True
    for name, fn in (("t1", t1), ("t2", t2)):
        if name in which:
            r = fn()
            print(json.dumps({name: r}, indent=1), flush=True)
            ok &= r["pass"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
