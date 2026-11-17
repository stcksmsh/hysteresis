"""WO51 pulse v2 (BRAIN_SPEC 7.80 Q1): v1's oscillator bank, drive and integrator (pulse_lib, grfnn) with
(b) a harmonic-support readout, (s) a stricter level-change rule that relaxes near a causal novelty boundary, and
(c) a confidence output. Every value and its source: docs/PULSE2_RULES.md.

    features (fast_features, 100 Hz) -> drive (pulse_lib.drive, unchanged) -> bank (v1 oscillators + support oscillators 0.25-0.5 and 4-8 Hz)
    -> harmonic score H(f) = A(f) + 0.5 A(2f) + 0.5 A(f/2), times prior, f <= f_max -> selection (35 % / 4 s, 1.5 s near a boundary)
    -> period, phase, confidence, selected frequency per 10 ms frame; pulse events (phase-zero crossings) with their confidence
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brain"))
import grfnn  # noqa: E402
import pulse_lib as P1  # noqa: E402

FRAME_HZ = P1.FRAME_HZ
# ---- bank: v1's 73 oscillators (0.5-4 Hz, 24 per octave) plus one octave of support oscillators on each side (same grid) ----
I_LO, I_HI = -P1.PER_OCTAVE, 3 * P1.PER_OCTAVE + P1.PER_OCTAVE   # f = 0.5 * 2^(i/24), i = -24..96: 0.25-8 Hz, 121 oscillators
# ---- (b) harmonic-support readout ----
W_UP, W_DOWN = 0.5, 0.5                                   # weights of A(2f) and A(f/2)
# ---- (s) stability ----
SWITCH_RATIO = 1.35                                       # margin M = 35 % (v1: 20 %)
HOLD_S = 4.0                                              # hold H = 4 s (v1: 2 s)
HOLD_NEAR_S = 1.5                                         # H near a novelty boundary
NEAR_S = 1.0                                              # "near": the evidence run started within +-1 s of a boundary
LOCAL = P1.LOCAL                                          # +-2 oscillators followed freely (as v1)
# ---- novelty detector (causal ear change, after cortexev's E-change) ----
NOV_WIN_S = 1.0                                           # mean of the last 1 s vs the 1 s before
NOV_CONFIRM_S = 0.5                                       # a peak is confirmed 0.5 s after it (max over [peak - 1 s, peak + 0.5 s])
NOV_PCTL, NOV_HIST_S, NOV_MIN_HIST_S = 90.0, 60.0, 10.0   # peak >= 90th percentile of the change over the past 60 s (needs >= 10 s of history)
NOV_GAP_S = 4.0                                           # boundaries at least 4 s apart
# ---- (c) confidence ----
PROM_FULL = 4.0                                           # prominence S_sel / median_band(S) at which the prominence term reaches 1
COH_TAU_S, DRIVE_TAU_S = 2.0, 30.0                        # coherent-drive EMA, long-term drive EMA
COH_FULL = 0.6                                            # coherent drive / long-term drive at which the drive term reaches 1


def frequencies():
    return P1.F_LO * 2.0 ** (np.arange(I_LO, I_HI + 1) / P1.PER_OCTAVE)


def bank(x):
    f = frequencies()
    zr, zi = grfnn._run(np.ascontiguousarray(x, np.float64), 2 * np.pi * f, P1.ALPHA, P1.BETA1, P1.BETA2, P1.EPS, 1.0,
                        1.0 / (FRAME_HZ * P1.SUBSTEPS), P1.SUBSTEPS, P1.Z0, P1.R_MAX)
    return f, np.hypot(zr, zi), np.arctan2(zi, zr)


def amp_at(f, amp, q):
    """amplitude at frequencies q (any), linear interpolation on the log2-frequency grid; 0 outside the bank. (frames, len(q))"""
    lf, lq = np.log2(f), np.log2(np.asarray(q, float))
    out = np.zeros((amp.shape[0], len(lq)))
    for j, v in enumerate(lq):
        if v < lf[0] - 1e-9 or v > lf[-1] + 1e-9:
            continue
        k = int(np.clip(np.searchsorted(lf, v - 1e-9), 1, len(lf) - 1))
        if abs(lf[k] - v) < 1e-9:
            out[:, j] = amp[:, k]
        elif abs(lf[k - 1] - v) < 1e-9:
            out[:, j] = amp[:, k - 1]
        else:
            w = (v - lf[k - 1]) / (lf[k] - lf[k - 1])
            out[:, j] = (1 - w) * amp[:, k - 1] + w * amp[:, k]
    return out


def harmonic_score(f, amp, band):
    """S = (A(f) + W_UP A(2f) + W_DOWN A(f/2)) * prior(f) for the selectable oscillators `band` (frames, len(band))"""
    fb = f[band]
    H = amp[:, band] + W_UP * amp_at(f, amp, 2 * fb) + W_DOWN * amp_at(f, amp, fb / 2)
    return H * P1.prior(fb)


def ema(v, tau_s):
    a = 1.0 / (tau_s * FRAME_HZ)
    out = np.empty(len(v), dtype=np.result_type(v, np.float64))
    m = 0.0
    for i, s in enumerate(v):
        m += a * (s - m)
        out[i] = m
    return out


def novelty(feat):
    """causal ear change: every column of the 44 fast features as a running z-score (grfnn.standardise_causal, 10 s), delayed 3 frames
    (as the drive); c(t) = |mean z over (t-1 s, t] - mean z over (t-2 s, t-1 s]| / sqrt(44). -> c (frames,)"""
    z = np.stack([grfnn.standardise_causal(feat[:, j], 1.0, P1.STD_TAU_S) for j in range(feat.shape[1])], 1)
    z = np.concatenate([np.zeros((P1.CAUSAL_DELAY, z.shape[1])), z[:len(z) - P1.CAUSAL_DELAY]])
    n = int(NOV_WIN_S * FRAME_HZ)
    cs = np.concatenate([np.zeros((1, z.shape[1])), np.cumsum(z, 0)])
    T = len(z)
    c = np.zeros(T)
    t = np.arange(2 * n, T)
    m1 = (cs[t + 1] - cs[t + 1 - n]) / n
    m0 = (cs[t + 1 - n] - cs[t + 1 - 2 * n]) / n
    c[t] = np.linalg.norm(m1 - m0, axis=1) / np.sqrt(z.shape[1])
    return c


def boundaries(c):
    """large novelty peaks, causal: a peak frame p is detected at p + 0.5 s when c(p) is the maximum of c over [p - 1 s, p + 0.5 s],
    c(p) >= the 90th percentile of c over the 60 s before p (threshold updated once per second, needs >= 10 s of history), and p is
    at least 4 s after the previous boundary. -> peak frames (sorted)"""
    T = len(c)
    k_back, k_fwd = int(FRAME_HZ), int(NOV_CONFIRM_S * FRAME_HZ)
    hist, min_hist, gap = int(NOV_HIST_S * FRAME_HZ), int(NOV_MIN_HIST_S * FRAME_HZ), int(NOV_GAP_S * FRAME_HZ)
    th = np.full(T, np.inf)
    for s in range(min_hist, T, int(FRAME_HZ)):
        th[s:s + int(FRAME_HZ)] = np.percentile(c[max(s - hist, 0):s], NOV_PCTL)
    out, last = [], -10 ** 9
    for p in range(k_back, T - k_fwd):
        if c[p] < th[p] or p - last < gap or c[p] <= 0:
            continue
        if c[p] >= c[p - k_back:p + k_fwd + 1].max() and c[p] > c[p - k_back:p].max():
            out.append(p)
            last = p
    return np.array(out, np.int64)


def readout(f, amp, phase, x, bounds=(), fmax=None):
    """selection on the harmonic score with the (s) rule; rate, phase, events as v1 (pulse_lib.readout); confidence (c)."""
    fmax = P1.f_max() if fmax is None else fmax
    band = np.flatnonzero((f >= P1.F_LO - 1e-9) & (f <= fmax + 1e-9))
    S = harmonic_score(f, amp, band)
    T = amp.shape[0]
    need, need_near, near = int(round(HOLD_S * FRAME_HZ)), int(round(HOLD_NEAR_S * FRAME_HZ)), int(round(NEAR_S * FRAME_HZ))
    bounds = np.asarray(bounds, np.int64)
    sel = np.zeros(T, np.int64)
    switches = []                                          # (frame, from index, to index, near boundary)
    cur, run = None, 0
    for t in range(T):
        b = int(np.argmax(S[t]))
        if cur is not None:                                # local following, free (as v1)
            lo, hi = max(cur - LOCAL, 0), min(cur + LOCAL + 1, len(band))
            cur = lo + int(np.argmax(S[t, lo:hi]))
        if cur is None:
            cur = b
        elif S[t, b] > SWITCH_RATIO * S[t, cur]:
            run += 1
            s0 = t - run + 1                               # first frame of the evidence run
            nb = len(bounds) and bool(np.any(np.abs(bounds[(bounds <= t - int(NOV_CONFIRM_S * FRAME_HZ))] - s0) <= near))
            if run >= need or (nb and run >= need_near):
                switches.append((t, int(band[cur]), int(band[b]), bool(nb and run < need)))
                cur, run = b, 0
        else:
            run = 0
        sel[t] = cur
    idx = np.arange(T)
    gsel = band[sel]
    ph = phase[idx, gsel]
    a = amp[idx, gsel]
    dph = np.zeros(T)
    dph[1:] = np.mod(phase[idx[1:], gsel[1:]] - phase[idx[1:] - 1, gsel[1:]] + np.pi, 2 * np.pi) - np.pi
    w = int(P1.RATE_WIN_S * FRAME_HZ)
    cs = np.concatenate([[0.0], np.cumsum(dph)])
    lo = np.maximum(idx + 1 - w, 1)
    rate = (cs[idx + 1] - cs[lo]) / np.maximum(idx + 1 - lo, 1) * FRAME_HZ / (2 * np.pi)
    rate[0] = f[gsel[0]]
    # (c) confidence = prominence term x coherent-drive term
    Ssel = S[idx, sel]
    prom = Ssel / np.maximum(np.median(S, 1), 1e-12)
    p_term = np.clip((prom - 1.0) / (PROM_FULL - 1.0), 0.0, 1.0)
    coh = np.abs(ema(np.asarray(x, float) * np.exp(-1j * ph), COH_TAU_S)) / np.maximum(ema(np.asarray(x, float), DRIVE_TAU_S), 1e-6)
    d_term = np.clip(coh / COH_FULL, 0.0, 1.0)
    conf = p_term * d_term
    prev = np.concatenate([[np.nan], phase[idx[1:] - 1, gsel[1:]]])
    up = (prev < 0) & (ph >= 0) & (ph - prev < np.pi)
    up[1:] &= gsel[1:] == gsel[:-1]
    k = np.flatnonzero(up)
    events = (k - 1 + (-prev[k]) / (ph[k] - prev[k])) / FRAME_HZ
    return dict(sel=gsel, freq=f[gsel], rate=rate, period=1.0 / np.maximum(rate, 1e-6), phase=ph, amp=a, conf=conf, prom=prom, coh=coh,
                score=Ssel, events=events, event_conf=conf[k], switches=switches)


def pulse(feat, fmax=None):
    x = P1.drive(feat)
    f, amp, phase = bank(x)
    c = novelty(feat)
    bd = boundaries(c)
    r = readout(f, amp, phase, x, bd, fmax)
    r.update(drive=x, novelty=c, boundaries=bd / FRAME_HZ, bank_amp=amp, f=f)
    return r
