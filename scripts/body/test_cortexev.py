"""Synthetic checks of the cortexev detectors and scoring (no song audio)."""
import unittest

import numpy as np

import cortexev as C


class T(unittest.TestCase):
    def test_dropout_and_drop(self):
        rng = np.random.default_rng(0)
        n = 600
        L = 1 + 0.1 * rng.random(n)
        O = 1 + 0.1 * rng.random(n)
        F = 0.1 + 0.02 * rng.random(n)
        L[300:330] = 0.01
        O[300:330] = 0.01
        F[330] = 2.0
        on, end = C.dropouts(L, O)
        self.assertEqual(on.tolist(), [300])
        self.assertEqual(end.tolist(), [330])
        self.assertEqual(C.drops(L, F).tolist(), [330])

    def test_short_gap_is_not_a_dropout(self):
        L, O = np.ones(300), np.ones(300)
        L[200:203] = O[200:203] = 0.0
        self.assertEqual(len(C.dropouts(L, O)[0]), 0)

    def test_peaks_and_counts(self):
        x = np.zeros(400)
        x[[100, 250]] = 5.0
        span = np.ones(400, bool)
        self.assertEqual(C.peaks(x, span).tolist(), [100, 250])
        c = C.counts([10.0, 25.0], [10.4, 40.0], 0.5)
        self.assertEqual(c.tolist(), [1, 2, 1, 2])
        self.assertAlmostEqual(float(C.f1(c)[0]), 0.5)
        s = C.shifted_counts(np.array([[10.0, 25.0]]), [10.4, 40.0], 0.5)
        self.assertEqual(s[0].tolist(), c.tolist())


if __name__ == "__main__":
    unittest.main()
