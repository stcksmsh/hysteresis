"""WO48 internal pulse tests (docs/PULSE_RULES.md section 6): synthetic audio through fast_features and the whole pulse.
/secondary/hyst-env/brain/bin/python -m unittest discover -s scripts/body -p test_pulse.py"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "brain"))
import fast_features as ff  # noqa: E402
import pulse_lib as P  # noqa: E402

SR = 44100


def render(dur, kicks, hats=(), silence=None, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(0.2 * SR)) / SR
    kick = (0.6 * np.sin(2 * np.pi * 60 * t) * np.exp(-t * 25)).astype(np.float32)
    t = np.arange(int(0.05 * SR)) / SR
    hat = (0.15 * np.diff(rng.standard_normal(len(t)), prepend=0) * np.exp(-t * 80)).astype(np.float32)
    y = 0.005 * rng.standard_normal(int(dur * SR)).astype(np.float32)
    for times, s in ((kicks, kick), (hats, hat)):
        for tt in times:
            a = int(round(tt * SR)); m = min(len(s), len(y) - a)
            if m > 0:
                y[a:a + m] += s[:m]
    if silence:
        y[int(silence[0] * SR):int(silence[1] * SR)] = 0.0
    return y


def offsets(ev, grid):
    return np.array([e - grid[np.argmin(abs(grid - e))] for e in ev])


class Pulse(unittest.TestCase):
    def test_click_train_120_bpm_is_tracked_at_2_hz_with_phase_on_the_clicks(self):
        k = np.arange(0.25, 40, 0.5)
        r = P.pulse(ff.fast_features(render(40, k)))
        self.assertAlmostEqual(float(np.median(r["rate"][1500:])), 2.0, delta=0.04)
        o = offsets(r["events"][r["events"] > 15], k)
        self.assertLess(abs(float(np.median(o))), 0.05, o)
        self.assertLess(float(o.std()), 0.02)

    def test_pulse_persists_through_4_s_of_silence(self):
        k = np.arange(0.25, 40, 0.5)
        r = P.pulse(ff.fast_features(render(40, k[(k < 16) | (k >= 20)], silence=(16, 20))))
        e = r["events"]
        w = e[(e > 14) & (e < 24)]
        self.assertLessEqual(float(np.diff(w).max()), 0.55)
        self.assertTrue(np.allclose(r["freq"][1400:2400], 2.0, atol=0.03))
        self.assertLess(float(np.abs(offsets(e[(e > 16) & (e < 24)], k)).max()), 0.05)

    def test_60_bpm_kicks_with_240_bpm_hats_pick_an_admissible_level_not_the_hats(self):
        r = P.pulse(ff.fast_features(render(40, np.arange(0.25, 40, 1.0), np.arange(0.25, 40, 0.25))))
        rate = float(np.median(r["rate"][2000:]))
        self.assertLessEqual(rate, P.f_max())
        self.assertTrue(abs(rate - 1.0) < 0.04 or abs(rate - 2.0) < 0.08, rate)

    def test_tempo_ramp_100_to_120_bpm_is_followed(self):
        def bpm(t):
            return 100 if t < 10 else (100 + 20 * (t - 10) / 30 if t < 40 else 120)
        t, ks = 0.25, []
        while t < 60:
            ks.append(t); t += 60 / bpm(t)
        r = P.pulse(ff.fast_features(render(60, np.array(ks))))
        tt = np.arange(len(r["rate"])) / 100
        true = np.array([bpm(x) / 60 for x in tt])
        m = (tt >= 12) & (tt < 40)
        self.assertLess(float(np.abs(r["rate"][m] / true[m] - 1).max()), 0.07)
        m2 = (tt >= 10) & (tt < 40)
        self.assertGreater(spearmanr(r["rate"][m2], true[m2])[0], 0.9)
        self.assertLess(float(np.abs(r["rate"][tt >= 50] / 2.0 - 1).max()), 0.02)

    def test_arm_limit_and_causality(self):
        self.assertAlmostEqual(P.f_max(), np.sqrt(300 / 5) / np.pi, places=6)
        self.assertAlmostEqual(P.f_max(), 2.4656, places=3)
        y = render(20, np.arange(0.25, 20, 0.5))
        y2 = y.copy()
        y2[12 * SR:] = np.random.default_rng(5).standard_normal(len(y2) - 12 * SR).astype(np.float32) * 0.3
        a, b = P.pulse(ff.fast_features(y)), P.pulse(ff.fast_features(y2))
        n = 1200   # frame 1200 = 12.00 s; the drive at t uses audio up to t - 6.8 ms
        self.assertTrue(np.array_equal(a["drive"][:n], b["drive"][:n]))
        for key in ("rate", "phase", "amp", "sel"):
            self.assertTrue(np.array_equal(a[key][:n], b[key][:n]), key)
        self.assertFalse(np.array_equal(a["drive"], b["drive"]))


class Check(unittest.TestCase):
    def test_check_primitives(self):
        import pulse_run as R
        ev = np.arange(0, 60, 0.5)
        self.assertAlmostEqual(R.tempo_bpm(ev), 120.0)
        self.assertLess(R.regularity_ms(ev), 1e-6)
        self.assertEqual(R.level(0.5)[0], "1/2")
        grid = np.concatenate([np.arange(0, 20, 0.5), np.arange(24, 60, 0.5)])   # a 4 s dropout at 20-24 s
        self.assertEqual(R.grid_dropouts(grid), [(19.5, 24.0)])
        p = R.persistence(R.grid_dropouts(grid), dict(pulse=ev, grid=grid))
        self.assertTrue(p[0]["pulse"]["kept"])
        self.assertFalse(p[0]["grid"]["kept"])
        rms = np.ones(6000); rms[3000:3400] = 0.1
        (s, e), = R.quiet_passages(rms); self.assertAlmostEqual(s, 30.05, delta=0.02); self.assertAlmostEqual(e, 33.95, delta=0.02)
        rate = np.full(6000, 2.0)
        f = R.following(rate, ev)
        self.assertEqual(f["share_within_4pct"], 1.0)
        f = R.following(np.full(6000, 1.0), ev)                                   # half tempo folds to the same level
        self.assertEqual(f["share_within_4pct"], 1.0)


if __name__ == "__main__":
    unittest.main()
