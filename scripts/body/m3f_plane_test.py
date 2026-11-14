"""WO15A held-contact test (BRAIN_SPEC 7.30 points 6 and 7). Measures how deep the mirror ball and the link capsules sink below a table plane at z = 0.05 m on the v2f body with the hard joint
stop (the training body: MJX, one Newton iteration, 2 ms steps, 5 per control step, frictionless contact), and checks that the contact is stable at that step. Provisional servo model
(Feetech STS3215 12 V assumed).

Held poses: the arm is driven (targets well below the plane, clipped by the hard stop to the joint ranges) and held 10 s at the control rate (29 poses: shoulder 20/45/70/100 x elbow -40/0/40 x
wrist bend -30/30, plus five fold/extension poses); plus the WO14A 15 s adversarial sequence (targets +-150 deg flipping every 0.7 s with noise). Sinking, per control step: ball = plane - (p5 z - 0.06);
link = plane - (min(p1..p4 z) - 0.01) (positive = below the plane). d = the deepest sinking over everything, rounded up to the next millimetre; d > 5 mm: the plane cannot be raised by this rule.
Stability (7.30.7 check i), per held pose: no NaN; growth = mean sinking in seconds 7-10 minus seconds 3-6 (a growing sinking is positive); oscillation = standard deviation of the ball height in the
last 3 s; settled hand speed = mean |hand velocity| over the last second (m/s). Pass lines: no NaN, growth <= 0.1 mm, oscillation <= 0.05 mm, settled speed < 0.01 m/s in every held pose; the adversarial
sequence finite.
    m3f_plane_test.py OUT.json [--ctc 0.006] [--plane 0.05]
"""
import argparse
import json
import math

import jax
import jax.numpy as jnp
import numpy as np

import m3f_jax as F
import m3f_report as R
import make_arm as MA

BALL_R, LINK_R = 0.06, 0.01


def make(ctc, plane):
    cfg = {"body": "v2f", "obs_lp": False, "phase_lp": False, "xfade": False, "clip": True, "plane": plane}
    if ctc is not None:
        cfg["ctc"] = ctc
    step = jax.jit(lambda d, tgt, tv, t: F.arm_step(cfg, d, tgt, tv, t))
    return cfg, step


def run(cfg, step, targets_fn, steps):
    d, tgt, tv = F.arm_init(cfg, np.array(MA.NEUTRAL_DEG, float))
    qs = []
    for k in range(steps):
        d, tgt, tv, _ = step(d, tgt, tv, jnp.asarray(targets_fn(k)))
        qs.append(np.degrees(np.asarray(d.qpos)))
    return np.array(qs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--ctc", type=float, default=None)
    ap.add_argument("--plane", type=float, default=0.05)
    a = ap.parse_args()
    PLANE = a.plane
    cfg, step = make(a.ctc, PLANE)

    def sinking(qs):
        P = R.fk_points(qs)
        return PLANE - (P[:, 5, 2] - BALL_R), PLANE - (P[:, 1:5, 2].min(1) - LINK_R), P

    out = {"plane_z": PLANE, "contact_tc": a.ctc, "poses": []}
    held = []
    for sh in (20.0, 45.0, 70.0, 100.0):
        for el in (-40.0, 0.0, 40.0):
            for wr in (-30.0, 30.0):
                held.append([0.0, sh, el, wr, 0.0])
    held += [[0.0, 150.0, 150.0, 150.0, 0.0], [0.0, 100.0, 100.0, 100.0, 0.0], [90.0, 60.0, 60.0, 0.0, 0.0], [0.0, 150.0, 0.0, 0.0, 0.0], [0.0, 90.0, 20.0, 110.0, 0.0]]
    worst_ball = worst_link = -1e9
    stab = {"nan": False, "growth_mm_max": -1e9, "oscillation_mm_max": 0.0, "settled_speed_max": 0.0}
    for h in held:
        qs = run(cfg, step, lambda k: np.array(h, float), 1000)
        b, l, P = sinking(qs)
        nan = bool(not np.isfinite(qs).all())
        sink = np.maximum(b, l)
        growth = float(sink[700:].mean() - sink[300:600].mean())
        osc = float(P[-300:, 5, 2].std())
        speed = float(np.linalg.norm(np.diff(P[-101:, 5], axis=0), axis=1).mean() * 100.0)
        stab["nan"] |= nan
        stab["growth_mm_max"] = max(stab["growth_mm_max"], 1000 * growth)
        stab["oscillation_mm_max"] = max(stab["oscillation_mm_max"], 1000 * osc)
        stab["settled_speed_max"] = max(stab["settled_speed_max"], speed)
        worst_ball, worst_link = max(worst_ball, float(b.max())), max(worst_link, float(l.max()))
        out["poses"].append({"target": h, "ball_max_sink_mm": 1000 * float(b.max()), "link_max_sink_mm": 1000 * float(l.max()), "ball_steady_mm": 1000 * float(b[-200:].mean()), "link_steady_mm": 1000 * float(l[-200:].mean()),
                             "growth_mm": 1000 * growth, "oscillation_mm": 1000 * osc, "settled_hand_speed_mps": speed, "nan": nan})
        print(h, "ball max %.3f steady %.3f | link max %.3f steady %.3f mm | growth %.3f mm osc %.4f mm speed %.5f m/s%s" % (
            1000 * b.max(), 1000 * b[-200:].mean(), 1000 * l.max(), 1000 * l[-200:].mean(), 1000 * growth, 1000 * osc, speed, " NaN" if nan else ""), flush=True)
    rng = np.random.default_rng(0)
    seq = lambda k: np.array([0.0, 150.0, 150.0, 150.0, 0.0]) * (1.0 if (k // 70) % 2 == 0 else -1.0) + rng.normal(0, 3.0, 5)
    qs = run(cfg, step, seq, 1500)
    b, l, P = sinking(qs)
    finite = bool(np.isfinite(qs).all())
    out["adversarial"] = {"ball_max_sink_mm": 1000 * float(b.max()), "link_max_sink_mm": 1000 * float(l.max()), "finite": finite}
    print("adversarial 15 s: ball max %.3f mm, link max %.3f mm, finite %s" % (1000 * b.max(), 1000 * l.max(), finite))
    worst_ball, worst_link = max(worst_ball, float(b.max())), max(worst_link, float(l.max()))
    deepest = max(worst_ball, worst_link)
    d = math.ceil(deepest * 1000 - 1e-9) / 1000
    stab["pass"] = bool((not stab["nan"]) and finite and stab["growth_mm_max"] <= 0.1 and stab["oscillation_mm_max"] <= 0.05 and stab["settled_speed_max"] < 0.01)
    out.update({"deepest_ball_mm": 1000 * worst_ball, "deepest_link_mm": 1000 * worst_link, "deepest_mm": 1000 * deepest, "d_m": d, "d_over_5mm": bool(d > 0.005), "stability": stab})
    print("deepest ball %.3f mm, deepest link %.3f mm -> d = %.3f m%s" % (1000 * worst_ball, 1000 * worst_link, d, "  (> 5 mm: STOP)" if d > 0.005 else ""))
    print("stability:", stab)
    json.dump(out, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
