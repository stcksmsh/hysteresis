"""WO15A step 1 (BRAIN_SPEC 7.30 point 6): held-contact test. Measures how deep the mirror ball and the link capsules sink below a table plane at z = 0.05 m on the v2f body with the hard
joint stop (the training body: MJX, one Newton iteration, 2 ms steps, 5 per control step, frictionless contact). Provisional servo model (Feetech STS3215 12 V assumed).

Held poses: the arm is driven (targets well below the plane, clipped by the hard stop to the joint ranges) and held 10 s at the control rate; plus the WO14A 15 s adversarial sequence (targets
+-150 deg flipping every 0.7 s with noise). Sinking, per control step: ball = plane - (p5 z - 0.06); link = plane - (min(p1..p4 z) - 0.01) (positive = below the plane).
d = the deepest sinking over everything, rounded up to the next millimetre. If d > 5 mm the plane cannot be raised by this rule (7.30.6): stop and report.
    m3f_plane_test.py [OUT.json]
"""
import json
import math
import sys

import jax
import jax.numpy as jnp
import numpy as np

import m3f_jax as F
import m3f_report as R
import make_arm as MA

PLANE = 0.05
BALL_R, LINK_R = 0.06, 0.01
F.MODELS["probe"] = F._model_v2(condim=1, table_z=PLANE)
F.MX["probe"] = F.mjx.put_model(F.MODELS["probe"])
CFG = {"body": "probe", "obs_lp": False, "phase_lp": False, "xfade": False, "clip": True}
STEP = jax.jit(lambda d, tgt, tv, t: F.arm_step(CFG, d, tgt, tv, t))


def run(targets_fn, steps):
    d, tgt, tv = F.arm_init(CFG, np.array(MA.NEUTRAL_DEG, float))
    qs = []
    for k in range(steps):
        d, tgt, tv, _ = STEP(d, tgt, tv, jnp.asarray(targets_fn(k)))
        qs.append(np.degrees(np.asarray(d.qpos)))
    return np.array(qs)


def sinking(qs):
    P = R.fk_points(qs)
    ball = PLANE - (P[:, 5, 2] - BALL_R)
    link = PLANE - (P[:, 1:5, 2].min(1) - LINK_R)
    return ball, link


def main():
    out = {"plane_z": PLANE, "poses": []}
    held = []
    for sh in (20.0, 45.0, 70.0, 100.0):                     # arm pointing forward and down, from shallow to steep
        for el in (-40.0, 0.0, 40.0):
            for wr in (-30.0, 30.0):
                held.append([0.0, sh, el, wr, 0.0])
    held += [[0.0, 150.0, 150.0, 150.0, 0.0], [0.0, 100.0, 100.0, 100.0, 0.0], [90.0, 60.0, 60.0, 0.0, 0.0], [0.0, 150.0, 0.0, 0.0, 0.0], [0.0, 90.0, 20.0, 110.0, 0.0]]
    worst_ball = worst_link = -1e9
    for h in held:
        qs = run(lambda k: np.array(h, float), 1000)         # 10 s
        b, l = sinking(qs)
        worst_ball, worst_link = max(worst_ball, float(b.max())), max(worst_link, float(l.max()))
        out["poses"].append({"target": h, "ball_max_sink_mm": 1000 * float(b.max()), "link_max_sink_mm": 1000 * float(l.max()), "ball_steady_mm": 1000 * float(b[-200:].mean()), "link_steady_mm": 1000 * float(l[-200:].mean())})
        print(h, "ball max %.3f mm steady %.3f mm | link max %.3f mm steady %.3f mm" % (1000 * b.max(), 1000 * b[-200:].mean(), 1000 * l.max(), 1000 * l[-200:].mean()), flush=True)
    rng = np.random.default_rng(0)
    seq = lambda k: np.array([0.0, 150.0, 150.0, 150.0, 0.0]) * (1.0 if (k // 70) % 2 == 0 else -1.0) + rng.normal(0, 3.0, 5)
    qs = run(seq, 1500)
    b, l = sinking(qs)
    out["adversarial"] = {"ball_max_sink_mm": 1000 * float(b.max()), "link_max_sink_mm": 1000 * float(l.max())}
    print("adversarial 15 s: ball max %.3f mm, link max %.3f mm" % (1000 * b.max(), 1000 * l.max()))
    worst_ball, worst_link = max(worst_ball, float(b.max())), max(worst_link, float(l.max()))
    deepest = max(worst_ball, worst_link)
    d = math.ceil(deepest * 1000 - 1e-9) / 1000
    out.update({"deepest_ball_mm": 1000 * worst_ball, "deepest_link_mm": 1000 * worst_link, "deepest_mm": 1000 * deepest, "d_m": d, "stop": bool(d > 0.005)})
    print("deepest ball %.3f mm, deepest link %.3f mm -> d = %.3f m%s" % (1000 * worst_ball, 1000 * worst_link, d, "  (> 5 mm: STOP)" if d > 0.005 else ""))
    json.dump(out, open(sys.argv[1] if len(sys.argv) > 1 else "plane_test.json", "w"), indent=1)


if __name__ == "__main__":
    main()
