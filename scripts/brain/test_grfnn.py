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
    """The round-2 readout: S = A * P(f), P(f) = exp(-2 (log2(f / 2 Hz))^2); argmax S with hysteresis on S."""

    @staticmethod
    def synthetic(freqs, amps, frames=1200):
        """oscillators at `freqs` (Hz) with amplitude series `amps` (frames x oscillators); phase advances at the oscillator's own frequency."""
        freqs = np.asarray(freqs, float)
        t = np.arange(frames) / 100.0
        phase = np.angle(np.exp(2j * np.pi * (np.outer(t, freqs) - 0.25)))
        return freqs, np.asarray(amps, float), phase

    def test_the_prior_is_one_at_2_hz_and_falls_by_octaves(self):
        p = grfnn.pulse_prior([0.5, 1.0, 2.0, 3.0, 4.0])
        self.assertAlmostEqual(p[2], 1.0)
        self.assertAlmostEqual(p[1], np.exp(-2.0))
        self.assertAlmostEqual(p[4], np.exp(-2.0))
        self.assertAlmostEqual(p[0], np.exp(-8.0))
        self.assertAlmostEqual(p[3], np.exp(-2.0 * np.log2(1.5) ** 2))

    def test_equal_amplitudes_at_2_and_4_hz_read_out_2_hz(self):
        freqs, amp, phase = self.synthetic([2.0, 4.0], np.full((1200, 2), 0.5))
        _, chosen, _, f = grfnn.readout(freqs, amp, phase)
        self.assertTrue((f == 2.0).all() and (chosen == 0).all())

    def test_a_strong_3_hz_oscillator_wins_where_the_score_says_so(self):
        # S(3 Hz) = 0.5 * 0.505 = 0.2525 > S(2 Hz) = 0.2; a weak 3 Hz one (0.3 * 0.505 = 0.15) loses
        strong = self.synthetic([2.0, 3.0], np.tile([0.2, 0.5], (1200, 1)))
        weak = self.synthetic([2.0, 3.0], np.tile([0.2, 0.3], (1200, 1)))
        self.assertTrue((grfnn.readout(*strong)[3] == 3.0).all())
        self.assertTrue((grfnn.readout(*weak)[3] == 2.0).all())
        # the amplitude returned is the oscillator's own, not the score
        self.assertTrue(np.allclose(grfnn.readout(*strong)[2], 0.5))

    def test_beats_are_upward_phase_zero_crossings_of_the_selected_oscillator(self):
        freqs, amp, phase = self.synthetic([1.0, 2.0], np.tile([0.1, 0.9], (1200, 1)))
        beats, chosen, _, f = grfnn.readout(freqs, amp, phase)
        self.assertTrue((chosen == 1).all())
        self.assertTrue(np.allclose(beats, 0.125 + 0.5 * np.arange(len(beats)), atol=0.011))

    def test_hysteresis_applies_to_the_score_20_percent_for_2_s(self):
        prior = grfnn.pulse_prior([2.0, 2.0001])             # equal priors, so S ratios are amplitude ratios
        n = 1200

        def run(ratio, frames, interrupt=None):
            amp = np.tile([1.0, 0.5], (n, 1))                # oscillator 0 is the readout
            amp[100:100 + frames, 1] = ratio
            if interrupt is not None:
                amp[interrupt, 1] = 0.5
            return grfnn.readout(*self.synthetic([2.0, 2.0001], amp))[1]

        self.assertFalse((run(1.19, 1000) == 1).any())        # 19 % for ever: never
        self.assertFalse((run(1.25, 150) == 1).any())         # 25 % for 1.5 s: not yet
        self.assertTrue((run(1.25, 205) == 1).any())          # 25 % for 2.05 s: switches
        self.assertFalse((run(1.25, 300, interrupt=200) == 1).any())   # an interruption resets the run
        first = int(np.flatnonzero(run(1.25, 500) == 1)[0])
        self.assertTrue(299 <= first <= 301, first)           # it switches at the end of the 2 s
        # the prior counts: a 25 % larger amplitude at 4 Hz does not beat the 2 Hz readout
        amp = np.tile([1.0, 1.25], (n, 1))
        self.assertFalse((grfnn.readout(*self.synthetic([2.0, 4.0], amp))[1] == 1).any())

    def test_readout_is_deterministic(self):
        x, _ = clicks(2.0, 20)
        a, b = grfnn.pulse(x, x), grfnn.pulse(x, x)
        self.assertTrue(np.array_equal(a["readout_index"], b["readout_index"]) and np.array_equal(a["beats"], b["beats"]))


if __name__ == "__main__":
    unittest.main()
