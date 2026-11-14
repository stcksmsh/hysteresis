"""WO33: the jitter measures return known values on synthetic signals. Run: python -m unittest test_jitter_diag (body env)."""
import unittest

import numpy as np

import jitter_diag as J


def sine(f, fs=100.0, amp=10.0, dur=20.0):
    t = np.arange(round(dur * fs)) / fs
    return amp * np.sin(2 * np.pi * f * t)


class Measures(unittest.TestCase):
    def test_sign_changes_of_a_sine_are_two_per_period(self):
        m = J.measures(sine(2.0), 100.0)
        self.assertAlmostEqual(m["acc_sign_changes_per_s"], 4.0, delta=0.15)           # acceleration of a 2 Hz sine changes sign 4 times a second

    def test_jerk_rms_of_a_sine(self):
        A, f = 10.0, 2.0
        m = J.measures(sine(f, amp=A), 100.0)
        self.assertAlmostEqual(m["jerk_rms"] / (A * (2 * np.pi * f) ** 3 / np.sqrt(2)), 1.0, delta=0.02)

    def test_jerk_rms_of_a_cubic_is_its_constant_jerk(self):
        t = np.arange(2000) / 100.0
        m = J.measures(2.0 * t ** 3, 100.0)                                              # x = 2 t^3 -> jerk = 12 deg/s^3 everywhere
        self.assertAlmostEqual(m["jerk_rms"], 12.0, delta=0.05)
        self.assertEqual(m["acc_sign_changes_per_s"], 0.0)

    def test_power_shares_split_at_3_and_6_hz(self):
        low = J.measures(sine(1.0), 100.0)
        mid = J.measures(sine(4.5), 100.0)
        high = J.measures(sine(8.0), 100.0)
        self.assertLess(low["p_gt3"], 0.05)
        self.assertGreater(mid["p_gt3"], 0.9)
        self.assertLess(mid["p_gt6"], 0.05)
        self.assertGreater(high["p_gt6"], 0.9)

    def test_same_sine_at_30_fps_gives_the_same_values(self):
        a, b = J.measures(sine(2.0, 100.0), 100.0), J.measures(sine(2.0, 30.0), 30.0)
        self.assertAlmostEqual(a["acc_sign_changes_per_s"], b["acc_sign_changes_per_s"], delta=0.2)
        self.assertAlmostEqual(a["jerk_rms"], b["jerk_rms"], delta=0.03 * a["jerk_rms"])

    def test_h2_share_and_flips(self):
        lim = np.array([1000.0] * 5)
        n = 600
        t = np.arange(n) / 100.0
        L = np.zeros((n, 5))
        # bang-bang position: acceleration alternates +-a with period 1 s -> 2 flips per second, always at the limit
        a = np.where(np.floor(t / 0.5) % 2 == 0, 1000.0, -1000.0)
        v = np.cumsum(a) / 100.0
        L[:, 1] = np.cumsum(v) / 100.0
        r = J.h2(L, lim, 0)[1]
        self.assertGreater(r["share_ge_0p98_100hz"], 0.95)
        self.assertAlmostEqual(r["acc_sign_flips_per_s"], 2.0, delta=0.3)


if __name__ == "__main__":
    unittest.main()
