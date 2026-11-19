import unittest

import numpy as np

import check1
import common
import extract
import features


class SplitTests(unittest.TestCase):
    def test_folds_assign_every_song_once_and_are_balanced(self):
        keys = [f"deam_{i}" for i in range(1, 1003)]
        folds = common.assign_folds(keys)
        self.assertEqual(set(folds), set(keys))
        counts = np.bincount(list(folds.values()), minlength=common.N_FOLDS)
        self.assertLessEqual(counts.max() - counts.min(), 1)

    def test_folds_are_deterministic_and_seeded(self):
        keys = [f"k{i}" for i in range(200)]
        self.assertEqual(common.assign_folds(keys), common.assign_folds(list(reversed(keys))))
        self.assertNotEqual(common.assign_folds(keys), common.assign_folds(keys, seed=1))

    def test_genre_groups_balanced_within_each_genre(self):
        keys = [f"e{i}" for i in range(400)]
        genres = {k: ("a", "b", "c", "d")[i // 100] for i, k in enumerate(keys)}
        folds = common.assign_folds(keys, genres)
        for g in "abcd":
            counts = np.bincount([folds[k] for k in keys if genres[k] == g], minlength=common.N_FOLDS)
            self.assertTrue((counts == 20).all())

    def test_no_song_in_train_and_test(self):
        rng = np.random.default_rng(0)
        songs = np.repeat(np.arange(50), 15)
        folds = common.assign_folds([f"deam_{s}" for s in np.unique(songs)])
        fold_of_row = np.array([folds[f"deam_{s}"] for s in songs])
        for f in range(common.N_FOLDS):
            test = fold_of_row == f
            self.assertFalse(set(songs[test]) & set(songs[~test]))


class ReadoutTests(unittest.TestCase):
    def synthetic(self, noise=0.1, signal=True, seed=3):
        rng = np.random.default_rng(seed)
        n_songs, per = 120, 15
        songs = np.repeat(np.arange(1, n_songs + 1), per)
        x = rng.normal(size=(len(songs), 12)) * rng.uniform(0.5, 3, size=12)
        w = rng.normal(size=(12, 2))
        y = x @ w + noise * rng.normal(size=(len(songs), 2)) if signal else rng.normal(size=(len(songs), 2))
        return x, y, songs, w

    def test_ridge_recovers_a_known_linear_signal(self):
        x, y, songs, w = self.synthetic()
        std = common.Standardizer().fit(x)
        model = common.ridge_fit(std(x), y, 1e-3)
        pred = common.ridge_predict(model, std(x))
        self.assertGreater(1 - ((y - pred) ** 2).sum() / ((y - y.mean(0)) ** 2).sum(), 0.99)
        recovered = model[0] / std.scale[:, None]
        np.testing.assert_allclose(recovered, w, atol=0.05)

    def test_timing_pipeline_scores_signal_high_and_noise_near_zero(self):
        for signal, low, high in ((True, 0.95, 1.0), (False, -0.1, 0.05)):
            x, y, songs, _ = self.synthetic(signal=signal)
            data = {"song": songs, "y": y}
            folds = common.assign_folds([f"deam_{s}" for s in np.unique(songs)])
            _, stats, _ = check1.timing_stats(x, data, folds, layered=False)
            pooled, _ = check1.r2_from_stats(stats)
            self.assertTrue(low < pooled.mean() < high, (signal, pooled))

    def test_inner_selection_never_sees_the_test_fold(self):
        x, y, songs, _ = self.synthetic()
        folds = common.assign_folds([f"deam_{s}" for s in np.unique(songs)])
        test = np.array([folds[f"deam_{s}"] == 0 for s in songs])
        changed = y.copy()
        changed[test] += 1000.0          # wrecking the test labels must not change the fit
        a = check1.select_and_fit(x[~test], y[~test], songs[~test], False)
        b = check1.select_and_fit(x[~test], changed[~test], songs[~test], False)
        np.testing.assert_allclose(a[1][0], b[1][0])
        self.assertEqual(a[3], b[3])

    def test_layer_selection_picks_the_informative_layer(self):
        x, y, songs, _ = self.synthetic()
        rng = np.random.default_rng(1)
        layered = np.stack([rng.normal(size=x.shape), x, rng.normal(size=x.shape)], axis=1)
        _, _, option, _ = check1.select_and_fit(layered, y, songs, True)
        self.assertEqual(option, 1)


class StatsTests(unittest.TestCase):
    def test_pooled_r2_from_song_stats_matches_direct(self):
        rng = np.random.default_rng(5)
        songs = np.repeat(np.arange(10), 7)
        y = rng.normal(size=(70, 2))
        pred = y + 0.5 * rng.normal(size=(70, 2))
        stats = np.zeros((10, 2, 7))
        for i in range(10):
            m = songs == i
            for j in range(2):
                t, p = y[m, j], pred[m, j]
                stats[i, j] = [m.sum(), t.sum(), (t ** 2).sum(), ((t - p) ** 2).sum(),
                               ((t - t.mean()) ** 2).sum(), (((t - t.mean()) - (p - p.mean())) ** 2).sum(), 0]
        pooled, _ = check1.r2_from_stats(stats)
        direct = 1 - ((y - pred) ** 2).sum(0) / ((y - y.mean(0)) ** 2).sum(0)
        np.testing.assert_allclose(pooled, direct)

    def test_geometry_ratio_above_one_for_separated_groups(self):
        rng = np.random.default_rng(2)
        dominant = np.repeat([0, 1], 20)
        pts = rng.normal(size=(40, 3)) * 0.1 + dominant[:, None] * 5
        dist = np.linalg.norm(pts[:, None] - pts[None], axis=2)
        fold = np.zeros(40, int)
        self.assertGreater(check1.geometry_ratio(dist, fold, dominant), 10)

    def test_pass_rule_requires_clear_intervals(self):
        def row(t, tci, r, rci, a, aci):
            return {"timing": t, "timingCI": tci, "rho": r, "rhoCI": rci, "agree": a, "agreeCI": aci, "geometry": 1.1}
        results = {
            "baseline": row(0.30, (0.28, 0.32), 0.40, (0.35, 0.45), 0.30, (0.25, 0.35)),
            "overlap": row(0.40, (0.31, 0.45), 0.50, (0.47, 0.53), 0.40, (0.37, 0.45)),
            "clear": row(0.45, (0.43, 0.47), 0.50, (0.47, 0.53), 0.40, (0.37, 0.45)),
        }
        verdicts, pick = check1.judge(results)
        self.assertFalse(verdicts["overlap"]["pass"])
        self.assertTrue(verdicts["clear"]["pass"])
        self.assertEqual(pick, "clear")


class WindowTests(unittest.TestCase):
    def test_pool_frames_is_the_window_mean(self):
        frames = np.arange(200, dtype=float).reshape(100, 2)
        out = common.pool_frames(frames, 20.0, [2.5], window=1.0)   # frames 40..60
        np.testing.assert_allclose(out[0], frames[40:60].mean(axis=0))

    def test_mert_windows_match_manual_mean(self):
        rng = np.random.default_rng(0)
        hidden = rng.normal(size=(2, 75 * 20, 4)).astype(np.float32)   # 20 s at 75 Hz
        out = extract.mert_windows(hidden)
        k = 12                                                         # centre 6 s: frames 4..8 s
        lo, hi = int(4 * 75), int(8 * 75)
        np.testing.assert_allclose(out[k], hidden[:, lo:hi].mean(axis=1), atol=1e-3)

    def test_eval_centres_only_full_windows(self):
        self.assertEqual(common.eval_centres(45.06, 15.0)[-1], 43.0)
        self.assertEqual(common.eval_centres(60.0, 2.0)[0], 2.0)

    def test_baseline_features_track_loudness_and_tone(self):
        sr = 44100
        t = np.arange(sr * 8) / sr
        quiet = 0.05 * np.sin(2 * np.pi * 220 * t)
        loud = 0.5 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 3000 * t)
        a, b = features.mix_frames(quiet, sr), features.mix_frames(loud, sr)
        self.assertGreater(b[:, 0].mean(), a[:, 0].mean() + 15)       # rms dB
        self.assertGreater(b[:, 6].mean(), a[:, 6].mean())            # centroid
        v = features.window_matrix(b, None, [4.0])
        self.assertEqual(v.shape, (1, 29))
        self.assertTrue(np.isfinite(v).all())


if __name__ == "__main__":
    unittest.main()
