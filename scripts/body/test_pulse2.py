"""WO51 pulse v2 tests (docs/PULSE2_RULES.md section 7): synthetic audio through fast_features and the whole pulse v2.
/secondary/hyst-env/brain/bin/python -m unittest discover -s scripts/body -p test_pulse2.py"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brain"))
import fast_features as ff  # noqa: E402
import pulse2_lib as P2  # noqa: E402
import pulse_lib as P1  # noqa: E402
from test_pulse import offsets, render  # noqa: E402

SR = 44100


def tone_hits(dur, times, amp, fr):
    """decaying sine hits (a low tom at fr Hz), 150 ms"""
    t = np.arange(int(0.15 * SR)) / SR
    s = (amp * np.sin(2 * np.pi * fr * t) * np.exp(-t * 30)).astype(np.float32)
    y = np.zeros(int(dur * SR), np.float32)
    for tt in times:
        a = int(round(tt * SR)); m = min(len(s), len(y) - a)
        if m > 0:
            y[a:a + m] += s[:m]
    return y


def hats_only(dur, times, gain):
    """the noise hats of test_pulse.render, without kicks or the noise bed, scaled by gain"""
    return (render(dur, (), times, seed=1) - render(dur, (), (), seed=1)) * gain


class PulseV1Carried(unittest.TestCase):
    """v1's tests 1-5 (test_pulse.py), applied to pulse v2"""

    def test_click_train_120_bpm(self):
        k = np.arange(0.25, 40, 0.5)
        r = P2.pulse(ff.fast_features(render(40, k)))
        self.assertAlmostEqual(float(np.median(r["rate"][1500:])), 2.0, delta=0.04)
        o = offsets(r["events"][r["events"] > 15], k)
        self.assertLess(abs(float(np.median(o))), 0.05)
        self.assertLess(float(o.std()), 0.02)
        self.assertGreater(float(np.median(r["conf"][1000:])), 0.8)

    def test_60_bpm_kicks_with_240_bpm_hats(self):
        r = P2.pulse(ff.fast_features(render(40, np.arange(0.25, 40, 1.0), np.arange(0.25, 40, 0.25))))
        rate = float(np.median(r["rate"][2000:]))
        self.assertLessEqual(rate, P1.f_max())
        self.assertTrue(abs(rate - 1.0) < 0.04 or abs(rate - 2.0) < 0.08, rate)

    def test_tempo_ramp_100_to_120_bpm(self):
        def bpm(t):
            return 100 if t < 10 else (100 + 20 * (t - 10) / 30 if t < 40 else 120)
        t, ks = 0.25, []
        while t < 60:
            ks.append(t); t += 60 / bpm(t)
        r = P2.pulse(ff.fast_features(render(60, np.array(ks))))
        tt = np.arange(len(r["rate"])) / 100
        true = np.array([bpm(x) / 60 for x in tt])
        m = (tt >= 12) & (tt < 40)
        self.assertLess(float(np.abs(r["rate"][m] / true[m] - 1).max()), 0.07)
        m2 = (tt >= 10) & (tt < 40)
        self.assertGreater(spearmanr(r["rate"][m2], true[m2])[0], 0.9)
        self.assertLess(float(np.abs(r["rate"][tt >= 50] / 2.0 - 1).max()), 0.02)

    def test_causality(self):
        y = render(20, np.arange(0.25, 20, 0.5))
        y2 = y.copy()
        y2[12 * SR:] = np.random.default_rng(5).standard_normal(len(y2) - 12 * SR).astype(np.float32) * 0.3
        a, b = P2.pulse(ff.fast_features(y)), P2.pulse(ff.fast_features(y2))
        n = 1200
        for key in ("drive", "novelty", "rate", "phase", "amp", "sel", "conf"):
            self.assertTrue(np.array_equal(a[key][:n], b[key][:n]), key)
        self.assertFalse(np.array_equal(a["conf"], b["conf"]))


class PulseV2(unittest.TestCase):
    def test_silence_lowers_confidence_and_phase_resumes(self):
        """4 s digital silence at 16-20 s in a 120 BPM kick train: mean confidence over 19-20 s below 0.3; events continue (longest IOI
        in 14-24 s at most 0.55 s), and every event in 20-24 s is within +-50 ms of the continued click grid"""
        k = np.arange(0.25, 40, 0.5)
        r = P2.pulse(ff.fast_features(render(40, k[(k < 16) | (k >= 20)], silence=(16, 20))))
        self.assertGreater(float(np.median(r["conf"][1000:1600])), 0.8)
        self.assertLess(float(np.mean(r["conf"][1900:2000])), 0.3)
        e = r["events"]
        self.assertLessEqual(float(np.diff(e[(e > 14) & (e < 24)]).max()), 0.55)
        self.assertLess(float(np.abs(offsets(e[(e > 20) & (e < 24)], k)).max()), 0.05)
        self.assertTrue(np.allclose(r["freq"][1400:2400], 2.0, atol=0.03))
        # each event carries the confidence of its frame
        self.assertEqual(len(r["event_conf"]), len(e))

    def test_3_against_2_hats_over_2_hz_kick_pick_the_binary_level(self):
        """kicks at 2 Hz, hats at 3 Hz four times as loud as test_pulse's hats: the rate after 20 s is within 2 % of 2 Hz or of 1 Hz"""
        y = render(40, np.arange(0.25, 40, 0.5)) + hats_only(40, np.arange(0.25, 40, 1 / 3), 4.0)
        r = P2.pulse(ff.fast_features(y))
        rate = float(np.median(r["rate"][2000:]))
        self.assertTrue(abs(rate / 2.0 - 1) < 0.02 or abs(rate / 1.0 - 1) < 0.02, rate)

    def test_one_second_fill_does_not_switch_the_level(self):
        """2 Hz kicks with a loud 1 s fill of low tom hits at 3 Hz (20-21 s): no level switch after 10 s, selection within +-2 oscillators of 2 Hz"""
        k = np.arange(0.25, 40, 0.5)
        y = render(40, k) + tone_hits(40, np.arange(20, 21, 1 / 3), 1.2, 100)
        r = P2.pulse(ff.fast_features(y))
        self.assertEqual([s for s in r["switches"] if s[0] >= 1000], [])
        i2 = int(np.argmin(np.abs(r["f"] - 2.0)))
        f = r["f"]
        sel_idx = np.searchsorted(f, r["freq"][1000:] - 1e-9)
        self.assertLessEqual(int(np.abs(sel_idx - i2).max()), 2)

    def test_noise_bed_has_low_confidence(self):
        """after 10 s of a 120 BPM train, 20 s of the 0.005 RMS noise bed alone: median confidence over the last 10 s below 0.3"""
        k = np.arange(0.25, 10, 0.5)
        r = P2.pulse(ff.fast_features(render(30, k)))
        self.assertLess(float(np.median(r["conf"][2000:])), 0.3)


class Readout(unittest.TestCase):
    def test_amp_at_interpolates_and_is_zero_outside(self):
        f = P2.frequencies()
        amp = np.tile(np.log2(f), (3, 1))
        self.assertTrue(np.allclose(P2.amp_at(f, amp, [1.0, 2.0, 1.5])[0], np.log2([1.0, 2.0, 1.5])))
        self.assertTrue(np.all(P2.amp_at(f, amp, [0.1, 9.0]) == 0))
        self.assertAlmostEqual(f[0], 0.25); self.assertAlmostEqual(f[-1], 8.0); self.assertEqual(len(f), 121)
        # v1's oscillators are a subset, bit for bit
        self.assertTrue(np.array_equal(f[24:24 + 73], P1.frequencies()))

    def test_harmonic_score_prefers_the_candidate_with_octave_support(self):
        f = P2.frequencies()
        amp = np.full((1, len(f)), 0.01)
        i1, i15, i2, i4 = (int(np.argmin(np.abs(f - q))) for q in (1.0, 1.5, 2.0, 4.0))
        amp[0, i2] = amp[0, i15] = 0.3          # equal own amplitude at 2 Hz and at 1.5 Hz (3:4 of it)
        amp[0, i1] = amp[0, i4] = 0.1           # binary neighbours of 2 Hz
        band = np.flatnonzero((f >= 0.5) & (f <= 2.4656))
        S = P2.harmonic_score(f, amp, band)[0]
        self.assertEqual(f[band[int(np.argmax(S))]], f[i2])

    def test_switch_needs_4_s_or_1_5_s_near_a_boundary(self):
        f = P2.frequencies()
        T = 3000
        amp = np.full((T, len(f)), 0.01)
        i1, i2 = int(np.argmin(np.abs(f - 1.3))), int(np.argmin(np.abs(f - 2.0)))
        amp[:, i2] = 0.2
        amp[1000:, i1] = 0.5                    # from 10 s, 1.3 Hz scores about twice 2 Hz (prior and support included)
        ph = np.zeros_like(amp); x = np.zeros(T)
        r = P2.readout(f, amp, ph, x, [])
        self.assertEqual(r["switches"][0][0], 1000 + 400 - 1)
        r = P2.readout(f, amp, ph, x, [1050])  # boundary 0.5 s after the run starts
        self.assertEqual(r["switches"][0][0], 1000 + 150 - 1)
        self.assertTrue(r["switches"][0][3])
        r = P2.readout(f, amp, ph, x, [1300])  # boundary 3 s after: not near
        self.assertEqual(r["switches"][0][0], 1000 + 400 - 1)
        amp2 = amp.copy(); amp2[1000:, i1] = 1.3 * 0.21 / P1.prior(f[i1]) - 0.01 - 1e-3   # score 1.3 x the 2 Hz score, below the 35 % margin
        self.assertEqual(P2.readout(f, amp2, ph, x, [])["switches"], [])

    def test_novelty_marks_a_texture_change(self):
        """kicks at 2 Hz for 20 s, then a loud 300 Hz tone with hats: one boundary between 20 and 22 s"""
        y = render(40, np.arange(0.25, 40, 0.5))
        t = np.arange(len(y)) / SR
        y[t >= 20] += (0.3 * np.sin(2 * np.pi * 300 * t[t >= 20])).astype(np.float32)
        y += hats_only(40, np.arange(20, 40, 0.25), 2.0)
        r = P2.pulse(ff.fast_features(y))
        b = r["boundaries"]
        self.assertEqual(int(np.sum((b >= 20) & (b <= 22))), 1, b)


if __name__ == "__main__":
    unittest.main()


class Passages(unittest.TestCase):
    def test_periodicity_labels_beat_beatless_silence(self):
        """kicks at 2 Hz to 30 s, random kicks 30-45 s, digital silence 45-50 s, kicks 50-60 s; flat RMS grid with no dropouts"""
        import pulse2_run as PR
        rng = np.random.default_rng(4)
        k = np.arange(0.25, 60, 0.5)
        k = np.concatenate([k[k < 30], np.sort(rng.uniform(30, 45, 30)), k[(k >= 50)]])
        y = render(60, k, silence=(45, 50))
        F = ff.fast_features(y)
        lab, per = PR.passages(F[:, 41], F[:, 32], np.arange(0, 60, 0.5), 60)
        self.assertTrue(all(lab[s] == "beat" for s in range(12, 27)), list(lab))
        self.assertGreaterEqual(sum(lab[s] == "beatless" for s in range(31, 44)), 8, list(per.round(2)))
        self.assertTrue(all(lab[s] == "silence" for s in range(46, 49)), list(lab))
        self.assertEqual(sum(lab[:10] != ""), 0)
