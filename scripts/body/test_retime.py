"""Synthetic checks of scripts/body/retime.py (docs/RETIME_RULES.md)."""
import unittest

import numpy as np

import retime as RT


class T(unittest.TestCase):
    def test_pulse_lands_at_t_minus_L(self):
        rate = 50.0
        for v in ("V1", "V2"):
            for t in (1.0, 7.3, 15.02):
                x = np.zeros(int(20 * rate))
                x[int(round(t * rate))] = 1.0
                y, n = RT.retime(x, rate, v)
                self.assertEqual(n, len(y))
                self.assertEqual(n, len(x) - int(round(RT.L[v] * rate)))
                self.assertAlmostEqual(np.argmax(y) / rate, t - RT.L[v], delta=0.5 / rate + 1e-9)  # half a sample: round() of 17.5 samples

    def test_drops_tail_never_pads(self):
        x = np.arange(1000.0)
        y, n = RT.retime(x, 50.0, "V1")
        self.assertEqual(n, 1000 - 18)  # round(0.35 * 50) = 18 (17.5 rounds to even 18)
        self.assertEqual(y[0], 18.0)
        self.assertEqual(y[-1], 999.0)

    def test_2d_time_axis_0(self):
        x = np.arange(200.0).reshape(100, 2)
        y, n = RT.retime(x, 50.0, "V2")
        self.assertEqual(y.shape, (100 - 14, 2))

    def test_rows_start(self):
        self.assertAlmostEqual(RT.retime_rows_start(3.0, "V1"), 3.35)
        self.assertAlmostEqual(RT.retime_rows_start(3.0, "V2"), 3.28)


if __name__ == "__main__":
    unittest.main()
