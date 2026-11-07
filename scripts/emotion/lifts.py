"""Known lifts for gate 4 of check 1b, from an energy curve.

The rule is fixed in docs/NEXT_BODY_THEN_MIND.md, step 2, "Known lifts for gate 4, taken from
the curves" (commit b1775f8). Curve at 10 Hz, values 0..1:

1. clean-up: running median over 15 samples (1.5 s), then a centred running mean over 2 s;
2. a rise is any time t where cleaned(t + 4 s) - cleaned(t) >= 0.15; touching rise times merge
   into one rise whose onset is its earliest t;
3. the lift is placed at onset - 1.5 s (reaction lag);
4. the first 2 s and the last 5 s of a song are never a lift; a rise that touches a masked span
   is not a lift (the first 2 s and last 5 s are treated as masked spans, so an end flick is out);
5. of two lifts closer than 16 beats, only the first is kept.

Points the rule text leaves open and this code fixes (listed in the handoff, to be ruled on):
the median and mean are centred and shrink at the ends of the curve (the mean over 2 s is 20
samples, [i - 10, i + 10)); "touching" means adjacent samples; a rise spans [onset, last rise
time + 4 s] and is dropped if that span touches a mask, the first 2 s or the last 5 s of the song
(the alternative reading, the limits on the placed lift time, would let an end flick through);
"closer than 16 beats" compares beat positions of the placed lifts, against the last one kept.
"""
from __future__ import annotations

import numpy as np

RATE = 10
MEDIAN_SAMPLES = 15
MEAN_SAMPLES = 20
RISE_SECONDS = 4.0
RISE_MIN = 0.15
LAG_SECONDS = 1.5
HEAD_SECONDS = 2.0
TAIL_SECONDS = 5.0
MIN_BEATS_APART = 16


def clean(curve):
    """Running median (15 samples) then centred running mean (20 samples); windows shrink at the ends."""
    x = np.asarray(curve, dtype=np.float64)
    n = len(x)
    half = MEDIAN_SAMPLES // 2
    med = np.array([np.median(x[max(0, i - half):i + half + 1]) for i in range(n)])
    csum = np.concatenate([[0.0], np.cumsum(med)])
    lo = np.maximum(np.arange(n) - MEAN_SAMPLES // 2, 0)
    hi = np.minimum(np.arange(n) + MEAN_SAMPLES // 2, n)
    return (csum[hi] - csum[lo]) / (hi - lo)


def beat_position(times, beats):
    """Fractional beat index of each time on the grid `beats` (seconds); linear between beats and
    extended past either end with the nearest beat interval."""
    beats = np.asarray(beats, dtype=np.float64)
    t = np.asarray(times, dtype=np.float64)
    idx = np.arange(len(beats), dtype=np.float64)
    pos = np.interp(t, beats, idx)
    first, last = beats[1] - beats[0], beats[-1] - beats[-2]
    pos = np.where(t < beats[0], (t - beats[0]) / first, pos)
    return np.where(t > beats[-1], len(beats) - 1 + (t - beats[-1]) / last, pos)


def find_lifts(curve, beats, duration=None, masks=()):
    """Lift times in seconds. `curve` is the 0..1 energy curve at 10 Hz from t = 0, `beats` the
    song's beat times, `duration` the song length (default: the curve's), `masks` a sequence
    of (start, end) seconds that no lift may touch."""
    x = clean(curve)
    duration = len(x) / RATE if duration is None else duration
    lag = int(round(RISE_SECONDS * RATE))
    if len(x) <= lag:
        return []
    rising = np.flatnonzero(x[lag:] - x[:-lag] >= RISE_MIN)
    runs = np.split(rising, np.flatnonzero(np.diff(rising) > 1) + 1) if len(rising) else []
    blocked = list(masks) + [(-1.0, HEAD_SECONDS), (duration - TAIL_SECONDS, float("inf"))]
    lifts = []
    for run in runs:
        onset = run[0] / RATE
        span = (onset, run[-1] / RATE + RISE_SECONDS)
        if any(span[0] < b and a < span[1] for a, b in blocked):
            continue
        lifts.append(onset - LAG_SECONDS)
    kept, last_pos = [], None
    for t, pos in zip(lifts, beat_position(lifts, beats) if lifts else []):
        if last_pos is not None and pos - last_pos < MIN_BEATS_APART:
            continue
        kept.append(t)
        last_pos = pos
    return kept
