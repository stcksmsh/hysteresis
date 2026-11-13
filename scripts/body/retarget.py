"""WO32B retarget look test: FineDance joint rotations -> human angles (V1 arm-as-arm, V2 arm-as-whole-body) -> robot commands. Rules: docs/RETARGET_RULES.md.

Body env (/secondary/hyst-env/body). numpy + scipy only; no SMPL model file, no torch. Disposable; no learning.
"""
import json
import pathlib

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation as Rot

ROOT = pathlib.Path("/secondary/hyst-data/datasets/finedance/data/finedance")
FPS = 30
REF_S = 5.0                                                              # earliest window start (s)
WIN_S, STRIDE_S = 20.0, 5.0                                            # scale pooling: every 20 s window, starts every 5 s from REF_S
CENTRE = np.array([0.0, -60.0, 30.0, -15.0, 0.0])                       # round 1's calibration centre (MOTORNET_PARAMS)
TARGET_HALF = np.array([180.0, 40.0, 64.0, 76.0, 150.0])                # rules (c): base, 0.8x50, 0.8x80, 0.8x95, roll
SCALE_FILE = pathlib.Path(__file__).resolve().parents[2] / "docs" / "RETARGET_SCALE.json"
JOINTS = (0, 3, 6, 9, 12, 14, 15, 17, 19, 21)
PARENT = {3: 0, 6: 3, 9: 6, 12: 9, 14: 9, 15: 12, 17: 14, 19: 17, 21: 19}
XM, YP, ZP = np.array([-1.0, 0, 0]), np.array([0, 1.0, 0]), np.array([0, 0, 1.0])


def six_to_matrix(d6):
    """pytorch3d rotation_6d_to_matrix: the 6D holds the first two ROWS; b1, b2, b3 are the rows of R. d6 (..., 6) -> (..., 3, 3)"""
    a1, a2 = d6[..., :3], d6[..., 3:]
    b1 = a1 / np.linalg.norm(a1, axis=-1, keepdims=True)
    b2 = a2 - (b1 * a2).sum(-1, keepdims=True) * b1
    b2 = b2 / np.linalg.norm(b2, axis=-1, keepdims=True)
    return np.stack((b1, b2, np.cross(b1, b2)), axis=-2)


def load_rotations(path):
    """motion npy (T, 315) -> dict joint -> local rotation matrices (T, 3, 3)"""
    a = np.load(path).astype(np.float64)
    r6 = a[:, 3:].reshape(len(a), 52, 6)
    return {j: six_to_matrix(r6[:, j]) for j in JOINTS}


def _unwrap_deg(x):
    return np.degrees(np.unwrap(np.radians(x)))


def _yaw(G):
    F = G @ ZP
    return _unwrap_deg(np.degrees(np.arctan2(F[:, 0], F[:, 2])))


def _twist(Rm):
    """twist angle (deg) of a local rotation about its bone axis x; unwrapped over time"""
    q = Rot.from_matrix(Rm).as_quat()                                    # x, y, z, w
    return _unwrap_deg(np.degrees(2 * np.arctan2(q[:, 0], q[:, 3])))


def _swing_z(Rm):
    """z component (deg) of the rotation vector of the swing part of a local rotation (twist about x removed): wrist flexion"""
    q = Rot.from_matrix(Rm).as_quat()
    qt = np.stack([q[:, 0], 0 * q[:, 0], 0 * q[:, 0], q[:, 3]], 1)
    qt /= np.maximum(np.linalg.norm(qt, axis=1, keepdims=True), 1e-12)
    sw = (Rot.from_quat(q) * Rot.from_quat(qt).inv()).as_rotvec()
    return np.degrees(sw[:, 2])


def _ry(deg):
    c, s = np.cos(np.radians(deg)), np.sin(np.radians(deg))
    M = np.zeros((len(deg), 3, 3))
    M[:, 0, 0], M[:, 0, 2], M[:, 1, 1], M[:, 2, 0], M[:, 2, 2] = c, s, 1.0, -s, c
    return M


def human_angles(rot):
    """local rotations -> (V1, V2), each (T, 5) human angles in deg (base, shoulder, elbow, wrist bend, wrist roll), per rules (b), un-referenced (yaw/twist unwrapped)"""
    G = {0: rot[0]}
    for j in (3, 6, 9, 12, 14, 15, 17, 19, 21):
        G[j] = G[PARENT[j]] @ rot[j]
    tT = np.swapaxes(G[9], 1, 2)
    u, f = [np.einsum("tij,tj->ti", tT, G[j] @ XM) for j in (17, 19)]
    e = np.degrees(np.arcsin(np.clip(u[:, 1], -1, 1)))
    flex = np.degrees(np.arccos(np.clip((u * f).sum(1), -1, 1)))
    v1 = np.stack([_yaw(G[9]), e, flex, _swing_z(rot[21]), _twist(rot[19]) + _twist(rot[21])], 1)
    yaw0 = _yaw(G[0])
    up = np.einsum("tij,tj->ti", _ry(-yaw0), G[9] @ YP)
    hu = np.einsum("tij,tj->ti", np.swapaxes(G[12], 1, 2), G[15] @ YP)
    v2 = np.stack([yaw0, np.degrees(np.arctan2(up[:, 2], up[:, 1])), np.degrees(np.arctan2(up[:, 0], up[:, 1])),
                   np.degrees(np.arctan2(hu[:, 2], hu[:, 1])), _unwrap_deg(np.degrees(np.arctan2(hu[:, 0], hu[:, 1])))], 1)
    return v1, v2


def referenced(v, i):
    """yaw (col 0) and twist (col 4) relative to frame i (the window start, rules (h)); the other columns absolute"""
    v = v.copy()
    for c in (0, 4):
        v[:, c] -= v[i, c]
    return v


def sequence_angles(path):
    """un-referenced human angles (V1, V2) of a whole sequence; call referenced(v, window_start_frame) per window"""
    return human_angles(load_rotations(path))


def to_commands(v, variant, scale=None):
    """human angles (T, 5) at 30 fps -> robot command rows (T, 5) deg. Shoulder = centre - s (x - mid) (rising x raises the link); others centre + s (x - mid)"""
    sc = scale or json.loads(SCALE_FILE.read_text())
    mid, s = np.array(sc[variant]["mid"]), np.array(sc[variant]["s"])
    d = s * (v - mid)
    d[:, 1] = -d[:, 1]
    return CENTRE + d


def to_100hz(y, t0_s, dur_s):
    """30 fps command rows -> cubic interpolation to 100 Hz over [t0_s, t0_s + dur_s] (inclusive of both ends)"""
    t = np.arange(len(y)) / FPS
    tt = t0_s + np.arange(round(dur_s * 100) + 1) / 100.0
    return CubicSpline(t, y, axis=0)(tt)
