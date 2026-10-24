"""The smoothing control of step 2b (docs/NEXT_BODY_THEN_MIND.md, "Round 1 result and step 2b").

A prediction series is passed through a causal exponential smoother with time constant tau and then
delayed by L: the output at t is the smoothed prediction at t - L. tau = 0 means no smoothing, L = 0 no
delay. Both are applied to the whole step series of a song (0.5 s steps) from step 0, then read at the
scored steps.

Fixed here, not by the note: the smoother starts at the first prediction (no ramp from zero), and the
first L seconds of the delayed series repeat the first smoothed value.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import lfilter

import common

TAUS = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0)
LAGS = tuple(0.5 * i for i in range(9))      # 0, 0.5, ..., 4 s


def smooth_delay(pred, tau, lag, hop=common.HOP_SECONDS):
    """pred (T,) or (T, k) -> same shape. y[t] = a y[t-1] + (1 - a) pred[t], a = exp(-hop / tau), y[-1] = pred[0];
    out[t] = y[t - lag / hop], held at y[0] before that."""
    p = np.asarray(pred, dtype=np.float64)
    y = p.copy()
    if tau > 0:
        a = np.exp(-hop / tau)
        zi = (a * p[0])[None] if p.ndim == 1 else a * p[:1]    # state of y[-1] = p[0]
        y, _ = lfilter([1.0 - a], [1.0, -a], p, axis=0, zi=zi)
    shift = int(round(lag / hop))
    if shift == 0:
        return y
    out = np.empty_like(y)
    out[:shift] = y[0]
    out[shift:] = y[:len(y) - shift]
    return out
