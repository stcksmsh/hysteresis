"""WO46 part 2 pure functions (docs/METRIC_RULES.md sections 3-5). numpy + scipy only; no data access."""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

FS = 50
SEP, SEP_ONSET = 10, 15
LEVELS = ("beat", "half_beat", "half_time", "bar")
HIT_W = 0.05
LAGS = np.arange(-250, 251, 25) / 1000.0


def box5(x):
    return uniform_filter1d(x, 5, axis=0, mode="reflect")


def _mins_peaks(x, prom, dist=SEP):
    p, _ = find_peaks(x, prominence=prom, distance=dist)
    return p


def events(q50, lamp, A, p90, P):
    """q50 (n, 5) deg, lamp (n, 3) m at 50 Hz -> dict id -> event times (s): E1, E2, E4, E5, E3_0..E3_4 (rules section 3)"""
    import controls_lib as C
    v = np.gradient(lamp, axis=0) * FS
    a = np.gradient(v, axis=0) * FS
    w = np.gradient(q50, axis=0) * FS
    speed = np.linalg.norm(v, axis=1)
    out = {}
    e1 = _mins_peaks(-box5(speed), 0.05)
    out["E1"] = e1
    out["E2"] = _mins_peaks(box5(np.linalg.norm(a, axis=1)), 0.25 * A)
    for j in range(5):
        out[f"E3_{j}"] = _mins_peaks(box5(np.abs(w[:, j])), 0.25 * p90[j])
    k = []
    b, f = int(0.04 * FS), int(0.20 * FS)
    for t in e1:
        if t - f < 0 or t + f >= len(v):
            continue
        v0, v1 = v[t - f:t - b + 1].mean(0), v[t + b:t + f + 1].mean(0)
        n0, n1 = np.linalg.norm(v0), np.linalg.norm(v1)
        if n0 >= 0.10 and n1 >= 0.10 and np.degrees(np.arccos(np.clip(v0 @ v1 / (n0 * n1), -1, 1))) > 120:
            k.append(t)
    out["E4"] = np.array(k, int)
    on = C.onsets(speed, P)
    keep = []
    for t in on:
        if not keep or t - keep[-1] >= SEP_ONSET:
            keep.append(t)
    out["E5"] = np.array(keep, int)
    return {k: np.asarray(v, int) / FS for k, v in out.items()}


def choose_bar(beats, onset_at_beat):
    """parity (half-time) and offset (bar) with the largest mean onset strength at beats with that residue -> (parity, offset)"""
    s = np.asarray(onset_at_beat, float)
    i = np.arange(len(s))
    par = int(np.argmax([s[i % 2 == r].mean() if (i % 2 == r).any() else -np.inf for r in range(2)]))
    off = int(np.argmax([s[i % 4 == r].mean() if (i % 4 == r).any() else -np.inf for r in range(4)]))
    return par, off


def phases(t, beats, level, par=0, off=0):
    """event times -> phase in [0, 1) at `level`; events outside [beats[0], beats[-1]) are dropped"""
    b = np.asarray(beats, float)
    t = np.asarray(t, float)
    t = t[(t >= b[0]) & (t < b[-1])]
    i = np.searchsorted(b, t, side="right") - 1
    f = (t - b[i]) / (b[i + 1] - b[i])
    if level == "beat":
        return f
    if level == "half_beat":
        return (2 * f) % 1.0
    if level == "half_time":
        return (((i - par) % 2) + f) / 2
    if level == "bar":
        return (((i - off) % 4) + f) / 4
    raise ValueError(level)


def resultant(phi):
    """-> (R, preferred phase as fraction of the period, complex mean)"""
    z = np.exp(2j * np.pi * np.asarray(phi)).mean()
    return float(abs(z)), float((np.angle(z) / (2 * np.pi)) % 1.0), complex(z)


def hit_rate(t, beats, lag, w=HIT_W):
    """share of events within +-w of a beat time shifted by `lag` (s)"""
    b = np.asarray(beats, float) + lag
    t = np.asarray(t, float)
    if len(t) == 0 or len(b) == 0:
        return np.nan
    i = np.searchsorted(b, t)
    d = np.minimum(np.abs(t - b[np.clip(i, 0, len(b) - 1)]), np.abs(t - b[np.clip(i - 1, 0, len(b) - 1)]))
    return float((d <= w).mean())


def signed_offset(t, beats):
    """event - nearest beat (s), array"""
    b, t = np.asarray(beats, float), np.asarray(t, float)
    i = np.clip(np.searchsorted(b, t), 1, len(b) - 1)
    d0, d1 = t - b[i - 1], t - b[i]
    return np.where(np.abs(d0) <= np.abs(d1), d0, d1)


def shuffle_ibi(beats, rng):
    """permute the inter-beat intervals, keep the first beat -> same length, same multiset of intervals"""
    b = np.asarray(beats, float)
    return b[0] + np.concatenate([[0.0], np.cumsum(rng.permutation(np.diff(b)))])


def donor_grid(donor, first, span_end):
    """tile the donor's intervals so the grid starts at `first` and covers up to span_end"""
    d = np.diff(np.asarray(donor, float))
    n = int(np.ceil((span_end - first) / d.sum())) + 1
    return first + np.concatenate([[0.0], np.cumsum(np.tile(d, n))])


def median_ibi(beats):
    return float(np.median(np.diff(beats)))


def circ_shift(idx, n, rng, min_shift=10):
    """boundary indices shifted circularly over n tokens by a random shift in [min_shift, n - min_shift]"""
    return np.sort((np.asarray(idx, int) + int(rng.integers(min_shift, max(n - min_shift, min_shift + 1)))) % n)


def hit_scan(t, beats, lags=LAGS, w=HIT_W):
    """H(L) for every lag at once: offsets of each event to its previous and next beat; exact while |lag| + w < one inter-beat interval"""
    b, t = np.asarray(beats, float), np.asarray(t, float)
    t = t[(t >= b[0]) & (t < b[-1])]
    if len(t) == 0:
        return np.full(len(lags), np.nan)
    i = np.searchsorted(b, t, side="right") - 1
    d = np.stack([t - b[i], t - b[i + 1]], 1)
    return (np.abs(d[:, :, None] - np.asarray(lags)[None, None]) <= w).any(1).mean(0)


def half_grid(beats):
    b = np.asarray(beats, float)
    return np.sort(np.concatenate([b, (b[1:] + b[:-1]) / 2]))
