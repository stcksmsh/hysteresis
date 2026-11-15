"""WO41 T2 measure formulas (docs/T1B_RULES.md section 6). Pure numpy/scipy, no data access. Every function states its formula."""
import numpy as np


def ident_repeat_share(c1, c2):
    """share of tokens whose (code 1, code 2) pair already occurred earlier in the same dance (7.65.1)"""
    seen, n = set(), 0
    for p in zip(np.asarray(c1).tolist(), np.asarray(c2).tolist()):
        n += p in seen
        seen.add(p)
    return n / max(len(c1), 1)


def triples_per_min(c1, c2, v, p, minutes):
    """distinct (code 1, code 2, vigour bin, posture entries) per minute of dance"""
    p = np.asarray(p).reshape(len(c1), -1)
    return len({(a, b, c, tuple(d)) for a, b, c, d in zip(np.asarray(c1).tolist(), np.asarray(c2).tolist(), np.asarray(v).tolist(), p.tolist())}) / minutes


def approx_repeat(g):
    """g (n, 50, 5) decoded gesture chunks, scaled units: median over tokens (from the second) of the RMS distance to the nearest EARLIER chunk of the same dance"""
    f = g.reshape(len(g), -1)
    d = [np.sqrt(((f[:i] - f[i]) ** 2).mean(1)).min() for i in range(1, len(f))]
    return float(np.median(d))


def _cos(a):
    a = a - a.mean(0)
    a = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-9)
    return a @ a.T


def window_desc(x, w):
    """x (n, d) per-token features -> (n - w + 1, w * d): flattened windows of w consecutive tokens"""
    return np.stack([x[i:i + w].reshape(-1) for i in range(len(x) - w + 1)])


def selfsim_corr(music, move, w, min_lag=2):
    """correlation of the music and movement self-similarity matrices (cosine of mean-removed w-token window descriptors), upper triangle with start lag >= min_lag tokens (1 s)"""
    a, b = _cos(window_desc(music, w)), _cos(window_desc(move, w))
    i, j = np.triu_indices(len(a), k=min_lag)
    if len(i) < 3:
        return float("nan")
    return float(np.corrcoef(a[i, j], b[i, j])[0, 1])


def kinematic_beats(speed, hz, smooth_s=0.1):
    """indices of local minima of the box-smoothed speed"""
    k = max(1, round(smooth_s * hz))
    s = np.convolve(speed, np.ones(k) / k, "same")
    return np.flatnonzero((s[1:-1] < s[:-2]) & (s[1:-1] <= s[2:])) + 1


def beat_alignment(speed, hz, beats_s, sigma=0.1):
    """Bailando-style score: mean over kinematic beats (speed minima) of exp(-d^2 / (2 sigma^2)), d = time to the nearest music beat (s); 0 if no beats"""
    kb = kinematic_beats(speed, hz) / hz
    b = np.asarray(beats_s, float)
    if len(kb) == 0 or len(b) == 0:
        return 0.0
    d = np.abs(kb[:, None] - b[None]).min(1)
    return float(np.exp(-d ** 2 / (2 * sigma ** 2)).mean())


def hand_speed(h, hz):
    return np.linalg.norm(np.gradient(h, axis=0), axis=1) * hz


def frozen_longest_s(speed, hz, thr=0.05):
    """longest run (s) with hand speed below thr m/s"""
    run = best = 0
    for lo in speed < thr:
        run = run + 1 if lo else 0
        best = max(best, run)
    return best / hz


def endpoint_jerk_dirchanges(h, hz, vmin=0.05, lag_s=0.1):
    """hand points h (T, 3) m: (RMS jerk m/s^3, direction changes per s = onsets of runs where the velocity points against the velocity lag_s earlier, both faster than vmin)"""
    v = np.gradient(h, axis=0) * hz
    a = np.gradient(v, axis=0) * hz
    j = np.gradient(a, axis=0) * hz
    k = max(1, round(lag_s * hz))
    v0, v1 = v[:-k], v[k:]
    ok = (np.linalg.norm(v0, axis=1) > vmin) & (np.linalg.norm(v1, axis=1) > vmin)
    flips = ((v0 * v1).sum(1) < 0) & ok
    return float(np.sqrt((np.linalg.norm(j, axis=1) ** 2).mean())), float((flips[1:] & ~flips[:-1]).sum() / (len(h) / hz))


def range_p5_p95(q):
    """per joint p95 - p5 of the rows (T, 5)"""
    lo, hi = np.percentile(q, [5, 95], axis=0)
    return hi - lo


def sign_change_rate(x, fs, eps=1.0):
    """acceleration sign changes per second of a joint angle series (deg), accelerations below eps deg/s^2 ignored (as jitter_diag.measures)"""
    a = (x[2:] - 2 * x[1:-1] + x[:-2]) * fs * fs
    s = np.sign(a[np.abs(a) >= eps])
    return float((np.diff(s) != 0).sum() / (len(x) / fs))


def bootstrap_mean_ci(d, n=2000, seed=36202):
    """mean and 95 % bootstrap interval of the mean (resampled by song)"""
    d = np.asarray(d, float)
    rng = np.random.default_rng(seed)
    m = np.array([d[rng.integers(len(d), size=len(d))].mean() for _ in range(n)])
    return float(d.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def detect_events(ear, hz=100):
    """events from the standardised 44-feature lane (T, 44) at 100 Hz, causal-free offline detection (report only):
    onsets = col 40 local maxima within +-0.1 s above the song's 95th percentile; energy jumps = col 41 (RMS) 3 s trailing mean minus the previous 3 s mean > 6 dB-equivalent
    (the lane is standardised, so: > 1.0 sd); returns (onset frames, energy-jump frames)"""
    o = ear[:, 40]
    thr = np.percentile(o, 95)
    w = int(0.1 * hz)
    from scipy.ndimage import maximum_filter1d
    on = np.flatnonzero((o >= thr) & (o == maximum_filter1d(o, 2 * w + 1)))
    r = np.cumsum(np.r_[0, ear[:, 41]])
    n = 3 * hz
    i = np.arange(2 * n, len(ear))
    d = (r[i] - r[i - n]) / n - (r[i - n] - r[i - 2 * n]) / n
    up = i[1:][(d[1:] > 1.0) & (d[:-1] <= 1.0)] if len(d) > 1 else np.array([], int)
    return on, up


def slow_changes(h4, hz=100, win_s=1.0):
    """cortex slow-state changes: cosine distance between the layer-4 mean state over the last 1 s and the 1 s before, frames above its song-wise 95th percentile (local maxima)"""
    n = int(win_s * hz)
    c = np.cumsum(np.vstack([np.zeros((1, h4.shape[1])), h4]), 0)
    i = np.arange(2 * n, len(h4))
    a, b = (c[i] - c[i - n]) / n, (c[i - n] - c[i - 2 * n]) / n
    d = 1 - (a * b).sum(1) / (np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1) + 1e-9)
    thr = np.percentile(d, 95)
    pk = np.flatnonzero((d >= thr) & (d >= np.r_[d[0], d[:-1]]) & (d >= np.r_[d[1:], d[-1]]))
    return pk + 2 * n


def event_response(speed, hz, frames100, before_s=1.0, after_s=1.0):
    """mean over events of (mean hand speed in [0, after] minus [-before, 0]) around events given in 100 Hz frames; events too close to the edges skipped; nan if none"""
    out = []
    for f in frames100:
        t = int(round(f / 100 * hz))
        a, b = int(before_s * hz), int(after_s * hz)
        if t - a >= 0 and t + b <= len(speed):
            out.append(speed[t:t + b].mean() - speed[t - a:t].mean())
    return float(np.mean(out)) if out else float("nan")


def viterbi(unary, trans):
    """unary (n, M) costs, trans(i, a, b) -> (M, M)-free callable giving the cost matrix between candidates of token i and i+1 -> best index per token"""
    n, M = unary.shape
    cost = unary[0].copy()
    back = np.zeros((n, M), int)
    for i in range(1, n):
        t = trans(i - 1)                                    # (M, M): from candidate a at i-1 to b at i
        tot = cost[:, None] + t
        back[i] = tot.argmin(0)
        cost = tot.min(0) + unary[i]
    path = [int(cost.argmin())]
    for i in range(n - 1, 0, -1):
        path.append(int(back[i][path[-1]]))
    return path[::-1]
