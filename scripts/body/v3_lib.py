"""WO35 shared helpers: human forward kinematics from the FineDance local rotations (canonical T-pose offsets of the WO34 viewing figure, no SMPL model file) and jitter measures of 3D
position signals. Report-only work; nothing here changes V1/V2 or round 1.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_viewing as JV  # noqa: E402  (PARENT, OFF: the viewing video's canonical T-pose skeleton)
import retarget as RT  # noqa: E402

PARENT, OFF = JV.PARENT, JV.OFF
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
FPS = 30
EPS_POS = 0.01                  # m/s^2: accelerations below this count as zero (1 deg/s^2 at a 0.57 m radius is 0.01 m/s^2; same role as jitter_diag.EPS_ACC)
PELVIS_H = 0.95                 # standing pelvis height of the canonical skeleton (legs 0.95 m); root translation y is added


def fk(seq, k0=None, k1=None):
    """FineDance sequence -> (P (n, 22, 3) world positions in metres (human axes: x left, y up, z forward; root translation included), G (n, 22, 3, 3) global rotations) for frames k0..k1"""
    a = np.load(FD / "motion" / f"{seq}.npy").astype(np.float64)
    k0 = 0 if k0 is None else max(0, k0)
    k1 = len(a) - 1 if k1 is None else min(len(a) - 1, k1)
    R = RT.six_to_matrix(a[k0:k1 + 1, 3:].reshape(-1, 52, 6)[:, :22])
    n = len(R)
    G = np.zeros((n, 22, 3, 3))
    P = np.zeros((n, 22, 3))
    for j in range(22):
        p = PARENT[j]
        if p < 0:
            G[:, j] = R[:, j]
            P[:, j] = a[k0:k1 + 1, :3] + np.array([0.0, PELVIS_H, 0.0])
        else:
            G[:, j] = G[:, p] @ R[:, j]
            P[:, j] = P[:, p] + np.einsum("tij,j->ti", G[:, p], OFF[j])
    return P, G


def pos_measures(X, fs, eps=EPS_POS):
    """X (n, 3) positions (m) at rate fs -> per axis acceleration sign changes per second, their mean over axes, and the share of speed-vector power above 3 and 6 Hz
    (Welch, Hann, 5 s segments, mean removed per axis, power summed over the three axes)"""
    X = np.asarray(X, float)
    flips = []
    for i in range(3):
        a = (X[2:, i] - 2 * X[1:-1, i] + X[:-2, i]) * fs * fs
        s = np.sign(a[np.abs(a) >= eps])
        flips.append(float((np.diff(s) != 0).sum()) / (len(X) / fs))
    V = np.diff(X, axis=0) * fs
    tot = np.zeros(1)
    hi3 = hi6 = 0.0
    totp = 0.0
    for i in range(3):
        f, P = welch(V[:, i] - V[:, i].mean(), fs, window="hann", nperseg=min(len(V), round(5 * fs)), detrend=False)
        totp += P[f > 0].sum()
        hi3 += P[f > 3].sum()
        hi6 += P[f > 6].sum()
    return dict(flips_per_s=dict(zip("xyz", flips)), flips_mean=float(np.mean(flips)), p_gt3=float(hi3 / totp) if totp > 0 else 0.0, p_gt6=float(hi6 / totp) if totp > 0 else 0.0)
