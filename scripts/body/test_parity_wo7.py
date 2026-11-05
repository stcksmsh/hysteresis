"""WO7 parity tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_parity_wo7   (JAX env).
Identical inputs and solver settings give identical output: the MJX arm twice, and the numpy ArmSim twice (bitwise)."""
import unittest

import numpy as np

import m3d
import parity_wo7 as W


class Parity(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(1)
        self.q0 = m3d.start_poses(2, 5)
        self.t = self.q0[:, None] + np.cumsum(rng.normal(0, 3, (2, 120, 5)), 1)         # 1.2 s of random-walk targets

    def test_mjx_deterministic(self):
        a, b = W.run_mjx(W.J.MX, self.q0, self.t), W.run_mjx(W.J.MX, self.q0, self.t)
        self.assertTrue(np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))

    def test_mujoco_deterministic(self):
        a, b = W.run_mujoco(self.q0, self.t), W.run_mujoco(self.q0, self.t)
        self.assertTrue(np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))

    def test_zero_difference_is_zero(self):
        a = W.run_mujoco(self.q0, self.t)[0]
        s = W.joint_stats(a, a)
        self.assertEqual(max(s["1s"]["max"]), 0.0)

    def test_block_descriptors_full_60s(self):
        q0 = m3d.start_poses(1, 5)
        q = q0[:, None] + 5 * np.sin(np.arange(W.STEPS)[None, :, None] / 40.0 + np.arange(5))      # (1, 6000, 5)
        d = W.block_descriptors(q, q0)
        self.assertEqual(d.shape, (1, m3d.NB - m3d.VALID_FROM, 31))
        self.assertTrue(np.isfinite(d).all())
        # window of the last block is exactly the last 201 frames of the trajectory
        self.assertTrue(np.allclose(d[0, -1], np.asarray(W.J.descriptors(W.J.window_frames(W.jnp.asarray(q[0, -201:]))))))


if __name__ == "__main__":
    unittest.main()
