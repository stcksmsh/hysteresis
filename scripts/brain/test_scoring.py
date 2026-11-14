import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import scoring  # noqa: E402


def grid(period=0.5, n=80, offset=0.3):
    return offset + period * np.arange(n)


class Metrics(unittest.TestCase):
    def test_perfect_shifted_and_double_time_beats(self):
        ref = grid()
        m = scoring.beat_metrics(ref, ref)
        self.assertAlmostEqual(m["f"], 1.0)
        self.assertAlmostEqual(m["cmlt"], 1.0)
        self.assertAlmostEqual(m["amlt"], 1.0)
        self.assertAlmostEqual(m["phase_ms"], 0.0)
        self.assertAlmostEqual(m["tempo_error"], 0.0)
        off = scoring.beat_metrics(ref, ref + 0.2)            # a fifth of a second late: outside +-70 ms
        self.assertLess(off["f"], 0.05)
        self.assertAlmostEqual(off["phase_ms"], 200.0, delta=1.0)
        dbl = scoring.beat_metrics(ref, grid(0.25, 160))      # double time: AMLt allows it, CMLt does not
        self.assertGreater(dbl["amlt"], 0.9)
        self.assertLess(dbl["cmlt"], 0.1)
        self.assertAlmostEqual(dbl["tempo_error"], 1.0, delta=0.01)
        self.assertEqual(scoring.beat_metrics(ref, [])["f"], 0.0)

    def test_beats_before_five_seconds_are_dropped(self):
        ref = grid()
        est = np.concatenate([np.arange(0.1, 4.9, 0.37), ref[ref >= 5.0]])
        self.assertAlmostEqual(scoring.beat_metrics(ref, est)["f"], 1.0)


class Bootstrap(unittest.TestCase):
    def test_interval_covers_the_mean_and_is_seeded(self):
        x = np.random.default_rng(0).normal(0.3, 0.1, 400)
        lo, hi = scoring.bootstrap(lambda i: x[i].mean(), len(x))
        self.assertTrue(lo < x.mean() < hi and hi - lo < 0.05)
        self.assertEqual((lo, hi), scoring.bootstrap(lambda i: x[i].mean(), len(x)))

    def test_gate1_passes_an_equal_tracker_and_fails_a_worse_one(self):
        rng = np.random.default_rng(1)
        base = rng.uniform(0.4, 0.9, 300)
        pll = {"ballroom": {"f": base, "amlt": base}, "gtzan": {"f": base, "amlt": base}}
        same = {k: {m: base + rng.normal(0, 0.02, 300) for m in v} for k, v in pll.items()}
        self.assertTrue(scoring.gate1(same, pll)["pass"])
        worse = {k: {m: base - 0.12 for m in v} for k, v in pll.items()}
        r = scoring.gate1(worse, pll)
        self.assertFalse(r["pass"])
        self.assertFalse(r["rows"]["ballroom.f"]["pass"])
        one_bad = {k: {m: base for m in v} for k, v in pll.items()}
        one_bad["gtzan"]["amlt"] = base - 0.12
        r = scoring.gate1(one_bad, pll)
        self.assertFalse(r["pass"])
        self.assertTrue(r["rows"]["ballroom.amlt"]["pass"] and not r["rows"]["gtzan.amlt"]["pass"])


class Gap(unittest.TestCase):
    def test_phase_error_at_the_end_of_a_gap_and_amplitude_ratio(self):
        ref = grid(0.5, 100, 0.0)
        est_good = ref + 0.02                                  # 20 ms late
        est_bad = ref + 0.2
        self.assertAlmostEqual(scoring.gap_end_error_ms(ref, est_good, 20.0), 20.0, delta=0.5)
        self.assertAlmostEqual(scoring.gap_end_error_ms(ref, est_bad, 20.0), 200.0, delta=0.5)
        self.assertTrue(np.isnan(scoring.gap_end_error_ms(ref, est_good, 200.0)))      # no annotated beat there
        amp = np.ones((3000, 3))
        amp[1600:2000, 1] = 0.4                                # gap from 16 s to 20 s: oscillator 1 sagged to 40 %
        amp[1600:2000, 2] = 5.0                                # another oscillator became the current readout and is loud
        self.assertAlmostEqual(scoring.amplitude_ratio(amp, 1, 16.0, 20.0), 0.4)   # measured on the readout from before the gap
        self.assertAlmostEqual(scoring.amplitude_ratio(amp, 2, 16.0, 20.0), 5.0)
        idx = np.zeros(3000, int)
        idx[1700:1800] = 2                                     # one excursion: two switches inside the gap
        self.assertEqual(scoring.readout_switches(idx, 16.0, 20.0), 2)
        self.assertEqual(scoring.readout_switches(idx, 20.0, 25.0), 0)

    def test_gate2_rules(self):
        n = 120
        good = scoring.gate2(np.full(n, 30.0), np.full(n, 35.0), np.full(n, 0.8))
        self.assertTrue(good["pass"], good)
        late = scoring.gate2(np.full(n, 90.0), np.full(n, 95.0), np.full(n, 0.8))
        self.assertFalse(late["checks"]["phase"])
        worse_than_pll = scoring.gate2(np.full(n, 60.0), np.full(n, 30.0), np.full(n, 0.8))
        self.assertFalse(worse_than_pll["checks"]["vs_pll"])
        self.assertTrue(worse_than_pll["checks"]["phase"])
        faded = scoring.gate2(np.full(n, 30.0), np.full(n, 35.0), np.full(n, 0.3))
        self.assertFalse(faded["checks"]["amplitude"])
        nan_dropped = scoring.gate2(np.r_[np.full(n, 30.0), np.nan], np.r_[np.full(n, 35.0), 10.0], np.full(n + 1, 0.8))
        self.assertEqual(nan_dropped["clips"], n)


class Meter(unittest.TestCase):
    def test_amplitude_at_the_nearest_oscillator_and_ratio(self):
        from grfnn import frequencies
        f = frequencies()
        amp = np.full((1000, len(f)), 0.1)
        k3, k2 = int(np.argmin(abs(f - 1.0))), int(np.argmin(abs(f - 1.5)))
        amp[:, k3] = 0.9                                       # a triple-meter bank: 3 beats per bar at f_b = 3 Hz -> 1 Hz resonance
        self.assertAlmostEqual(scoring.meter_ratio(f, amp, 3.0), 0.9 / 0.1)
        amp2 = np.full((1000, len(f)), 0.1)
        amp2[:, k2] = 0.9                                      # duple: f_b = 3 Hz -> 1.5 Hz resonance
        self.assertAlmostEqual(scoring.meter_ratio(f, amp2, 3.0), 0.1 / 0.9)

    def test_auc_and_permutation_test(self):
        rng = np.random.default_rng(0)
        labels = np.r_[np.ones(50, bool), np.zeros(150, bool)]
        sep = np.where(labels, rng.normal(2, 1, 200), rng.normal(0, 1, 200))
        r = scoring.gate3(sep, labels)
        self.assertTrue(r["pass"], r)
        self.assertGreater(r["auc"], 0.85)
        noise = rng.normal(0, 1, 200)
        r2 = scoring.gate3(noise, labels)
        self.assertFalse(r2["pass"])
        self.assertAlmostEqual(scoring.auc([1, 2, 3, 4], [0, 0, 1, 1]), 1.0)
        self.assertAlmostEqual(scoring.auc([1, 1, 1, 1], [0, 0, 1, 1]), 0.5)
        self.assertEqual(scoring.permutation_p(sep, labels), scoring.permutation_p(sep, labels))   # seeded

    def test_half_or_double_share(self):
        r = scoring.half_or_double_share([1.0, 2.0, 4.0, 2.05, 3.0], [2.0, 2.0, 2.0, 1.0, 2.0])
        self.assertAlmostEqual(r["half"], 0.2)
        self.assertAlmostEqual(r["double"], 0.4)


if __name__ == "__main__":
    unittest.main()
