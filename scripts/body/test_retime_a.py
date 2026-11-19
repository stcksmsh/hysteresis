"""Synthetic checks of the WO55 part A wrappers (docs/RETIME_RULES.md); no human data."""
import unittest

import numpy as np

import retime as RT
import retime_a as RA


def lagged_lamp(lag, beat=1.0, secs=60.0):
    """lamp moving along x whose speed has its minima `lag` s after every beat (n beat) -> (lamp (T, 3), beats)"""
    t = np.arange(int(secs * 50)) / 50.0
    sp = 1.0 - np.cos(2 * np.pi * (t - lag) / beat) + 0.05
    x = np.cumsum(sp) / 50.0
    return np.stack([x, np.zeros_like(x), np.zeros_like(x)], 1), np.arange(1.0, secs - 1.0, beat)


class T(unittest.TestCase):
    def test_bas_recovers_lag(self):
        lamp, beats = lagged_lamp(RT.L["V1"])
        grids = dict(proj=beats, lib=beats)
        o = RA.lamp_bas(lamp, grids, len(lamp) / 50, np.random.default_rng(1))
        lr, n = RT.retime(lamp, 50, "V1")
        r = RA.lamp_bas(lr, grids, n / 50, np.random.default_rng(1))
        self.assertLess(o["lib|music"][0], 0.1)
        self.assertGreater(r["lib|music"][0], 0.95)
        self.assertGreater(r["lib|music"][0] - r["lib|music"][1], 0.5)

    def test_var_of(self):
        self.assertEqual(RA.var_of("fd_001__V1.npz"), "V1")
        self.assertEqual(RA.var_of("aioz_x_p2__V2m"), "V2")

    def test_outside(self):
        self.assertEqual(RA.outside(0.5, [0.4, 0.3, 0.6]), 0.0)
        self.assertAlmostEqual(RA.outside(0.7, [0.4, 0.3, 0.6]), 0.1)
        self.assertAlmostEqual(RA.outside(0.1, [0.4, 0.3, 0.6]), 0.2)

    def test_interval_mean(self):
        ts = (10 * np.arange(100) + 9) / 100.0
        f = np.arange(100.0)
        cs = np.r_[0.0, np.cumsum(f)]
        m = RA.interval_mean(ts, cs, np.array([0.0, 1.0, 50.0]), np.array([0.5, 1.5, 51.0]))
        self.assertAlmostEqual(m[0], np.mean(f[ts < 0.5]))
        self.assertAlmostEqual(m[1], np.mean(f[(ts >= 1.0) & (ts < 1.5)]))
        self.assertTrue(np.isnan(m[2]))

    def test_token_controls(self):
        ctl = np.zeros((6, 18))
        ctl[:, 14] = [0, 0.3, 0.5, 0, 0.25, 0.1]
        ctl[:, 15] = [1, 0, 1, 1, 1, 1]
        ctl[:, 10] = 0.7
        c = RA.token_controls(ctl)
        np.testing.assert_array_equal(c["pause_on"][1:], [1, 0, 0, 1, 0])
        self.assertTrue(np.isnan(c["pause_on"][0]))
        self.assertTrue(np.isnan(c["sharp"][1]))
        self.assertEqual(c["sharp"][0], 0.7)

    def test_retimed_alignment_moves_correlation_peak_by_L(self):
        """a control series that follows a music feature 0.35 s late peaks at lag -0.35 originally and near 0 re-timed (token-interval sampling)"""
        rng = np.random.default_rng(3)
        ts = (10 * np.arange(3000) + 9) / 100.0
        f = np.convolve(rng.standard_normal(3000), np.ones(5) / 5, "same")
        cs = np.r_[0.0, np.cumsum(f)]
        tt = np.arange(2.0, 290.0, 0.5)
        x = RA.interval_mean(ts, cs, tt - 0.35, tt + 0.15)   # control of token k = music over [t_k - L, t_k - L + 0.5)
        peaks = {}
        for name, d in (("orig", 0.0), ("ret", 0.35)):
            r = []
            for lag in RA.CLAGS:
                y = RA.interval_mean(ts, cs, tt - d + lag, tt - d + lag + 0.5)
                r.append(np.corrcoef(x, y)[0, 1])
            peaks[name] = RA.CLAGS[int(np.argmax(np.abs(r)))]
        self.assertAlmostEqual(peaks["orig"], -0.3, delta=0.11)
        self.assertAlmostEqual(peaks["ret"], 0.0, delta=0.11)


if __name__ == "__main__":
    unittest.main()
