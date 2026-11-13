"""WO35 V3 targets: the human end point (and its orientation) relative to its origin in the dancer's heading frame, mapped to the robot's workspace; the scale step. Rules: RETARGET_RULES.md (m).

V3a: end point = right wrist (joint 21), origin = right shoulder (17), orientation = G21;   V3b: end point = head (15), origin = pelvis (0), orientation = G15.
Heading frame: the world rotated about the vertical by minus the pelvis yaw (yaw = atan2(F_x, F_z), F = G0 (0,0,1)), so the human's own forward axis is +z; then human axes (x left, y up, z forward)
map to the robot's (X forward, Y left, Z up) by A: robot = (z, x, y).
Lamp target = c0 + s * A (rel - r_med); tool rotation target = A Ry(-yaw) G_end M, with M the fixed tool-axis matrices below.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.spatial.transform import Rotation as Rot, RotationSpline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import v3_ik as K  # noqa: E402
import v3_lib as L  # noqa: E402

VAR = {"V3a": dict(end=21, origin=17), "V3b": dict(end=15, origin=0)}
A_MAP = np.array([[0, 0, 1], [1, 0, 0], [0, 1, 0]], float)                   # robot = A @ human (x left, y up, z forward) -> (X forward, Y left, Z up)
# tool frame (columns: tool x = stem / distal, tool y = bend axis, tool z) expressed in the end joint's local axes
M_TOOL = {"V3a": np.array([[-1, 0, 0], [0, 0, 1], [0, 1, 0]], float),        # wrist: tool x = distal (-x_local), tool y = flexion axis (z_local), tool z = y_local
          "V3b": np.array([[0, 1, 0], [0, 0, 1], [1, 0, 0]], float)}         # head: tool x = face direction (z_local), tool y = x_local (nod axis), tool z = y_local (up)
SCALE = Path(__file__).resolve().parents[2] / "docs" / "RETARGET_SCALE.json"
WIN_S, STRIDE_S, REF_S = 20.0, 5.0, 5.0
FD = L.FD


def c0():
    return K.fk_batch(K.CENTRE_POSE[None])[0][0, 5]


def heading_rel(P, G, var):
    """P (n, 22, 3), G (n, 22, 3, 3) -> rel (n, 3) in the heading frame (human axes) and the heading-frame end-joint rotation (n, 3, 3)"""
    v = VAR[var]
    F = G[:, 0] @ np.array([0.0, 0.0, 1.0])
    yaw = np.degrees(np.arctan2(F[:, 0], F[:, 2]))
    Rinv = J._ry(-yaw)
    rel = np.einsum("nij,nj->ni", Rinv, P[:, v["end"]] - P[:, v["origin"]])
    return rel, Rinv @ G[:, v["end"]]


def compute_scale():
    """pooled over the 4,603 eligible windows of RETARGET_SCALE.json (every 20 s window, starts every 5 s from 5 s, all frames): per variant the median r_med of rel, the p98 of |rel - r_med| (the reach used)
    and, for the record, the literal p98 of |rel| from the origin; scale s = 0.8 * arm reach / reach"""
    pool = {v: [] for v in VAR}
    nwin = 0
    for p in sorted((FD / "motion").glob("*.npy")):
        P, G = L.fk(p.stem)
        n = round(WIN_S * 30)
        starts = list(range(round(REF_S * 30), len(P) - n + 1, round(STRIDE_S * 30)))
        for var in VAR:
            rel, _ = heading_rel(P, G, var)
            for i in starts:
                pool[var].append(rel[i:i + n + 1])
        nwin += len(starts)
    out = {}
    for var in VAR:
        X = np.concatenate(pool[var])
        med = np.median(X, axis=0)
        h98 = float(np.percentile(np.linalg.norm(X - med, axis=1), 98))
        lit = float(np.percentile(np.linalg.norm(X, axis=1), 98))
        out[var] = dict(r_med_human_heading_frame=med.tolist(), reach_p98_from_median_m=h98, reach_p98_from_origin_literal_m=lit, arm_reach_m=K.REACH_M, share=0.8,
                        scale=0.8 * K.REACH_M / h98, scale_if_literal_origin_reach=0.8 * K.REACH_M / lit, frames=int(len(X)), windows=nwin)
    return out


def load_scale():
    return json.loads(SCALE.read_text())


def build_targets(seq, var, start_s, pre_s=1.5, show_s=20.0, scale=None):
    """-> 100 Hz lamp target positions (n, 3) and tool rotation targets (n, 3, 3) in the robot frame for times start - pre_s ... start + show_s (n = (pre_s + show_s) * 100 + 1), cubic spline in time
    (positions) and quaternion cubic spline (rotations) through the dataset's 30 fps frames"""
    sc = (scale or load_scale())[var]
    k0, k1 = int(np.floor((start_s - pre_s) * 30)) - 3, int(np.ceil((start_s + show_s) * 30)) + 3
    P, G = L.fk(seq, k0, k1)
    rel, Rh = heading_rel(P, G, var)
    t = np.arange(k0, k0 + len(P)) / 30.0
    pt = c0() + sc["scale"] * (A_MAP @ (rel - np.array(sc["r_med_human_heading_frame"])).T).T
    Rt = A_MAP @ Rh @ M_TOOL[var]
    tt = start_s - pre_s + np.arange(round((pre_s + show_s) * 100) + 1) / 100.0
    pos = CubicSpline(t, pt, axis=0)(tt)
    rot = RotationSpline(t, Rot.from_matrix(Rt))(tt).as_matrix()
    return pos, rot, dict(t30=t, p30=pt)


if __name__ == "__main__":
    res = compute_scale()
    sc = json.loads(SCALE.read_text())
    sc.update({k: v for k, v in res.items()})
    SCALE.write_text(json.dumps(sc, indent=1))
    print(json.dumps(res, indent=1))
