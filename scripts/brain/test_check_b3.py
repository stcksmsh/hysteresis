"""Tests for check_b3.py: the maths of every check on synthetic signals (a known repeat gives a drop, a known splice a z spike)."""
import unittest

import numpy as np

import b2
import check_b3 as C
import core
from fast_features import SR, fast_features

STATS = (np.zeros(core.FEAT), np.ones(core.FEAT))


def tone_audio(freqs_per_second, seed=0, noise=0.01):
    rng = np.random.default_rng(seed)
    t = np.arange(SR) / SR
    y = np.concatenate([np.sin(2 * np.pi * f * t) for f in freqs_per_second]) * 0.5
    return (y + noise * rng.standard_normal(len(y))).astype(np.float32)


def novelty_total(x):
    """Toy 'memory': per 0.1 s bin, the distance of the bin's features to the nearest earlier bin at least 2 s back (0 for the first 2 s)."""
    z = x[:, :core.FEAT]
    nb = len(z) // 10
    f = z[:nb * 10].reshape(nb, 10, -1).mean(1)
    out = np.zeros(nb)
    for k in range(20, nb):
        out[k] = np.sqrt(((f[:k - 19] - f[k]) ** 2).sum(1)).min()
    return out


def change_total(x):
    """Toy 'surprise at change': distance of each bin's features from the mean of the previous 2 s."""
    z = x[:, :core.FEAT]
    nb = len(z) // 10
    f = z[:nb * 10].reshape(nb, 10, -1).mean(1)
    out = np.zeros(nb)
    for k in range(20, nb):
        out[k] = np.sqrt(((f[k] - f[k - 20:k].mean(0)) ** 2).sum())
    return out


class TestHelpers(unittest.TestCase):
    def test_boot_ci(self):
        lo, hi, pt = C.boot_ci(np.full(10, 3.0))
        self.assertEqual((lo, hi, pt), (3.0, 3.0, 3.0))
        lo, hi, pt = C.boot_ci(np.arange(100.0))
        self.assertAlmostEqual(pt, 49.5)
        self.assertTrue(lo < 49.5 < hi and hi - lo < 15)
        self.assertEqual(C.boot_ci(np.arange(10.0)), C.boot_ci(np.arange(10.0)))

    def test_crossfade_keeps_constants_and_lengths(self):
        a, b = np.ones(SR, np.float32), np.ones(SR, np.float32)
        out = C.xfade_concat([a, b, a])
        n = int(round(C.XF * SR))
        self.assertEqual(len(out), 3 * SR - 2 * n)
        np.testing.assert_allclose(out, 1.0, atol=1e-6)
        ph = C.frames_concat([np.ones((100, 2)), np.ones((100, 2)), np.ones((100, 2))])
        self.assertEqual(len(ph), 300 - 2 * 5)

    def test_lane_mean_stamps_and_window_sd(self):
        lane = np.arange(100.0)                    # bin k stamped 0.1 (k + 1)
        self.assertEqual(C.lane_mean(lane, 0.0, 0.3), 1.0)         # bins 0, 1, 2
        self.assertEqual(C.lane_mean(lane, 1.0, 2.0), np.mean(np.arange(10, 20)))
        w = np.repeat([0.0, 2.0, 0.0, 2.0], 80)
        self.assertAlmostEqual(C.window_sd(w), 1.0)

    def test_song_scores_exact(self):
        z = np.random.default_rng(0).standard_normal((2100, core.FEAT)).astype(np.float32)
        y = [b2.targets(z, h)[0] for h in core.HORIZONS]
        nll, mse, n = C.song_scores(y, [np.zeros_like(a) for a in y], z)
        np.testing.assert_allclose(mse, 0.0, atol=1e-12)
        np.testing.assert_allclose(nll, 0.5 * math_log2pi(), rtol=1e-6)
        self.assertTrue((n > 0).all())
        self.assertEqual(n[0], 210 - 2)         # bins 10k + 9 with 10k + 9 + 20 <= 2100: k = 0 .. 207


def math_log2pi():
    return float(np.log(2 * np.pi))


class TestGate43(unittest.TestCase):
    def scores(self, b3_nll, base_nll, b3_mse, base_mse, n_songs=12):
        def s(nll, mse):
            return {"nll": np.tile(np.asarray(nll, float) / 4, (n_songs, 4)) + np.linspace(0, 0.01, n_songs)[:, None],
                    "mse": np.full((n_songs, 4), float(mse)), "n": np.full((n_songs, 4), 100.0)}
        return {"b3": s(b3_nll, b3_mse), "persistence": s(base_nll, base_mse), "ar_ridge": s(base_nll + 0.5, base_mse * 1.1), "b2": s(base_nll + 1, base_mse * 1.2)}

    def test_passes_when_better_on_both(self):
        r = C.gate_43(self.scores(4.0, 5.0, 0.80, 1.0))
        self.assertTrue(r["pass"])
        self.assertAlmostEqual(r["mse_ratio_to_best"], 0.8)
        self.assertTrue(all(v["above_0"] for v in r["baselines"].values()))

    def test_fails_on_the_mse_margin(self):
        r = C.gate_43(self.scores(4.0, 5.0, 0.97, 1.0))          # 3 % below, margin is 5 %
        self.assertFalse(r["mse_margin_ok"])
        self.assertFalse(r["pass"])
        self.assertTrue(all(v["above_0"] for v in r["baselines"].values()))

    def test_fails_when_one_baseline_is_not_beaten(self):
        r = C.gate_43(self.scores(4.0, 3.9, 0.5, 1.0))
        self.assertFalse(r["baselines"]["persistence"]["above_0"])
        self.assertFalse(r["pass"])


class TestBaselines(unittest.TestCase):
    def test_ar_rows_layout(self):
        z = np.arange(2000 * core.FEAT, dtype=np.float32).reshape(2000, core.FEAT)
        X = C.ar_rows(z, np.array([150]))                       # frame s = 1509
        self.assertEqual(X.shape, (1, 100 * 44 + 32 * 44 + 1))
        np.testing.assert_array_equal(X[0, :44], z[1410])         # the 100 frames s-99 .. s, oldest first
        np.testing.assert_array_equal(X[0, 99 * 44:100 * 44], z[1509])
        np.testing.assert_allclose(X[0, 4400:4444], z[1460:1510].mean(0), rtol=1e-6)   # pooled block 0: the latest 0.5 s
        self.assertEqual(X[0, -1], 1.0)
        early = C.ar_rows(z, np.array([0]))                      # frames before the song are zeros
        self.assertEqual(float(early[0, :44 * 90].max()), 0.0)

    def test_persistence_and_ar_on_a_predictable_series(self):
        rng = np.random.default_rng(1)
        def series(T):
            from scipy.signal import lfilter
            e = rng.standard_normal((T, core.FEAT)).astype(np.float32)
            return lfilter([0.1], [1.0, -0.97], e, axis=0).astype(np.float32)
        tr, te = [series(30000) for _ in range(4)], series(30000)
        C.ARRidge.ALPHAS = (1.0,)
        ar, pers = C.ARRidge().fit(tr, stride=2), C.Persistence().fit(tr)
        x = np.concatenate([te, np.zeros((len(te), 2), np.float32)], 1)
        sa = C.song_scores(*ar.bins(x), te)
        sp = C.song_scores(*pers.bins(x), te)
        self.assertTrue((sa[1][1:] < 0.7 * sp[1][1:]).all())       # AR's MSE well below persistence on the slow layers
        self.assertLess(sa[1][0], 1.1 * sp[1][0])                  # and about equal at +100 ms, where the last frame is hard to beat
        self.assertTrue(np.isfinite(sa[0]).all())


class TestHabituation(unittest.TestCase):
    def test_plan(self):
        p = C.hab_plan(120.0, 5)
        self.assertEqual(p, C.hab_plan(120.0, 5))
        spans = sorted((p[k], p[k] + L) for k, L in (("S", 16), ("Sp", 16), ("F", 30)))
        self.assertTrue(all(a[1] <= b[0] + 1e-9 for a, b in zip(spans, spans[1:])))
        self.assertTrue(spans[0][0] >= 0 and spans[-1][1] <= 120.0)
        self.assertIsNone(C.hab_plan(60.0, 5))
        t0, t1 = C.hab_second_window(16.0, 30.0)
        self.assertAlmostEqual(t0, 45.9)
        self.assertAlmostEqual(t1, 61.85)

    def test_stats_rules(self):
        self.assertTrue(C.hab_stats([1.0] * 8, [2.0] * 8)["pass"])
        self.assertFalse(C.hab_stats([1.0] * 8, [8.0] * 8)["pass"])          # ratio 0.125
        self.assertFalse(C.hab_stats([1.0, -1.0, 0.5, -0.5, 0.1, -0.1], [1.0] * 6)["pass"])   # interval includes 0

    def test_a_known_repeat_gives_a_drop(self):
        songs, audio, full = [], {}, {}
        for n in range(3):
            rng = np.random.default_rng(10 + n)
            y = tone_audio(rng.uniform(200, 3000, 95), seed=n)
            audio[f"s{n}"] = y
            T = len(fast_features(y))
            songs.append((f"s{n}", len(y) / SR, np.tile([1.0, 0.0], (T, 1)).astype(np.float32)))
            full[f"s{n}"] = novelty_total(C.song_inputs_from_audio(y, songs[-1][2], *STATS))
        drops, sds, skipped = C.habituation(songs, novelty_total, lambda s: audio[s], STATS, full)
        self.assertEqual(skipped, [])
        self.assertEqual(len(drops), 3)
        self.assertTrue(all(d > 0 for d in drops), drops)
        self.assertGreater(np.median(np.array(drops) / np.array(sds)), 0.25)
        self.assertTrue(C.hab_stats(drops, sds)["pass"])


class TestSplice(unittest.TestCase):
    def test_plan_and_z(self):
        c = C.splice_plan(120.0, 3)
        self.assertEqual(len(c), 4)
        self.assertTrue(min(c) >= 35.0 and max(c) <= 110.0 and (np.diff(c) >= 5.0).all())
        self.assertEqual(c, C.splice_plan(120.0, 3))
        self.assertIsNone(C.splice_plan(50.0, 3))
        lane = np.zeros(1000)
        lane[600:] = 10.0 + np.random.default_rng(0).standard_normal(400) * 0.0
        base = np.random.default_rng(1).standard_normal(1000) * 0.1
        z = C.splice_z(lane + base, 60.0)
        self.assertGreater(z, 20.0)
        self.assertLess(abs(C.splice_z(base, 60.0)), 3.0)

    def test_phase_match(self):
        T = 3000
        ang = (np.arange(T) / 50.0) * 2 * np.pi % (2 * np.pi)      # one beat every 0.5 s
        phase = np.stack([np.cos(ang), np.sin(ang)], 1)
        t = C.phase_match(phase, 20.13, 30.0)
        self.assertTrue(abs(t - 20.13) >= 5.0)
        self.assertLess(abs(((t - 20.13) / 0.5 + 0.5) % 1.0 - 0.5), 0.03)          # a whole number of beats away

    def test_a_known_splice_gives_a_z_spike(self):
        n = 2
        audio = {"a": tone_audio([440] * 90, seed=1), "b": tone_audio([3000] * 90, seed=2, noise=0.05)}
        songs = [(k, len(y) / SR, np.tile([1.0, 0.0], (len(fast_features(y)), 1)).astype(np.float32)) for k, y in audio.items()]
        rows, skipped = C.splice(songs, change_total, lambda s: audio[s], STATS)
        self.assertEqual(skipped, [])
        self.assertEqual(len(rows), n)
        for r in rows:
            self.assertTrue(all(z >= 3.0 for z in r["cross"]), r)
            self.assertTrue(all(w < 3.0 for w in r["within"]), r)
        st = C.splice_stats(rows)
        self.assertEqual(st["frac_cross_z_ge_3"], 1.0)
        self.assertGreater(st["cross_minus_within_mean"], 0)


class TestPAC(unittest.TestCase):
    def test_coupled_vs_uncoupled(self):
        fs, T = 100.0, 6000
        t = np.arange(T) / fs
        rng0 = np.random.default_rng(7)
        wander = np.convolve(rng0.standard_normal(T), np.ones(300) / 300, "same")
        phase = np.angle(np.exp(1j * 2 * np.pi * np.cumsum(0.5 + 8 * wander) / fs))   # not periodic: shifted copies lose the coupling
        coupled = 1.0 + 0.9 * np.cos(phase)
        mi, p, sur = C.pac(phase, coupled, 1)
        self.assertGreater(mi, 0.05)
        self.assertLess(p, 0.05)
        rng = np.random.default_rng(0)
        mi2, p2, sur2 = C.pac(phase, 1.0 + 0.05 * rng.standard_normal(T), 2)
        self.assertLess(mi2, 0.01)
        self.assertGreater(p2, 0.05)
        self.assertAlmostEqual(C.tort_mi(phase, np.ones(T)), 0.0, places=9)

    def test_layer_signal_band(self):
        fs, T = 100.0, 4000
        t = np.arange(T) / fs
        x = np.stack([np.sin(2 * np.pi * 6 * t), np.sin(2 * np.pi * 15 * t)] + [np.zeros(T)] * 126, 1)
        x[:, 1] *= 0.9
        s_in = C.layer_signal(x[:, [0] + [2] * 127], (4.0, 8.0))
        s_out = C.layer_signal(x[:, [1] + [2] * 127], (4.0, 8.0))
        self.assertGreater(np.std(s_in), 20 * np.std(s_out))


class TestPrecheck(unittest.TestCase):
    def test_within_r_and_ridge(self):
        a = np.arange(10.0)
        self.assertAlmostEqual(C.within_r(a + 5, a * 2), 1.0)
        self.assertAlmostEqual(C.within_r(-a, a), -1.0)
        self.assertTrue(np.isnan(C.within_r(np.ones(10), a)))
        X = np.random.default_rng(0).standard_normal((200, 5))
        y = X @ np.array([1.0, 0, 0, 0, 0])
        f = C.ridge_xy(X, y, 1e-6)
        np.testing.assert_allclose(f(X), y, atol=1e-3)

    def test_pooled_steps(self):
        a = np.arange(20.0)[:, None]
        p = C.pooled_steps(a, 5)
        np.testing.assert_array_equal(p[:, 0][:4], [2.0, 7.0, 12.0, 17.0])
        self.assertTrue(np.isnan(p[4, 0]))

    def test_precheck_ranks_a_good_feature_above_noise(self):
        rng = np.random.default_rng(0)
        clips = []
        for i in range(10):
            y = np.sin(np.arange(80) / 6.0 + i)
            clips.append({"key": f"k{i}", "dataset": "deam", "brain": np.stack([y, rng.standard_normal(80)], 1),
                          "fast": rng.standard_normal((80, 3)), "y": y})
        folds = {f"k{i}": i % 5 for i in range(10)}
        out = C.precheck(clips, folds, core2b={c["key"]: c["y"] for c in clips})
        self.assertGreater(out["deam"]["brain"]["mean_r"], 0.95)
        self.assertAlmostEqual(out["deam"]["core2b"]["mean_r"], 1.0)
        self.assertLess(out["deam"]["smoothed_baseline"]["mean_r"], 0.6)


class TestMain(unittest.TestCase):
    def test_smoke_results_never_go_to_the_results_folder(self):
        with self.assertRaises(SystemExit):
            C.main(["--ckpt", "x", "--manifest", "x", "--stats", "x", "--smoke", "--out", str(C.RESULTS_DIR / "x")])


if __name__ == "__main__":
    unittest.main()
