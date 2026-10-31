"""B3 checks (docs/BRAIN_SPEC.md 4.3 to 4.6), one script, from a checkpoint: `check_b3.py --ckpt last.pt --manifest M.json`.

Written and committed before any real result. Pass rules are the spec's; everything the spec leaves open is fixed here:
  surprisal   as b2.py: per layer NLL (nats per feature) of the prediction made 2h/10 bins earlier, stamped where its target window completes;
              total = sum over layers with a value. Models: B3 = the heads; B2 = frozen untrained core + ridge readouts.
  4.3         NLL per song = sum over the 4 layers of the mean NLL (per feature) over the bins whose target window lies in the song.
              The gate's NLL difference is (baseline - B3) per held-out song; 95 % bootstrap over songs (2,000 resamples, SEED_BOOT).
              MSE = mean over valid (bin, layer, feature) of (target - predicted mean)^2, pooled over held-out songs.
              Baselines: persistence (the last frame), ridge AR (last 1 s at 100 Hz + last 16 s pooled to 0.5 s, one ridge per horizon, rows
              every AR_STRIDE bins with every horizon's target inside the song, alpha by the last 10 % of the training songs), B2 (readouts on
              the frozen core, fitted on the training songs). Persistence and AR get a constant per-feature variance from their training
              residuals; B2's variance is its readout's. Bits per feature-frame = NLL per feature / ln 2, reported per layer.
  4.4         per held-out song of at least HAB_MIN_S seconds: three non-overlapping windows (S 16 s, S' 16 s, F 30 s) at seeded positions in a
              seeded order; H = S F S, N = S' F S, 50 ms crossfades (the two segments overlap by 50 ms), the grid phase cut and joined the same way.
              Surprisal on the second S = mean of the total over bins stamped inside it. Drop = N - H. Gate: paired 95 % bootstrap interval of
              the mean drop over songs above 0, and the median over songs of drop / SD (of the 8 s window means of that song's total) >= 0.25.
              B2 runs the same versions as the control.
  4.5         4 cuts per song at seeded fixed times in [35 s, duration - 10 s], at least 5 s apart. Cross-song: song audio up to the cut, then 10 s of
              another held-out song (seeded). Within-song: then 10 s of the same song at the time (>= 5 s from the cut) whose grid phase is nearest
              the cut's. z = (mean total in the 1 s after the cut - mean in the 5 s before) / SD of the 1 s window means over the 30 s before.
              The cut is the start of the 50 ms crossfade. Gate: z >= 3 on >= 80 % of cross-song cuts, and cross - within per song (mean over its
              cuts) with a bootstrap interval above 0.
  4.6         Tort modulation index (18 phase bins) of L3/L4 phase against L1/L2 amplitude, against PAC_SURROGATES circular time shifts (>= 10 s) of
              the amplitude; the layer signal is the first principal component of the layer output, band-passed to the layer's band. With and without
              grid phase = 4.3's table for a second checkpoint. DEAM/MERP arousal pre-check: ridge from the layer mode magnitudes pooled to
              0.5 s, 5 folds by song (common.assign_folds), within-song r, against core-2b predictions (if a file is given) and a smoothed-baseline
              control (ridge on pooled features, smoother tau and lag chosen on the training folds).
Round 2 (4.7): the checks above are unchanged and run on the best checkpoint; the baselines are fitted on the training artists without the
validation artists (--val-artists); evaluation chunks stay 6,000 frames (EVAL_CHUNK; the state is carried, so chunking does not change the maths).
Reported only, added: per-layer MSE, per-layer habituation drop, per-layer splice z, and how fast the predicted sigma rises after a cut.
All numbers go to results.json in --out. With --smoke the run is marked smoke and may not write into RESULTS_DIR.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "emotion"))
import b2  # noqa: E402
import core  # noqa: E402
import train  # noqa: E402
import val_split  # noqa: E402
from fast_features import SR, fast_features  # noqa: E402

RESULTS_DIR = Path("/secondary/hyst-data/brain/b3/results")
SCRATCH_DIR = Path("/secondary/hyst-data/brain/b3/scratch")
SEED_BOOT = 20261104
SEED_HAB = 20261101
SEED_SPLICE = 20261102
SEED_PAC = 20261103
N_BOOT = 2000
XF = 0.05
AR_STRIDE = 20
HAB_PASSAGE, HAB_GAP = 16.0, 30.0
HAB_MIN_S = 3 * HAB_PASSAGE + HAB_GAP + 4.0
SPLICE_TAIL = 10.0
PAC_SURROGATES = 200
PAC_BINS = 18
LN2 = math.log(2.0)
LAYERS = b2.LAYERS
EVAL_CHUNK = 6000
SIGMA_STEPS = 51     # predicted sigma against time from a cut: 0 to 5 s in 0.1 s steps


class Lazy:
    """A list that loads each item from disk when asked, so 178 h of inputs never sit in memory."""

    def __init__(self, items, fn):
        self.items, self.fn = items, fn

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        return self.fn(self.items[i])

    def __iter__(self):
        return (self.fn(t) for t in self.items)


# ---- shared maths -------------------------------------------------------------------------------------------------

def boot_ci(values, seed=SEED_BOOT, n=N_BOOT, stat=np.mean):
    """(lower, upper, point) of the 95 % percentile bootstrap of `stat` over `values` (resampling the entries)."""
    v = np.asarray(values, dtype=np.float64)
    idx = np.random.default_rng(seed).integers(0, len(v), size=(n, len(v)))
    s = np.array([stat(v[i]) for i in idx])
    return float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5)), float(stat(v))


def xfade_concat(parts, sr=SR, xf=XF):
    """Join audio arrays with a linear crossfade: the last xf seconds of one overlap the first xf seconds of the next."""
    n = int(round(xf * sr))
    out = parts[0].astype(np.float32).copy()
    fade = np.linspace(0.0, 1.0, n, dtype=np.float32)
    for p in parts[1:]:
        out[-n:] = out[-n:] * (1 - fade) + p[:n] * fade
        out = np.concatenate([out, p[n:]])
    return out


def frames_concat(parts, xf=XF):
    """The same join for per-frame arrays at 100 Hz: later parts lose their first xf * 100 frames."""
    k = int(round(xf * 100))
    return np.concatenate([parts[0]] + [p[k:] for p in parts[1:]])


def song_inputs_from_audio(y, phase, mean, std):
    """Audio (SR mono) and a (frames, 2) phase -> (T, 46) model input. The phase is cut or edge-padded to the feature frame count."""
    feats = fast_features(y)
    z = np.clip((feats - mean) / np.maximum(std, 1e-8), -core.CLIP, core.CLIP)
    if len(phase) < len(z):
        phase = np.concatenate([phase, np.repeat(phase[-1:], len(z) - len(phase), 0)])
    return np.concatenate([z, phase[:len(z)]], 1).astype(np.float32)


# ---- predictions: every method gives per-layer (mean, logvar) at the 10 Hz bins ------------------------------------------

def head_bins(model, x, chunk=EVAL_CHUNK, signals=False):
    """B3: heads of the whole song, state carried. -> means[4], logvars[4] (nb, 44) [, layer outputs [4] (T, 128)]."""
    import torch
    nb = len(x) // b2.STRIDE
    state, M, V, X = model.init_state(), [[] for _ in range(4)], [[] for _ in range(4)], [[] for _ in range(4)]
    with torch.no_grad():
        for a in range(0, len(x), chunk):
            out, state = model(torch.from_numpy(x[a:a + chunk])[None], state)
            j = np.arange(a, a + out[0]["mean"].shape[1])
            keep = torch.from_numpy((j % b2.STRIDE == b2.STRIDE - 1) & (j // b2.STRIDE < nb))
            for i, o in enumerate(out):
                M[i].append(o["mean"][0][keep].numpy())
                V[i].append(o["logvar"][0][keep].numpy())
                if signals:
                    X[i].append(o["x"][0].numpy())
    res = ([np.concatenate(m) for m in M], [np.concatenate(v) for v in V])
    return res + ([np.concatenate(x_) for x_ in X],) if signals else res


class B2Method:
    """Frozen untrained core + ridge readouts (b2.py)."""

    def __init__(self, phase, readouts, head_norm=True):
        self.model, self.readouts = core.Core(phase=phase, head_norm=head_norm).eval(), readouts

    def bins(self, x):
        run = b2.run_core(self.model, x)
        p = [b2.apply_layer(r, s) for r, s in zip(self.readouts, run["states"])]
        return [a for a, _ in p], [b for _, b in p]

    @classmethod
    def fit(cls, phase, train_inputs, groups=10, stride=20, head_norm=True):
        """Readouts from the training songs' states every `stride` bins (20 = 2 s); the songs are dealt into `groups` leave-out groups."""
        model = core.Core(phase=phase, head_norm=head_norm).eval()
        Xs = [[[] for _ in range(groups)] for _ in range(4)]
        Ys = [[[] for _ in range(groups)] for _ in range(4)]
        for n, x in enumerate(train_inputs):
            run = b2.run_core(model, x)
            for i, hz in enumerate(core.HORIZONS):
                y, ok = b2.targets(x[:, :core.FEAT], hz)
                sel = np.arange(0, len(y), stride)           # stride in 10 Hz bins: 20 = every 2 s
                Xs[i][n % groups].append(run["states"][i][sel])
                Ys[i][n % groups].append((y[sel], ok[sel]))
        readouts = []
        for i in range(4):
            xs = [np.concatenate(g) for g in Xs[i]]
            ys = [(np.concatenate([a for a, _ in g]), np.concatenate([b for _, b in g])) for g in Ys[i]]
            readouts.append(b2.fit_layer(xs, ys)[0])
        return cls(phase, readouts, head_norm)


class Persistence:
    """Predicts every window mean as the last frame; constant per-feature variance from the training residuals."""

    def fit(self, train_z):
        ss, n = np.zeros((4, core.FEAT)), np.zeros(4)
        for z in train_z:
            last = z[np.arange(len(z) // b2.STRIDE) * b2.STRIDE + b2.STRIDE - 1]
            for i, hz in enumerate(core.HORIZONS):
                y, ok = b2.targets(z, hz)
                ss[i] += ((y[ok] - last[ok]) ** 2).sum(0)
                n[i] += ok.sum()
        self.logvar = np.clip(np.log(ss / np.maximum(n, 1)[:, None] + 1e-6), core.LOGVAR_MIN, core.LOGVAR_MAX)
        return self

    def bins(self, x):
        z = x[:, :core.FEAT]
        last = z[np.arange(len(z) // b2.STRIDE) * b2.STRIDE + b2.STRIDE - 1]
        return [last for _ in range(4)], [np.tile(self.logvar[i], (len(last), 1)) for i in range(4)]


def ar_rows(z, k):
    """AR inputs at bins k (frame s = 10k + 9): the last 100 frames, the last 16 s as 32 pooled 0.5 s blocks, and a 1.
    Frames before the song are zeros (the standardised mean). -> (len(k), 100 * 44 + 32 * 44 + 1) float32."""
    pad = 1600
    zp = np.concatenate([np.zeros((pad, z.shape[1]), np.float32), z.astype(np.float32)])
    cs = np.concatenate([np.zeros((1, z.shape[1]), np.float64), np.cumsum(zp, 0, dtype=np.float64)])
    s = np.asarray(k) * b2.STRIDE + b2.STRIDE - 1 + pad
    last = np.stack([zp[s - 99 + j] for j in range(100)], 1).reshape(len(s), -1)
    pooled = np.stack([(cs[s + 1 - 50 * j] - cs[s + 1 - 50 * j - 50]) / 50 for j in range(32)], 1).reshape(len(s), -1)
    return np.concatenate([last, pooled.astype(np.float32), np.ones((len(s), 1), np.float32)], 1)


class ARRidge:
    ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)

    def fit(self, train_z, stride=AR_STRIDE, block=2000):
        d = 100 * core.FEAT + 32 * core.FEAT + 1
        order = list(range(len(train_z)))
        n_val = max(1, len(order) // 10)
        sets = {"fit": order[:-n_val], "val": order[-n_val:]}
        acc = {k: {"G": np.zeros((d, d)), "XY": np.zeros((d, 4 * core.FEAT)), "yy": np.zeros(4 * core.FEAT), "n": 0} for k in sets}
        for name, ids in sets.items():
            a = acc[name]
            for i in ids:
                z = train_z[i]
                top = (len(z) - 2 * core.HORIZONS[-1] - (b2.STRIDE - 1)) // b2.STRIDE
                ks = np.arange(0, max(top, 0), stride)
                if len(ks) == 0:
                    continue
                Y = np.concatenate([b2.targets(z, hz)[0] for hz in core.HORIZONS], 1)[ks]
                for lo in range(0, len(ks), block):
                    X = ar_rows(z, ks[lo:lo + block])
                    a["G"] += (X.T @ X).astype(np.float64)
                    a["XY"] += X.T @ Y[lo:lo + block]
                    a["yy"] += (Y[lo:lo + block] ** 2).sum(0)
                    a["n"] += len(X)
        f, v = acc["fit"], acc["val"]

        def sse(W, a):
            return float(a["yy"].sum() - 2 * (W * a["XY"]).sum() + (W * (a["G"] @ W)).sum())

        costs = {al: sse(np.linalg.solve(f["G"] + al * f["n"] * np.eye(d), f["XY"]), v) for al in self.ALPHAS}
        self.alpha = min(costs, key=costs.get)
        n = f["n"] + v["n"]
        G, XY, yy = f["G"] + v["G"], f["XY"] + v["XY"], f["yy"] + v["yy"]
        self.W = np.linalg.solve(G + self.alpha * n * np.eye(d), XY).astype(np.float32)
        resid = (yy - 2 * (self.W * XY).sum(0) + (self.W * (G @ self.W)).sum(0)) / n
        self.logvar = np.clip(np.log(np.maximum(resid, 0) + 1e-6), core.LOGVAR_MIN, core.LOGVAR_MAX).reshape(4, core.FEAT)
        self.costs = {str(k): v_ for k, v_ in costs.items()}
        return self

    def bins(self, x, block=2000):
        z = x[:, :core.FEAT]
        nb = len(z) // b2.STRIDE
        pred = np.concatenate([ar_rows(z, np.arange(lo, min(nb, lo + block))) @ self.W for lo in range(0, nb, block)])
        return [pred[:, i * core.FEAT:(i + 1) * core.FEAT] for i in range(4)], [np.tile(self.logvar[i], (nb, 1)) for i in range(4)]


# ---- 4.3 -------------------------------------------------------------------------------------------------------------

def song_scores(means, logvars, z):
    """Per layer mean NLL (per feature) and mean squared error over the bins whose target window lies in the song."""
    nll, mse, n = np.zeros(4), np.zeros(4), np.zeros(4)
    for i, hz in enumerate(core.HORIZONS):
        y, ok = b2.targets(z, hz)
        e = b2.nll(y, means[i], logvars[i])[ok]
        nll[i], mse[i], n[i] = e.mean() if len(e) else np.nan, ((y - means[i]) ** 2).mean(1)[ok].mean() if ok.any() else np.nan, ok.sum()
    return nll, mse, n


def gate_43(scores, b3="b3", margin=0.05):
    """scores: {method: {"nll": (songs, 4), "mse": (songs, 4), "n": (songs, 4)}}, same songs in the same order.
    Pass: per baseline the bootstrap interval of (baseline NLL - B3 NLL) per song is above 0, and B3's pooled MSE is at least
    `margin` below the best baseline's pooled MSE."""
    def pooled_mse(m):
        s = scores[m]
        return float(((s["mse"] * s["n"]).sum(0) / s["n"].sum(0)).mean())

    base = [m for m in scores if m != b3]
    nll_total = {m: scores[m]["nll"].sum(1) for m in scores}
    res = {"baselines": {}, "mse": {m: pooled_mse(m) for m in scores}}
    for m in base:
        lo, hi, pt = boot_ci(nll_total[m] - nll_total[b3])
        res["baselines"][m] = {"nll_diff_mean": pt, "ci": [lo, hi], "above_0": lo > 0}
    best = min(base, key=lambda m: res["mse"][m])
    res["best_baseline_by_mse"] = best
    res["mse_ratio_to_best"] = res["mse"][b3] / res["mse"][best]
    res["mse_margin_ok"] = res["mse"][b3] <= (1 - margin) * res["mse"][best]
    res["pass"] = bool(all(v["above_0"] for v in res["baselines"].values()) and res["mse_margin_ok"])
    res["mse_per_layer"] = {m: [float(v) for v in (scores[m]["mse"] * scores[m]["n"]).sum(0) / scores[m]["n"].sum(0)] for m in scores}   # reported only
    res["nll_per_layer"] = {m: [float(v) for v in np.average(scores[m]["nll"], axis=0, weights=scores[m]["n"] + 1e-9)] for m in scores}
    res["bits_per_feature_frame"] = {m: [float(v) / LN2 for v in res["nll_per_layer"][m]] for m in scores}
    return res


# ---- 4.4 -------------------------------------------------------------------------------------------------------------

def hab_plan(duration, seed):
    """Seeded start times (seconds, multiples of 10 ms) of S, S' and F as non-overlapping windows; None if the song is too short."""
    if duration < HAB_MIN_S:
        return None
    rng = np.random.default_rng(seed)
    lens = {"S": HAB_PASSAGE, "Sp": HAB_PASSAGE, "F": HAB_GAP}
    slack = duration - sum(lens.values()) - 0.01
    cuts = np.sort(rng.random(3)) * slack
    gaps = np.diff(np.concatenate([[0.0], cuts]))
    order = [str(k) for k in rng.permutation(["S", "Sp", "F"])]
    t, out = 0.0, {}
    for k, gap in zip(order, gaps):
        t += gap
        out[k] = round(t, 2)
        t += lens[k]
    return out


def hab_second_window(first_len, f_len, xf=XF):
    """Start of the second S in H and N (both are S-or-S' + F + S joined with xf overlaps) and its end."""
    t0 = first_len + f_len - 2 * xf
    return t0, t0 + HAB_PASSAGE - xf


def lane_mean(total, t_lo, t_hi):
    """Mean of a 10 Hz lane over the bins stamped in (t_lo, t_hi] (bin k is stamped 0.1 (k + 1))."""
    k = np.arange(len(total))
    sel = (0.1 * (k + 1) > t_lo + 1e-9) & (0.1 * (k + 1) <= t_hi + 1e-9)
    return float(np.nanmean(total[sel]))       # per-layer lanes are NaN before their first target window completes; the total never is


def window_sd(total, win=8.0):
    """SD of the means of non-overlapping `win` s windows of a 10 Hz lane."""
    n = int(round(win / 0.1))
    m = len(total) // n
    return float(total[:m * n].reshape(m, n).mean(1).std())


def hab_stats(drops, sds, min_ratio=0.25):
    lo, hi, pt = boot_ci(drops)
    ratio = float(np.median(np.asarray(drops) / np.maximum(sds, 1e-9)))
    return {"n_songs": len(drops), "drop_mean": pt, "ci": [lo, hi], "median_drop_over_sd": ratio,
            "pass": bool(lo > 0 and ratio >= min_ratio)}


def as_lanes(r):
    """A lane function returns the total lane (array) or a dict {"total", "L1".."L4", "sigma" (nb, 4)}."""
    return r if isinstance(r, dict) else {"total": r}


def habituation(songs, total_fn, audio_of, stats, full_total, per_layer=None):
    """songs: [(id, duration_s, phase (T, 2))]; total_fn(x) -> total lane (or lanes dict); audio_of(id) -> audio.
    -> (drops, sds, skipped ids). With a dict `per_layer`, it is filled with {layer: [drop per song]} (reported only)."""
    drops, sds, skipped = [], [], []
    for n, (sid, dur, phase) in enumerate(songs):
        plan = hab_plan(dur, SEED_HAB + n)
        if plan is None:
            skipped.append(sid)
            continue
        y = audio_of(sid)
        seg = lambda k, L: (y[int(plan[k] * SR):int((plan[k] + L) * SR)], phase[int(round(plan[k] * 100)):int(round((plan[k] + L) * 100))])
        S, Sp, F = seg("S", HAB_PASSAGE), seg("Sp", HAB_PASSAGE), seg("F", HAB_GAP)
        t0, t1 = hab_second_window(HAB_PASSAGE, HAB_GAP)
        tot = {}
        for name, first in (("H", S), ("N", Sp)):
            audio = xfade_concat([first[0], F[0], S[0]])
            ph = frames_concat([first[1], F[1], S[1]])
            lanes = as_lanes(total_fn(song_inputs_from_audio(audio, ph, *stats)))
            tot[name] = {k: lane_mean(lanes[k], t0, t1) for k in ("total", *LAYERS) if k in lanes}
        drops.append(tot["N"]["total"] - tot["H"]["total"])
        if per_layer is not None:
            for k in LAYERS:
                if k in tot["N"]:
                    per_layer.setdefault(k, []).append(tot["N"][k] - tot["H"][k])
        sds.append(window_sd(full_total[sid]))
    return drops, sds, skipped


# ---- 4.5 -------------------------------------------------------------------------------------------------------------

def splice_plan(duration, seed, n=4):
    """n seeded cut times in [35, duration - 10], at least 5 s apart; None if the song is too short."""
    lo, hi = 35.0, duration - SPLICE_TAIL
    if hi - lo < 5.0 * (n - 1):
        return None
    rng = np.random.default_rng(seed)
    for _ in range(1000):
        c = np.sort(np.round(rng.uniform(lo, hi, n), 2))
        if (np.diff(c) >= 5.0).all():
            return [float(v) for v in c]
    return None


def splice_z(total, t_cut):
    """z of 4.5: (mean in the 1 s after the cut - mean in the 5 s before) / SD of the 1 s window means over the 30 s before."""
    post, pre = lane_mean(total, t_cut, t_cut + 1.0), lane_mean(total, t_cut - 5.0, t_cut)
    wins = [lane_mean(total, t_cut - 30.0 + i, t_cut - 29.0 + i) for i in range(30)]
    return (post - pre) / max(float(np.nanstd(wins)), 1e-9)


def phase_match(phase, t_cut, dur, tail=SPLICE_TAIL):
    """Time (multiple of 10 ms) in [0, dur - tail], at least 5 s from t_cut, whose grid phase is nearest the phase at t_cut."""
    f = int(round(t_cut * 100))
    ang = np.arctan2(phase[:, 1], phase[:, 0])
    cand = np.arange(0, int((dur - tail) * 100))
    cand = cand[np.abs(cand - f) >= 500]
    d = np.abs(np.angle(np.exp(1j * (ang[cand] - ang[f]))))
    return float(cand[int(np.argmin(d))]) / 100.0


def sigma_rise(sigma, t_cut, steps=SIGMA_STEPS):
    """sigma: (nb, 4) predicted SD per layer at the 10 Hz bins (bin k stamped 0.1 (k + 1)). -> (4, steps) rise of sigma over its mean in the 5 s
    before t_cut, at 0, 0.1, ... s from t_cut."""
    k0 = int(round(t_cut / 0.1)) - 1
    base = sigma[k0 - 49:k0 + 1].mean(0)
    return np.stack([sigma[k0 + j] - base for j in range(steps)], 1)


def half_rise_time(curve, dt=0.1):
    """Seconds from the cut until a rise curve first reaches half of its peak; None if the peak is not above 0."""
    peak = float(np.max(curve))
    return None if peak <= 0 else float(np.argmax(curve >= 0.5 * peak)) * dt


def sigma_report(curves):
    """curves: [(4, steps) rise per cut] -> per layer the mean curve, its peak and the time to half the peak (reported only)."""
    m = np.mean(curves, 0)
    return {L: {"mean_rise": [float(v) for v in m[i]], "peak": float(m[i].max()), "peak_time_s": float(np.argmax(m[i])) * 0.1,
                "half_peak_time_s": half_rise_time(m[i])} for i, L in enumerate(LAYERS)}


def splice(songs, total_fn, audio_of, stats, z_gate=3.0, frac_gate=0.8):
    """songs: [(id, duration_s, phase)] held-out. -> per-song cross and within z lists and the gate.
    When total_fn gives lanes dicts the rows also carry per-layer z ("cross_layers", "within_layers") and the sigma rise curves."""
    rows, skipped = [], []
    for n, (sid, dur, phase) in enumerate(songs):
        cuts = splice_plan(dur, SEED_SPLICE + n)
        others = [i for i, s in enumerate(songs) if i != n and s[1] > SPLICE_TAIL + 1]
        if cuts is None or not others:
            skipped.append(sid)
            continue
        rng = np.random.default_rng(SEED_SPLICE * 7 + n)
        y = audio_of(sid)
        zc, zw = [], []
        zl = {"cross": {L: [] for L in LAYERS}, "within": {L: [] for L in LAYERS}}
        sg = {"cross": [], "within": []}
        for c in cuts:
            j = int(rng.choice(others))
            oid, odur, ophase = songs[j]
            b0 = round(float(rng.uniform(0, odur - SPLICE_TAIL - 0.01)), 2)
            head = (y[:int(c * SR)], phase[:int(round(c * 100))])
            ty = audio_of(oid)
            tail_x = (ty[int(b0 * SR):int((b0 + SPLICE_TAIL) * SR)], ophase[int(round(b0 * 100)):int(round((b0 + SPLICE_TAIL) * 100))])
            c2 = phase_match(phase, c, dur)
            tail_w = (y[int(c2 * SR):int((c2 + SPLICE_TAIL) * SR)], phase[int(round(c2 * 100)):int(round((c2 + SPLICE_TAIL) * 100))])
            for kind, tail, sink in (("cross", tail_x, zc), ("within", tail_w, zw)):
                x = song_inputs_from_audio(xfade_concat([head[0], tail[0]]), frames_concat([head[1], tail[1]]), *stats)
                lanes = as_lanes(total_fn(x))
                sink.append(splice_z(lanes["total"], c - XF))
                for L in LAYERS:
                    if L in lanes:
                        zl[kind][L].append(splice_z(lanes[L], c - XF))
                if "sigma" in lanes:
                    sg[kind].append(sigma_rise(lanes["sigma"], c - XF))
        rows.append({"id": sid, "cross": zc, "within": zw, "cross_layers": zl["cross"], "within_layers": zl["within"],
                     "sigma_cross": sg["cross"], "sigma_within": sg["within"]})
    return rows, skipped


def splice_layer_report(rows):
    """Per layer: median z over all cross-song and within-song cuts, and the share of cross-song cuts with z >= 3 (reported only). Then the
    sigma rise after a cut (mean over cuts), cross-song and within-song."""
    out = {"z": {}, "sigma_rise": {}}
    for L in LAYERS:
        cz = np.array([z for r in rows for z in r["cross_layers"].get(L, [])], dtype=float)
        wz = np.array([z for r in rows for z in r["within_layers"].get(L, [])], dtype=float)
        if len(cz):
            out["z"][L] = {"cross_median": float(np.nanmedian(cz)), "within_median": float(np.nanmedian(wz)),
                           "frac_cross_ge_3": float(np.mean(cz[np.isfinite(cz)] >= 3.0)), "n_cross": int(np.isfinite(cz).sum())}
    for kind in ("cross", "within"):
        curves = [c for r in rows for c in r[f"sigma_{kind}"]]
        if curves:
            out["sigma_rise"][kind] = sigma_report(curves)
    return out


def splice_stats(rows, z_gate=3.0, frac_gate=0.8):
    cross = np.array([z for r in rows for z in r["cross"]])
    diff = [float(np.mean(r["cross"]) - np.mean(r["within"])) for r in rows]
    lo, hi, pt = boot_ci(diff)
    frac = float((cross >= z_gate).mean())
    return {"n_songs": len(rows), "n_cross_cuts": int(len(cross)), "frac_cross_z_ge_3": frac, "cross_z_median": float(np.median(cross)),
            "within_z_median": float(np.median([z for r in rows for z in r["within"]])), "cross_minus_within_mean": pt, "ci": [lo, hi],
            "pass": bool(frac >= frac_gate and lo > 0)}


# ---- 4.6 -------------------------------------------------------------------------------------------------------------

def tort_mi(phase, amp, bins=PAC_BINS):
    """Tort modulation index: KL distance of the mean amplitude per phase bin from uniform, over log(bins)."""
    b = np.minimum(((phase + np.pi) / (2 * np.pi) * bins).astype(int), bins - 1)
    m = np.bincount(b, weights=amp, minlength=bins) / np.maximum(np.bincount(b, minlength=bins), 1)
    p = m / m.sum()
    return float((math.log(bins) + (p * np.log(p + 1e-12)).sum()) / math.log(bins))


def surrogate_shifts(seed, T, n_surr=PAC_SURROGATES, fs=100.0):
    """The circular shifts (>= 10 s) of the surrogate test; shared by the network side and the input control."""
    lo = int(10 * fs)
    return np.random.default_rng(seed).integers(lo, max(lo + 1, T - lo), n_surr)


def pac(phase, amp, seed, n_surr=PAC_SURROGATES, fs=100.0):
    """(MI, p) of phase vs amplitude with circular time-shift surrogates of the amplitude (shifts >= 10 s)."""
    obs = tort_mi(phase, amp)
    shifts = surrogate_shifts(seed, len(amp), n_surr, fs)
    sur = np.array([tort_mi(phase, np.roll(amp, int(s))) for s in shifts])
    return obs, float((1 + (sur >= obs).sum()) / (1 + n_surr)), float(sur.mean())


def layer_signal(x, band, fs=100.0):
    """First principal component of a layer's output (T, 128), band-passed to the layer's band."""
    xc = x - x.mean(0)
    v = np.linalg.svd(xc[::5], full_matrices=False)[2][0]
    sos = butter(2, [band[0], min(band[1], fs / 2 - 1)], btype="bandpass", fs=fs, output="sos")
    return sosfiltfilt(sos, xc @ v)


def pac_pairs(layer_x, seed):
    """layer_x: 4 arrays (T, 128). -> {"L3 phase / L1 amp": (MI, p, surrogate mean), ...}."""
    sig = [layer_signal(x, band) for x, band in zip(layer_x, core.BANDS)]
    ph, am = [np.angle(hilbert(s)) for s in sig], [np.abs(hilbert(s)) for s in sig]
    out = {}
    for pi, ai in ((2, 0), (2, 1), (3, 0), (3, 1)):
        out[f"L{pi + 1} phase / L{ai + 1} amp"] = pac(ph[pi], am[ai], seed + 10 * pi + ai)
    return out


def within_r(pred, true):
    """Pearson r over time with the song means removed; NaN labels are left out."""
    ok = np.isfinite(true) & np.isfinite(pred)
    if ok.sum() < 3:
        return np.nan
    a, b = pred[ok] - pred[ok].mean(), true[ok] - true[ok].mean()
    d = math.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / d) if d > 0 else np.nan


def pooled_steps(per_bin, n_steps, per=5):
    """(n_bins, d) at 10 Hz -> (n_steps, d) 0.5 s step means."""
    m = min(n_steps, len(per_bin) // per)
    out = np.full((n_steps, per_bin.shape[1]), np.nan)
    out[:m] = per_bin[:m * per].reshape(m, per, -1).mean(1)
    return out


def ridge_xy(X, y, alpha):
    mu, sd = X.mean(0), X.std(0) + 1e-8
    Xn = (X - mu) / sd
    W = np.linalg.solve(Xn.T @ Xn + alpha * len(X) * np.eye(X.shape[1]), Xn.T @ (y - y.mean()))
    return lambda Z: ((Z - mu) / sd) @ W + y.mean()


def precheck(clips, folds, core2b=None, alpha=1.0):
    """clips: [{"key", "dataset", "brain" (steps, k), "fast" (steps, 44), "y" (steps,)}]; folds: key -> fold.
    Within-song arousal r of: the brain readout, a pooled-fast-feature readout smoothed by the tau and lag that did best on the training
    folds (the matched smoothing control), and `core2b` ({key: predictions}) if given. -> {dataset: {method: {"mean_r", "ci", "n"}}}."""
    import smoothing
    preds = {"brain": {}, "smoothed_baseline": {}}
    for f in sorted(set(folds.values())):
        tr = [c for c in clips if folds[c["key"]] != f]
        te = [c for c in clips if folds[c["key"]] == f]
        for name, field in (("brain", "brain"), ("smoothed_baseline", "fast")):
            ok = [np.isfinite(c["y"]) & np.isfinite(c[field]).all(1) for c in tr]
            fit = ridge_xy(np.concatenate([c[field][m] for c, m in zip(tr, ok)]), np.concatenate([c["y"][m] for c, m in zip(tr, ok)]), alpha)
            if name == "brain":
                for c in te:
                    preds[name][c["key"]] = fit(np.nan_to_num(c[field]))
                continue
            best = max(((np.nanmean([within_r(smoothing.smooth_delay(fit(np.nan_to_num(c[field])), tau, lag), c["y"]) for c in tr]), tau, lag)
                        for tau in smoothing.TAUS for lag in smoothing.LAGS), key=lambda t: (t[0] if np.isfinite(t[0]) else -9, -t[1], -t[2]))
            for c in te:
                preds[name][c["key"]] = smoothing.smooth_delay(fit(np.nan_to_num(c[field])), best[1], best[2])
    if core2b:
        def fit_len(p, n):
            p = np.asarray(p, dtype=np.float64)[:n]
            return np.concatenate([p, np.full(n - len(p), np.nan)])
        preds["core2b"] = {c["key"]: fit_len(core2b[c["key"]], len(c["y"])) for c in clips if c["key"] in core2b}
    out = {}
    for ds in sorted({c["dataset"] for c in clips}):
        out[ds] = {}
        for name, p in preds.items():
            r = np.array([within_r(p[c["key"]], c["y"]) for c in clips if c["dataset"] == ds and c["key"] in p])
            r = r[np.isfinite(r)]
            if len(r):
                lo, hi, pt = boot_ci(r)
                out[ds][name] = {"mean_r": pt, "ci": [lo, hi], "n": int(len(r))}
    return out


# ---- the run ----------------------------------------------------------------------------------------------------------

def load_manifest(path):
    return [train.Track(t["id"], t["feats"], t["beats"], t["split"]) for t in json.loads(Path(path).read_text())]


def heldout_nll(model, ho, load):
    """Per-layer NLL and MSE of a model's heads over the held-out tracks (bin-weighted)."""
    sc = {"nll": [], "mse": [], "n": []}
    for t in ho:
        x = load(t)
        for key, v in zip(("nll", "mse", "n"), song_scores(*head_bins(model, x), x[:, :core.FEAT])):
            sc[key].append(v)
    sc = {k: np.array(v) for k, v in sc.items()}
    return [float(v) for v in np.average(sc["nll"], axis=0, weights=sc["n"] + 1e-9)], [float(v) for v in np.average(sc["mse"], axis=0, weights=sc["n"] + 1e-9)]


def ablation(with_phase_nll, ckpt_nophase, ho, load):
    model, meta = train.load_model(ckpt_nophase)
    nll, mse = heldout_nll(model, ho, load)
    return {"with_phase_nll_per_layer": with_phase_nll, "without_phase_nll_per_layer": nll, "without_phase_mse_per_layer": mse,
            "without_phase_epoch": meta["epoch"], "without_phase_stopped_by_cap": meta["stopped_by_cap"]}


def ablation_only(args):
    """With and without grid phase on the held-out tracks, nothing else: for a no-phase run that finishes after the main checks."""
    mean, std = train.load_stats(args.stats)
    tracks = load_manifest(args.manifest)
    ho = [t for t in tracks if t.split == "heldout"][:args.heldout_limit]
    load = lambda t: train.load_inputs(t, mean, std)
    main_model, meta = train.load_model(args.ckpt)
    nll, mse = heldout_nll(main_model, ho, load)
    return {"smoke": args.smoke, "checkpoint": str(args.ckpt), "n_heldout_tracks": len(ho), "with_phase_mse_per_layer": mse,
            **ablation(nll, args.ckpt_nophase, ho, load)}


# ---- 4.7 PAC control -------------------------------------------------------------------------------------------------

PAC_CONTROL_PAIRS = {"L3 phase / L1 amp": (2, 0), "L3 phase / L2 amp": (2, 1)}


def pac_input_max(phase, x, band, seed, n_surr=PAC_SURROGATES, fs=100.0):
    """Input side of the control. x: (T, F) standardised features, each band-passed to `band` (same filter as layer_signal), Hilbert
    envelope, Tort MI against `phase`. -> (max MI over features, argmax, p, mean surrogate max). Surrogates use the network side's shifts;
    the surrogate statistic is the max over features per shift, so the max-selection is inside the test."""
    sos = butter(2, [band[0], min(band[1], fs / 2 - 1)], btype="bandpass", fs=fs, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, x - x.mean(0), axis=0), axis=0))
    obs = np.array([tort_mi(phase, env[:, f]) for f in range(env.shape[1])])
    sur = np.array([max(tort_mi(phase, np.roll(env[:, f], int(s))) for f in range(env.shape[1]))
                    for s in surrogate_shifts(seed, len(env), n_surr, fs)])
    return float(obs.max()), int(obs.argmax()), float((1 + (sur >= obs.max()).sum()) / (1 + n_surr)), float(sur.mean())


def pac_control_song(layer_x, x, seed):
    """One song. layer_x: 4 arrays (T, 128) from head_bins(signals=True); x: model input (T, 46: 44 features, cos, sin of grid phase).
    -> {pair: {"net": (MI, p, surrogate mean), "inp": (max MI, argmax, p, surrogate max mean)}}. Seeds as pac_pairs."""
    sig = [layer_signal(layer_x[i], core.BANDS[i]) for i in range(3)]
    gp = np.arctan2(x[:, core.FEAT + 1], x[:, core.FEAT])
    out = {}
    for name, (pi, ai) in PAC_CONTROL_PAIRS.items():
        s = seed + 10 * pi + ai
        out[name] = {"net": pac(np.angle(hilbert(sig[pi])), np.abs(hilbert(sig[ai])), s),
                     "inp": pac_input_max(gp, x[:, :core.FEAT], core.BANDS[ai], s)}
    return out


def pac_control_stats(rows):
    """rows: pac_control_song outputs. Per pair: medians, paired difference (network - input max) with a 95 % bootstrap interval."""
    res = {}
    for name in PAC_CONTROL_PAIRS:
        net = np.array([r[name]["net"][0] for r in rows])
        inp = np.array([r[name]["inp"][0] for r in rows])
        lo, hi, pt = boot_ci(net - inp)
        res[name] = {"n_songs": len(rows), "median_network_mi": float(np.median(net)), "median_input_max_mi": float(np.median(inp)),
                     "median_network_surrogate_mi": float(np.median([r[name]["net"][2] for r in rows])),
                     "median_input_surrogate_max_mi": float(np.median([r[name]["inp"][3] for r in rows])),
                     "frac_network_p_below_0.05": float(np.mean([r[name]["net"][1] < 0.05 for r in rows])),
                     "frac_input_p_below_0.05": float(np.mean([r[name]["inp"][2] < 0.05 for r in rows])),
                     "diff_mean": pt, "diff_ci": [lo, hi], "diff_median": float(np.median(net - inp)),
                     "frac_network_above_input": float(np.mean(net > inp)),
                     "input_argmax_feature_counts": {str(k): int(v) for k, v in zip(*np.unique([r[name]["inp"][1] for r in rows], return_counts=True))},
                     "coupling_claimable": bool(lo > 0), "network_mi": net.tolist(), "input_max_mi": inp.tolist()}
    return res


def pac_control(args, log=print):
    mean, std = train.load_stats(args.stats)
    ho = [t for t in load_manifest(args.manifest) if t.split == "heldout"][:args.heldout_limit][:args.pac_songs]   # round 1's slice
    model, meta = train.load_model(args.ckpt)
    rows, no_grid = [], []
    for i, t in enumerate(ho):
        x = train.load_inputs(t, mean, std)
        no_grid.append(bool(np.all(x[:, core.FEAT:] == 0)))
        _, _, xs = head_bins(model, x, signals=True)
        rows.append(pac_control_song(xs, x, SEED_PAC))
        log(f"{i + 1}/{len(ho)} {t.id}")
    return {"smoke": args.smoke, "checkpoint": str(args.ckpt), "checkpoint_epoch": meta["epoch"], "song_ids": [t.id for t in ho],
            "songs_without_grid_phase": int(sum(no_grid)), "seeds": {"pac": SEED_PAC, "boot": SEED_BOOT},
            "n_surrogates": PAC_SURROGATES, "bins": PAC_BINS, "pairs": pac_control_stats(rows)}


def run_all(args, log=print):
    t0 = time.time()
    mean, std = train.load_stats(args.stats)
    raw = json.loads(Path(args.manifest).read_text())
    audio = {t["id"]: t["audio"] for t in raw}
    tracks = load_manifest(args.manifest)
    tr = [t for t in tracks if t.split == "train"]
    if args.val_artists:             # round 2: the baselines see the same 90 % of the training artists as B3
        tr = val_split.split_tracks(tr, val_split.load(args.val_artists))[0]
    tr = tr[:args.train_limit]
    ho = [t for t in tracks if t.split == "heldout"][:args.heldout_limit]
    load = lambda t: train.load_inputs(t, mean, std)
    audio_of = lambda sid: b2.decode(audio[sid])
    model, meta = train.load_model(args.ckpt)
    phase = meta["phase"]
    res = {"smoke": args.smoke, "checkpoint": str(args.ckpt), "checkpoint_meta": {k: meta.get(k) for k in ("epoch", "wall_s", "params", "stopped_by_cap", "phase", "best_epoch", "cut", "stopped_early", "beta", "chunk", "batch", "grad_checkpoint")},
           "val_artists": args.val_artists,
           "n_train_tracks_for_baselines": len(tr), "n_heldout_tracks": len(ho), "seeds": {"boot": SEED_BOOT, "hab": SEED_HAB, "splice": SEED_SPLICE, "pac": SEED_PAC}}

    log("fitting baselines")
    train_x = Lazy(tr, load)
    train_z = Lazy(tr, lambda t: load(t)[:, :core.FEAT])
    methods = {"persistence": Persistence().fit(train_z), "ar_ridge": ARRidge().fit(train_z)}
    res["ar_alpha"] = methods["ar_ridge"].alpha
    methods["b2"] = B2Method.fit(phase, train_x, head_norm=meta.get("head_norm", True))
    del train_x

    log("scoring held-out songs")
    scores = {m: {"nll": [], "mse": [], "n": []} for m in ("b3", *methods)}
    full_total, b2_total, held = {}, {}, []
    for t in ho:
        x = load(t)
        z = x[:, :core.FEAT]
        means, logvars = head_bins(model, x)
        preds = {"b3": (means, logvars), **{m: mm.bins(x) for m, mm in methods.items()}}
        for m, (a, b) in preds.items():
            nll, mse, n = song_scores(a, b, z)
            for key, v in (("nll", nll), ("mse", mse), ("n", n)):
                scores[m][key].append(v)
        full_total[t.id] = b2.surprisal_lanes(means, logvars, z)[0]["total"]
        held.append((t.id, len(x) / 100.0, x[:, core.FEAT:]))
    scores = {m: {k: np.array(v) for k, v in s.items()} for m, s in scores.items()}
    res["gate_4_3"] = gate_43(scores)

    def total_b3(x):
        means, logvars = head_bins(model, x)
        lanes = b2.surprisal_lanes(means, logvars, x[:, :core.FEAT])[0]
        lanes["sigma"] = np.stack([np.exp(0.5 * v).mean(1) for v in logvars], 1)     # predicted SD per layer at the time of the prediction
        return lanes

    total_b2 = lambda x: b2.surprisal_lanes(*methods["b2"].bins(x), x[:, :core.FEAT])[0]["total"]
    stats = (mean, std)
    log("habituation")
    out = {}
    for name, fn in (("b3", total_b3), ("b2", total_b2)):
        full = full_total if name == "b3" else {t.id: total_b2(load(t)) for t in ho}
        per_layer = {}
        drops, sds, skipped = habituation(held, fn, audio_of, stats, full, per_layer if name == "b3" else None)
        out[name] = hab_stats(drops, sds) if drops else {"n_songs": 0, "pass": False}
        out[name]["skipped"] = skipped
        out[name]["drops"] = drops
        if name == "b3" and drops:       # reported only
            out[name]["per_layer_drop"] = {L: dict(zip(("mean", "ci_lo", "ci_hi"), (lambda r: (r[2], r[0], r[1]))(boot_ci(v)))) for L, v in per_layer.items()}
    if out["b3"]["n_songs"] and out["b3"]["n_songs"] == out["b2"]["n_songs"]:
        lo, hi, pt = boot_ci(np.array(out["b3"]["drops"]) - np.array(out["b2"]["drops"]))
        out["b3_minus_b2_drop"] = {"mean": pt, "ci": [lo, hi], "above_0": lo > 0}   # reported, not gated
    res["gate_4_4"] = out
    log("splice")
    rows, skipped = splice(held, total_b3, audio_of, stats)
    res["gate_4_5"] = {**splice_stats(rows), "per_layer_and_sigma_reported_only": splice_layer_report(rows), "skipped": skipped} if rows else {"n_songs": 0, "pass": False, "skipped": skipped}

    log("phase-amplitude coupling")
    pairs = {}
    for t in ho[:args.pac_songs]:
        _, _, xs = head_bins(model, load(t), signals=True)
        for k, v in pac_pairs(xs, SEED_PAC).items():
            pairs.setdefault(k, []).append(v)
    res["pac"] = {k: {"median_mi": float(np.median([a for a, _, _ in v])), "median_surrogate_mi": float(np.median([c for _, _, c in v])),
                      "frac_songs_p_below_0.05": float(np.mean([p < 0.05 for _, p, _ in v])), "n_songs": len(v)} for k, v in pairs.items()}

    if args.ckpt_nophase:
        log("no-phase ablation")
        res["with_vs_without_phase"] = ablation(res["gate_4_3"]["nll_per_layer"]["b3"], args.ckpt_nophase, ho, load)

    if args.precheck:
        res["precheck_arousal"] = args.precheck_fn(model, stats)
    res["wall_s"] = time.time() - t0
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--ckpt-nophase")
    ap.add_argument("--manifest", required=True, help="JSON list of {id, audio, feats, beats, split}")
    ap.add_argument("--stats", required=True, help="npz with mean and std of the training-side fast features")
    ap.add_argument("--out", help="output directory (default: RESULTS_DIR, or SCRATCH_DIR/<name> with --smoke)")
    ap.add_argument("--val-artists", help="JSON from val_split.py: its tracks are left out of the baselines' training side (round 2)")
    ap.add_argument("--smoke", action="store_true", help="smoke run: results are marked smoke and never go to RESULTS_DIR")
    ap.add_argument("--train-limit", type=int)
    ap.add_argument("--heldout-limit", type=int)
    ap.add_argument("--pac-songs", type=int, default=40)
    ap.add_argument("--precheck", action="store_true", help="DEAM/MERP arousal pre-check (reads DEAM and MERP audio and labels)")
    ap.add_argument("--pac-control-only", action="store_true", help="only the 4.7 PAC control; writes pac_control.json")
    ap.add_argument("--ablation-only", action="store_true", help="only with/without grid phase (needs --ckpt-nophase); writes ablation.json")
    ap.add_argument("--precheck-only", action="store_true", help="only the DEAM/MERP pre-check; writes precheck.json")
    ap.add_argument("--core2b", help="npz of core-2b arousal predictions per clip key, for the pre-check")
    args = ap.parse_args(argv)
    out = Path(args.out) if args.out else (SCRATCH_DIR / "smoke" if args.smoke else RESULTS_DIR)
    if args.smoke and RESULTS_DIR in (out, *out.parents):
        raise SystemExit("smoke results may not go to the results folder")
    if args.precheck:
        import precheck_data
        args.precheck_fn = lambda model, stats: precheck_data.run(model, stats, args.core2b, precheck)
    if args.precheck_only:
        import precheck_data
        mean, std = train.load_stats(args.stats)
        model, _ = train.load_model(args.ckpt)
        out.mkdir(parents=True, exist_ok=True)
        (out / "precheck.json").write_text(json.dumps(precheck_data.run(model, (mean, std), args.core2b, precheck), indent=1, default=float))
        return
    if args.pac_control_only:
        out.mkdir(parents=True, exist_ok=True)
        (out / "pac_control.json").write_text(json.dumps(pac_control(args), indent=1, default=float))
        return
    if args.ablation_only:
        out.mkdir(parents=True, exist_ok=True)
        (out / "ablation.json").write_text(json.dumps(ablation_only(args), indent=1, default=float))
        return
    res = run_all(args)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(res, indent=1, default=float))
    print(json.dumps({k: res[k].get("pass") if isinstance(res.get(k), dict) else None for k in ("gate_4_3", "gate_4_5")}, default=str))


if __name__ == "__main__":
    main()
