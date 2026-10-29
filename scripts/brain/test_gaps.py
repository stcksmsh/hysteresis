import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import fast_features as ff  # noqa: E402
import gaps  # noqa: E402

SR = ff.SR


def music(seconds=30.0, seed=0):
    """120 bpm pulses (a 80 Hz thump and a noisy tick) over a coloured bed: something with onsets and a spectrum."""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    y = 0.02 * rng.standard_normal(n).astype(np.float32)
    t = np.arange(int(0.2 * SR)) / SR
    hit = (0.6 * np.sin(2 * np.pi * 80 * t) * np.exp(-t * 25) + 0.2 * rng.standard_normal(len(t)) * np.exp(-t * 60)).astype(np.float32)
    for k in range(int(seconds * 2)):
        a = int(k * 0.5 * SR)
        y[a:a + len(hit)] += hit[:max(0, min(len(hit), n - a))]
    return y


class Gaps(unittest.TestCase):
    def test_gap_start_is_after_10_s_inside_the_clip_and_fixed_by_the_seed(self):
        for g in gaps.GAPS:
            for kind in gaps.KINDS:
                s = gaps.gap_start("ballroom/x", g, kind, 30.0)
                if g == 8.0:
                    self.assertTrue(10.0 <= s <= 30.0 - 8.0 - gaps.MARGIN_S)
                else:
                    self.assertTrue(10.0 <= s <= 30.0 - g - gaps.MARGIN_S)
                self.assertEqual(s, gaps.gap_start("ballroom/x", g, kind, 30.0))
        self.assertNotEqual(gaps.gap_start("a", 4.0, "silence", 30.0), gaps.gap_start("b", 4.0, "silence", 30.0))
        self.assertIsNone(gaps.gap_start("short", 8.0, "silence", 18.0))
        self.assertEqual(gaps.SEED, 20261029)

    def test_silence_gap_is_zero_inside_and_untouched_outside(self):
        y = music()
        out = gaps.make_gap(y, SR, 12.0, 4.0, "silence")
        a, b, x = 12 * SR, 16 * SR, int(gaps.XFADE_S * SR)
        self.assertEqual(out.shape, y.shape)
        self.assertTrue(np.array_equal(out[:a], y[:a]) and np.array_equal(out[b:], y[b:]))
        self.assertEqual(float(np.abs(out[a + x:b - x]).max()), 0.0)
        # crossfade: monotone fade of the music, no click at the joins
        for lo, hi in ((a - 5, a + x), (b - x, b + 5)):
            self.assertLessEqual(float(np.abs(np.diff(out[lo:hi])).max()), float(np.abs(np.diff(y[lo:hi])).max()) + 1e-6)

    def test_noise_gap_has_the_spectrum_and_level_of_the_two_seconds_before(self):
        y = music()
        out = gaps.make_gap(y, SR, 12.0, 4.0, "noise", clip_id="t")
        a, b, x = 12 * SR, 16 * SR, int(gaps.XFADE_S * SR)
        self.assertTrue(np.array_equal(out[:a], y[:a]) and np.array_equal(out[b:], y[b:]))
        before, inside = y[a - 2 * SR:a], out[a + x:b - x]
        self.assertAlmostEqual(float(inside.std()), float(before.std()), delta=0.1 * float(before.std()))
        sb = np.abs(np.fft.rfft(before[:2 ** 16])) ** 2
        si = np.abs(np.fft.rfft(inside[:2 ** 16])) ** 2
        k = np.ones(256) / 256
        lb, li = np.log(np.convolve(sb, k, "valid") + 1e-9)[::128], np.log(np.convolve(si, k, "valid") + 1e-9)[::128]
        self.assertGreater(float(np.corrcoef(lb, li)[0, 1]), 0.9)
        self.assertEqual(gaps.make_gap(y, SR, 12.0, 4.0, "noise", clip_id="t").tobytes(), out.tobytes())  # seeded

    def test_onset_rule_passes_a_silent_gap_and_fails_a_gap_with_a_beat_in_it(self):
        y = music()
        f0 = ff.fast_features(y)
        ok, inside, limit = gaps.onset_ok(ff.fast_features(gaps.make_gap(y, SR, 12.0, 4.0, "silence")), f0, 12.0, 4.0)
        self.assertTrue(ok, (inside, limit))
        self.assertGreater(limit, 0.0)
        # the same clip with the gap not cut: its onset strength inside is far above 5 % of the median
        ok2, inside2, limit2 = gaps.onset_ok(f0, f0, 12.0, 4.0)
        self.assertFalse(ok2, (inside2, limit2))

    def test_noise_gap_onset_is_reported_either_way(self):
        y = music()
        f0 = ff.fast_features(y)
        ok, inside, limit = gaps.onset_ok(ff.fast_features(gaps.make_gap(y, SR, 12.0, 4.0, "noise", clip_id="t")), f0, 12.0, 4.0)
        self.assertIsInstance(ok, bool)
        self.assertTrue(np.isfinite(inside) and np.isfinite(limit))


if __name__ == "__main__":
    unittest.main()
