"""Tests of the smoothing control (smoothing.py). Synthetic data only."""
import unittest

import numpy as np

import smoothing as sm


class SmoothingTests(unittest.TestCase):
    def setUp(self):
        self.p = np.random.default_rng(0).normal(size=(40, 2))

    def test_tau_zero_and_lag_zero_is_the_identity(self):
        np.testing.assert_array_equal(sm.smooth_delay(self.p, 0.0, 0.0), self.p)

    def test_the_recursion(self):
        a = np.exp(-0.5 / 2.0)
        expected, carry = np.empty_like(self.p), self.p[0]
        for t in range(len(self.p)):
            carry = a * carry + (1 - a) * self.p[t]
            expected[t] = carry
        np.testing.assert_allclose(sm.smooth_delay(self.p, 2.0, 0.0), expected, atol=1e-12)
        self.assertEqual(sm.smooth_delay(self.p[:, 0], 2.0, 0.0).shape, (40,))

    def test_it_is_causal(self):
        for tau, lag in ((0.0, 1.0), (4.0, 0.0), (8.0, 2.5), (0.5, 4.0)):
            before = sm.smooth_delay(self.p, tau, lag)
            changed = self.p.copy()
            changed[25:] += 7.0
            after = sm.smooth_delay(changed, tau, lag)
            np.testing.assert_array_equal(before[:25], after[:25])
            self.assertFalse(np.allclose(before[25:], after[25:]) and tau > 0 and lag == 0)

    def test_the_delay_shifts_by_exactly_lag_over_hop_steps(self):
        out = sm.smooth_delay(self.p, 0.0, 1.5)
        np.testing.assert_array_equal(out[3:], self.p[:-3])
        np.testing.assert_array_equal(out[:3], np.repeat(self.p[:1], 3, axis=0))
        both = sm.smooth_delay(self.p, 4.0, 2.0)
        np.testing.assert_allclose(both[4:], sm.smooth_delay(self.p, 4.0, 0.0)[:-4])

    def test_a_constant_stays_constant_and_a_step_rises_slowly(self):
        np.testing.assert_allclose(sm.smooth_delay(np.full(20, 0.3), 8.0, 1.0), 0.3)
        step = np.r_[np.zeros(10), np.ones(30)]
        slow, fast = sm.smooth_delay(step, 16.0, 0.0), sm.smooth_delay(step, 0.5, 0.0)
        self.assertLess(slow[15], fast[15])
        self.assertTrue((np.diff(slow[10:]) >= 0).all())

    def test_the_grids_are_those_of_the_note(self):
        self.assertEqual(sm.TAUS, (0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0))
        self.assertEqual(sm.LAGS, (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0))


if __name__ == "__main__":
    unittest.main()
