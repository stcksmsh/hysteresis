import os
import sys
import unittest

import numpy as np
from scipy.ndimage import gaussian_filter1d

sys.path.insert(0, os.path.dirname(__file__))
import grfnn  # noqa: E402


def clicks(rate, dur, gap=None, width=0.03, height=4.0, start=0.25):
    """Click train as an onset-strength-like series: 100 Hz frames, each click a Gaussian bump of `width` s
    (the 46 ms STFT window smooths real onset strength about this much; a one-frame impulse has a flat spectrum
    and is not what the bank is driven with)."""
    x = np.zeros(int(dur * 100))
    times = []
    t = start
    while t < dur:
        if gap is None or not (gap[0] <= t < gap[1]):
            x[int(round(t * 100))] = 1.0
        times.append(t)
        t += 1.0 / rate
    x = gaussian_filter1d(x, width * 100)
    return height * x / x.max(), np.array(times)


def offsets(beats, times):
    return np.array([b - times[np.argmin(abs(times - b))] for b in beats])


class Bank(unittest.TestCase):
    def test_frequencies_are_log_spaced_from_a_quarter_to_eight_hz(self):
        f = grfnn.frequencies()
        self.assertEqual(len(f), 5 * 48 + 1)
        self.assertAlmostEqual(f[0], 0.25)
        self.assertAlmostEqual(f[-1], 8.0)
        r = f[1:] / f[:-1]
        self.assertTrue(np.allclose(r, r[0]))

    def test_entrains_to_a_click_train_at_2_hz_and_1_5_hz(self):
        for rate in (2.0, 1.5):
            x, times = clicks(rate, 40)
            r = grfnn.pulse(x, x)
            late = r["readout_freq"][2500:]
            self.assertAlmostEqual(float(np.median(late)), rate, delta=0.03 * rate, msg=rate)
            b = r["beats"][r["beats"] > 25]
            self.assertAlmostEqual(float(np.median(np.diff(b))), 1.0 / rate, delta=0.02 / rate)
            off = offsets(b, times)
            self.assertLess(float(off.std()), 0.04, (rate, off.std()))  # phase-locked: constant offset to the clicks
            self.assertGreater(float(r["readout_amp"][2500:].mean()), 0.2)

    def test_keeps_oscillating_through_a_4_s_silent_gap(self):
        x, times = clicks(2.0, 40, gap=(16, 20))
        self.assertLess(float(x[1630:1980].max()), 1e-3)  # the gap is silent in the input
        r = grfnn.pulse(x, x)
        before = r["readout_amp"][1550:1600].mean()
        end = r["readout_amp"][1950:2000].mean()
        self.assertGreater(end, 0.5 * before, (before, end))
        b = r["beats"]
        inside = b[(b > 17) & (b < 20)]
        self.assertGreaterEqual(len(inside), 5)                       # still produces beats, one per click period
        self.assertAlmostEqual(float(np.median(np.diff(inside))), 0.5, delta=0.015)
        ref = offsets(b[(b > 12) & (b < 15)], times).mean()           # the locked offset before the gap
        self.assertLess(float(abs(offsets(inside[-2:], times).mean() - ref)), 0.07)  # phase kept within 70 ms

    def test_is_deterministic(self):
        x, _ = clicks(2.0, 20)
        a, b = grfnn.pulse(x, x), grfnn.pulse(x, x)
        self.assertTrue(np.array_equal(a["beats"], b["beats"]))
        self.assertTrue(np.array_equal(a["amp"], b["amp"]))

    def test_input_is_standardised_summed_and_capped(self):
        rng = np.random.default_rng(0)
        a, b = rng.random(3000) * 7 + 3, rng.random(3000) * 0.1
        x = grfnn.bank_input(a, b)
        self.assertTrue((x >= 0).all() and (x <= grfnn.X_MAX).all())
        # each channel is standardised, so a 70-fold difference in scale changes nothing after the first seconds
        x2 = grfnn.bank_input(a * 70.0, b)
        self.assertTrue(np.allclose(x[1500:], x2[1500:], atol=0.02))


class Readout(unittest.TestCase):
    def synthetic(self, amp_b, frames=1200):
        """two oscillators in the beat band, 1 Hz and 2 Hz; phase advances at their own frequency."""
        freqs = np.array([1.0, 2.0])
        t = np.arange(frames) / 100.0
        phase = np.angle(np.exp(2j * np.pi * (np.outer(t, freqs) - 0.25)))
        amp = np.stack([np.full(frames, 1.0), amp_b], axis=1)
        return freqs, amp, phase

    def test_beats_are_upward_phase_zero_crossings(self):
        freqs, amp, phase = self.synthetic(np.full(1200, 0.5))
        beats, chosen, _, f = grfnn.readout(freqs, amp, phase)
        self.assertTrue((chosen == 0).all())
        self.assertTrue(np.allclose(beats, 0.25 + np.arange(len(beats)), atol=0.011))

    def test_switches_only_after_2_s_at_more_than_20_percent(self):
        n = 1200
        for ratio, frames, expect in [(1.19, 1000, False), (1.25, 150, False), (1.25, 205, True)]:
            amp_b = np.full(n, 0.5)
            amp_b[100:100 + frames] = ratio
            freqs, amp, phase = self.synthetic(amp_b)
            _, chosen, _, _ = grfnn.readout(freqs, amp, phase)
            self.assertEqual(bool((chosen == 1).any()), expect, (ratio, frames))
        # an interruption resets the run
        amp_b = np.full(n, 0.5)
        amp_b[100:250] = 1.25
        amp_b[250] = 1.0
        amp_b[251:350] = 1.25
        freqs, amp, phase = self.synthetic(amp_b)
        self.assertFalse((grfnn.readout(freqs, amp, phase)[1] == 1).any())
        # it switches at the end of the 2 s, not before
        amp_b = np.full(n, 0.5)
        amp_b[100:600] = 1.25
        freqs, amp, phase = self.synthetic(amp_b)
        chosen = grfnn.readout(freqs, amp, phase)[1]
        first = int(np.flatnonzero(chosen == 1)[0])
        self.assertTrue(299 <= first <= 301, first)


if __name__ == "__main__":
    unittest.main()
