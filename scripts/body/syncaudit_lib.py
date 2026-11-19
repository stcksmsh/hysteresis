"""WO54 A1 measuring and synthetic-input helpers (docs/SYNCAUDIT_RULES_A.md). Pure numpy/scipy; no pipeline import. Offset sign: positive = movement LATER than its music."""
import numpy as np
from scipy.spatial.transform import Rotation as Rot

SR = 44100
BUMP_S, BUMP_DEG = 0.30, 70.0
REG_CLICKS = [3.0 + 0.5 * i for i in range(0, 53)]          # every 0.5 s from 3.0
IRREG = [7.23, 11.61, 14.07, 19.37, 23.91, 27.45, 33.13, 41.77, 46.29]
FAMILY_JOINTS = {"arm": ((17, (0, 0, 1)), (19, (0, 0, 1)), (21, (0, 0, 1))), "torso": ((9, (0, 1, 0)), (12, (0, 1, 0))), "pelvis": ((0, (0, 1, 0)),),
                 "feet": ((7, (1, 0, 0)), (8, (1, 0, 0)), (10, (1, 0, 0)), (11, (1, 0, 0)))}


def click_times(dur_s):
    """fixed list: 3.0 s and every 0.5 s up to dur - 2 s, the irregular ones, sorted, the irregular ones kept clear (>= 0.15 s) of the regular grid"""
    reg = [t for t in REG_CLICKS if t <= dur_s - 2.0]
    irr = [t for t in IRREG if t <= dur_s - 2.0 and min(abs(t - r) for r in reg) >= 0.15]
    return sorted(reg + irr)


def click_audio(times, dur_s, sr=SR):
    """mono float32: a 5 ms Hann-windowed 1 kHz burst, peak 0.8, centred exactly on each click time"""
    a = np.zeros(int(round(dur_s * sr)), np.float32)
    n = int(round(0.005 * sr)) | 1
    w = np.hanning(n + 2)[1:-1] * np.sin(2 * np.pi * 1000 * (np.arange(n) - n // 2) / sr)
    w = (0.8 * w / np.abs(w).max()).astype(np.float32)
    for t in times:
        c = int(round(t * sr)); a[c - n // 2:c - n // 2 + n] += w
    return a


def bump(t, tc, width=BUMP_S):
    x = (t - tc) / width
    return np.where(np.abs(x) < 0.5, 0.5 * (1 + np.cos(2 * np.pi * x)), 0.0)


def six_d(R):
    """(..., 3, 3) rotation -> (..., 6): the first two ROWS (retarget.six_to_matrix reads them as rows b1, b2)"""
    return np.concatenate([R[..., 0, :], R[..., 1, :]], -1)


def synth_motion(times, fam_of, dur_s, fps=30):
    """(T, 315) float32 FineDance-format motion: zeros translation, identity rotations, one bump per click on the family's joints. fam_of: click index -> family"""
    T = int(round(dur_s * fps))
    t = np.arange(T) / fps
    r6 = np.tile(six_d(np.eye(3)), (T, 52, 1))
    for i, tc in enumerate(times):
        b = bump(t, tc)
        if not b.any():
            continue
        for j, ax in FAMILY_JOINTS[fam_of(i)]:
            R = Rot.from_rotvec(np.radians(BUMP_DEG) * b[:, None] * np.array(ax, float)).as_matrix()
            r6[:, j] = six_d(R @ _rows(r6[:, j]))
    out = np.zeros((T, 315), np.float32)
    out[:, 3:] = r6.reshape(T, 312)
    return out


def _rows(d6):
    a1, a2 = d6[..., :3], d6[..., 3:]
    return np.stack([a1, a2, np.cross(a1, a2)], -2)


# ------------------------------------------------------------------ measuring
def centroid_time(t, x, tc, half=0.75, floor=0.10):
    """centroid time (s) of |x - median| inside [tc - half, tc + half]; weights below floor x the window peak zeroed. None when flat"""
    m = (t >= tc - half) & (t <= tc + half)
    if m.sum() < 3:
        return None
    y = np.abs(x[m] - np.median(x))
    if y.max() <= 1e-9:
        return None
    y = np.where(y >= floor * y.max(), y, 0.0)
    return float((t[m] * y).sum() / y.sum())


def peak_time(t, x, tc, half=0.75):
    """parabolic peak time of |x - median| inside the window"""
    m = np.flatnonzero((t >= tc - half) & (t <= tc + half))
    if len(m) < 3:
        return None
    y = np.abs(x - np.median(x))
    k = m[np.argmax(y[m])]
    if k == 0 or k == len(x) - 1:
        return float(t[k])
    a, b, c = y[k - 1], y[k], y[k + 1]
    d = a - 2 * b + c
    return float(t[k] + (0.5 * (a - c) / d if d != 0 else 0.0) * (t[1] - t[0]))


def offsets_ms(t, x, clicks, half=0.75):
    """-> (centroid offsets ms, peak offsets ms) per click (nan where flat); offset = movement time - click time"""
    c = [centroid_time(t, x, tc, half) for tc in clicks]
    p = [peak_time(t, x, tc, half) for tc in clicks]
    f = lambda v, tc: np.nan if v is None else 1000 * (v - tc)
    return np.array([f(a, tc) for a, tc in zip(c, clicks)]), np.array([f(a, tc) for a, tc in zip(p, clicks)])


def summarise(off):
    o = off[~np.isnan(off)]
    if not len(o):
        return dict(n=0)
    return dict(n=int(len(o)), mean=float(o.mean()), sd=float(o.std()), min=float(o.min()), max=float(o.max()))


def audio_click_offsets_ms(a, expected_s, sr=SR, half=0.02):
    """click centroid of |a| around each expected time (the audio click is 5 ms): offset ms = measured - expected"""
    t = np.arange(len(a)) / sr
    out = []
    for e in expected_s:
        m = (t >= e - half) & (t <= e + half)
        if not m.any() or e < 0 or e * sr >= len(a):
            out.append(np.nan); continue
        w = np.abs(a[m]).astype(float)
        out.append(np.nan if w.max() < 0.05 else 1000 * (float((t[m] * w).sum() / w.sum()) - e))
    return np.array(out)


def xcorr_lag_s(x, y, dt, maxlag_s=0.5):
    """lag (s) of y relative to x (positive = y later), parabolic sub-sample, over normalised cross-correlation of the mean-removed signals"""
    x = x - x.mean(); y = y - y.mean()
    n = min(len(x), len(y)); x, y = x[:n], y[:n]
    L = int(round(maxlag_s / dt))
    best, cs = None, {}
    for k in range(-L, L + 1):
        a = x[max(0, -k):n - max(0, k)]; b = y[max(0, k):n - max(0, -k)]
        d = np.linalg.norm(a) * np.linalg.norm(b)
        cs[k] = float(a @ b / d) if d else 0.0
    k0 = max(cs, key=cs.get)
    if -L < k0 < L:
        a, b, c = cs[k0 - 1], cs[k0], cs[k0 + 1]
        d = a - 2 * b + c
        return (k0 + (0.5 * (a - c) / d if d else 0.0)) * dt, cs[k0]
    return k0 * dt, cs[k0]
