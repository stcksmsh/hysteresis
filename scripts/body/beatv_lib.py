"""WO47 pure functions (docs/BEATV_RULES.md): raw FineDance motion measures, BAS, per-file sync scan, local phase locking. numpy + scipy only."""
import numpy as np
from scipy.ndimage import gaussian_filter1d
from scipy.signal import argrelextrema

PARENT = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]       # SMPL-X body joints 0-21
OFFSET = np.array([[0, 0, 0], [.09, -.05, 0], [-.09, -.05, 0], [0, .11, 0], [0, -.40, 0], [0, -.40, 0], [0, .13, 0], [0, -.40, 0], [0, -.40, 0], [0, .05, 0], [0, -.05, .10], [0, -.05, .10],
                   [0, .12, 0], [.08, .04, 0], [-.08, .04, 0], [0, .10, 0], [.10, 0, 0], [-.10, 0, 0], [.28, 0, 0], [-.28, 0, 0], [.26, 0, 0], [-.26, 0, 0]], float)   # approximate generic T-pose (rules section 1)
BAS_SIGMA_S = 0.1


def rot6(x):
    """(..., 6) -> (..., 3, 3) rotation, rows = the two 6D vectors and their cross product (Gram-Schmidt)"""
    a, b = x[..., 0:3], x[..., 3:6]
    a = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b - (a * b).sum(-1, keepdims=True) * a
    b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    return np.stack([a, b, np.cross(a, b)], -2)


def local_rots(m):
    """raw FineDance motion (T, 315) -> (T, 22, 3, 3) local rotations of the body joints"""
    return rot6(m[:, 3:].reshape(len(m), -1, 6)[:, :22])


def angle_speed(R, fps):
    """(T, J, 3, 3) -> (T, J) rotation angle between consecutive frames x fps (rad/s), last frame repeated"""
    dR = np.einsum("tjab,tjcb->tjac", R[:-1], R[1:])
    ang = np.arccos(np.clip((np.trace(dR, axis1=2, axis2=3) - 1) / 2, -1, 1)) * fps
    return np.vstack([ang, ang[-1:]])


def fk(R, root):
    """local rotations (T, 22, 3, 3), root position (T, 3) -> world positions (T, 22, 3) with the generic skeleton"""
    T = len(R)
    G = np.zeros((T, 22, 3, 3))
    P = np.zeros((T, 22, 3))
    for j in range(22):
        p = PARENT[j]
        if p < 0:
            G[:, j] = R[:, j]
            P[:, j] = root
        else:
            G[:, j] = G[:, p] @ R[:, j]
            P[:, j] = P[:, p] + np.einsum("tab,b->ta", G[:, p], OFFSET[j])
    return P


def kin_beats(speed, fs, sigma_frames30=5.0):
    """local minima (times, s) of the Gaussian-smoothed speed (sigma 5 frames at 30 fps, scaled to fs): Bailando get_mb"""
    v = gaussian_filter1d(np.asarray(speed, float), sigma_frames30 / 30.0 * fs)
    return argrelextrema(v, np.less)[0] / fs


def bas(music, kin, duration=None, sigma=BAS_SIGMA_S, mode="music"):
    """beat align score; mode 'music' = mean over music beats of exp(-min dist^2 / 2 sigma^2) (released-code reading), 'kin' = mean over kinematic beats (paper text)"""
    music, kin = np.asarray(music, float), np.asarray(kin, float)
    if duration is not None:
        music = music[music < duration]
    if len(music) == 0 or len(kin) == 0:
        return np.nan
    a, b = (music, kin) if mode == "music" else (kin, music)
    d = np.abs(a[:, None] - b[None]).min(1)
    return float(np.exp(-d ** 2 / (2 * sigma ** 2)).mean())


def bas_chance(music, kin, duration, rng, n=20, sigma=BAS_SIGMA_S, mode="music"):
    """same BAS with the music beats shifted by a uniform offset in [0.25, 1] x the median beat interval (wrapping inside the duration)"""
    ibi = float(np.median(np.diff(music)))
    out = []
    for _ in range(n):
        sh = (np.asarray(music) + rng.uniform(0.25, 1.0) * ibi) % duration
        out.append(bas(np.sort(sh), kin, duration, sigma, mode))
    return float(np.mean(out))


def xcorr_circ(a, e, kmax):
    """circular normalised cross-correlation c(k) = corr(a[t], e[(t + k) mod n]), k = -kmax..kmax, and the full circular function C (index = lag mod n)"""
    n = min(len(a), len(e))
    a, e = np.asarray(a[:n], float), np.asarray(e[:n], float)
    a, e = a - a.mean(), e - e.mean()
    den = np.sqrt((a ** 2).sum() * (e ** 2).sum()) + 1e-12
    C = np.fft.irfft(np.conj(np.fft.rfft(a)) * np.fft.rfft(e), n) / den                  # C[L] = sum_t a[t] e[t + L]
    ks = np.arange(-kmax, kmax + 1)
    return ks, C[ks % n], C


def sync_scan(a, e, kmax, rng, n_null=200, min_shift_frames=150):
    """best offset (frames), strength, and the strength under circular shifts of e: (best_k, cmax, z, null_max_95, c(k))"""
    ks, c, C = xcorr_circ(a, e, kmax)
    n = len(C)
    nm = []
    for _ in range(n_null):
        s = int(rng.integers(min_shift_frames, max(n - min_shift_frames, min_shift_frames + 1)))
        nm.append(C[(s + ks) % n].max())
    nm = np.array(nm)
    k = int(ks[np.argmax(c)])
    return k, float(c.max()), float((c.max() - nm.mean()) / (nm.std() + 1e-12)), float(np.percentile(nm, 95)), c


def local_windows(events, beats, rng, win=8, hop=2, min_events=6, n_perm=20):
    """sliding windows of `win` beats: least-squares line through the beat times, event phase against it; real R, R with period x1.13 and x0.87, R with the window's beat intervals permuted (refit)
    -> list of dicts (R, R113, R087, Rperm, n, resid_s, vec)"""
    ev = np.asarray(events, float)
    b = np.asarray(beats, float)
    k = np.arange(win)
    out = []

    def Rof(t, t0, T):
        ph = ((t - t0) / T) % 1.0
        z = np.exp(2j * np.pi * ph).mean()
        return float(abs(z)), z

    for i in range(0, len(b) - win + 1, hop):
        bb = b[i:i + win]
        t = ev[(ev >= bb[0]) & (ev < bb[-1])]
        if len(t) < min_events:
            continue
        T, t0 = np.polyfit(k, bb, 1)
        R, z = Rof(t, t0, T)
        r113, _ = Rof(t, t0, 1.13 * T)
        r087, _ = Rof(t, t0, 0.87 * T)
        rp = []
        for _ in range(n_perm):
            pb = bb[0] + np.concatenate([[0.0], np.cumsum(rng.permutation(np.diff(bb)))])
            Tp, tp0 = np.polyfit(k, pb, 1)
            rp.append(Rof(t, tp0, Tp)[0])
        out.append(dict(R=R, R113=r113, R087=r087, Rperm=float(np.mean(rp)), n=len(t), resid=float(np.sqrt(((bb - (t0 + T * k)) ** 2).mean())), vec=z))
    return out
