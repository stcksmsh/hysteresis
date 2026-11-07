"""Unit tests of the mind spike (mind.py), the lift rule (lifts.py) and the MERP labels (merp_labels.py).
Synthetic data only. Run: cd scripts/emotion && /secondary/hyst-env/emotion/bin/python -m unittest
"""
import unittest

import numpy as np

import lifts
import merp_labels as ml
import mind
from mind import Clip


def make_clip(key, steps=60, dim=12, seed=0, beat=0.5):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((steps, dim)).astype(np.float32)
    return Clip(key, "deam", x, np.arange(0, steps * 0.5, beat))


def fitted(clips, radius=0.9, units=32):
    ear = mind.fit_projector([c.x for c in clips], 6)
    return mind.MindModel(ear, radius, mind.SEED_CORE, units, state_k=8, rehearsal_k=3).fit_projectors(clips)


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.clips = [make_clip(f"c{i}", seed=i) for i in range(6)]

    def test_same_seed_same_output_other_seed_differs(self):
        model_a, model_b = fitted(self.clips), fitted(self.clips)
        a, b = model_a.run(self.clips[:2], 1.0), model_b.run(self.clips[:2], 1.0)
        for k in a:
            np.testing.assert_array_equal(a[k]["mind"], b[k]["mind"])
            np.testing.assert_array_equal(a[k]["rehearsal"], b[k]["rehearsal"])
        ear = mind.fit_projector([c.x for c in self.clips], 6)
        other = mind.MindModel(ear, 0.9, mind.SEED_CORE + 1, 32, state_k=8, rehearsal_k=3).fit_projectors(self.clips)
        c = other.run(self.clips[:1], 1.0)["c0"]["mind"]
        self.assertFalse(np.allclose(c, a["c0"]["mind"]))

    def test_radius_and_time_constants(self):
        core = mind.Core(6, 9, 0.8, units=64)
        self.assertAlmostEqual(float(np.abs(np.linalg.eigvals(core.w)).max()), 0.8, places=4)
        self.assertGreaterEqual(core.tau.min(), mind.TAU_MIN)
        self.assertLessEqual(core.tau.max(), mind.TAU_MAX)
        self.assertAlmostEqual(float((core.w != 0).mean()), mind.DENSITY, delta=0.03)

    def test_shuffling_the_steps_changes_the_state(self):
        model = fitted(self.clips)
        clip = self.clips[0]
        order = np.random.default_rng(1).permutation(len(clip.x))
        plain = model.run([clip], 1.0)[clip.key]["mind"]
        shuffled = model.run([clip], 1.0, {clip.key: order})[clip.key]["mind"]
        self.assertFalse(np.allclose(plain[order], shuffled))
        # pass 1 at the first step sees only that step's input from rest
        first = model.run([Clip("one", "deam", clip.x[order][:1], clip.beats)], 1.0)["one"]["rehearsal"][0]
        shuffled_pass1 = model.run([clip], 1.0, {clip.key: order})[clip.key]["rehearsal"]
        np.testing.assert_allclose(shuffled_pass1[0], first, atol=1e-5)

    def test_rho_zero_drops_the_rehearsal_input_exactly(self):
        model = fitted(self.clips)
        zero = model.run(self.clips[:3], 0.0)
        one = model.run(self.clips[:3], 1.0)
        for k in zero:
            np.testing.assert_array_equal(zero[k]["mind"], zero[k]["rehearsal"])   # pass 2 at rho 0 is pass 1
            np.testing.assert_array_equal(zero[k]["rehearsal"], one[k]["rehearsal"])  # pass 1 never sees it
            self.assertFalse(np.allclose(one[k]["mind"], zero[k]["mind"]))

    def test_core_run_ignores_rehearsal_at_rho_zero(self):
        core = mind.Core(4, 6, 0.9, units=16)
        ear = np.random.default_rng(0).standard_normal((2, 10, 4)).astype(np.float32)
        reh = np.random.default_rng(1).standard_normal((2, 10, 6)).astype(np.float32)
        np.testing.assert_array_equal(core.run(ear), core.run(ear, reh, 0.0))
        self.assertFalse(np.allclose(core.run(ear), core.run(ear, reh, 1.0)))

    def test_rho_scales_the_rehearsal_input(self):
        core = mind.Core(4, 6, 0.9, units=16)
        ear = np.random.default_rng(0).standard_normal((2, 10, 4)).astype(np.float32)
        reh = np.random.default_rng(1).standard_normal((2, 10, 6)).astype(np.float32)
        np.testing.assert_allclose(core.run(ear, reh, 0.5), core.run(ear, reh * 0.5, 1.0), atol=1e-6)
        self.assertFalse(np.allclose(core.run(ear, reh, 0.5), core.run(ear, reh, 1.0)))

    def test_leaky_units_remember_longer_when_slow(self):
        core = mind.Core(1, 3, 0.0 + 1e-9, units=64)
        ear = np.zeros((1, 40, 1), np.float32)
        ear[0, 0, 0] = 5.0
        states = core.run(ear)[0]
        fast, slow = np.argsort(core.tau)[:8], np.argsort(core.tau)[-8:]
        self.assertGreater(np.abs(states[30, slow]).mean(), np.abs(states[30, fast]).mean())

    def test_rehearsal_index_on_a_regular_grid(self):
        beats = np.arange(0, 100, 0.5)            # 120 bpm: one bar = 2 s = 4 steps
        index = mind.rehearsal_index(50, beats)
        np.testing.assert_array_equal(index[0, :46], np.arange(46) + 4)
        np.testing.assert_array_equal(index[0, 46:], -1)
        self.assertEqual(index[1, 0], 16)          # 4 bars = 16 steps
        self.assertEqual(index[2, 0], 64 if 64 < 50 else -1)   # 16 bars = 64 steps: after the end
        reh = mind.rehearsal_input(np.arange(50)[:, None] * np.ones((1, 2)), index)
        self.assertEqual(reh.shape, (50, 6))
        self.assertEqual(reh[3, 0], 7.0)           # step 3 remembers step 7 at +1 bar
        self.assertEqual(reh[3, 4], 0.0)           # nothing remembered 16 bars ahead of step 3
        self.assertEqual(reh[49, 0], 0.0)

    def test_mind_state_field_is_additive_and_complete(self):
        mind_state = np.random.default_rng(0).standard_normal((20, 8))
        field = mind.mind_state_field(mind_state, mind_state, 1.0, mind.SEED_CORE, np.arange(0, 10, 1.0), {"arousal": [0.0] * 20}, {"pca": "x"})
        for key in ("version", "seed", "rho", "hopSeconds", "steps", "perBeat", "readouts", "provenance"):
            self.assertIn(key, field)
        self.assertEqual(len(field["steps"]), 20)
        self.assertEqual(len(field["perBeat"]), 10)
        self.assertNotIn("pulse", field)


class LiftTests(unittest.TestCase):
    BEATS = np.arange(0, 200, 0.5)

    @staticmethod
    def ramp(length_s, knots):
        """Piecewise-linear curve at 10 Hz through (time s, value) knots, held flat before and after."""
        times, values = zip(*knots)
        return np.interp(np.arange(int(length_s * 10)) / 10.0, times, values)

    def test_a_clean_rise_gives_one_lift_before_its_onset(self):
        x = self.ramp(60, [(20, 0.2), (26, 0.8)])
        found = lifts.find_lifts(x, self.BEATS)
        self.assertEqual(len(found), 1)
        self.assertAlmostEqual(found[0], 17.5 - 1.5, delta=0.4)

    def test_a_quick_jitter_is_not_a_lift(self):
        x = np.full(600, 0.5)
        x[200:203] = 0.95
        x[320:324] = 0.05
        self.assertEqual(lifts.find_lifts(x, self.BEATS), [])

    def test_an_end_flick_is_not_a_lift(self):
        x = self.ramp(60, [(57, 0.3), (58.5, 0.9)])
        self.assertEqual(lifts.find_lifts(x, self.BEATS), [])

    def test_the_first_two_seconds_are_never_a_lift(self):
        x = self.ramp(60, [(0, 0.1), (3, 0.9)])
        self.assertEqual(lifts.find_lifts(x, self.BEATS), [])

    def test_a_masked_span_blocks_a_rise_that_touches_it(self):
        x = self.ramp(100, [(20, 0.2), (26, 0.5), (60, 0.5), (66, 0.9)])
        self.assertEqual(len(lifts.find_lifts(x, self.BEATS)), 2)
        both = lifts.find_lifts(x, self.BEATS, masks=[(24.0, 30.0)])
        self.assertEqual(len(both), 1)
        self.assertGreater(both[0], 50)
        self.assertEqual(len(lifts.find_lifts(x, self.BEATS, masks=[(80.0, 99.0)])), 2)

    def test_two_lifts_closer_than_sixteen_beats_keep_the_first(self):
        x = self.ramp(100, [(0, 0.1), (20, 0.1), (22, 0.5), (26, 0.5), (28, 0.9)])
        close = lifts.find_lifts(x, self.BEATS)                     # 120 bpm: 16 beats = 8 s; rises 6 s apart
        self.assertEqual(len(close), 1)
        slow = lifts.find_lifts(x, np.arange(0, 200, 0.2))          # 300 bpm: 16 beats = 3.2 s: both stay
        self.assertEqual(len(slow), 2)
        self.assertLess(close[0], 20)

    def test_a_flat_curve_has_no_lift(self):
        self.assertEqual(lifts.find_lifts(np.full(500, 0.4), self.BEATS), [])


class LabelTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        self.raw = {"rater": "r1", "song": "s", "arousal": np.clip(np.cumsum(rng.normal(0, 0.05, 330)), -1, 1),
                    "valence": np.clip(np.cumsum(rng.normal(0, 0.05, 330)), -1, 1)}
        # the "filtered" trial: smoothed raw, every 5th sample, end-aligned with 16 samples skipped
        self.filt = {"rater": "r1", "song": "s",
                     **{ax: ml.smooth(self.raw[ax])[17::5] for ax in ("arousal", "valence")}}

    def test_best_offset_finds_the_alignment(self):
        offset, mse = ml.best_offset(ml.smooth(self.raw["arousal"]), self.filt["arousal"])
        self.assertEqual(offset, 17)
        self.assertLess(mse, 1e-20)

    def test_the_data_chooses_no_rescale_when_the_file_was_not_rescaled(self):
        pairs = [(self.raw, self.filt)]
        report = ml.match_variants(pairs)
        self.assertEqual(ml.choose_variant(report), ("none", "before"))
        self.assertLess(report[("none", "before")]["rmse"], 1e-9)
        self.assertGreater(report[("trial", "before")]["rmse"], 0.01)

    def test_the_data_chooses_the_rater_rescale_when_the_file_was_rescaled(self):
        other = dict(self.raw, song="t", arousal=self.raw["arousal"] * 0.5, valence=self.raw["valence"] * 0.5)
        limits = ml._limits([(self.raw, None), (other, None)])
        filt = {"rater": "r1", "song": "s",
                **{ax: ml.smooth(ml.rescale(self.raw[ax], *limits[("r1", ax)]))[17::5] for ax in ("arousal", "valence")}}
        filt2 = {"rater": "r1", "song": "t",
                 **{ax: ml.smooth(ml.rescale(other[ax], *limits[("r1", ax)]))[17::5] for ax in ("arousal", "valence")}}
        report = ml.match_variants([(self.raw, filt), (other, filt2)])
        self.assertEqual(ml.choose_variant(report), ("rater", "before"))

    def test_duplicates_resolve_to_the_best_matching_trial(self):
        wrong = dict(self.raw, arousal=self.raw["arousal"][::-1].copy(), valence=self.raw["valence"][::-1].copy())
        pairs, duplicates = ml.resolve_kept([wrong, self.raw], [self.filt])
        self.assertEqual(duplicates, 1)
        self.assertIs(pairs[0][0], self.raw)

    def test_step_means_and_the_song_average(self):
        series = np.arange(40, dtype=float)                       # sample i is t = i / 10 s
        steps = ml.step_means(series, 8)
        self.assertEqual(steps[0], np.mean([0, 1, 2]))           # [-0.25, 0.25) holds samples 0, 1, 2
        self.assertEqual(steps[1], np.mean([3, 4, 5, 6, 7]))     # [0.25, 0.75)
        self.assertTrue(np.isnan(ml.step_means(series, 12)[11]))  # step 11 starts at 5.25 s: no samples
        a = dict(self.raw, rater="r1")
        b = dict(self.raw, rater="r2", arousal=self.raw["arousal"] * 0.0, valence=self.raw["valence"] * 0.0)
        pairs = [(a, self.filt), (b, dict(self.filt, rater="r2"))]
        out = ml.song_labels(pairs, ("none", "before"), {"s": 32.0})
        self.assertEqual(out["s"]["trials"], 2)
        np.testing.assert_allclose(out["s"]["arousal10"], ml.smooth(a["arousal"])[:320] / 2, atol=1e-12)
        self.assertEqual(len(out["s"]["arousal"]), 65)


if __name__ == "__main__":
    unittest.main()
