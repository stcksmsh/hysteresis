"""WO32C body variant v2p (docs/RETARGET_RULES.md (j), BRAIN_SPEC 7.51): v2f with the raised plane replaced by a square pillar under the base and a floor 1.0 m below its top.

make_arm_v2.py and the rest of v2f are not edited. Also holds the v2p clearance margins and the backstop guard (same margin tests for both).
"""
import mujoco
import numpy as np

import dialstudy as D
import make_arm as MA
import make_arm_v2 as V2
import m3f_report as R

TOP = V2.RAISED_PLANE_Z                  # the old table plane = the column top, m
COL_HALF = 0.05 + 0.02                   # base box half-size 0.05 (make_arm.py) + 2 cm per side
FLOOR = TOP - 1.0                        # floor plane, 1.0 m below the column top
MARGIN, DISC = 0.05, V2.DISC_M
HAND_MARGIN = MARGIN + DISC              # the ball's surface keeps 0.05 m, as the old 0.11 m rule


def xml_v2p(kv):
    xml = V2.xml_v2(kv=kv, table=False, condim=1)
    h = (TOP - FLOOR) / 2
    geoms = (f'<geom name="pillar" type="box" size="{COL_HALF} {COL_HALF} {h}" pos="0 0 {TOP - h}" contype="1" conaffinity="0" condim="1" rgba="0.3 0.3 0.35 1"/>\n'
             f'    <geom name="floor" type="plane" size="2 2 0.1" pos="0 0 {FLOOR}" contype="1" conaffinity="0" condim="1" rgba="0.4 0.4 0.4 1"/>')
    return xml.replace("<worldbody>", "<worldbody>\n    " + geoms, 1)


def make_model(kp_scale, zeta):
    """same as dialstudy.make_model (servo gains, contact time constant) on the v2p geometry"""
    kp = MA.KP * kp_scale
    kv = 2 * zeta * np.sqrt(kp * D._inertia())
    m = mujoco.MjModel.from_xml_string(xml_v2p(list(kv)))
    m.geom_solref[:] = [D.CTC, 1.0]
    m.actuator_gainprm[:, 0] = kp
    m.actuator_biasprm[:, 1] = -kp
    m.actuator_biasprm[:, 2] = -kv
    return m


def _col_dist(p):
    """distance of points (..., 3) to the solid column x, y in +-COL_HALF, z <= TOP"""
    d = np.stack([np.maximum(np.abs(p[..., 0]) - COL_HALF, 0), np.maximum(np.abs(p[..., 1]) - COL_HALF, 0), np.maximum(p[..., 2] - TOP, 0)], -1)
    return np.linalg.norm(d, axis=-1)


def margins(q):
    """q (T, 5) deg -> (T,) smallest clearance margin (m, >= 0 is clear) over p2, p3, p4 (0.05 m from the column and above the floor) and the hand p5 (0.11 m)"""
    P = R.fk_points(q)
    pts = P[:, 2:5]
    m = [(_col_dist(pts) - MARGIN).min(1), (pts[..., 2] - FLOOR - MARGIN).min(1), _col_dist(P[:, 5]) - HAND_MARGIN, P[:, 5, 2] - FLOOR - HAND_MARGIN]
    return np.min(m, axis=0)


def guard(G):
    """backstop (rules (j)): command rows G (n, 5) deg at 100 Hz -> (held rows, share of frames held). An unsafe commanded pose (FK of the angles clipped inside the ranges)
    is replaced by the last safe command; frames before the first safe one take the first safe command."""
    lo, hi = D.LO + D.CLIP_MARGIN, D.HI - D.CLIP_MARGIN
    safe = margins(np.clip(G, lo, hi)) >= 0
    if not safe.any():
        return G.copy(), 1.0
    idx = np.where(safe, np.arange(len(G)), -1)
    np.maximum.accumulate(idx, out=idx)
    first = int(np.argmax(safe))
    idx[idx < 0] = first
    return G[idx], float((~safe).mean())
