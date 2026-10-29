import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import fast_features as ff  # noqa: E402
import gaps  # noqa: E402
import grfnn  # noqa: E402

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

    def test_a_click_train_gap_is_rejected_and_a_silent_one_is_valid(self):
        rng = np.random.default_rng(0)
        x = np.abs(rng.standard_normal(3000)) * 0.1
        x[1200:1600] = 0.0
        for k in range(1200, 1600, 50):                       # 2 Hz clicks inside the gap
            x[k:k + 4] = 0.5
        valid, stat, thr = gaps.gap_valid(x, 12.0, 4.0, "c", "noise")
        self.assertFalse(valid)
        self.assertGreater(stat, thr)
        silent = np.zeros(3000)
        self.assertEqual(gaps.gap_valid(silent, 12.0, 4.0, "c", "silence"), (True, 0.0, 0.0))
        # a real silence gap through the whole pipeline: finite input, valid
        y = music()
        out = gaps.make_gap(y, SR, 12.0, 4.0, "silence")
        p = grfnn.pulse(*(lambda f: (f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET]))(ff.fast_features(out)))
        self.assertTrue(np.isfinite(p["input"]).all() and np.isfinite(p["amp"]).all())
        self.assertTrue(gaps.gap_valid(p["input"], 12.0, 4.0, "c", "silence")[0])
        # the same clip with the music left in the gap (a click train in the input) is rejected
        pm = grfnn.pulse(*(lambda f: (f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET]))(ff.fast_features(y)))
        self.assertFalse(gaps.gap_valid(pm["input"], 12.0, 4.0, "c", "noise")[0])

    def test_linear_detrending_removes_a_ramp_but_the_gated_test_is_unchanged(self):
        rng = np.random.default_rng(3)
        ramp = np.linspace(0.0, 1.0, 1000)
        rejected_plain = rejected_detrended = 0
        for k in range(60):
            x = np.abs(rng.standard_normal(1000)) * 0.3 + ramp
            rejected_plain += not gaps.gap_valid(x, 2.0, 4.0, f"r{k}", "noise")[0]
            rejected_detrended += not gaps.gap_valid(x, 2.0, 4.0, f"r{k}", "noise", detrend=True)[0]
        self.assertGreater(rejected_plain, 40)           # the ramp looks like rhythm to the autocorrelation
        self.assertLess(rejected_detrended, 12)          # about 5 % once the trend is out
        self.assertEqual(gaps.gap_valid(np.zeros(1000), 2.0, 4.0, "z", "silence", detrend=True), (True, 0.0, 0.0))
        self.assertEqual(gaps.gap_valid(np.full(1000, 0.7), 2.0, 4.0, "z", "silence", detrend=True), (True, 0.0, 0.0))

    def test_white_noise_passes_at_about_95_percent_and_the_seed_is_per_clip(self):
        passes = 0
        for seed in range(200):
            x = np.abs(np.random.default_rng(seed).standard_normal(1000))
            passes += gaps.gap_valid(x, 2.0, 4.0, f"clip{seed}", "noise")[0]
        self.assertTrue(0.90 <= passes / 200 <= 0.995, passes)
        x = np.abs(np.random.default_rng(1).standard_normal(1000))
        a = gaps.gap_valid(x, 2.0, 4.0, "same", "noise")
        self.assertEqual(a, gaps.gap_valid(x, 2.0, 4.0, "same", "noise"))
        self.assertNotEqual(a[2], gaps.gap_valid(x, 2.0, 4.0, "other", "noise")[2])

    def test_shaped_noise_gaps_pass_at_about_95_percent_through_the_pipeline(self):
        y = music()
        passes, n = 0, 40
        for k in range(n):
            out = gaps.make_gap(y, SR, 12.0, 4.0, "noise", clip_id=f"shaped{k}")
            f = ff.fast_features(out)
            p = grfnn.pulse(f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET])
            passes += gaps.gap_valid(p["input"], 12.0, 4.0, f"shaped{k}", "noise")[0]
        self.assertGreaterEqual(passes / n, 0.85, passes)


if __name__ == "__main__":
    unittest.main()
