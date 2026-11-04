"""Self-surprisal lane (BRAIN_SPEC 7.14 point 1): "cerebellum: prediction error of its own arm". No claim (K1 failed).

For each danced song and each of the six v47 arms: replay the 100 Hz joint CSV in physics (build_v47.replay, as the M1 set did), run the K1 round-2
cerebellum over the whole song, and take the Gaussian NLL of the actual change of proprioception at each horizon (mean over the 15 dims, nats in
the model's standardised units). Written at 30 Hz (mean over the 100 Hz steps of each bin) to <out>/<song>.npz and <out>/schema.json.

The net was trained on 200-step chunks with a 20-step warm-up, so it runs here the same way: chunks of 200, stride 180, the first 20 steps of each
chunk are warm-up and only the first chunk's are left undefined (NaN). Steps with k + 10 >= T have no label (NaN at the horizons that run past the end).

    python selfsurprisal.py CSV_DIR BUNDLE.pt OUT_DIR
"""
import json
import sys
from pathlib import Path

import numpy as np
import torch

import build_v47
import cerebellum as cb

SONGS = {"ic": "instant-crush", "fy": "five-years", "pr": "presence"}
HZ_OUT = 30


def lane(obs, tgt, net, st):
    """(T, 15), (T, 5) -> (T, 3) per-step NLL at horizons +10/+50/+100 ms, NaN where undefined."""
    T = len(obs)
    X = cb.features(obs[None], tgt[None], st)[0]
    Y, valid = cb.labels(obs[None], st)
    Y, valid = Y[0], valid[0]
    starts = list(range(0, T - cb.CHUNK + 1, cb.CHUNK - cb.WARM))
    if starts[-1] != T - cb.CHUNK:
        starts.append(T - cb.CHUNK)
    out = np.full((T, len(cb.HORIZONS)), np.nan, np.float32)
    with torch.no_grad():
        for b in range(0, len(starts), 128):
            ss = starts[b:b + 128]
            m, lv = net(torch.from_numpy(np.stack([X[s:s + cb.CHUNK] for s in ss])))
            m, lv = m.numpy(), lv.numpy()
            for j, s in enumerate(ss):
                lo = 0 if s == 0 else cb.WARM
                y = Y[s:s + cb.CHUNK]
                nll = cb.gauss_nll(m[j], lv[j], y).mean(-1)                 # (CHUNK, 3)
                out[s + lo:s + cb.CHUNK] = nll[lo:]
    out[~valid] = np.nan
    out[:cb.WARM] = np.nan
    return out


def to_hz(a, hz_in=100, hz_out=HZ_OUT):
    n = int(len(a) * hz_out / hz_in)
    edges = np.floor(np.arange(n + 1) * hz_in / hz_out).astype(int)
    r = np.full((n,) + a.shape[1:], np.nan, np.float32)
    for i in range(n):
        seg = a[edges[i]:edges[i + 1]]
        if np.isfinite(seg).any():
            r[i] = np.nanmean(seg, 0)
    return r


def main(csv_dir, bundle, out):
    net, st, _, _ = cb.load_bundle(bundle)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for s, name in SONGS.items():
        lanes = []
        for arm in range(6):
            tgt = build_v47.load_csv(f"{csv_dir}/{s}-{arm}.csv")
            obs, _ = build_v47.replay(tgt)
            lanes.append(to_hz(lane(obs, tgt.astype(np.float32), net, st)))
        n = min(len(l) for l in lanes)
        nll = np.stack([l[:n] for l in lanes])                                # (6, n, 3)
        p = out / f"{name}.npz"
        np.savez_compressed(p, nll=nll, hz=np.float32(HZ_OUT), horizons_steps=np.array(cb.HORIZONS), bundle=Path(bundle).name)
        sizes[name] = {"bytes": p.stat().st_size, "bins": n, "seconds": n / HZ_OUT, "finite_fraction": float(np.isfinite(nll).mean()),
                       "median_nll": float(np.nanmedian(nll)), "p99_nll": float(np.nanpercentile(nll, 99))}
        print(name, sizes[name], flush=True)
    schema = {
        "name": "cerebellum: prediction error of its own arm", "claim": "none (K1 failed, BRAIN_SPEC 7.14 point 1)",
        "source": "K1 round-2 bundle m1_r2.pt (scripts/body/cerebellum.py); v47 trajectories (Off) replayed in physics (build_v47.replay)",
        "file": "<song>.npz, song in {instant-crush, five-years, presence}",
        "arrays": {"nll": "float32 (arms=6, bins, horizons=3): mean over the 15 proprioception dims of the Gaussian NLL (nats, standardised units) of the actual change at +10/+50/+100 ms; NaN = undefined",
                   "hz": "30; bin i covers [i/30, (i+1)/30) s, value = mean over the 100 Hz steps in it, stamped at the step the prediction was issued (the error is known h steps later)",
                   "horizons_steps": "[1, 5, 10] steps of 10 ms", "bundle": "file name of the model bundle"},
        "undefined": "first 20 steps of a song (GRU warm-up); steps with k + 10 >= T at the horizons that run past the end",
        "sizes": sizes,
    }
    (out / "schema.json").write_text(json.dumps(schema, indent=1))


if __name__ == "__main__":
    main(*sys.argv[1:4])
