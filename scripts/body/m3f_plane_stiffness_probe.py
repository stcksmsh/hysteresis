"""WO15A information probe (not part of the order, nothing here is applied): deepest sinking of the ball / links into a table plane at z = 0.05 m in four hard held poses of the v2f body with the
hard stop, for four values of the contact time constant (geom solref[0]; the body uses MuJoCo's default 0.02). Provisional servo model (Feetech STS3215 12 V assumed).
    m3f_plane_stiffness_probe.py
"""
import sys
sys.path.insert(0, '.')
import jax, jax.numpy as jnp, numpy as np
import m3f_jax as F, m3f_report as R, make_arm as MA

PLANE, BALL_R, LINK_R = 0.05, 0.06, 0.01
poses = {"150/150/150": [0.0, 150.0, 150.0, 150.0, 0.0], "100/100/100": [0.0, 100.0, 100.0, 100.0, 0.0], "sh100 el0 wr30": [0.0, 100.0, 0.0, 30.0, 0.0], "sh45 el40 wr-30": [0.0, 45.0, 40.0, -30.0, 0.0]}
for tc in (0.02, 0.01, 0.006, 0.004):
    m = F._model_v2(condim=1, table_z=PLANE)
    m.geom_solref[:] = [tc, 1.0]
    F.MODELS["p"] = m
    F.MX["p"] = F.mjx.put_model(m)
    cfg = {"body": "p", "obs_lp": False, "phase_lp": False, "xfade": False, "clip": True}
    step = jax.jit(lambda d, tgt, tv, t: F.arm_step(cfg, d, tgt, tv, t))
    res = {}
    for name, h in poses.items():
        d, tgt, tv = F.arm_init(cfg, np.array(MA.NEUTRAL_DEG, float))
        qs = []
        for k in range(800):
            d, tgt, tv, _ = step(d, tgt, tv, jnp.asarray(h))
            qs.append(np.degrees(np.asarray(d.qpos)))
        P = R.fk_points(np.array(qs))
        ball = PLANE - (P[:, 5, 2] - BALL_R)
        link = PLANE - (P[:, 1:5, 2].min(1) - LINK_R)
        res[name] = (round(1000 * max(ball.max(), link.max()), 2), round(1000 * ball[-200:].mean(), 2))
    print('solref timeconst', tc, 'max sink / steady ball (mm):', res, flush=True)
