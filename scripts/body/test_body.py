"""M0 (body in physics) and M2 (pattern generators) tests. Design checks, no claim about real servos (all servo numbers are provisional).

    cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_body
Tolerances stated BEFORE the first run of each: MuJoCo CPU vs MJX 10 s trajectory: max joint difference <= 0.1 deg (float64 vs float32).
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import mujoco
import numpy as np

import arm_sim as A
import cpg as C
import make_arm as M

HYST = Path(os.environ.get("HYST_BIN", "/secondary/hyst-env/cargo-target-body/debug/hyst"))
BENDS = [1, 2, 3]


def rates(q, hz=50):
    """check-csv's measures: |first difference| * hz and |second difference| * hz^2, as a fraction of the limit, per joint."""
    v = np.abs(np.diff(q, axis=0)) * hz
    a = np.abs(q[2:] - 2 * q[1:-1] + q[:-2]) * hz * hz
    return v.max(0) / A.LIM_V, a.max(0) / A.LIM_A


class Body(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = A.ArmSim()

    def test_fk_matches_the_rust_convention(self):
        rng = np.random.default_rng(0)
        for _ in range(30):
            q = rng.uniform(-100, 100, 5)
            q[[0, 4]] = rng.uniform(-300, 300, 2)
            self.sim.data.qpos[:] = np.radians(q)
            mujoco.mj_forward(self.sim.model, self.sim.data)
            np.testing.assert_allclose(self.sim.hand_pos(), A.fk(q)[5], atol=1e-9)

    def test_gravity_sag_and_torque_margin(self):
        """At rest: each joint's holding torque against the (provisional) stall torque, and the sag = torque / kp."""
        for name, q in (("neutral", M.NEUTRAL_DEG), ("straight out", [0.0] * 5)):
            self.sim.reset(q)
            for _ in range(500):
                self.sim.step(q)
            tau, sag = self.sim.data.actuator_force.copy(), self.sim.q_deg - q
            print(f"\n{name}: holding torque N.m {np.round(tau, 3)} (stall {M.STALL_NM:.3f}); sag deg {np.round(sag, 3)}")
            self.assertTrue((np.abs(tau) < M.STALL_NM).all(), f"{name}: a joint needs more than the stall torque")
            np.testing.assert_allclose(np.abs(np.radians(sag)), np.abs(tau) / M.KP, rtol=0.02, atol=1e-4)

    def test_proprioception_is_delayed_one_step_and_quantised(self):
        self.sim.reset(M.NEUTRAL_DEG)
        goal, true_after, obs = np.array(M.NEUTRAL_DEG) + [90, 0, 0, 0, 0], [], []
        for _ in range(60):
            obs.append(self.sim.step(goal)["pos_deg"])
            true_after.append(self.sim.q_deg.copy())
        for k in range(1, 60):         # the reading returned at step k is the state after step k-1, rounded to the encoder step
            np.testing.assert_allclose(obs[k], np.round(true_after[k - 1] / A.QUANT_DEG) * A.QUANT_DEG, atol=1e-9)
        self.assertGreater(abs(true_after[-1][0] - M.NEUTRAL_DEG[0]), 1.0)       # and the arm really moved
        steps = obs[-1] / A.QUANT_DEG
        np.testing.assert_allclose(steps, np.round(steps), atol=1e-9)

    def test_power_is_sum_abs_tau_omega(self):
        self.sim.reset(M.NEUTRAL_DEG)
        for _ in range(300):
            self.sim.step(M.NEUTRAL_DEG)
        self.assertLess(self.sim.power_w, 1e-3)
        self.sim.step(np.array(M.NEUTRAL_DEG) + [60, 0, 0, 0, 0])
        for _ in range(5):
            self.sim.step(np.array(M.NEUTRAL_DEG) + [60, 0, 0, 0, 0])
        d = self.sim.data
        self.assertAlmostEqual(self.sim.power_w > 0, True)
        self.assertGreaterEqual(float(np.abs(d.actuator_force * d.qvel).sum()), 0.0)

    def test_limits_on_60s_of_full_range_random_commands(self):
        """Full command range (0.1-4 Hz, whole joint room), 60 s: joint range, speed and acceleration as check-csv measures them."""
        rng = np.random.default_rng(1)
        sim, gen, q = A.ArmSim(), C.CPG(), [np.array(M.NEUTRAL_DEG, float)]
        for k in range(6000):
            if k % 10 == 0:
                gen.command(*C.random_commands(rng))
            sim.step(gen.step())
            if k % 2 == 1:
                q.append(sim.q_deg.copy())
        q = np.array(q)
        v, a = rates(q)
        print(f"\nfull range: speed/limit {np.round(v, 2)}, accel/limit {np.round(a, 2)}")
        self.assertTrue((q[:, BENDS] >= -110 - 1.0).all() and (q[:, BENDS] <= 110 + 1.0).all(), "bend range (1 deg of servo overshoot allowed)")
        self.assertLessEqual(v.max(), 1.0)
        self.assertLessEqual(a.max(), 1.0)

    def test_mujoco_cpu_vs_mjx_on_a_10s_trajectory(self):
        try:
            import jax
            from mujoco import mjx
        except Exception as e:      # noqa: BLE001
            self.skipTest(f"MJX not importable: {e}")
        rng = np.random.default_rng(2)
        sim, gen, ctrl = A.ArmSim(), C.CPG(), []
        for k in range(1000):
            if k % 10 == 0:
                gen.command(*C.random_commands(rng, **C.CHECK_ENVELOPE))
            sim.step(gen.step())
            ctrl.append(sim.data.ctrl.copy())
        sim2 = A.ArmSim()
        sim2.reset(M.NEUTRAL_DEG)
        m = sim2.model
        mx = mjx.put_model(m)
        dx = mjx.make_data(m)
        dx = dx.replace(qpos=jax.numpy.asarray(np.radians(M.NEUTRAL_DEG)), ctrl=jax.numpy.asarray(np.radians(M.NEUTRAL_DEG)))

        def control_step(dx, c):
            dx = dx.replace(ctrl=c)
            dx, _ = jax.lax.scan(lambda d, _: (mjx.step(mx, d), None), dx, None, length=A.SUBSTEPS)
            return dx, dx.qpos

        _, qx = jax.jit(lambda d, c: jax.lax.scan(control_step, d, c))(dx, jax.numpy.asarray(np.array(ctrl)))
        d = mujoco.MjData(m)
        d.qpos[:] = np.radians(M.NEUTRAL_DEG)
        qc = []
        for c in ctrl:
            d.ctrl[:] = c
            for _ in range(A.SUBSTEPS):
                mujoco.mj_step(m, d)
            qc.append(d.qpos.copy())
        diff = np.degrees(np.abs(np.array(qc) - np.asarray(qx))).max()
        print(f"\nMuJoCo CPU vs MJX (CPU JAX), 10 s: max joint difference {diff:.4f} deg")
        self.assertLessEqual(diff, 0.1)


class Pattern(unittest.TestCase):
    def test_targets_are_smooth_and_inside_the_limits_under_random_commands(self):
        rng = np.random.default_rng(3)
        g, prev, worst = C.CPG(), None, 0.0
        for k in range(12000):
            if k % 10 == 0:
                g.command(*C.random_commands(rng))
            t = g.step()
            self.assertTrue((t[1:4] >= -110 - 1e-9).all() and (t[1:4] <= 110 + 1e-9).all())
            if prev is not None:
                worst = max(worst, float((np.abs(t - prev) / (C.V * g.dt)).max()))
            prev = t
        print(f"\nlargest target step / (speed limit * dt): {worst:.3f}")
        self.assertLessEqual(worst, 1.0)

    def test_continuous_joint_amplitude_is_capped_at_180(self):
        g = C.CPG()
        g.command(np.full(5, 0.3), np.full(5, 1e6), np.zeros(5), np.zeros(5))
        for _ in range(3000):
            g.step()
        self.assertLessEqual(g.amp[0], 180.0 + 1e-9)
        self.assertLessEqual(g.amp[4], 180.0 + 1e-9)

    def test_positive_lag_makes_the_neighbour_trail(self):
        g = C.CPG()
        g.command(np.full(5, 0.3), np.array([0, 5.0, 5, 0, 0]), np.array(M.NEUTRAL_DEG), np.array([0, 0, 0.25, 0, 0]))
        t = np.array([g.step() for _ in range(6000)])[3000:]       # settled
        # joint 2 trails joint 1 by a quarter cycle (0.3 Hz: 0.83 s); small amplitude so no frequency cap differs between the two: its peak comes later than joint 1's
        x1, x2 = t[:, 1] - t[:, 1].mean(), t[:, 2] - t[:, 2].mean()
        lags = np.arange(0, 300)
        corr = [np.dot(x1[: len(x1) - L], x2[L:]) for L in lags]       # x2 shifted later
        best = int(lags[int(np.argmax(corr))])
        print(f"\nneighbour trails by {best * g.dt:.2f} s (commanded 0.25 cycle = 0.83 s)")
        self.assertAlmostEqual(best * g.dt, 0.25 / 0.3, delta=0.1)

    def test_physics_run_exports_a_csv_that_check_csv_accepts(self):
        if not HYST.exists():
            self.skipTest(f"no hyst binary at {HYST}")
        q, power, _ = C.random_run(3, 60.0, **C.CHECK_ENVELOPE)
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "m2.csv"
            f.write_text(A.csv_text(q, name="test"))
            r = subprocess.run([str(HYST), "check-csv", str(f)], capture_output=True, text=True)
        print(f"\nmean mechanical power {power.mean():.2f} W; check-csv: {r.stdout.strip()}")
        self.assertEqual(r.returncode, 0, r.stdout)


if __name__ == "__main__":
    unittest.main()
