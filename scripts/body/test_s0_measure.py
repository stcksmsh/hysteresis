"""Tests for s0_measure.py (WO19). Run: /secondary/hyst-env/brain/bin/python -m unittest test_s0_measure (from scripts/body)."""
import unittest

import numpy as np

import s0_measure as S

HZ = S.HZ


def song(freq, offset=(0, 0, 0, 0, 0), secs=300, seed=0, amp=(40, 25, 30, 25, 20)):
    """One fixed 5-joint shape (sines, fixed phases) played at `freq` Hz around `offset` deg; seed only jitters a little."""
    t = np.arange(int(secs * HZ)) / HZ
    ph = np.array([0.0, 1.1, 2.3, 0.7, 1.9])
    q = np.stack([amp[j] * np.sin(2 * np.pi * freq * (1 + 0.5 * j / 5) * t + ph[j]) + offset[j] for j in range(5)], 1)
    return q + np.random.default_rng(seed).normal(0, 0.3, q.shape)


class Js(unittest.TestCase):
    def test_identical_is_zero_disjoint_is_one(self):
        a = {(0, 0, 0): 1.0}
        b = {(5, 5, 5): 1.0}
        self.assertAlmostEqual(S.js_dist(a, a), 0.0)
        self.assertAlmostEqual(S.js_dist(a, b), 1.0)            # base 2, distance = sqrt(divergence), disjoint support -> 1

    def test_speed_only_difference_gives_small_js_posture_difference_large(self):
        slow, fast = song(0.05), song(0.11, seed=1)
        shifted = song(0.05, offset=(0, 35, -30, 0, 0), seed=2)
        half = S.js_dist(*[S.cell_dist(h) for h in S.split_halves(slow)])
        speed = S.js_dist(S.cell_dist(slow), S.cell_dist(fast))
        post = S.js_dist(S.cell_dist(slow), S.cell_dist(shifted))
        self.assertLess(speed, 0.35)
        self.assertGreater(post, 0.8)
        self.assertGreater(post, 2 * speed)
        self.assertLess(half, post)          # finite-sample bias keeps the half-song control above 0 (that is why it is reported)


class Measures(unittest.TestCase):
    def test_peak_speed_and_postures(self):
        still = np.zeros((500, 5))
        m = S.song_measures(still)
        self.assertEqual(m["postures"], 1)
        self.assertAlmostEqual(m["peak_hand_speed"], 0.0)
        self.assertAlmostEqual(m["shoulder_sd_deg"], 0.0)
        m2 = S.song_measures(song(0.1, secs=60))
        self.assertGreater(m2["postures"], 5)
        self.assertGreater(m2["peak_hand_speed"], 0.0)

    def test_program_entropy(self):
        self.assertAlmostEqual(S.program_entropy(np.zeros(100, int)), 0.0)
        self.assertAlmostEqual(S.program_entropy(np.arange(800) % 8), 3.0)


class Pairs(unittest.TestCase):
    def test_greedy_one_to_one_different_artists(self):
        tempo = {"a": 100.0, "b": 102.0, "c": 103.0, "d": 140.0, "e": 142.0, "f": 200.0}
        art = {"a": 1, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5}
        pr = S.tempo_pairs(tempo, art, list(tempo))
        names = {frozenset(p[:2]) for p in pr}
        self.assertIn(frozenset("de"), names)
        self.assertIn(frozenset("bc"), names)                  # a-b share an artist; closest allowed pair b-c (1 BPM) wins before a-c (3)
        used = [x for p in pr for x in p[:2]]
        self.assertEqual(len(used), len(set(used)))
        self.assertNotIn("f", used)
        self.assertTrue(all(p[2] <= 5 for p in pr))


class Afc(unittest.TestCase):
    def test_speed_only_songs_are_separable_by_speed_features(self):
        r = S.pair_2afc(song(0.05), song(0.11, seed=1))
        self.assertGreaterEqual(r["acc"], 0.9)

    def test_posture_differing_songs_are_separable(self):
        r = S.pair_2afc(song(0.05), song(0.05, offset=(0, 35, -30, 0, 0), seed=1))
        self.assertGreaterEqual(r["acc"], 0.9)

    def test_same_process_two_songs_are_not_separable_and_shuffle_is_chance(self):
        # two songs drawn from the same process (same shape and speed, different noise seed): about chance
        rng = np.random.default_rng(3)
        accs, shuf = [], []
        for k in range(12):
            r = S.pair_2afc(song(0.07, seed=2 * k), song(0.07, seed=2 * k + 1), rng, n_shuffle=4)
            accs.append(r["acc"])
            shuf += r["shuffled"]
        self.assertLess(abs(np.mean(shuf) - 0.5), 0.1)
        self.assertLess(np.mean(accs), 0.8)

    def test_shuffled_control_on_separable_songs_is_near_chance(self):
        rng = np.random.default_rng(5)
        shuf = []
        for k in range(10):
            shuf += S.pair_2afc(song(0.05, seed=k), song(0.11, seed=100 + k), rng, n_shuffle=6)["shuffled"]
        self.assertLess(abs(np.mean(shuf) - 0.5), 0.1)

    def test_unequal_song_lengths_do_not_lift_the_shuffled_control(self):
        rng = np.random.default_rng(7)
        shuf = []
        for k in range(12):
            shuf += S.pair_2afc(song(0.05, secs=600, seed=k), song(0.11, secs=130, seed=50 + k), rng, n_shuffle=6)["shuffled"]
        self.assertLess(abs(np.mean(shuf) - 0.5), 0.07)

    def test_too_short_song_is_skipped(self):
        self.assertIsNone(S.pair_2afc(song(0.05, secs=100), song(0.11, secs=300)))

    def test_clips_are_non_overlapping_and_in_their_half(self):
        q = np.arange(300 * HZ * 5, dtype=float).reshape(-1, 5)
        a, b = S.clips_of(q, 0), S.clips_of(q, 1)
        self.assertEqual((len(a), len(b)), (5, 5))
        self.assertLess(a[-1][-1, 0], b[0][0, 0])

    def test_bootstrap_interval_brackets_the_mean(self):
        b = S.boot_mean([0.5, 0.6, 0.7, 0.8])
        self.assertTrue(b["lo"] <= b["mean"] <= b["hi"])
        self.assertAlmostEqual(b["mean"], 0.65)


if __name__ == "__main__":
    unittest.main()
