"""Body-study motion descriptors in Python (port of crates/hyst-compile/src/body.rs `descriptors`, docs/BODY_STUDY.md), wrist roll excluded.

31 numbers per window of joint positions (T, 5) deg at 60 fps, joint order base_yaw, shoulder, elbow, wrist_bend, wrist_roll:
  per non-roll joint (4): speed, acceleration, jerk, each mean and 90th percentile (24);  posture: mean hand height, mean extension (shoulder-to-hand over
  the straight reach 0.69 m), mean curl (|elbow| + |wrist bend|) (3);  lag of best cross-correlation of joint speed base>shoulder, shoulder>elbow,
  elbow>wrist bend (3);  periodicity: highest autocorrelation of hand speed over lags 0.3 s .. `max_lag_s` (1).
Rust's 37 minus the roll's 6 (the roll moves no chain point, so the hand height, extension and periodicity are unchanged by it).
Window handling: the sliding window is 2 s = 121 frames. Rust's periodicity lags (0.3-3 s) do not fit in 2 s (its loop would underflow), so on the 2 s window
`max_lag_s = 1.0` (half the window, every lag then overlaps itself by at least 1 s); the parity test uses 3.0 on the 8 s clips, which is Rust's own range.
Every other descriptor is defined on 2 s as is (the lag search is +-0.5 s = +-30 frames of 120 speed samples).
Provisional servo model elsewhere (Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25).
"""
import math

import numpy as np

from make_arm import AXES, LINKS

FPS = 60.0
REACH_M = 0.69
N_DESC = 31
SHOULDER_Z = LINKS[0][2]                    # point 1: after joint 0's link (0, 0, 0.08), independent of every angle


def _rot(axis, deg):
    """(T,) degrees about a fixed axis -> (T, 3, 3) Rodrigues matrices."""
    a = np.asarray(axis, float)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    th = np.radians(deg)[:, None, None]
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * (K @ K)


def hand_points(q):
    """q (T, 5) deg -> hand point (T, 3) as ensemble.rs forward_kinematics (origin 0, yaw 0): the frame turns about axis_local, then advances by link_m."""
    T = len(q)
    B = np.broadcast_to(np.eye(3), (T, 3, 3)).copy()
    p = np.zeros((T, 3))
    for j in range(5):
        B = B @ _rot(AXES[j], q[:, j])
        p = p + B @ np.asarray(LINKS[j], float)
    return p


def _p90(v):
    s = np.sort(v)
    return float(s[int(math.floor((len(s) - 1) * 0.9 + 0.5))])        # Rust round(): half away from zero


def best_lag(a, b):
    """Seconds in -0.5..0.5 of the best normalised cross-correlation (positive: b follows a); ties go to the last lag, as Rust's max_by."""
    def norm(v):
        sd = v.std()
        return (v - v.mean()) / sd if sd > 1e-12 else np.zeros_like(v)
    a, b = norm(a), norm(b)
    max_lag = int(0.5 * FPS)
    best, best_c = None, -np.inf
    for l in range(-max_lag, max_lag + 1):
        i0, i1 = max(0, -l), min(len(a), len(b) - l)
        c = float(a[i0:i1] @ b[i0 + l:i1 + l]) / (i1 - i0)
        if c >= best_c:
            best, best_c = l, c
    return best / FPS


def descriptors(q, max_lag_s=1.0):
    q = np.asarray(q, float)
    out, speeds = [], []
    for j in range(4):
        s = q[:, j]
        d1 = np.abs(np.diff(s)) * FPS
        d2 = np.abs(s[2:] - 2 * s[1:-1] + s[:-2]) * FPS ** 2
        d3 = np.abs(s[3:] - 3 * s[2:-1] + 3 * s[1:-2] - s[:-3]) * FPS ** 3
        for d in (d1, d2, d3):
            out += [float(d.mean()), _p90(d)]
        speeds.append(d1)
    h = hand_points(q)
    out.append(float(h[:, 2].mean()))
    out.append(float(np.mean(np.sqrt(h[:, 0] ** 2 + h[:, 1] ** 2 + (h[:, 2] - SHOULDER_Z) ** 2)) / REACH_M))
    out.append(float(np.mean(np.abs(q[:, 2]) + np.abs(q[:, 3]))))
    out += [best_lag(speeds[a], speeds[b]) for a, b in ((0, 1), (1, 2), (2, 3))]
    hs = np.sqrt((np.diff(h, axis=0) ** 2).sum(1)) * FPS
    m = hs.mean()
    var = float(((hs - m) ** 2).sum())
    per = -np.inf
    for l in range(int(0.3 * FPS), int(max_lag_s * FPS) + 1):
        per = max(per, 0.0 if var < 1e-12 else float(((hs[:len(hs) - l] - m) * (hs[l:] - m)).sum() / var))
    out.append(per)
    return np.array(out)


# subset of Rust's 37 that this port reproduces: joints 0..3 (blocks of 6), posture 3, lags 3, periodicity 1
RUST_INDEX = list(range(24)) + list(range(30, 37))


def window_frames(pos100):
    """(..., 201, 5) positions at 100 Hz covering 2.00 s -> (..., 121, 5) at 60 fps by linear interpolation."""
    t = np.arange(121) / FPS * 100.0
    i0 = np.minimum(t.astype(int), 199)
    w = (t - i0)[:, None]
    return pos100[..., i0, :] * (1 - w) + pos100[..., i0 + 1, :] * w
