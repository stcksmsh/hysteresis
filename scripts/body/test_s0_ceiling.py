"""Tests for s0_ceiling.py (WO21). Run from scripts/body with the body env: python -m unittest test_s0_ceiling"""
import math
import unittest

import numpy as np

import cpg
import s0_ceiling as C


class Analytic(unittest.TestCase):
    def test_jacobian_matches_a_pure_base_rotation(self):
        q = np.array([[30.0, 20.0, -10.0, 5.0, 0.0]])
        J = C.jacobian(q)[0]
        r = np.linalg.norm(C.hand_pos(q)[0, :2])
        self.assertAlmostEqual(np.linalg.norm(J[:, 0]), r, places=3)         # d(hand)/d(base yaw) = horizontal radius, m per rad

    def test_speed_at_single_joint_is_radius_times_rate(self):
        q = np.array([[0.0, 30.0, 30.0, 0.0, 0.0]])
        frac = np.array([1.0, 0.0, 0.0, 0.0, 0.0])
        r = np.linalg.norm(C.hand_pos(q)[0, :2])
        self.assertAlmostEqual(C.speed_at(q, frac)[0], r * math.radians(C.V[0]), places=3)

    def test_box_max_is_monotone_in_speed_fraction(self):
        lo, hi = np.full(5, -60.0), np.full(5, 60.0)
        a, _ = C.box_max(np.full(5, 0.5), lo, hi, n=3000)
        b, _ = C.box_max(np.full(5, 1.0), lo, hi, n=3000)
        self.assertAlmostEqual(b, 2 * a, delta=0.02 * b)

    def test_peak_of_a_known_circle(self):
        t = np.arange(500) / 50.0
        q = np.stack([20.0 * np.sin(2 * math.pi * 0.2 * t), np.zeros_like(t), np.zeros_like(t), np.zeros_like(t), np.zeros_like(t)], 1)
        i, v = C.peak(q)
        r = np.linalg.norm(C.hand_pos(q[:1])[0, :2])
        self.assertAlmostEqual(v, r * math.radians(20.0) * 2 * math.pi * 0.2, delta=0.01)


class Caps(unittest.TestCase):
    def test_frequency_caps_match_the_generator(self):
        amp = np.array([30.0, 20.0, 40.0, 10.0, 90.0])
        fs, fa = C.f_caps(amp)
        w = 2 * math.pi * (1 + cpg.COUPLING)
        self.assertTrue(np.allclose(fs, 0.8 * C.V / amp / w))
        self.assertTrue(np.allclose(fa, np.sqrt(cpg.ACC_SHARE * C.A / amp) / w))

    def test_at_peak_marks_the_binding_cap(self):
        T = 5
        g = {"centre": np.zeros((T, 5)), "amp": np.full((T, 5), 100.0), "freq": np.full((T, 5), 4.0), "tgt": np.zeros((T, 5)), "q": np.zeros((T, 5))}
        r = C.at_peak(g, 2)
        self.assertEqual(r["base_yaw"]["binding"], "speed_cap")             # 4 Hz is far above what 100 deg of amplitude allows under 0.8 V
        g["amp"][:] = 0.01
        self.assertEqual(C.at_peak(g, 2)["base_yaw"]["binding"], "F_MAX")   # a tiny amplitude lets the commanded 4 Hz through


if __name__ == "__main__":
    unittest.main()
