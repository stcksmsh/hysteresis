"""Ear energy lane (docs/EAR_ENERGY_RULES.md, WO30A).  Fixed formula, do not retune.

    ear_energy.py norm OUTDIR      brain env: writes ear_energy_norm.json from OUTDIR/<song>.feat.npy of the three danced songs
    ear_energy.py lane FEAT.npy OUT.npy   10 Hz raw ear energy lane of one song's 44-feature array
    ear_energy.py input FEAT.npy OUT.npy  the same, as network input (standardised, clipped to +-3)
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import maximum_filter1d, uniform_filter1d

COL_ONSET, COL_RMS = 40, 41
NORM = Path(__file__).resolve().parent / "ear_energy_norm.json"
SONGS3 = ("instant-crush", "five-years", "presence")
RMS_FLOOR = 1e-4
LOUD_WIN = 101      # 1 s
PEAK_HALF = 5       # +-5 frames
PEAK_MIN = 1.0
DENS_WIN = 201      # 2 s
BLOCK = 10          # 100 Hz -> 10 Hz
CLIP = 3.0


def terms(feats):
    """(loudness dB, 1 s mean; onset peaks per s over 2 s) per 100 Hz frame"""
    f = np.asarray(feats, float)
    loud = uniform_filter1d(20 * np.log10(np.maximum(f[:, COL_RMS], RMS_FLOOR)), LOUD_WIN, mode="nearest")
    o = f[:, COL_ONSET]
    peak = (o >= PEAK_MIN) & (o == maximum_filter1d(o, 2 * PEAK_HALF + 1, mode="nearest"))
    # first of equal neighbours wins: drop a peak that equals the frame just before it inside the window
    peak[1:] &= ~((o[1:] == o[:-1]) & peak[:-1])
    c = np.concatenate([[0], np.cumsum(peak)])
    h = DENS_WIN // 2
    lo, hi = np.clip(np.arange(len(o)) - h, 0, len(o)), np.clip(np.arange(len(o)) + h + 1, 0, len(o))
    return loud, (c[hi] - c[lo]) / 2.0


def blocks(x):
    n = len(x) // BLOCK
    return np.asarray(x)[:n * BLOCK].reshape(n, BLOCK).mean(1)


def norm():
    return json.loads(NORM.read_text())


def lane(feats, nm=None):
    """raw ear energy, 10 Hz"""
    nm = nm or norm()
    loud, dens = terms(feats)
    return blocks(((loud - nm["loud_mean"]) / nm["loud_sd"] + (dens - nm["dens_mean"]) / nm["dens_sd"]) / 2)


def network_input(feats, nm=None):
    nm = nm or norm()
    return np.clip((lane(feats, nm) - nm["mu"]) / nm["sd"], -CLIP, CLIP)


def fit_norm(feats_by_song):
    t = [terms(f) for f in feats_by_song]
    L, D = np.concatenate([a for a, _ in t]), np.concatenate([b for _, b in t])
    nm = dict(loud_mean=float(L.mean()), loud_sd=float(L.std()), dens_mean=float(D.mean()), dens_sd=float(D.std()))
    e = np.concatenate([lane(f, nm) for f in feats_by_song])
    nm.update(mu=float(e.mean()), sd=float(e.std()))
    return nm


def main():
    cmd = sys.argv[1]
    if cmd == "norm":
        d = Path(sys.argv[2])
        nm = fit_norm([np.load(d / f"{s}.feat.npy") for s in SONGS3])
        NORM.write_text(json.dumps(nm, indent=1) + "\n")
        print(nm)
    elif cmd in ("lane", "input"):
        f = np.load(sys.argv[2])
        np.save(sys.argv[3], lane(f) if cmd == "lane" else network_input(f))
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
