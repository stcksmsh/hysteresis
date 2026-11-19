"""Generate arm.xml (MJCF) for the M0 body from the rig numbers of `Rig::illustrative_five_axis()` (crates/hyst-compile/src/ensemble.rs).

    python make_arm.py [OUT.xml]        # default: arm.xml next to this file; prints the mass table

One source for every number: the constants below. Every mass and inertia has its basis in BODY_NOTES.md; the servo is a PROVISIONAL stand-in
(Feetech STS3215, 12 V, 30 kg.cm class), no servo has been chosen. Forward-kinematics convention (ensemble.rs `forward_kinematics`): joint i
rotates the frame about `axis_local`, THEN the frame advances by `link_m` of that joint. In MJCF that is: body i carries joint i and the link
that follows it; body i+1 sits at `link_m` of joint i. Positive angle = right-hand rotation about the axis, as in `rotate()`.
"""
import math
import sys
from pathlib import Path

import mujoco
import numpy as np

JOINTS = ["base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll"]     # body.rs JOINTS
AXES = [(0, 0, 1), (0, 1, 0), (0, 1, 0), (0, 1, 0), (1, 0, 0)]
LINKS = [(0, 0, 0.08), (0.28, 0, 0), (0.22, 0, 0), (0.08, 0, 0), (0.11, 0, 0)]    # link_m after each joint
NEUTRAL_DEG = [0.0, -55.0, 35.0, 5.0, 0.0]
RANGE_DEG = [None, (-110, 110), (-110, 110), (-110, 110), None]           # None = continuous (the rig sets +-1e6)
LIMITS = [(120.0, 600.0), (90.0, 300.0), (150.0, 1000.0), (200.0, 2000.0), (250.0, 3000.0)]   # body.rs LIMITS: deg/s, deg/s2

# ---- provisional servo: Feetech STS3215, 12 V variant (BODY_NOTES.md) ----
STALL_NM = 30 * 0.0980665          # 30 kg.cm
SERVO_KG = 0.055                   # listing weight (7.4 V variant); 12 V weight unconfirmed
SERVO_BOX_M = (0.0452, 0.0247, 0.035)    # full size, approximate
ENCODER_STEPS = 4096               # 12-bit magnetic encoder
GEAR = 345                         # 1:345
ROTOR_KGM2 = 1e-7                  # ASSUMED motor rotor inertia (coreless DC class); reflected inertia = ROTOR * GEAR^2
ARMATURE = ROTOR_KGM2 * GEAR ** 2
KP = STALL_NM / math.radians(10.0)       # N.m/rad: full stall torque at 10 deg error (PROVISIONAL: the servo's own loop gains are not known)
ZETA = 1.5

# ---- printed parts (BODY_NOTES.md) ----
PLA = 1240.0                       # kg/m3
TUBE_OUTER, TUBE_WALL = 0.020, 0.002     # square tube, m
STEM_D = 0.008                     # solid rod, m

TIMESTEP = 0.002


def tube_kg(length):
    return PLA * (TUBE_OUTER ** 2 - (TUBE_OUTER - 2 * TUBE_WALL) ** 2) * length


def stem_kg(length):
    return PLA * math.pi * (STEM_D / 2) ** 2 * length


def ball():
    """Mirror-ball implement (Implement::mirror_ball, ported): -> dict reach_m, mean_r_m, mass_kg, tiles, shell_kg, mirror_kg.
    Shell: printed PLA, 1.2 mm; tiles: 1 mm acrylic mirror (1180 kg/m3). Both are estimates (BODY_NOTES.md)."""
    unit = lambda v: np.array(v, float) / np.linalg.norm(v)
    noise = lambda i, k: (lambda x: x - math.floor(x))(math.sin(i * 12.9898 + k * 78.233) * 43758.5453)
    dents = [(unit([0.3, 0.8, 0.5]), 0.45, 0.10), (unit([-0.5, -0.6, 0.6]), 0.32, 0.14),
             (unit([0.7, -0.2, -0.7]), 0.40, 0.07), (unit([-0.2, 0.5, -0.8]), 0.28, 0.05)]

    def radius(d):
        lobes = 0.60 + 0.34 * abs(0.8 * d[1] + 0.6 * d[2]) ** 1.4 + 0.10 * d[0]
        ripples = 1.0 + 0.13 * math.sin(5 * d[0] + 1) * math.sin(4 * d[1] - 0.5) + 0.09 * math.sin(6 * d[2] + 2)
        dent = 1.0
        for at, depth, width in dents:
            dent *= 1.0 - depth * math.exp(-(1.0 - float(d @ at)) / width)
        return 0.066 * lobes * ripples * dent

    n, reach, rs, tile_area = 110, 0.0, [], 0.0
    for i in range(n):
        z = 1.0 - 2.0 * (i + 0.5) / n
        r, phi = math.sqrt(1 - z * z), i * 2.39996
        d = np.array([z, r * math.cos(phi), r * math.sin(phi)])
        rad, half = radius(d), 0.008 + 0.006 * noise(i, 4)
        reach = max(reach, rad + half)
        rs.append(rad)
        tile_area += (2 * half) ** 2
    mean_r = float(np.mean(rs))
    shell = PLA * 0.0012 * 4 * math.pi * mean_r ** 2
    mirror = 1180.0 * 0.001 * tile_area
    return {"reach_m": math.ceil(reach * 1000) / 1000, "mean_r_m": mean_r, "shell_kg": shell, "mirror_kg": mirror,
            "mass_kg": shell + mirror, "tiles": n}


def parts():
    """Every mass in the model: name -> (kg, basis). The sum is the total arm mass."""
    b = ball()
    p = {"column (tube, 0.08 m)": tube_kg(LINKS[0][2]), "upper arm (tube, 0.28 m)": tube_kg(LINKS[1][0]),
         "forearm (tube, 0.22 m)": tube_kg(LINKS[2][0]), "wrist link (tube, 0.08 m)": tube_kg(LINKS[3][0]),
         "stem (rod, 0.11 m)": stem_kg(LINKS[4][0]), "mirror ball: shell": b["shell_kg"], "mirror ball: tiles": b["mirror_kg"]}
    for j in JOINTS:
        p[f"servo {j}"] = SERVO_KG
    return p


def build_xml(kv=None):
    """MJCF text. `kv`: per-joint damping gain (N.m.s/rad); default = a first guess, `tune_kv` gives the real one."""
    kv = kv or [1.0] * 5
    b = ball()
    f = lambda v: " ".join(f"{x:.6g}" for x in v)
    mass_link = [tube_kg(LINKS[0][2]), tube_kg(LINKS[1][0]), tube_kg(LINKS[2][0]), tube_kg(LINKS[3][0]), stem_kg(LINKS[4][0])]
    sx, sy, sz = (x / 2 for x in SERVO_BOX_M)
    servo = lambda pos: f'<geom type="box" size="{sx:.5f} {sy:.5f} {sz:.5f}" pos="{f(pos)}" mass="{SERVO_KG}" contype="0" conaffinity="0" rgba="0.2 0.2 0.25 1"/>'
    link = lambda i: f'<geom type="capsule" fromto="0 0 0 {f(LINKS[i])}" size="0.01" mass="{mass_link[i]:.6g}" contype="0" conaffinity="0" rgba="0.8 0.8 0.85 1"/>'
    jr = lambda i: "" if RANGE_DEG[i] is None else f' limited="true" range="{RANGE_DEG[i][0]} {RANGE_DEG[i][1]}"'
    joint = lambda i: f'<joint name="{JOINTS[i]}" type="hinge" axis="{f(AXES[i])}" armature="{ARMATURE:.6g}"{jr(i)}/>'
    ball_i = 2.0 / 3.0 * b["mass_kg"] * b["mean_r_m"] ** 2
    xml = f'''<mujoco model="hyst_arm">
  <compiler angle="degree"/>
  <option timestep="{TIMESTEP}" gravity="0 0 -9.81" integrator="implicitfast"/>
  <worldbody>
    <body name="base">
      <geom type="box" size="0.05 0.05 0.01" pos="0 0 -0.01" mass="0.001" contype="0" conaffinity="0"/>
      <body name="b0" pos="0 0 0">
        {joint(0)}
        {link(0)}
        {servo(LINKS[0])}
        <body name="b1" pos="{f(LINKS[0])}">
          {joint(1)}
          {link(1)}
          {servo(LINKS[1])}
          <body name="b2" pos="{f(LINKS[1])}">
            {joint(2)}
            {link(2)}
            {servo(LINKS[2])}
            <body name="b3" pos="{f(LINKS[2])}">
              {joint(3)}
              {link(3)}
              {servo(LINKS[3])}
              <body name="b4" pos="{f(LINKS[3])}">
                {joint(4)}
                {link(4)}
                <body name="implement" pos="{f(LINKS[4])}">
                  <inertial pos="0 0 0" mass="{b["mass_kg"]:.6g}" diaginertia="{ball_i:.6g} {ball_i:.6g} {ball_i:.6g}"/>
                  <site name="hand" pos="0 0 0" size="0.005"/>
                </body>
              </body>
            </body>
          </body>
        </body>
      </body>
    </body>
  </worldbody>
  <actuator>
''' + "\n".join(f'    <position name="{JOINTS[i]}" joint="{JOINTS[i]}" kp="{KP:.6g}" kv="{kv[i]:.6g}" forcerange="{-STALL_NM:.6g} {STALL_NM:.6g}" forcelimited="true"/>'
                 for i in range(5)) + "\n  </actuator>\n</mujoco>\n"
    return xml


def tune_kv():
    """Damping per joint: kv = 2 zeta sqrt(kp I) with I the joint's effective inertia (mass-matrix diagonal, armature included) with the arm
    straight out, the pose with the largest reflected inertia."""
    m = mujoco.MjModel.from_xml_string(build_xml())
    d = mujoco.MjData(m)
    mujoco.mj_forward(m, d)
    M = np.zeros((m.nv, m.nv))
    mujoco.mj_fullM(m, d, M)
    return [2 * ZETA * math.sqrt(KP * M[i, i]) for i in range(5)]


def final_xml():
    return build_xml(tune_kv())


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("arm.xml")
    out.write_text(final_xml())
    m = mujoco.MjModel.from_xml_path(str(out))
    print(f"wrote {out}; total mass {m.body_mass.sum():.4f} kg")
    for k, v in parts().items():
        print(f"  {k:32s} {v * 1000:8.1f} g")
    b = ball()
    print(f"  mirror ball reach {b['reach_m']} m, mean radius {b['mean_r_m']:.4f} m, {b['tiles']} tiles, mass {b['mass_kg'] * 1000:.1f} g")
    print("  kv:", [round(x, 3) for x in tune_kv()], f"kp {KP:.3f}, armature {ARMATURE:.4f}")


if __name__ == "__main__":
    main()
