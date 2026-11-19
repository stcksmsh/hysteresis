"""Synthetic tests for ear_energy.  python test_ear_energy.py"""
import unittest
import numpy as np
import ear_energy as ee

NM = dict(loud_mean=-20.0, loud_sd=5.0, dens_mean=2.0, dens_sd=1.0, mu=0.0, sd=1.0)


def feats(n=3000, rms=0.1, clicks_every=None, click=5.0):
    f = np.zeros((n, 44)); f[:, 41] = rms; f[:, 40] = 0.2
    if clicks_every:
        f[::clicks_every, 40] = click
    return f


class T(unittest.TestCase):
    def test_louder_is_higher(self):
        self.assertGreater(ee.lane(feats(rms=0.2), NM).mean(), ee.lane(feats(rms=0.05), NM).mean())

    def test_denser_is_higher(self):
        self.assertGreater(ee.lane(feats(clicks_every=25), NM).mean(), ee.lane(feats(clicks_every=100), NM).mean())
        self.assertGreater(ee.lane(feats(clicks_every=100), NM).mean(), ee.lane(feats(), NM).mean())

    def test_density_value(self):
        _, d = ee.terms(feats(clicks_every=50))  # 2 per s
        self.assertAlmostEqual(d[1500], 2.0, delta=0.51)
        _, d = ee.terms(feats(clicks_every=50, click=0.9))  # below the 1.0 peak minimum
        self.assertEqual(d.max(), 0)

    def test_silence_is_floor(self):
        l, d = ee.terms(feats(rms=0.0))
        np.testing.assert_allclose(l, -80.0); self.assertEqual(d.max(), 0)
        self.assertLess(ee.lane(feats(rms=0.0), NM).max(), ee.lane(feats(rms=0.01), NM).min())

    def test_rate_and_clip(self):
        self.assertEqual(len(ee.lane(feats(3005), NM)), 300)
        x = ee.network_input(feats(clicks_every=5, rms=0.5), NM)
        self.assertLessEqual(x.max(), 3.0); self.assertGreaterEqual(x.min(), -3.0)

    def test_fit_norm_standardises(self):
        fs = [feats(rms=r, clicks_every=c) for r, c in ((0.05, 100), (0.1, 50), (0.2, 25))]
        nm = ee.fit_norm(fs)
        e = np.concatenate([ee.lane(f, nm) for f in fs])
        self.assertAlmostEqual(e.mean(), nm["mu"]); self.assertAlmostEqual(e.std(), nm["sd"])


if __name__ == "__main__":
    unittest.main()
