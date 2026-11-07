"""Tests for the M3f body, penalties, movement switches and old-path identity (work order 13B). Provisional servo model (Feetech STS3215 12 V assumed).

    python -m unittest -v test_m3f        # from scripts/body, brain env; the first-epoch test (`FirstEpoch`) takes about 5 minutes
"""
import json
import os
import unittest

import jax
import jax.numpy as jnp
import mujoco
import numpy as np

import m3d
import m3e
import m3e_jax as M
import m3f
import m3f_jax as F
import m3f_report as R
import make_arm as MA
import make_arm_v2 as V2

TOY = "/secondary/hyst-data/body/m3d/toy.npz"
OFF = dict(body="v1", obs_lp=False, phase_lp=False, xfade=False)


def drive(model, target, secs=3.0):
    """Start at neutral, ramp the servo targets to `target` over half the time, hold. -> (data, lowest point-z over the run)."""
    d = mujoco.MjData(model)
    q0 = np.array(MA.NEUTRAL_DEG, float)
    d.qpos[:] = np.radians(q0)
    mujoco.mj_forward(model, d)
    n = int(secs / model.opt.timestep)
    low = 1e9
    for k in range(n):
        a = min(1.0, k / (n * 0.5))
        d.ctrl[:] = np.radians(q0 + a * (np.array(target, float) - q0))
        mujoco.mj_step(model, d)
        low = min(low, R.fk_points(np.degrees(d.qpos)[None])[0, 1:5, 2].min())
    return d, low


class Body(unittest.TestCase):
    def test_mass_unchanged(self):
        self.assertAlmostEqual(mujoco.MjModel.from_xml_string(MA.final_xml()).body_mass.sum(), mujoco.MjModel.from_xml_string(V2.xml_v2()).body_mass.sum(), places=12)

    def test_pose_through_table_is_pushed_out(self):
        tgt = [0, 100, 0, 0, 0]                                   # the arm points down at the table
        _, low1 = drive(mujoco.MjModel.from_xml_string(MA.final_xml()), tgt)
        d2, low2 = drive(mujoco.MjModel.from_xml_string(V2.xml_v2()), tgt)
        self.assertLess(low1, -0.15)                              # the old body goes through the plane z = 0
        self.assertGreater(low2, -0.02)                           # the new one rests on it (link-axis points; the capsule surface touches at +0.01)
        self.assertLess(np.degrees(d2.qpos)[1], 60.0)             # and the shoulder did not reach the commanded 100 deg
        self.assertGreater(d2.ncon, 0)

    def test_frictionless_body_also_stops_the_arm(self):
        d2, low2 = drive(mujoco.MjModel.from_xml_string(V2.xml_v2(condim=1)), [0, 100, 0, 0, 0])
        self.assertGreater(low2, -0.02)
        self.assertLess(np.degrees(d2.qpos)[1], 60.0)
        m = mujoco.MjModel.from_xml_string(V2.xml_v2(condim=1))
        self.assertTrue(all(m.geom_condim[g] == 1 for g in range(m.ngeom) if m.geom_contype[g] or m.geom_conaffinity[g]))

    def test_self_intersecting_pose_collides(self):
        m = mujoco.MjModel.from_xml_string(V2.xml_v2(table=False))
        d = mujoco.MjData(m)
        d.qpos[:] = np.radians([0, 0, 110, 110, 0])               # shoulder up, elbow and wrist folded fully: the mirror ball pushes into the base column
        mujoco.mj_forward(m, d)
        self.assertGreater(d.ncon, 0)
        d.qpos[:] = np.radians(MA.NEUTRAL_DEG)
        mujoco.mj_forward(m, d)
        self.assertEqual(d.ncon, 0)
        d.qpos[:] = np.radians([0, 0, 110, 110, 0])
        mujoco.mj_forward(m, d)
        m1 = mujoco.MjModel.from_xml_string(MA.final_xml())
        d1 = mujoco.MjData(m1)
        d1.qpos[:] = d.qpos
        mujoco.mj_forward(m1, d1)
        self.assertEqual(d1.ncon, 0)                              # the old body never collides with itself

    def test_neutral_pose_has_no_contact(self):
        m = mujoco.MjModel.from_xml_string(V2.xml_v2())
        d = mujoco.MjData(m)
        d.qpos[:] = np.radians(MA.NEUTRAL_DEG)
        mujoco.mj_forward(m, d)
        self.assertEqual(d.ncon, 0)


class Penalties(unittest.TestCase):
    def test_zero_inside_the_limits(self):
        t = np.linspace(0, 1, 60)[:, None]
        full = jnp.asarray(np.array(MA.NEUTRAL_DEG)[None] + 5.0 * np.sin(2 * np.pi * 0.5 * t) * np.array([1, 1, 1, 1, 1]))   # slow, small, well inside +-100 deg
        full = jnp.concatenate([full, full[-1:] * 0 + full[-1:]])[:60]
        p = F.penalties(full)
        self.assertEqual(float(p["lim"]), 0.0)
        self.assertEqual(float(p["hand_v"]), 0.0)
        self.assertEqual(float(p["jolt"]), 0.0)
        self.assertGreater(float(p["jerk"]), 0.0)

    def test_positive_outside(self):
        full = jnp.tile(jnp.asarray([0.0, 109.0, 0.0, 0.0, 0.0]), (60, 1))
        self.assertAlmostEqual(float(F.penalties(full)["lim"]), 1.0 / 3.0 * 0.9, places=6)            # shoulder alone: (109 - 100) / 10 over 3 bends
        fast = jnp.asarray(np.cumsum(np.full((60, 5), 3.0), 0))                                      # 300 deg/s on every joint
        self.assertGreater(float(F.penalties(fast)["hand_v"]), 0.0)
        wob = jnp.asarray(np.stack([np.where(np.arange(60) < 30, 0.0, 40.0)] * 5, 1))                  # still, then a 40 deg step: a hand-speed spike, large jolt
        self.assertGreater(float(F.penalties(wob)["jolt"]), 0.0)


class Switches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toy = m3f.ToyF(TOY)
        cls.C = M.load_cb()
        cls.P = M.init_policy(jax.random.PRNGKey(0))

    def run_chunk(self, cfg, P=None, nb=8, idx=np.arange(0, 2)):
        chunk = jax.jit(F.make_chunk(cfg), static_argnums=(2,))
        inps = self.toy.inputs(idx, jax.random.PRNGKey(1))
        carry = jax.vmap(lambda q: F.init_carry(cfg, q, self.C))(jnp.asarray(m3d.start_poses(len(idx), 5)))
        _, o = chunk(self.C, self.P if P is None else P, "argmax", 0.0, carry, m3d.take(inps, 0, nb))
        return {k: np.asarray(v) for k, v in o.items()}

    @classmethod
    def run_chunk_static(cls, cfg, nb=8, idx=np.arange(0, 2)):
        cls.setUpClass()
        return cls.run_chunk(cls, cfg, nb=nb, idx=idx)

    def test_old_path_identity(self):
        """body v1 with every switch off is m3e_jax.chunk: every shared output equal bit for bit."""
        idx = np.arange(0, 2)
        inps = self.toy.inputs(idx, jax.random.PRNGKey(1))
        c0 = jax.vmap(lambda q: M.init_carry(q, self.C))(jnp.asarray(m3d.start_poses(2, 5)))
        _, old = jax.jit(M.chunk, static_argnums=(2,))(self.C, self.P, "argmax", 0.0, c0, m3d.take(inps, 0, 8))
        new = self.run_chunk(OFF)
        for k in old:
            self.assertTrue(np.array_equal(np.asarray(old[k]), new[k]), k)

    def test_observer_inputs(self):
        on = self.run_chunk({**OFF, "obs_lp": True})
        off = self.run_chunk(OFF)
        self.assertEqual(on["desc"].shape[-1], 23)
        self.assertEqual(on["idesc"].shape[-1], 27)
        self.assertEqual(off["desc"].shape[-1], 31)
        self.assertTrue(np.array_equal(on["q"], off["q"]))                       # the low-pass is on the observers' input only, not on the motion
        keep = np.array([i for i in range(31) if i not in F.JERK_E])
        self.assertFalse(np.allclose(on["desc"], off["desc"][..., keep]))        # the descriptors are computed on the filtered trajectory

    def test_lowpass_response(self):
        t = np.arange(400) / 100.0
        lp = lambda f: np.asarray(F.lowpass(jnp.asarray(np.sin(2 * np.pi * f * t)[:, None] * np.ones((1, 5)))))[200:, 0]
        self.assertGreater(np.abs(lp(2.0)).max(), 0.95)
        self.assertLess(np.abs(lp(30.0)).max(), 0.12)

    def test_phase_filter_smooths_a_jump(self):
        z, ph = jnp.zeros(2), []
        zh = jnp.asarray(0.0)
        for k in range(40):
            raw = 0.0 if k < 20 else np.pi                                         # a phase jump of pi at step 20
            z, p = F.phase_filter(z, zh, jnp.asarray(raw), jnp.asarray(0.0))
            zh = jnp.asarray(1.0)
            ph.append(float(p))
        steps = np.abs(np.diff(np.unwrap(ph)))
        self.assertLess(steps[19], 0.6 * np.pi)                                    # the raw phase jumped pi in one step; the filtered one moves less
        self.assertAlmostEqual(float(np.cos(ph[-1])), -1.0, places=1)              # and it gets there

    def test_order_parameter_scales_coupling(self):
        on = self.run_chunk({**OFF, "phase_lp": True})
        self.assertTrue(np.all(on["kappa"] <= 2 * np.pi * self.toy.R.max() + 1e-9))
        P0 = {**self.P, "kappa_fix": jnp.zeros(5)}
        a, b = self.run_chunk({**OFF, "phase_lp": True}, P0), self.run_chunk({**OFF, "phase_lp": True}, P0)
        self.assertTrue(np.array_equal(a["q"], b["q"]))
        # with kappa = 0 the phase filter changes the drive only through the filtered phase; with R = 0 and learned kappa the coupling is exactly absent:
        idx = np.arange(0, 2)
        cfg = {**OFF, "phase_lp": True}
        chunk = jax.jit(F.make_chunk(cfg), static_argnums=(2,))
        inps = self.toy.inputs(idx, jax.random.PRNGKey(1))
        inps = {**inps, "R": jnp.zeros_like(inps["R"])}
        carry = jax.vmap(lambda q: F.init_carry(cfg, q, self.C))(jnp.asarray(m3d.start_poses(2, 5)))
        _, o0 = chunk(self.C, self.P, "argmax", 0.0, carry, m3d.take(inps, 0, 8))
        _, o1 = chunk(self.C, P0, "argmax", 0.0, carry, m3d.take(inps, 0, 8))
        self.assertTrue(np.array_equal(np.asarray(o0["q"]), np.asarray(o1["q"])))

    def test_crossfade_ramp(self):
        u0, u1 = jnp.zeros((4, 5)), jnp.ones((4, 5))
        self.assertAlmostEqual(float(F.xfade_u(u0, u1, 0)[0, 0]), 1 / 75, places=9)
        self.assertAlmostEqual(float(F.xfade_u(u0, u1, 49)[0, 0]), 50 / 75, places=9)         # the ramp is cut by the next block
        self.assertAlmostEqual(float(F.xfade_u(u0, u1, 74)[0, 0]), 1.0, places=9)
        o = self.run_chunk({**OFF, "xfade": True})
        self.assertEqual(float(o["tv"][0, 0]), 0.0)                                           # no switch cost before the first choice
        self.assertTrue(np.all(o["tv"] >= 0) and np.all(o["tv"] <= 1.0 + 1e-9))

    def test_switches_independent(self):
        base = self.run_chunk(OFF, nb=20)["q"]                      # 20 blocks: the toy's state input is zero before block 8, so the programs only change after it
        for sw in ("phase_lp", "xfade"):
            self.assertFalse(np.array_equal(self.run_chunk({**OFF, sw: True}, nb=20)["q"], base), sw)
        self.assertTrue(np.array_equal(self.run_chunk({**OFF, "obs_lp": True}, nb=20)["q"], base))


class Report(unittest.TestCase):
    def test_hf_share_separates_slow_and_fast(self):
        t = np.arange(3000) / 50.0
        slow = np.stack([20 * np.sin(2 * np.pi * 0.5 * t)] * 5, 1)
        fast = np.stack([2 * np.sin(2 * np.pi * 8.0 * t)] * 5, 1)
        self.assertLess(R.hf_share_q50(slow), 0.01)
        self.assertGreater(R.hf_share_q50(fast), 0.95)

    def test_breaches_flag_a_dive_and_pass_a_calm_pose(self):
        calm = np.tile(np.array(MA.NEUTRAL_DEG), (1, 60, 50, 1))
        b = R.breaches(calm)
        self.assertTrue(all(v["episodes_with_breach"] == 0 for v in b.values()), b)
        dive = calm.copy()
        dive[..., 1] = 100.0
        self.assertEqual(R.breaches(dive)["floor_m"]["episodes_with_breach"], 1)

    def test_hf_share_matches_reference(self):
        import hf_share
        q = np.stack([np.cumsum(np.random.default_rng(3).normal(0, 1.0, 600), 0)] * 5, 1)
        q = np.tile(q, (10, 1))[:6000]                                                            # 60 s at 100 Hz
        self.assertAlmostEqual(R.eprime_rollout(q.reshape(1, 120, 50, 5))["e"][0], hf_share.hf_share(q[::2], 50.0), places=12)

    def test_fk_points_match_arm_sim_fk(self):
        import arm_sim
        q = np.random.default_rng(1).uniform(-110, 110, (20, 5))
        got = R.fk_points(q)
        for i in range(20):
            self.assertTrue(np.allclose(got[i], arm_sim.fk(q[i]), atol=1e-9))

    def test_hand_metrics(self):
        t = np.arange(500) / 50.0
        still = np.tile(np.array(MA.NEUTRAL_DEG), (500, 1))
        m = R.hand_metrics(still)
        self.assertEqual((m["acc_p99"], m["fast"], m["contact"]), (0.0, 0.0, 0.0))
        shake = still + np.stack([0 * t, 0 * t, 20 * np.sin(2 * np.pi * 3.0 * t), 0 * t, 0 * t], 1)    # elbow shaken at 3 Hz
        self.assertGreater(R.hand_metrics(shake)["acc_p99"], 6.0)
        down = np.tile(np.array([0.0, 100.0, 0.0, 0.0, 0.0]), (500, 1))                            # arm pointing down: through the table
        self.assertEqual(R.hand_metrics(down)["contact"], 1.0)


class FirstEpoch(unittest.TestCase):
    """M3e try 1's first epoch is reproduced by m3f.Trainer with body v1 and every new thing off (~5 min). Compares the stored epoch-0 record of try 1."""

    def test_first_epoch_matches_try1(self):
        ref = json.load(open("/secondary/hyst-data/body/m3e/try1/result.json"))["hist"][0]
        toy = m3f.ToyF(TOY)
        C = M.load_cb()
        tr = m3f.Trainer(toy, C, OFF, 0.03, 1e-3, 40, 8, seed=0, log=lambda s: None, opts={"pen": False})
        tr.calibrate()
        rec = tr.run_epoch()
        for k in ("dec_e", "dec_i", "energy_rel", "rms_speed", "kappa_mean", "rate_mult", "abs_delta", "clip_share", "critic_loss", "sigma_delta"):
            self.assertAlmostEqual(rec[k], ref[k], delta=1e-6 * max(1.0, abs(ref[k])), msg=k)


class Hinges714(unittest.TestCase):
    """BRAIN_SPEC 7.27: floor-margin and hand-acceleration hinges, hard clip of the targets."""

    def test_floor_hinge(self):
        calm = jnp.tile(jnp.asarray(MA.NEUTRAL_DEG), (60, 1))
        self.assertEqual(float(F.penalties(calm)["floor"]), 0.0)
        down = jnp.tile(jnp.asarray([0.0, 100.0, 0.0, 0.0, 0.0]), (60, 1))             # points under the plane
        self.assertGreater(float(F.penalties(down)["floor"]), 0.1)

    def test_floor_hinge_matches_report_margin(self):
        rng = np.random.default_rng(5)
        for _ in range(5):
            q = np.array([0.0, *rng.uniform(-100, 100, 3), 0.0])
            P = R.fk_points(q[None])[0]
            margin = min(P[1:5, 2].min() - R.FLOOR_M, P[5, 2] - R.FLOOR_M - R.DISC_M)
            self.assertAlmostEqual(float(F.penalties(jnp.tile(jnp.asarray(q), (60, 1)))["floor"]), max(0.0, -margin), places=9)

    def test_acc_hinge(self):
        t = np.arange(60) / 100.0
        slow = np.array(MA.NEUTRAL_DEG)[None] + np.stack([0 * t, 0 * t, 2 * np.sin(2 * np.pi * 0.5 * t), 0 * t, 0 * t], 1)
        self.assertEqual(float(F.penalties(jnp.asarray(slow))["acc"]), 0.0)
        shake = np.array(MA.NEUTRAL_DEG)[None] + np.stack([0 * t, 0 * t, 25 * np.sin(2 * np.pi * 3.0 * t), 0 * t, 0 * t], 1)
        self.assertGreater(float(F.penalties(jnp.asarray(shake))["acc"]), 0.0)

    def drive_far(self, cfg, secs, flip=None, noise=0.0):
        d, tgt, tv = F.arm_init(cfg, np.array(MA.NEUTRAL_DEG, float))
        step = jax.jit(lambda d, tgt, tv, t: F.arm_step(cfg, d, tgt, tv, t))
        rng = np.random.default_rng(0)
        held_max, q_max = np.zeros(3), np.zeros(3)
        for k in range(int(secs * 100)):
            sgn = 1.0 if flip is None or (k // flip) % 2 == 0 else -1.0
            t = jnp.asarray([0.0, sgn * 150.0, sgn * 150.0, sgn * 150.0, 0.0]) + rng.normal(0, noise, 5)
            d, tgt, tv, _ = step(d, tgt, tv, t)
            held_max = np.maximum(held_max, np.abs(np.asarray(tgt)[1:4]))
            q_max = np.maximum(q_max, np.abs(np.degrees(np.asarray(d.qpos))[1:4]))
        return held_max, q_max

    def test_hard_clip_holds_the_target_inside_the_range(self):
        on, off = {**OFF, "body": "v2f", "clip": True}, {**OFF, "body": "v2f"}
        held_on, q_on = self.drive_far(on, 6.0)                       # a target 40 deg beyond every limit, held 6 s
        held_off, q_off = self.drive_far(off, 6.0)
        self.assertLessEqual(float(held_on.max()), 110.0 - F.CLIP_MARGIN_DEG + 1e-9)             # the held target stops CLIP_MARGIN_DEG inside the range
        self.assertAlmostEqual(float(held_off.max()), 110.0, places=6)                           # without the option it stops at the range itself
        print("hard clip, target 150 deg held 6 s: max |q| per bend", q_on.round(3), "(no clip:", q_off.round(3), ")")
        self.assertLessEqual(float((q_on - 110.0).max()), 1e-9)       # and the joint does not pass the range (a held target beyond it: the wrist alone reaches 111.07 deg without the stop)

    def test_hard_clip_adversarial_excess_is_zero(self):
        _, q_on = self.drive_far({**OFF, "body": "v2f", "clip": True}, 15.0, flip=70, noise=3.0)
        excess = q_on - 110.0
        print("hard clip, adversarial episode (targets +-150 deg flipping every 0.7 s plus noise), max excess beyond +-110 deg per bend:", excess.round(6))
        self.assertLessEqual(float(excess.max()), 1e-9)               # without the stop: 0.557 deg at the elbow, 1.072 deg at the wrist

    def test_clip_off_by_default_and_identical(self):
        a = Switches.run_chunk_static({**OFF, "body": "v2f"})
        b = Switches.run_chunk_static({**OFF, "body": "v2f", "clip": False})
        self.assertTrue(np.array_equal(a["q"], b["q"]))


class FirstEpochM3f(unittest.TestCase):
    """WO13B's try 1 (body v2f, switches 2-4, jerk 0.03, switch 0.01) first epoch is reproduced with the new options off (~5 min)."""

    def test_first_epoch_matches_wo13b_try1(self):
        ref = json.load(open("/secondary/hyst-data/body/m3f/try1/result.json"))["hist"][0]
        toy = m3f.ToyF(TOY)
        C = M.load_cb()
        cfg = {"body": "v2f", "obs_lp": True, "phase_lp": True, "xfade": True}
        tr = m3f.Trainer(toy, C, cfg, 0.03, 1e-3, 40, 8, seed=0, log=lambda s: None, opts={"pen": True, "jerk": True, "sw": True}, w_jerk=0.03, w_sw=0.01)
        tr.calibrate()
        rec = tr.run_epoch()
        for k in ("dec_e", "dec_i", "energy_rel", "rms_speed", "kappa_mean", "rate_mult", "abs_delta", "clip_share", "critic_loss", "sigma_delta", "hand_v", "jolt", "lim", "jerk", "tv"):
            self.assertAlmostEqual(rec[k], ref[k], delta=1e-6 * max(1.0, abs(ref[k])), msg=k)


if __name__ == "__main__":
    unittest.main()
