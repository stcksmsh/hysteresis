"""WO48 internal pulse (BRAIN_SPEC 7.78 2.1): a GrFNN oscillator bank driven by the ear features, and its pulse readout.
Every value and its source: docs/PULSE_RULES.md. Reuses the B1 integrator (scripts/brain/grfnn.py, RK4, numba) unchanged.

    features (fast_features, 44 columns, 100 Hz) -> drive (causal) -> bank (73 oscillators, 0.5-4 Hz) -> readout
    readout per 10 ms frame: selected index, rate (Hz), phase (rad), amplitude; pulse events = phase crossings
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brain"))
import grfnn  # noqa: E402

FRAME_HZ = 100.0
# ---- bank (Velasco & Large 2011 section 2.1 values; range and count from the work order) ----
F_LO, F_HI, PER_OCTAVE = 0.5, 4.0, 24                      # 3 octaves x 24 + 1 = 73 oscillators
ALPHA, BETA1, BETA2, EPS = 0.0, -1.0, -0.25, 1.0
SUBSTEPS = 2                                               # RK4 at 5 ms, input held over each 10 ms frame
Z0, R_MAX = 1e-3, 0.95
# ---- drive ----
COLS = {32: 1.0, 33: 0.5, 40: 0.5}                         # flux 30-200 Hz (kick), flux 200-400 Hz (rim/snare body), onset strength (all bands)
SD_REF = {32: grfnn.SD_REF_FLUX, 33: grfnn.SD_REF_FLUX, 40: grfnn.SD_REF_ONSET}
STD_TAU_S = 10.0
C_IN, X_MAX = 0.05, 0.5
CAUSAL_DELAY = 3                                           # frames: the centred 2048-sample STFT looks 23.2 ms ahead; 3 frames = 30 ms removes it
# ---- arm limit (make_arm.LIMITS: shoulder 90 deg/s, 300 deg/s2; base 120 deg/s, 600 deg/s2) ----
SWING_DEG = 5.0                                            # reference movement: theta(t) = A sin(pi f t), one side-to-side swing of +-A per pulse period
ARM = {"shoulder": (90.0, 300.0), "base_yaw": (120.0, 600.0)}
# ---- selection ----
PRIOR_HZ, PRIOR_SIGMA_OCT = 2.0, 1.0                       # log-Gaussian prior P(f) = exp(-0.5 (log2(f / 2) / 1)^2)
SWITCH_RATIO, SWITCH_SECONDS = 1.2, 2.0                    # hysteresis (B1 rule): switch only after 2 s in a row of S_other > 1.2 S_current
LOCAL = 2                                                  # +-2 oscillators (+-1/12 octave, +-5.9 %) are followed without hysteresis
RATE_WIN_S = 1.0                                          # rate = mean phase advance of the selected oscillator over the last 1 s


def frequencies():
    n = int(round(np.log2(F_HI / F_LO) * PER_OCTAVE)) + 1
    return F_LO * 2.0 ** (np.arange(n) / PER_OCTAVE)


def f_max(swing_deg=SWING_DEG, arm=ARM):
    """Highest pulse rate the arm can follow with theta = A sin(pi f t): peak speed pi f A <= v, peak acceleration (pi f)^2 A <= a,
    for every listed joint. f <= min(v / (pi A), sqrt(a / A) / pi)."""
    return float(min(min(v / (np.pi * swing_deg), np.sqrt(a / swing_deg) / np.pi) for v, a in arm.values()))


def prior(f):
    return np.exp(-0.5 * (np.log2(np.asarray(f, float) / PRIOR_HZ) / PRIOR_SIGMA_OCT) ** 2)


def drive(feat):
    """(frames, 44) fast features -> bank input x (frames,), causal: weighted sum of running z-scores, half-wave rectified,
    scaled by C_IN, capped at X_MAX, delayed by CAUSAL_DELAY frames."""
    u = sum(w * grfnn.standardise_causal(feat[:, c], SD_REF[c], STD_TAU_S) for c, w in COLS.items())
    x = np.minimum(C_IN * np.maximum(u, 0.0), X_MAX)
    return np.concatenate([np.zeros(CAUSAL_DELAY), x[:len(x) - CAUSAL_DELAY]])


def bank(x):
    f = frequencies()
    zr, zi = grfnn._run(np.ascontiguousarray(x, np.float64), 2 * np.pi * f, ALPHA, BETA1, BETA2, EPS, 1.0,
                        1.0 / (FRAME_HZ * SUBSTEPS), SUBSTEPS, Z0, R_MAX)
    return f, np.hypot(zr, zi), np.arctan2(zi, zr)


def readout(f, amp, phase, fmax=None):
    """Selected oscillator per frame (argmax amplitude x prior among f <= fmax, with the hysteresis rule), its amplitude, phase,
    rate (Hz, mean phase advance of the selected oscillator over the last RATE_WIN_S, causal) and pulse events (upward crossings
    of phase 0 of the selected oscillator, linearly interpolated; none in the frame of a switch)."""
    fmax = f_max() if fmax is None else fmax
    band = np.flatnonzero(f <= fmax + 1e-9)
    score = amp[:, band] * prior(f[band])
    T = amp.shape[0]
    need = int(round(SWITCH_SECONDS * FRAME_HZ))
    sel = np.zeros(T, np.int64)
    cur, run = None, 0
    for t in range(T):
        b = int(np.argmax(score[t]))
        if cur is not None:                                # follow the local peak within +-LOCAL oscillators freely (tempo following)
            lo, hi = max(cur - LOCAL, 0), min(cur + LOCAL + 1, len(band))
            cur = lo + int(np.argmax(score[t, lo:hi]))
        if cur is None:
            cur = b
        elif score[t, b] > SWITCH_RATIO * score[t, cur]:
            run += 1
            if run >= need:
                cur, run = b, 0
        else:
            run = 0
        sel[t] = band[cur]
    idx = np.arange(T)
    ph = phase[idx, sel]
    a = amp[idx, sel]
    # phase advance of the selected oscillator between t-1 and t (same oscillator both frames)
    dph = np.zeros(T)
    dph[1:] = np.mod(phase[idx[1:], sel[1:]] - phase[idx[1:] - 1, sel[1:]] + np.pi, 2 * np.pi) - np.pi
    w = int(RATE_WIN_S * FRAME_HZ)
    cs = np.concatenate([[0.0], np.cumsum(dph)])
    lo = np.maximum(idx + 1 - w, 1)
    rate = (cs[idx + 1] - cs[lo]) / np.maximum(idx + 1 - lo, 1) * FRAME_HZ / (2 * np.pi)
    rate[0] = f[sel[0]]
    prev = np.concatenate([[np.nan], phase[idx[1:] - 1, sel[1:]]])
    up = (prev < 0) & (ph >= 0) & (ph - prev < np.pi)
    up[1:] &= sel[1:] == sel[:-1]
    k = np.flatnonzero(up)
    events = (k - 1 + (-prev[k]) / (ph[k] - prev[k])) / FRAME_HZ
    return dict(sel=sel, freq=f[sel], rate=rate, phase=ph, amp=a, events=events)


def pulse(feat, fmax=None):
    x = drive(feat)
    f, amp, phase = bank(x)
    r = readout(f, amp, phase, fmax)
    r["drive"] = x
    r["bank_amp"] = amp
    return r
