"""WO35: v3_lib known-value tests. Run: python -m unittest test_v3_lib (body env)."""
import unittest

import numpy as np

import v3_lib as L


class Lib(unittest.TestCase):
    def test_pos_measures_on_a_known_sine(self):
        t = np.arange(2000) / 100.0
        X = np.stack([0.2 * np.sin(2 * np.pi * 2 * t), 0 * t, 0.1 * np.sin(2 * np.pi * 2 * t)], 1)          # 2 Hz on x and z, still on y
        m = L.pos_measures(X, 100.0)
        self.assertAlmostEqual(m["flips_per_s"]["x"], 4.0, delta=0.15)
        self.assertAlmostEqual(m["flips_per_s"]["z"], 4.0, delta=0.15)
        self.assertEqual(m["flips_per_s"]["y"], 0.0)
        self.assertAlmostEqual(m["flips_mean"], 8.0 / 3, delta=0.1)
        self.assertLess(m["p_gt3"], 0.05)

    def test_power_split(self):
        t = np.arange(2000) / 100.0
        X = np.stack([0.05 * np.sin(2 * np.pi * 8 * t), 0 * t, 0 * t], 1)
        m = L.pos_measures(X, 100.0)
        self.assertGreater(m["p_gt6"], 0.9)

    def test_fk_t_pose_wrist_and_head(self):
        """with identity rotations the canonical skeleton is the T-pose: right wrist 0.67 m to the right of the spine, head straight above"""
        import tempfile
        a = np.zeros((2, 315))
        a[:, 3:] = np.tile(np.array([1, 0, 0, 0, 1, 0], float), 52)[None]                                 # identity 6D (first two rows)
        d = tempfile.mkdtemp()
        (L.Path(d) / "motion").mkdir()
        np.save(L.Path(d) / "motion" / "000.npy", a)
        old, L.FD = L.FD, L.Path(d)
        try:
            P, G = L.fk("000")
        finally:
            L.FD = old
        self.assertTrue(np.allclose(P[0, 0], [0, 0.95, 0]))
        self.assertAlmostEqual(P[0, 21, 0], -(0.04 + 0.12 + 0.26 + 0.25), places=6)                          # right wrist: -x (the subject's right)
        self.assertAlmostEqual(P[0, 21, 1], 0.95 + 0.11 + 0.13 + 0.05 + 0.19, places=6)
        self.assertAlmostEqual(P[0, 15, 0], 0.0, places=6)
        self.assertGreater(P[0, 15, 1], P[0, 21, 1])


if __name__ == "__main__":
    unittest.main()
