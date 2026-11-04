"""brainDump exporter (docs/BODY_BRAIN_PLAN.md 8, work order 2 phase 2): B7 epoch 6 run over one song, its internal variables written to disk.
No claims; mechanism names only. Fixed here, before the danced songs are run (also in braindump.schema.json):

  model       B7 epoch 6 (`ckpt/phase/epoch_006.pt`), hippocampus off as trained, run over the whole song in chunks of 6,000 frames (a multiple of the
              2 s block) with the state carried. Input = the 44 corpus-standardised fast features + grid phase (b2.build_inputs, corpus feature_stats).
  grid        30 Hz: sample k is song frame (10 k) // 3 at 100 Hz, time k / 30 s. Block lanes (gain, exponent) hold the value of the 2 s block the frame is in.
  modes       the four layers' 256 complex modes h at the sample frame: (n, 4, 256, 2) float16, last axis [Re, Im].
  pred_mean   each layer's predicted mean (44 features) made at the sample frame, for the window [t + h, t + 2h) (h = 10, 50, 200, 800 frames).
  target      the actual mean of the 44 features over that same window, stamped on the frame the prediction was made; NaN where the window runs past the end.
  surprisal   per layer: mean over the 44 features of the Gaussian NLL (nats) of the prediction made at frame t - 2h + 1, scored at frame t (the frame its
              window completes), as in core_b7's arousal; NaN before frame 2h - 1.
  arousal     core_b7's arousal value (one-pole rise 1 s, decay 8 s, running mean 60 s) at the frame; gain = 1 + w_g dev, exponent = clamp(1 + w_tau dev) of
              each layer for the block (core_b7 definitions), dev = arousal - its running mean read at the block start.
  selfsimilarity  1 - max cosine between the current code and the codes stored >= 17 s earlier. Code = a FIXED random projection (hippo_h2.SEED_H2) of
              [features pooled over the last 2 s, layer norm of the [Re, Im] modes of L3 and L4 at the tick frame] to 2,048 dimensions, L2-normalised, no
              sparsification, no centring, one per 0.5 s tick (frame 50 j); held between ticks; NaN until the first entry is 17 s old. Independent of H2.
  layer_mean_re  per layer, the mean over the 256 modes of Re h at EVERY frame (100 Hz, (T, 4)): the trace the viewer draws as the layer's "EEG" strip. The
              30 Hz mode grid cannot show L1's 8-20 Hz band without aliasing.
  coherence   per layer, the magnitude-weighted Kuramoto order parameter of the 256 mode phases at each frame, R = |sum h| / sum |h|, averaged over 1 s windows
              (100 frames) stepped every 0.1 s: (nw, 4) at 10 Hz, window m ends at frame 10 m + 100 (time (m + 10) / 10 s). A crossing = at least 3 of the 4
              layers above their own threshold in that window. Thresholds = the 99th percentile of each layer's windowed values over 20 training songs
              (`thresholds` below; fixed seed for which songs; committed in braindump_thresholds.json before the danced songs run).
Outputs: <out>/<song>.braindump.npz (float16 arrays, one compressed file) and <song>.braindump.json (the shapes and metadata); braindump.schema.json
in git describes the format.

  braindump.py thresholds [--n 20]        fit and write braindump_thresholds.json (training songs only)
  braindump.py song NAME [NAME ...]       export the danced songs (instant-crush five-years presence)
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2  # noqa: E402
import core  # noqa: E402
import core_b7  # noqa: E402
import hippo_h2  # noqa: E402
import train  # noqa: E402
import train_b7  # noqa: E402
import val_split  # noqa: E402

CKPT = Path("/secondary/hyst-data/brain/b7/ckpt/phase/epoch_006.pt")
CORPUS = Path("/secondary/hyst-data/brain/corpus")
OUT = Path("/secondary/hyst-data/brain/braindump")
THRESHOLDS = Path(__file__).resolve().parent / "braindump_thresholds.json"
HZ = 30
CHUNK = 6000
WIN, STEP = 100, 10
SELECT_SEED = 20261104
N_THRESHOLD_SONGS = 20
PERCENTILE = 99.0
MIN_LAYERS = 3
SELF_MIN_AGE = core_b7.MIN_AGE


# ---- pure functions (unit-tested) ------------------------------------------------------------------------------------

def sample_frames(T):
    """Song frames of the 30 Hz grid: sample k -> frame (10 k) // 3."""
    k = np.arange((T * HZ + 99) // 100)
    return (10 * k) // 3


def order_parameter(h):
    """h (T, M) complex -> (T,) magnitude-weighted Kuramoto order parameter |sum h| / sum |h|."""
    return np.abs(h.sum(-1)) / np.maximum(np.abs(h).sum(-1), 1e-12)


def window_means(r, win=WIN, step=STEP):
    """r (T, ...) -> windows [m * step, m * step + win) averaged: (nw, ...); none if T < win."""
    if len(r) < win:
        return np.zeros((0,) + r.shape[1:], r.dtype)
    cs = np.concatenate([np.zeros((1,) + r.shape[1:], np.float64), np.cumsum(r, 0, dtype=np.float64)])
    m = np.arange(0, len(r) - win + 1, step)
    return ((cs[m + win] - cs[m]) / win).astype(np.float32)


def crossings(coh, thresholds, min_layers=MIN_LAYERS):
    """coh (nw, 4), thresholds (4,) -> (nw,) bool: at least `min_layers` layers above their own threshold."""
    return (coh > np.asarray(thresholds)[None]).sum(1) >= min_layers


def targets(z, h):
    """z (T, 44) -> (T, 44) mean of z over [t + h, t + 2h) at frame t; NaN where the window runs past the end."""
    T = len(z)
    cs = np.concatenate([np.zeros((1, z.shape[1]), np.float64), np.cumsum(z, 0, dtype=np.float64)])
    t = np.arange(T)
    ok = t + 2 * h <= T
    out = np.full(z.shape, np.nan, np.float32)
    out[ok] = ((cs[t[ok] + 2 * h] - cs[t[ok] + h]) / h)
    return out


def surprisal(err, logvar, h):
    """err, logvar (T, 44): err[t] scores the prediction made at t - 2h + 1, whose log-variance is logvar[t - 2h + 1]. -> (T,), NaN before frame 2h - 1."""
    T = len(err)
    out = np.full(T, np.nan, np.float32)
    if T < 2 * h:
        return out
    t = np.arange(2 * h - 1, T)
    lvp = logvar[t - 2 * h + 1]
    out[t] = 0.5 * (lvp + err[t] ** 2 * np.exp(-lvp) + np.log(2 * np.pi)).mean(-1)
    return out


def selfsim_lane(codes, ticks, T):
    """codes (J, D) L2-normalised, one per tick frame `ticks` (J,) -> (T,) held lane 1 - max cosine to codes >= 17 s older; NaN until the first entry is that old."""
    val = np.full(len(codes), np.nan, np.float32)
    sim = codes @ codes.T
    for j in range(len(codes)):
        el = ticks <= ticks[j] - SELF_MIN_AGE
        if el.any():
            val[j] = 1.0 - sim[j, el].max()
    lane = np.full(T, np.nan, np.float32)
    for j in range(len(ticks)):
        lane[ticks[j]:(ticks[j + 1] if j + 1 < len(ticks) else T)] = val[j]
    return lane


def pooled(z, t):
    """z (T, 44), t (J,) frames -> (J, 44) mean of z over [t - 200, t), zero-padded before the song (divided by 200, as core_b7._pooled)."""
    cs = np.concatenate([np.zeros((1, z.shape[1]), np.float64), np.cumsum(z, 0, dtype=np.float64)])
    return ((cs[t] - cs[np.maximum(t - core_b7.POOL, 0)]) / core_b7.POOL).astype(np.float32)


def projection():
    g = torch.Generator().manual_seed(hippo_h2.SEED_H2)
    d_in = core.FEAT + 4 * core.N
    return torch.randn(d_in, hippo_h2.DG_DIM, generator=g) / np.sqrt(d_in)


# ---- the run ---------------------------------------------------------------------------------------------------------

def run_song(model, x, chunk=CHUNK):
    """x (T, 46) -> the model's raw per-frame results over the whole song (state carried across chunks)."""
    T = len(x)
    nl = len(core.BANDS)
    frames = sample_frames(T)
    per = {k: [[] for _ in range(nl)] for k in ("mean", "logvar", "err", "coh", "pw", "lfp", "modes", "expo", "gain")}
    ticks, tick_state, arousal = [], [], []
    st = model.init_state(1)
    with torch.no_grad():
        for a in range(0, T, chunk):
            xc = torch.from_numpy(x[a:a + chunk])[None]
            out, st = model(xc, st)
            n = xc.shape[1]
            sel = frames[(frames >= a) & (frames < a + n)] - a
            for i, o in enumerate(out):
                h = o["h"][0]
                for k in ("mean", "logvar", "err"):
                    per[k][i].append(o[k][0].numpy())
                per["coh"][i].append(order_parameter(h.numpy()))
                per["pw"][i].append((h.real ** 2 + h.imag ** 2).mean(-1).numpy())
                per["lfp"][i].append(h.real.mean(-1).numpy())
                per["modes"][i].append(torch.view_as_real(h[sel]).numpy().astype(np.float16))
                per["expo"][i].append(o["expo"][0].numpy())
                per["gain"][i].append(1.0 + float(model.w_g[i]) * out[0]["dev"][0].numpy())
            arousal.append(out[0]["arousal"][0].numpy())
            h3, h4 = out[2]["h"][0], out[3]["h"][0]
            for t in range(0, n, core_b7.TICK):
                v = torch.cat([h3[t].real, h3[t].imag, h4[t].real, h4[t].imag])
                tick_state.append(F.layer_norm(v, (4 * core.N,)).numpy())
                ticks.append(a + t)
    cat = lambda v: np.concatenate(v, 0)
    res = {k: [cat(v) for v in per[k]] for k in per}
    res.update(arousal=cat(arousal), ticks=np.array(ticks), tick_state=np.stack(tick_state))
    return res


def export_arrays(res, z, thresholds):
    """The run's results + the standardised features z (T, 44) -> (arrays dict for the npz, meta dict)."""
    T = len(z)
    frames = sample_frames(T)
    nl = len(core.BANDS)
    blk = frames // core_b7.BLOCK
    code = np.concatenate([pooled(z, res["ticks"]), res["tick_state"]], 1)
    codes = torch.from_numpy(code).float() @ projection()
    codes = F.normalize(codes, dim=-1).numpy()
    coh = window_means(np.stack(res["coh"], 1))
    cross = crossings(coh, thresholds) if len(coh) else np.zeros(0, bool)
    f16 = lambda a: np.asarray(a, np.float32).astype(np.float16)
    arr = {
        "modes": np.stack([res["modes"][i] for i in range(nl)], 1),
        "pred_mean": f16(np.stack([res["mean"][i][frames] for i in range(nl)], 1)),
        "target": f16(np.stack([targets(z, h)[frames] for h in core.HORIZONS], 1)),
        "surprisal": f16(np.stack([surprisal(res["err"][i], res["logvar"][i], h)[frames] for i, h in enumerate(core.HORIZONS)], 1)),
        "arousal": f16(res["arousal"][frames]),
        "gain": f16(np.stack([res["gain"][i][blk] for i in range(nl)], 1)),
        "exponent": f16(np.stack([res["expo"][i][blk] for i in range(nl)], 1)),
        "selfsimilarity": f16(selfsim_lane(codes, res["ticks"], T)[frames]),
        "coherence": f16(coh),
        "crossing": cross,
        "layer_mean_re": f16(np.stack(res["lfp"], 1)),
    }
    meta = {"frames": int(T), "duration_s": T / 100.0, "samples": int(len(frames)), "windows": int(len(coh)), "crossings": int(cross.sum()),
            "shapes": {k: list(v.shape) for k, v in arr.items()}}
    return arr, meta


def load_thresholds():
    return np.array(json.loads(THRESHOLDS.read_text())["thresholds"], np.float64)


def stats():
    return train.load_stats(CORPUS / "feature_stats.npz")


def write_song(name, model, meta_model, x, out=OUT, thresholds=None):
    thresholds = load_thresholds() if thresholds is None else thresholds
    t0 = time.time()
    res = run_song(model, x)
    arr, meta = export_arrays(res, x[:, :core.FEAT], thresholds)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(out / f"{name}.braindump.npz", **arr)
    meta.update(song=name, grid_hz=HZ, window_frames=WIN, window_step_frames=STEP, thresholds=[float(t) for t in thresholds], checkpoint=str(CKPT),
                checkpoint_epoch=meta_model.get("epoch"), checkpoint_sha256=hashlib.sha256(CKPT.read_bytes()).hexdigest(), seconds_to_export=time.time() - t0,
                npz_bytes=(out / f"{name}.braindump.npz").stat().st_size)
    (out / f"{name}.braindump.json").write_text(json.dumps(meta, indent=1))
    return meta


def danced_inputs(name):
    audio, sidecar = b2.SONG_FILES[name]
    beats = json.loads((b2.SONGS / sidecar).read_text())["beats"]
    mean, std = stats()
    return b2.build_inputs(b2.fast_features(b2.decode(b2.SONGS / audio)), beats, mean, std)


def fit_thresholds(n=N_THRESHOLD_SONGS, seed=SELECT_SEED, manifest=CORPUS / "manifest.json"):
    """The 99th percentile of each layer's windowed order parameter over n training songs (fit side of the validation-artist split), chosen with `seed`."""
    mean, std = stats()
    tracks = train.read_manifest(manifest)
    fit, _ = val_split.split_tracks([t for t in tracks if t.split == "train"], val_split.load(val_split.ARTISTS_JSON))
    pick = sorted(np.random.default_rng(seed).choice(len(fit), n, replace=False))
    model, _ = train_b7.load_model7(CKPT)
    wins = []
    for j in pick:
        res = run_song(model, train.load_inputs(fit[j], mean, std))
        wins.append(window_means(np.stack(res["coh"], 1)))
        print(fit[j].id, len(wins[-1]), flush=True)
    allw = np.concatenate(wins)
    th = np.percentile(allw, PERCENTILE, axis=0)
    return {"thresholds": [float(t) for t in th], "percentile": PERCENTILE, "seed": seed, "n_songs": n, "song_ids": [fit[j].id for j in pick],
            "windows": int(len(allw)), "checkpoint": str(CKPT), "min_layers": MIN_LAYERS,
            "crossing_share_on_these_songs": float(crossings(allw, th).mean())}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=("thresholds", "song"))
    ap.add_argument("names", nargs="*")
    ap.add_argument("--n", type=int, default=N_THRESHOLD_SONGS)
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args(argv)
    torch.set_num_threads(a.threads)
    if a.which == "thresholds":
        THRESHOLDS.write_text(json.dumps(fit_thresholds(a.n), indent=1))
        print(THRESHOLDS.read_text())
        return
    model, meta_model = train_b7.load_model7(CKPT)
    for name in a.names or list(b2.SONG_FILES):
        print(json.dumps(write_song(name, model, meta_model, danced_inputs(name), a.out)), flush=True)


if __name__ == "__main__":
    main()
