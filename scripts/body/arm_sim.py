"""The M0 body in MuJoCo: servo arm with gravity, a target rate limiter, bus-servo proprioception, and the 50 Hz joint CSV export.

    sim = ArmSim()                      # builds the model from make_arm.py (arm.xml is the same text)
    obs = sim.step(target_deg)          # one 10 ms control step (5 physics steps of 2 ms)

Plan §6: position servos (kp, kv) with torque saturation at the stall torque; the commanded target is limited in speed and acceleration by
body.rs LIMITS (a braking-aware second-order limiter, so the target itself never exceeds them); the two bends the rig bounds are clipped to
their range. Proprioception is what a bus servo reports: position quantised to the encoder step, velocity, load (actuator force), all of the
PREVIOUS control step (one step = 10 ms of delay). Mechanical power per step: mean over its physics steps of sum |tau * omega|.
"""
import json
import math

import mujoco
import numpy as np

import make_arm as M

CONTROL_HZ = 100
SUBSTEPS = round(1.0 / CONTROL_HZ / M.TIMESTEP)      # 5
DT = 1.0 / CONTROL_HZ
LIM_V = np.array([v for v, _ in M.LIMITS])
LIM_A = np.array([a for _, a in M.LIMITS])
LO = np.array([-np.inf if r is None else r[0] for r in M.RANGE_DEG], float)
HI = np.array([np.inf if r is None else r[1] for r in M.RANGE_DEG], float)
QUANT_DEG = 360.0 / M.ENCODER_STEPS


def rodrigues(v, axis, deg):
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    return v * c + np.cross(axis, v) * s + axis * (axis @ v) * (1 - c)


def fk(q_deg, origin=(0.0, 0.0, 0.0), yaw_deg=0.0):
    """Points 0..5 (origin, then after each joint's link) exactly as ensemble.rs `forward_kinematics`. -> (6, 3)."""
    z = np.array([0.0, 0, 1])
    basis = [rodrigues(np.array(e, float), z, yaw_deg) for e in ((1, 0, 0), (0, 1, 0))] + [z]
    mul = lambda v: basis[0] * v[0] + basis[1] * v[1] + basis[2] * v[2]
    p, pts = np.array(origin, float), [np.array(origin, float)]
    for ax, link, a in zip(M.AXES, M.LINKS, q_deg):
        axis_w = mul(np.array(ax, float))
        basis = [rodrigues(b, axis_w, a) for b in basis]
        p = p + mul(np.array(link, float))
        pts.append(p)
    return np.array(pts)


def floor_margin(q_deg, floor_m=0.05, disc_m=0.06):
    """score_csv.rs floor rule: points 1..4 clear the floor by `floor_m`, the hand by `floor_m + disc_m`."""
    p = fk(q_deg)
    return min(p[1:5, 2].min() - floor_m, p[5, 2] - floor_m - disc_m)


def swing_margin(centre_deg, amp_deg):
    """Worst floor margin (m) over the corners {centre - amp, centre, centre + amp} of the box a pattern generator can sweep. Base yaw turns about
    the vertical and the roll moves no chain point, so only the three bends (27 corners) change any height."""
    import itertools
    c, a = np.array(centre_deg, float), np.array(amp_deg, float)
    c[[0, 4]] = a[[0, 4]] = 0.0
    return min(floor_margin(c + np.array((0, *k, 0)) * a) for k in itertools.product((-1, 0, 1), repeat=3))


class ArmSim:
    def __init__(self, xml=None):
        self.model = mujoco.MjModel.from_xml_string(xml or M.final_xml())
        self.data = mujoco.MjData(self.model)
        self.hand = self.model.site("hand").id
        self.reset()

    def reset(self, q_deg=None):
        q = np.array(M.NEUTRAL_DEG if q_deg is None else q_deg, float)
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:] = np.radians(q)
        self.data.ctrl[:] = np.radians(q)
        mujoco.mj_forward(self.model, self.data)
        self.tgt, self.tgt_v = q.copy(), np.zeros(5)
        self.power_w = 0.0
        self._snap = self._proprio()
        return self._snap

    # ---- state ----
    @property
    def q_deg(self):
        return np.degrees(self.data.qpos)

    @property
    def qd_deg(self):
        return np.degrees(self.data.qvel)

    def hand_pos(self):
        return self.data.site_xpos[self.hand].copy()

    def _proprio(self):
        return {"pos_deg": np.round(self.q_deg / QUANT_DEG) * QUANT_DEG, "vel_deg_s": self.qd_deg.copy(),
                "load_nm": self.data.actuator_force.copy()}

    # ---- control ----
    def limit_target(self, target_deg):
        """Move the held target toward `target_deg` for one control step under LIM_V / LIM_A (braking-aware). Returns the new held target."""
        goal = np.clip(np.asarray(target_deg, float), LO, HI)
        e = goal - self.tgt
        v_des = np.sign(e) * np.minimum(LIM_V, np.sqrt(2 * LIM_A * np.abs(e)))
        # do not command more than reaches the goal in this step (no overshoot from the discrete step)
        v_des = np.where(np.abs(v_des) * DT > np.abs(e), e / DT, v_des)
        self.tgt_v = self.tgt_v + np.clip(v_des - self.tgt_v, -LIM_A * DT, LIM_A * DT)
        self.tgt_v = np.clip(self.tgt_v, -LIM_V, LIM_V)
        self.tgt = np.clip(self.tgt + self.tgt_v * DT, LO, HI)
        return self.tgt

    def step(self, target_deg):
        """One control step. -> proprioception of the previous step (one step of delay)."""
        old = self._snap
        self.data.ctrl[:] = np.radians(self.limit_target(target_deg))
        p = 0.0
        for _ in range(SUBSTEPS):
            mujoco.mj_step(self.model, self.data)
            p += float(np.abs(self.data.actuator_force * self.data.qvel).sum())      # tau * omega (position servo: force is the joint torque)
        self.power_w = p / SUBSTEPS
        self._snap = self._proprio()
        return old


def csv_text(q_rows_deg, hz=50, name="physics"):
    """The 50 Hz joint CSV `hyst check-csv` reads (score_csv.rs format). `q_rows_deg`: (n, 5) degrees at 1/hz spacing from t = 0."""
    ch = lambda i: {"name": M.JOINTS[i], "axisLocal": list(M.AXES[i]), "linkM": list(M.LINKS[i]), "neutralDegrees": M.NEUTRAL_DEG[i],
                    "intentMixDegrees": [0.0, 0.0, 0.0],
                    "minDegrees": M.RANGE_DEG[i][0] if M.RANGE_DEG[i] else -1e6, "maxDegrees": M.RANGE_DEG[i][1] if M.RANGE_DEG[i] else 1e6,
                    "maxSpeedDegreesPerSecond": M.LIMITS[i][0], "maxAccelerationDegreesPerSecond2": M.LIMITS[i][1]}
    rig = {"channels": [ch(i) for i in range(5)]}      # `implement` omitted: the loader's default is the mirror ball
    out = f"# hyst score-csv v1; angles in degrees, time in audio seconds from 0\n# source_score: {name}\n# mode: layered\n# body_source: mujoco\n# hz: {hz}\n"
    out += f"# rig_json: {json.dumps(rig)}\n# placement_json: {json.dumps({'originM': [0.0, 0.0, 0.0], 'yawDegrees': 0.0})}\n"
    out += "time_s,base_yaw,shoulder,elbow,wrist_bend,wrist_roll\n"
    for i, q in enumerate(q_rows_deg):
        out += f"{i / hz:.6f}," + ",".join(f"{v:.6f}" for v in q) + "\n"
    return out
