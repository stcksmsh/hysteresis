"""B2 (docs/BRAIN_SPEC.md 3): readouts on the frozen untrained core, per-song lanes, band traces.

Fixed here, before any result:
  standardisation  per-column mean / SD of the fast features pooled over the readout-fit tracks (FIT_DIR), clipped at +-CLIP.
  grid phase       2 pi * (position inside the beat interval); piecewise linear between beats, extrapolated with the
                   first / last interval. Fit tracks: beats of scripts/analyze (analyze_mix). Songs: sidecar `beats`.
  readout state    [Re h, Im h] of the layer's 256 modes (512 values), sampled at the end of each 100 ms bin (frame 10k+9).
  readout          ridge (bias unpenalised, inputs standardised), alpha from ALPHAS by leave-one-track-out MSE, per layer.
                   Mean: target = mean of the standardised features over [s+h, s+2h). Variance: ridge on
                   log(r^2) + 1.2704 (E[log chi2_1] = -1.2704), r = leave-one-track-out residual, logvar clipped to [-8, 4].
  surprisal        mean over the 44 features of the Gaussian NLL in nats. Stamped on the bin where the target window
                   completes (the prediction made at bin k is scored at bin k + 2h/10); NaN before that.
                   total = sum over the layers that have a value.
  band power       mean over the 256 modes of |h|^2, averaged over each 100 ms bin.
  lanes            arousal: total surprisal, asymmetric one-pole, rise tau 1 s, decay tau 8 s.
                   tension: mean over features of exp(L4 readout log-variance), one-pole tau 8 s.
                   familiarity: minus the least-squares slope (per s) of total surprisal over the past 30 s (300 bins).
"""
import json
import math
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core  # noqa: E402
from fast_features import SR, fast_features, load_mono  # noqa: E402

OUT = Path("/secondary/hyst-data/brain/b2")
FIT_DIR = Path("/secondary/hyst-data/brain/measure/mp3")
SONGS = Path("/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm")
SONG_FILES = {"instant-crush": ("instant-crush.m4a", "instant-crush.notes.sidecar.json"),
              "five-years": ("five-years.m4a", "five-years-steady.notes.sidecar.json"),
              "presence": ("presence.m4a", "presence.notes.sidecar.json")}
STRIDE = 10          # 10 Hz bins
CHUNK = 6000         # 60 s
ALPHAS = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0, 100.0)
LAYERS = ("L1", "L2", "L3", "L4")
N_STATE = 2 * core.N


def grid_phase(beats, n_frames):
    """(n_frames, 2) cos, sin of the beat-grid phase at frame times t / 100 s."""
    b = np.asarray(beats, dtype=np.float64)
    t = np.arange(n_frames) / 100.0
    k = np.interp(t, b, np.arange(len(b)))
    k = np.where(t < b[0], (t - b[0]) / (b[1] - b[0]), k)
    k = np.where(t > b[-1], len(b) - 1 + (t - b[-1]) / (b[-1] - b[-2]), k)
    ph = 2 * np.pi * (k % 1.0)
    return np.stack([np.cos(ph), np.sin(ph)], 1).astype(np.float32)


def build_inputs(feats, beats, mean, std):
    """Raw fast features (T, 44) + beats -> (T, 46) core input."""
    z = np.clip((feats - mean) / np.maximum(std, 1e-8), -core.CLIP, core.CLIP)
    return np.concatenate([z, grid_phase(beats, len(z))], 1).astype(np.float32)


def run_core(model, x, chunk=CHUNK):
    """Whole song, state carried across chunks. -> dict: states[i] (nb, 512) at frames 10k+9, power[i] (nb,), logvar/mean none."""
    T = len(x)
    nb = T // STRIDE
    state = model.init_state()
    states = [np.zeros((nb, N_STATE), np.float32) for _ in core.BANDS]
    pw = [np.zeros(T, np.float32) for _ in core.BANDS]
    with torch.no_grad():
        for a in range(0, T, chunk):
            out, state = model(torch.from_numpy(x[a:a + chunk])[None], state)
            for i, o in enumerate(out):
                h = o["h"][0]
                pw[i][a:a + len(h)] = (h.real ** 2 + h.imag ** 2).mean(-1).numpy()
                j = np.arange(a, a + len(h))
                keep = (j % STRIDE == STRIDE - 1) & (j // STRIDE < nb)
                if keep.any():
                    states[i][j[keep] // STRIDE] = torch.cat([h.real, h.imag], -1)[torch.from_numpy(keep)].numpy()
    power = [p[:nb * STRIDE].reshape(nb, STRIDE).mean(1) for p in pw]
    return {"states": states, "power": power, "nb": nb, "finite": all(np.isfinite(s).all() for s in states)}


def targets(z, h):
    """Mean of z over [s+h, s+2h) at s = 10k+9. -> (nb, 44), valid (nb,)."""
    nb = len(z) // STRIDE
    cs = np.concatenate([np.zeros((1, z.shape[1])), np.cumsum(z.astype(np.float64), 0)])
    s = np.arange(nb) * STRIDE + STRIDE - 1
    ok = s + 2 * h <= len(z)
    hi, lo = np.minimum(s + 2 * h, len(z)), np.minimum(s + h, len(z))
    return ((cs[hi] - cs[lo]) / h).astype(np.float32), ok


# ---- readouts -------------------------------------------------------------------------------------------------

def _solve(G, C, n, a):
    return np.linalg.solve(G + a * n * np.eye(len(G)), C)


def fit_layer(Xs, Ys):
    """Xs: per-track raw states (n, 512); Ys: per-track (targets, valid). -> readout dict and diagnostics."""
    X = [x[v] for x, (_, v) in zip(Xs, Ys)]
    Y = [y[v] for (y, v) in Ys]
    allx, ally = np.concatenate(X), np.concatenate(Y)
    mu, sd = allx.mean(0), np.maximum(allx.std(0), 1e-8)
    ymu = ally.mean(0)
    Xn = [((x - mu) / sd).astype(np.float64) for x in X]
    Yc = [(y - ymu).astype(np.float64) for y in Y]
    G = [x.T @ x for x in Xn]
    C = [x.T @ y for x, y in zip(Xn, Yc)]
    n = [len(x) for x in Xn]
    Gt, Ct, nt = sum(G), sum(C), sum(n)

    def loto(Cs, tgt):
        """Leave-one-track-out MSE per alpha for ridge on Gram sums G and cross terms Cs."""
        res = {}
        for a in ALPHAS:
            err = sum(((Xn[t] @ _solve(Gt - G[t], sum(Cs) - Cs[t], nt - n[t], a) - tgt[t]) ** 2).sum() for t in range(len(Xn)))
            res[a] = err / (nt * tgt[0].shape[1])
        return res

    mse = loto(C, Yc)
    a_mean = min(mse, key=mse.get)
    Wm = _solve(Gt, Ct, nt, a_mean)
    res = [y - (x @ _solve(Gt - g, Ct - c, nt - m, a_mean)) for x, y, g, c, m in zip(Xn, Yc, G, C, n)]
    zlog = [np.log(r ** 2 + 1e-6) + 1.2704 for r in res]
    zmu = np.concatenate(zlog).mean(0)
    Cz = [x.T @ (z - zmu) for x, z in zip(Xn, zlog)]
    zc = [z - zmu for z in zlog]
    mse_v = loto(Cz, zc)
    a_var = min(mse_v, key=mse_v.get)
    Wv = _solve(Gt, sum(Cz), nt, a_var)
    base = float((ally - ymu).var(0).mean())
    diag = {"alpha_mean": a_mean, "alpha_var": a_var, "loto_mse_mean": float(mse[a_mean]), "mse_of_train_mean": base,
            "loto_mse_by_alpha": {str(k): float(v) for k, v in mse.items()}, "n_samples": int(nt)}
    return {"mu": mu, "sd": sd, "ymu": ymu, "Wm": Wm, "zmu": zmu, "Wv": Wv}, diag


def apply_layer(r, X):
    """Raw states (n, 512) -> mean (n, 44), logvar (n, 44)."""
    Xn = (X - r["mu"]) / r["sd"]
    return (Xn @ r["Wm"] + r["ymu"]).astype(np.float32), np.clip(Xn @ r["Wv"] + r["zmu"], core.LOGVAR_MIN, core.LOGVAR_MAX).astype(np.float32)


# ---- lanes ----------------------------------------------------------------------------------------------------

def nll(y, mean, logvar):
    """Mean over features of the Gaussian NLL in nats. (n, 44) -> (n,)"""
    return (0.5 * (logvar + (y - mean) ** 2 * np.exp(-logvar) + math.log(2 * math.pi))).mean(1)


def one_pole(x, tau_up, tau_down, dt=0.1):
    y, out = x[0], np.empty_like(x)
    ku, kd = 1 - math.exp(-dt / tau_up), 1 - math.exp(-dt / tau_down)
    for i, v in enumerate(x):
        y += (ku if v > y else kd) * (v - y)
        out[i] = y
    return out


def slope(x, win=300, dt=0.1):
    """Causal least-squares slope per second of x over the last `win` samples (0 for the first sample)."""
    n = len(x)
    t = np.arange(n) * dt
    cx, ct, ctx, ctt = (np.concatenate([[0.0], np.cumsum(v)]) for v in (x, t, t * x, t * t))
    j = np.arange(n)
    a = np.maximum(j - win + 1, 0)
    m = (j - a + 1).astype(np.float64)
    sx, st, stx, stt = cx[j + 1] - cx[a], ct[j + 1] - ct[a], ctx[j + 1] - ctx[a], ctt[j + 1] - ctt[a]
    den = m * stt - st ** 2
    return np.where(m > 1, (m * stx - st * sx) / np.where(den == 0, 1, den), 0.0)


def lanes(run, z, readouts):
    """run: run_core output; z: standardised features (T, 44); readouts: per layer. -> dict of lane arrays at 10 Hz."""
    nb = run["nb"]
    sur, var4 = {}, None
    for i, (name, hz) in enumerate(zip(LAYERS, core.HORIZONS)):
        mean, logvar = apply_layer(readouts[i], run["states"][i])
        y, ok = targets(z, hz)
        e = np.where(ok, nll(y, mean, logvar), np.nan)
        s = np.full(nb, np.nan)
        lag = 2 * hz // STRIDE
        s[lag:] = e[:nb - lag]
        sur[name] = s
        if i == 3:
            var4 = np.exp(logvar).mean(1)
    total = np.nansum(np.stack([sur[n] for n in LAYERS]), 0)
    return {"band_power": dict(zip(LAYERS, run["power"])),
            "surprisal": {**sur, "total": total},
            "neuromod": {"arousal": one_pole(total, 1.0, 8.0), "tension": one_pole(var4, 8.0, 8.0), "familiarity": -slope(total)}}


# ---- audio and fit --------------------------------------------------------------------------------------------

def decode(path):
    """Audio file -> float32 mono at SR; m4a goes through ffmpeg to a wav under OUT/wav."""
    p = Path(path)
    if p.suffix.lower() == ".m4a":
        (OUT / "wav").mkdir(parents=True, exist_ok=True)
        w = OUT / "wav" / (p.stem + ".wav")
        if not w.exists():
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(p), "-ac", "1", "-ar", str(SR), str(w)], check=True)
        p = w
    return load_mono(p)


def fit_grid(path):
    """Offline-analysis beats of one audio file (scripts/analyze analyze_mix), cached."""
    c = OUT / "grids" / (Path(path).stem + ".json")
    if c.exists():
        return json.loads(c.read_text())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from analyze.structure import analyze_mix
    from analyze.wav import DecodedWav
    y = decode(path)
    d = analyze_mix(DecodedWav(SR, [y], len(y) / SR))
    c.parent.mkdir(parents=True, exist_ok=True)
    c.write_text(json.dumps({"beats": d["beats"], "tempo": d["tempo"]}))
    return {"beats": d["beats"], "tempo": d["tempo"]}


def fit(modes=("phase", "nophase")):
    """Standardisation, readouts and diagnostics for each mode, from the FIT_DIR tracks. Writes OUT/stats.npz, OUT/readouts_*.npz."""
    tracks = sorted(FIT_DIR.glob("*.mp3"))
    feats, beats = [], []
    for p in tracks:
        f = fast_features(decode(p))
        feats.append(f)
        beats.append(fit_grid(p)["beats"])
    allf = np.concatenate(feats)
    mean, std = allf.mean(0), allf.std(0)
    np.savez(OUT / "stats.npz", mean=mean, std=std, tracks=np.array([p.stem for p in tracks]))
    xs = [build_inputs(f, b, mean, std) for f, b in zip(feats, beats)]
    zs = [x[:, :core.FEAT] for x in xs]
    report = {}
    for mode in modes:
        model = core.Core(phase=(mode == "phase"))
        runs = [run_core(model, x) for x in xs]
        readouts, diag = [], {}
        for i, name in enumerate(LAYERS):
            Ys = [targets(z, core.HORIZONS[i]) for z in zs]
            r, d = fit_layer([run["states"][i] for run in runs], Ys)
            readouts.append(r)
            diag[name] = d
        np.savez(OUT / f"readouts_{mode}.npz", **{f"{k}_{i}": v for i, r in enumerate(readouts) for k, v in r.items()})
        report[mode] = diag
    (OUT / "fit_report.json").write_text(json.dumps({"tracks": [p.stem for p in tracks], "params": core.Core().n_params(), "readouts": report}, indent=1))
    return report


def load_fit(mode):
    s = np.load(OUT / "stats.npz")
    r = np.load(OUT / f"readouts_{mode}.npz")
    return s["mean"], s["std"], [{k: r[f"{k}_{i}"] for k in ("mu", "sd", "ymu", "Wm", "zmu", "Wv")} for i in range(4)]


# ---- export ---------------------------------------------------------------------------------------------------

def _clean(a):
    return [None if not np.isfinite(v) else round(float(v), 6) for v in a]


def process_song(name, mode="phase"):
    audio, sidecar = SONG_FILES[name]
    sc = json.loads((SONGS / sidecar).read_text())
    mean, std, readouts = load_fit(mode)
    feats = fast_features(decode(SONGS / audio))
    x = build_inputs(feats, sc["beats"], mean, std)
    model = core.Core(phase=(mode == "phase"))
    t0 = time.perf_counter()
    run = run_core(model, x)
    dt = time.perf_counter() - t0
    ln = lanes(run, x[:, :core.FEAT], readouts)
    nb = run["nb"]
    gp = x[STRIDE - 1:nb * STRIDE:STRIDE, core.FEAT:]
    doc = {"schema": "b2-lanes-v1", "song": name, "mode": mode, "rate_hz": 10, "n_bins": nb, "seed": core.SEED,
           "params": model.n_params(), "bins_start_s": [round(0.1 * k, 1) for k in (0, nb - 1)],
           "surprisal_first_bin": {n: 2 * h // STRIDE for n, h in zip(LAYERS, core.HORIZONS)},
           "band_power": {k: _clean(v) for k, v in ln["band_power"].items()},
           "surprisal": {k: _clean(v) for k, v in ln["surprisal"].items()},
           "neuromod": {k: _clean(v) for k, v in ln["neuromod"].items()},
           "grid_phase": {"cos": _clean(gp[:, 0]), "sin": _clean(gp[:, 1])}}
    (OUT / f"{name}.{mode}.lanes.json").write_text(json.dumps(doc))
    return doc, sc, {"core_s": dt, "audio_s": len(x) / 100, "finite": run["finite"]}


def marks(sc):
    """Section starts (sidecar `sections`) and the strongest long-scale novelty candidates of musicalStructure."""
    sec = [s["start"] for s in sc.get("sections", []) if s["start"] > 0]
    nov = [c["time"] for c in sc.get("musicalStructure", {}).get("noveltyCandidates", []) if c["scaleBeats"] >= 16 and c["rank"] == 1]
    return sec, nov


def trace(doc, sc, path):
    """One static HTML file with inline SVG: 4 band powers, total surprisal, 3 neuromod lanes; section marks; m:ss axis."""
    rows = [(f"{n} band power", doc["band_power"][n]) for n in LAYERS] + [("total surprisal", doc["surprisal"]["total"])] + \
           [(k, doc["neuromod"][k]) for k in ("arousal", "tension", "familiarity")]
    dur = 0.1 * doc["n_bins"]
    sec, nov = marks(sc)
    W, H, L, R, RH = 1400, 0, 120, 12, 92
    H = RH * len(rows) + 30
    px = lambda t: L + (W - L - R) * t / dur
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" font-family="monospace" font-size="10">']
    for r, (label, v) in enumerate(rows):
        y0 = r * RH + 6
        y = np.array([np.nan if u is None else u for u in v])
        ok = np.isfinite(y)
        lo, hi = (np.percentile(y[ok], [1, 99]) if ok.any() else (0, 1))
        hi = hi if hi > lo else lo + 1e-9
        py = lambda u: y0 + (RH - 14) * (1 - (min(max(u, lo), hi) - lo) / (hi - lo))
        for t in sec:
            out.append(f'<line x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{y0}" y2="{y0 + RH - 14}" stroke="#c8a15a" stroke-width="0.6" opacity="0.8"/>')
        for t in nov:
            out.append(f'<line x1="{px(t):.1f}" x2="{px(t):.1f}" y1="{y0}" y2="{y0 + RH - 14}" stroke="#3a4654" stroke-width="0.6" stroke-dasharray="2 3"/>')
        pts = " ".join(f"{px(0.1 * (k + 1)):.1f},{py(u):.1f}" for k, u in enumerate(y) if np.isfinite(u))
        out.append(f'<polyline points="{pts}" fill="none" stroke="#9fb4c7" stroke-width="0.6"/>')
        out.append(f'<text x="{L - 8}" y="{y0 + (RH - 14) / 2:.0f}" fill="#5d6b7a" text-anchor="end">{label}</text>')
        out.append(f'<text x="{L - 8}" y="{y0 + (RH - 14) / 2 + 12:.0f}" fill="#3a4654" text-anchor="end">{lo:.3g} to {hi:.3g}</text>')
    for t in range(0, int(dur) + 1, 30):
        out.append(f'<text x="{px(t):.1f}" y="{H - 8}" fill="#5d6b7a" text-anchor="middle">{t // 60}:{t % 60:02d}</text>')
    out.append("</svg>")
    Path(path).write_text('<!doctype html><meta charset="utf-8"><title>' + doc["song"] + ' B2 traces</title>'
                          '<body style="margin:0;background:#07090c">' + "".join(out) + "</body>")


def main(argv):
    OUT.mkdir(parents=True, exist_ok=True)
    cmd = argv[0]
    if cmd == "fit":
        print(json.dumps(fit(), indent=1))
    elif cmd == "run":
        for name in SONG_FILES:
            for mode in ("phase", "nophase"):
                doc, sc, info = process_song(name, mode)
                print(name, mode, info, flush=True)
                if mode == "phase":
                    trace(doc, sc, OUT / f"{name}.trace.html")
    else:
        raise SystemExit("usage: b2.py fit | run")


if __name__ == "__main__":
    main(sys.argv[1:])
