"""WO35 V3 "space retarget": damped-least-squares inverse kinematics of the v2p arm onto an end-point path (rules: docs/RETARGET_RULES.md (m)).

Residual per frame (metres; orientation weighted so that position comes first):
  position   p(q) - p_target                                   (3)
  orientation  w_o * (x, y components of vee(R_cur^T R_target)) (2; the wrist's two axes: roll about the tool x, bend about the tool y)
  column     w_c * max(0, margin - distance) for p2, p3, p4 (0.05 m) and the hand p5 (0.11 m)   (4)
Each frame: up to N Gauss-Newton iterations from the previous frame's solution, each solving (J^T J + (lam^2 + mu) I) dq = -J^T f - mu (q - q_prev);
bend joints clamped to +-(110 - 0.5) deg after each iteration; then a column projection. Numbers are fixed in the rules note, never tuned.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_arm as MA  # noqa: E402
import make_arm_v2p as P  # noqa: E402

AXES = [np.array(a, float) for a in MA.AXES]
LINKS = [np.array(l, float) for l in MA.LINKS]
LIM_LO = np.array([-np.inf, -109.5, -109.5, -109.5, -np.inf])
LIM_HI = np.array([np.inf, 109.5, 109.5, 109.5, np.inf])
CENTRE_POSE = np.array([0.0, -60.0, 30.0, -15.0, 0.0])
REACH_M = float(np.linalg.norm(sum(LINKS[1:], np.zeros(3)) + LINKS[0] - LINKS[0]))             # |p5 - p1| at full extension: 0.28 + 0.22 + 0.08 + 0.11 = 0.69 m
FD_STEP = 1e-4                                                                                   # rad, forward-difference Jacobian

# the numbers of rules note (m); set by `derive()` rules, written there, never tuned
PARAMS = dict(lam2=None, mu=None, w_o=0.05, w_c=1.0, iters=None, first_frame_iters=50, proj_steps=10, step_cap_rad=0.1)


def rot(axis, ang):
    """Rodrigues rotation matrices for axis (3,) and angles (n,) in radians -> (n, 3, 3)"""
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    s, c = np.sin(ang)[:, None, None], np.cos(ang)[:, None, None]
    return np.eye(3)[None] + s * K[None] + (1 - c) * (K @ K)[None]


def fk_batch(Q):
    """Q (n, 5) deg -> points (n, 6, 3) (origin and the point after each joint's link, as m3f_report.fk_points) and the tool rotation (n, 3, 3)"""
    n = len(Q)
    B = np.broadcast_to(np.eye(3), (n, 3, 3)).copy()
    p = np.zeros((n, 3))
    pts = [p.copy()]
    for j in range(5):
        B = B @ rot(AXES[j], np.radians(Q[:, j]))
        p = p + B @ LINKS[j]
        pts.append(p.copy())
    return np.stack(pts, 1), B


def signed_col_dist(p):
    """signed distance of points (..., 3) to the solid column x, y in +-COL_HALF, z <= TOP: positive outside, negative inside (the penetration depth). The gate's `make_arm_v2p._col_dist` is 0 inside, which has
    no gradient; the IK needs one to get out"""
    d = np.stack([np.abs(p[..., 0]) - P.COL_HALF, np.abs(p[..., 1]) - P.COL_HALF, p[..., 2] - P.TOP], -1)
    return np.linalg.norm(np.maximum(d, 0), axis=-1) + np.minimum(d.max(-1), 0)


NEED = np.array([P.MARGIN, P.MARGIN, P.MARGIN, P.HAND_MARGIN])


def col_rows(pts):
    """column clearance violations (n, 4): p2, p3, p4 against 0.05 m, the hand against 0.11 m (metres inside the margin, 0 when clear), on the signed distance"""
    return np.maximum(0.0, NEED - signed_col_dist(pts[:, 2:6]))


def col_margin(Q):
    """Q (n, 5) deg -> smallest signed margin (n,) over p2, p3, p4 and the hand (>= 0 clear): the gate's margins on the signed distance"""
    pts, _ = fk_batch(Q)
    return (signed_col_dist(pts[:, 2:6]) - NEED).min(1)


def residual(Q, pt, Rt, w_o, w_c):
    """Q (n, 5) deg -> residual (n, 9) for one target (pt (3,), Rt (3,3))"""
    pts, B = fk_batch(Q)
    E = np.einsum("nji,jk->nik", B, Rt)                                                          # R_cur^T R_target, in the current tool frame
    vee = np.stack([E[:, 2, 1] - E[:, 1, 2], E[:, 0, 2] - E[:, 2, 0]], 1) / 2                  # (x, y) components of the small rotation error (x = roll, y = bend)
    return np.concatenate([pts[:, 5] - pt, w_o * vee, w_c * col_rows(pts)], 1), pts


def solve_frame(q_prev, pt, Rt, iters, prm=PARAMS):
    """one frame: q_prev (5,), target position pt (3,) and rotation Rt (3,3) -> q (5,), end-point error (m), iterations used"""
    q = q_prev.copy()
    h = np.degrees(FD_STEP)
    damp = prm["lam2"] + prm["mu"]
    for _ in range(iters):
        Qp = np.vstack([q] + [q + h * np.eye(5)[j] for j in range(5)])
        F, _ = residual(Qp, pt, Rt, prm["w_o"], prm["w_c"])
        f0 = F[0]
        J = (F[1:] - f0).T / FD_STEP                                                             # (9, 5), per radian
        A = J.T @ J + damp * np.eye(5)
        dq = np.linalg.solve(A, -J.T @ f0 - prm["mu"] * np.radians(q - q_prev))
        nrm = np.linalg.norm(dq)
        if nrm > prm["step_cap_rad"]:                                                           # trust region (rules (m): 2 x 1 cm / sigma_c)
            dq *= prm["step_cap_rad"] / nrm
        q = np.clip(q + np.degrees(dq), LIM_LO, LIM_HI)
    return q


def project_column(q, steps=10):
    """if a column margin is still violated, move the joints along the margin's gradient (Newton step on the smallest signed margin, at most `steps` steps) and return the best pose seen
    (never worse than the input)"""
    h = np.degrees(FD_STEP)
    best, best_m = q.copy(), float(col_margin(q[None])[0])
    for _ in range(steps):
        if best_m >= 0:
            break
        m0 = float(col_margin(q[None])[0])
        g = np.array([(float(col_margin((q + h * np.eye(5)[j])[None])[0]) - m0) / FD_STEP for j in range(5)])
        if np.linalg.norm(g) < 1e-9:
            break
        q = np.clip(q + np.degrees(-m0 * g / (g @ g) * 1.05), LIM_LO, LIM_HI)
        m1 = float(col_margin(q[None])[0])
        if m1 > best_m:
            best, best_m = q.copy(), m1
    return best


def run_path(pts_t, R_t, q0=CENTRE_POSE, prm=PARAMS):
    """pts_t (n, 3), R_t (n, 3, 3) at 100 Hz -> Q (n, 5) deg, end-point error (n,) m. The first frame gets prm['first_frame_iters'] iterations, the rest prm['iters'], warm start from the previous frame."""
    n = len(pts_t)
    Q = np.empty((n, 5))
    err = np.empty(n)
    q = q0.copy()
    for i in range(n):
        q = solve_frame(q, pts_t[i], R_t[i], prm["first_frame_iters"] if i == 0 else prm["iters"], prm)
        q = project_column(q, prm["proj_steps"])
        Q[i] = q
        err[i] = np.linalg.norm(fk_batch(q[None])[0][0, 5] - pts_t[i])
    return Q, err


def load_params(path="/secondary/hyst-data/body/retarget_look/v3/ik_params.json"):
    """fill PARAMS from the file written by v3_derive.py (the rules-note numbers)"""
    import json
    d = json.loads(Path(path).read_text())
    PARAMS.update(lam2=d["lam2"], mu=d["mu"], w_o=d["w_o"], w_c=d["w_c"], iters=d["iters"], step_cap_rad=d.get("step_cap_rad", PARAMS["step_cap_rad"]))
    return PARAMS


load_params()
