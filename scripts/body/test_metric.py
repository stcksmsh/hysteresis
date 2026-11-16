import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import metric_lib as M  # noqa: E402

BEATS = np.arange(0, 120, 0.5)                   # 120 BPM


class Phase(unittest.TestCase):
    def test_known_phase_each_level(self):
        t = BEATS[:-1][:200] + 0.5 * 0.25         # quarter of every beat
        r, p, _ = M.resultant(M.phases(t, BEATS, "beat"))
        self.assertAlmostEqual(r, 1, 6)
        self.assertAlmostEqual(p, 0.25, 6)
        r, p, _ = M.resultant(M.phases(t, BEATS, "half_beat"))
        self.assertAlmostEqual(r, 1, 6)
        self.assertAlmostEqual(p, 0.5, 6)
        ph = M.phases(BEATS[4:100] + 0.1, BEATS, "bar", off=0)        # on beat 4k+0.. residues cycle: bar phase of beat i is ((i mod 4)+f)/4
        self.assertTrue(np.all(ph < 1))
        t2 = BEATS[:-8][::4] + 0.1                                    # one event on every 4th beat -> one bar phase
        r, p, _ = M.resultant(M.phases(t2, BEATS, "bar", off=0))
        self.assertAlmostEqual(r, 1, 6)
        t3 = BEATS[:-8][::2] + 0.1
        r, _, _ = M.resultant(M.phases(t3, BEATS, "half_time", par=0))
        self.assertAlmostEqual(r, 1, 6)

    def test_uniform_near_chance(self):
        rng = np.random.default_rng(1)
        n = 400
        rs = [M.resultant(M.phases(rng.uniform(0, 119, n), BEATS, "beat"))[0] for _ in range(200)]
        self.assertLess(abs(np.mean(rs) - np.sqrt(np.pi) / (2 * np.sqrt(n))), 0.02)
        self.assertLess(np.mean(rs), 0.1)

    def test_lag_scan_recovers_shift(self):
        t = BEATS[:-2] + 0.100                                            # events 100 ms after each beat
        h = [M.hit_rate(t, BEATS, L) for L in M.LAGS]
        self.assertAlmostEqual(M.LAGS[np.array(h) == max(h)].mean(), 0.100, 6)    # the hit window is +-50 ms wide: the plateau is centred on the injected lag
        self.assertEqual(max(h), 1.0)

    def test_hit_scan_matches_hit_rate(self):
        t = np.random.default_rng(5).uniform(1, 110, 300)
        a = M.hit_scan(t, BEATS)
        self.assertTrue(np.allclose(a, [M.hit_rate(t, BEATS, L) for L in M.LAGS]))

    def test_signed_offset(self):
        self.assertTrue(np.allclose(M.signed_offset([0.1, 0.45], [0, 0.5, 1.0]), [0.1, -0.05]))

    def test_bar_choice(self):
        s = np.ones(40)
        s[1::4] = 5
        s[::2] += 1                                                       # strong residue 1 mod 4 is odd; parity odd wins too? even beats get +1 at residue 0/2
        par, off = M.choose_bar(BEATS[:40], s)
        self.assertEqual(off, 1)


class Controls(unittest.TestCase):
    def test_shuffle_ibi(self):
        b = np.cumsum(np.r_[0, np.random.default_rng(2).uniform(0.4, 0.6, 50)])
        s = M.shuffle_ibi(b, np.random.default_rng(3))
        self.assertEqual(s[0], b[0])
        self.assertTrue(np.allclose(np.sort(np.diff(s)), np.sort(np.diff(b))))
        self.assertFalse(np.allclose(s, b))

    def test_donor_covers(self):
        g = M.donor_grid(np.arange(0, 10, 0.6), 3.0, 100.0)
        self.assertEqual(g[0], 3.0)
        self.assertGreaterEqual(g[-1], 100.0)
        self.assertTrue(np.allclose(np.diff(g)[:5], 0.6))

    def test_circ_shift(self):
        rng = np.random.default_rng(4)
        idx = np.array([5, 40, 90])
        for _ in range(50):
            s = M.circ_shift(idx, 100, rng)
            self.assertEqual(len(s), 3)
            self.assertTrue(np.all(s < 100))


class Events(unittest.TestCase):
    P = np.ones(5) * 100.0

    def lamp(self, x):
        n = len(x)
        return np.stack([x, np.zeros(n), np.zeros(n)], 1)

    def test_back_and_forth(self):
        t = np.arange(0, 20, 1 / 50)
        x = 0.2 * np.sin(2 * np.pi * 0.5 * t)                             # 0.5 Hz line: reversals at the extremes every 1 s
        q = np.zeros((len(t), 5))
        ev = M.events(q, self.lamp(x), A=1.0, p90=self.P, P=0.3)
        e4 = ev["E4"]
        self.assertGreater(len(e4), 15)
        ext = np.abs(((e4 - 0.5) % 1.0))                                  # extremes at t = 0.5 + k
        self.assertTrue(np.all(np.minimum(ext, 1 - ext) < 0.06))
        self.assertEqual(len(ev["E1"]) >= len(e4), True)

    def test_onset_after_rest(self):
        t = np.arange(0, 10, 1 / 50)
        x = np.where(t < 4, 0.0, 0.5 * (t - 4))                           # rest, then constant speed 0.5 m/s from t = 4
        ev = M.events(np.zeros((len(t), 5)), self.lamp(x), A=1.0, p90=self.P, P=0.4)
        self.assertEqual(len(ev["E5"]), 1)
        self.assertLess(abs(ev["E5"][0] - 4.1), 0.2)

    def test_joint_peaks(self):
        t = np.arange(0, 20, 1 / 50)
        q = np.zeros((len(t), 5))
        q[:, 2] = 30 * np.sin(2 * np.pi * 0.5 * t)                        # |w| peaks twice per period
        ev = M.events(q, self.lamp(np.zeros(len(t))), A=1.0, p90=self.P, P=0.3)
        self.assertGreater(len(ev["E3_2"]), 15)
        self.assertEqual(len(ev["E3_0"]), 0)


class Structure(unittest.TestCase):
    def test_corr_many(self):
        r = np.random.default_rng(6)
        x = r.normal(size=80)
        Y = r.normal(size=(5, 80))
        Y[0] = 2 * x + 1
        c = __import__("metric_run").corr_many(x, Y)
        self.assertAlmostEqual(c[0], 1, 6)
        self.assertAlmostEqual(c[1], np.corrcoef(x, Y[1])[0, 1], 6)

    def test_novelty_change_point_and_align(self):
        import metric_run as R
        n = 120
        F = np.zeros((n, 4))
        F[:60, 0] = 1
        F[60:, 1] = 1
        F += np.random.default_rng(7).normal(0, 0.05, F.shape)
        nv, pk = R.peaks_of(F, 4)
        self.assertTrue(np.any(np.abs(pk - 60) <= 1))
        ok = np.ones(n, bool)
        a = R.align(pk, nv, pk, nv, n, np.random.default_rng(8), ok)
        d0 = list(R.DELAYS).index(0)
        self.assertEqual(a["hit"][d0], 1.0)
        self.assertGreater(a["corr"][d0], 0.99)
        self.assertGreater(a["hit"][d0], a["hit_null"][d0])

    def test_independent_short_songs_show_no_excess(self):
        """two unrelated feature streams of a short clip: boundary-hit and novelty-correlation excess over the circular-shift null stay near 0 (no edge artefact)"""
        import metric_run as R
        ex_h, ex_c = [], []
        for seed in range(40):
            r = np.random.default_rng(100 + seed)
            n = 75
            Fa, Fb = r.normal(size=(n, 6)), r.normal(size=(n, 6))
            nva, pka = R.peaks_of(Fa, 16)
            nvb, pkb = R.peaks_of(Fb, 16)
            a = R.align(pka, nva, pkb, nvb, n, r, np.ones(n, bool))
            d0 = list(R.DELAYS).index(0)
            ex_h.append(a["hit"][d0] - a["hit_null"][d0])
            ex_c.append(a["corr"][d0] - a["corr_null"][d0])
        self.assertLess(abs(np.nanmean(ex_h)), 0.05)
        self.assertLess(abs(np.nanmean(ex_c)), 0.05)


if __name__ == "__main__":
    unittest.main()
