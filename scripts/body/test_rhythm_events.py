"""Synthetic checks of WO52 rhythm ratio and event lock (docs/RHYTHM_EVENTS_RULES.md section 7); no human data."""
import unittest

import numpy as np

import rhythm_events as R

FS = 50
BEAT = 0.5


def circle_lamp(pulse_period, secs=3.0, seed=0):
    """lamp on a 0.3 m circle, angular speed 1 + 0.8 sin(2 pi t / pulse_period) rad/s -> lamp (n, 3)"""
    t = np.arange(int(secs * FS) + 1) / FS
    ph = np.random.default_rng(seed).uniform(0, 2 * np.pi)
    th = t + 0.8 * pulse_period / (2 * np.pi) * (1 - np.cos(2 * np.pi * t / pulse_period + ph))
    return np.stack([0.3 * np.cos(th), 0.3 * np.sin(th), np.full_like(t, 0.5)], 1)


def ratio_bin(lamp):
    sp = R.speeds(np.zeros((len(lamp), 5)), lamp)["lamp"][:150]
    p, s = R.rhythm(sp)
    return p / BEAT, int(R.bins(np.array([p / BEAT]), np.array([s]))[0])


class T(unittest.TestCase):
    def test_pulse_at_beat_is_one(self):
        for seed in range(5):
            r, b = ratio_bin(circle_lamp(BEAT, seed=seed))
            self.assertAlmostEqual(r, 1.0, delta=0.05)
            self.assertEqual(R.BIN_NAMES[b], "1")

    def test_pulse_at_two_beats_is_two(self):
        for seed in range(5):
            r, b = ratio_bin(circle_lamp(2 * BEAT, seed=seed))
            self.assertAlmostEqual(r, 2.0, delta=0.1)
            self.assertEqual(R.BIN_NAMES[b], "2")

    def test_swing_of_two_beats_gives_one(self):
        t = np.arange(151) / FS
        lamp = np.stack([0.3 * np.sin(2 * np.pi * t / (2 * BEAT)), np.zeros_like(t), np.zeros_like(t)], 1)
        r, b = ratio_bin(lamp)
        self.assertAlmostEqual(r, 1.0, delta=0.05)

    def test_noise_is_none(self):
        rng = np.random.default_rng(1)
        res = [R.bins(np.array([p / BEAT]), np.array([s]))[0] for p, s in (R.rhythm(rng.random(150)) for _ in range(200))]
        self.assertGreaterEqual(np.mean(np.array(res) == 0), 0.9)
        self.assertEqual(R.rhythm(np.zeros(150))[1], 0.0)

    def test_bins_edges(self):
        b = R.bins(np.array([0.4, 0.6, 0.61, 0.8, 1.25, 1.3, 1.6, 2.5, 2.6, 1.0]), np.array([1] * 9 + [0.1]))
        self.assertEqual([R.BIN_NAMES[i] for i in b], ["1/2", "1/2", "other", "1", "1", "other", "2", "2", "other", "none"])

    def test_event_lock_planted_lag(self):
        rng = np.random.default_rng(2)
        span = (0.0, 300.0)
        ev = np.sort(rng.uniform(5, 295, 80))
        resp = np.sort(np.r_[ev + 0.3, rng.uniform(0, 300, 40)])
        obs, n, ch = R.lock_counts(resp, ev, span, np.random.default_rng(3))
        ex = obs - ch.mean(0)
        self.assertEqual(n, 80)
        self.assertAlmostEqual(R.LAGS[int(np.argmax(ex))] + 0.05, 0.35, delta=1e-9)   # +0.3 s lands in bin [0.3, 0.4)
        sh = rng.uniform(5, 295, 80)
        obs2, _, ch2 = R.lock_counts(resp, sh, span, np.random.default_rng(3))
        self.assertLess((obs2 - ch2.mean(0)).max(), 0.5 * ex.max())

    def test_shift_stays_in_span(self):
        resp = np.array([10.2, 15.0, 19.9])
        obs, n, ch = R.lock_counts(resp, np.array([15.0]), (10.0, 20.0), np.random.default_rng(4), nshift=500)
        self.assertEqual(ch.shape, (500, 20))
        self.assertLessEqual(ch.sum(1).max(), 3)

    def test_segments(self):
        self.assertEqual(R.segments([0, 1, 3, 4, 5, 7]), [[0, 1], [3, 4, 5], [7]])


if __name__ == "__main__":
    unittest.main()
