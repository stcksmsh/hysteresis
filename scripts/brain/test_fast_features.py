import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import fast_features as ff  # noqa: E402


def tone(freq, seconds, amp=0.5):
    t = np.arange(int(seconds * ff.SR)) / ff.SR
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


class FastFeatures(unittest.TestCase):
    def test_shape_rate_and_columns(self):
        y = tone(440, 2.0)
        f = ff.fast_features(y)
        self.assertEqual(f.shape, (1 + len(y) // 441, 44))
        self.assertEqual(f.dtype, np.float32)
        self.assertAlmostEqual(ff.FRAME_RATE, 100.0)
        self.assertEqual(len(ff.COLUMNS), 44)
        self.assertTrue(np.isfinite(f).all())

    def test_eight_groups_cover_30_to_16000_and_the_first_is_below_200(self):
        self.assertEqual(len(ff._GROUP), 8)
        self.assertEqual(ff.GROUP_EDGES_HZ[1], 200.0)
        self.assertTrue(all(len(g) > 0 for g in ff._GROUP))
        self.assertLess(ff._FREQ[ff._GROUP[0].max()], 200.0)

    def test_tone_lands_in_its_band_with_low_flatness_and_known_rms(self):
        f = ff.fast_features(tone(1000, 2.0, 0.5))
        mid = f[50:150]
        band = int(np.argmax(mid[:, :32].mean(axis=0)))
        edges = __import__("librosa").mel_frequencies(n_mels=34, fmin=ff.FMIN, fmax=ff.FMAX)
        self.assertTrue(edges[band] <= 1000 <= edges[band + 2], (band, edges[band:band + 3]))
        self.assertAlmostEqual(float(mid[:, ff.COLUMNS.index("centroid")].mean()), 1000 / (ff.SR / 2), delta=0.01)
        self.assertLess(float(mid[:, ff.COLUMNS.index("flatness")].mean()), 0.05)
        self.assertAlmostEqual(float(mid[:, ff.COLUMNS.index("rms")].mean()), 0.5 / np.sqrt(2), delta=0.01)
        self.assertLess(float(mid[:, ff.COL_ONSET].max()), 0.5)  # steady tone: no onsets

    def test_click_train_gives_one_onset_peak_per_click(self):
        n = 4 * ff.SR
        y = np.zeros(n, np.float32)
        clicks = [int((0.25 + 0.5 * k) * ff.SR) for k in range(7)]
        for c in clicks:
            y[c:c + 64] = 0.8 * np.hanning(64)
        f = ff.fast_features(y + 1e-4 * np.random.default_rng(0).standard_normal(n).astype(np.float32))
        onset = f[:, ff.COL_ONSET]
        for c in clicks:
            frame = c // ff.HOP
            self.assertGreater(onset[max(0, frame - 1):frame + 3].max(), 5 * np.median(onset) + 1.0, c)
            # the low-band flux channel is a column too and rises with the click
            self.assertGreater(f[max(0, frame - 1):frame + 3, ff.COL_FLUX_LOW].max(), np.median(f[:, ff.COL_FLUX_LOW]))
        peaks = [i for i in range(1, len(onset) - 1) if onset[i] > onset[i - 1] and onset[i] >= onset[i + 1] and onset[i] > 2.0]
        self.assertEqual(len(peaks), len(clicks))

    def test_noise_is_flat_and_bright(self):
        y = (0.2 * np.random.default_rng(1).standard_normal(2 * ff.SR)).astype(np.float32)
        f = ff.fast_features(y)[20:-20]
        self.assertGreater(float(f[:, ff.COLUMNS.index("flatness")].mean()), 0.4)
        self.assertAlmostEqual(float(f[:, ff.COLUMNS.index("centroid")].mean()), 0.5, delta=0.05)
        self.assertAlmostEqual(float(f[:, ff.COLUMNS.index("rms")].mean()), 0.2, delta=0.01)

    def test_silence_has_no_rises_and_standardise_hook(self):
        f = ff.fast_features(np.zeros(ff.SR, np.float32))
        self.assertEqual(float(f[:, 32:41].max()), 0.0)
        z = ff.standardise(f, f.mean(axis=0), f.std(axis=0))
        self.assertEqual(z.shape, f.shape)


if __name__ == "__main__":
    unittest.main()
