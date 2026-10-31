"""Tests of check 3 round 2 (check3r2.py, decoder.fit_map_bounded). Synthetic data only; the body generator is the real one."""
import json
import pathlib
import tempfile
import unittest

import numpy as np

import check3
import check3r2 as r2
import common
import decoder
from mind import Clip
from test_check3 import corpus, config
from test_decoder import small_surrogate


def rated_clips():
    """Hand-made clips with known labels."""
    x = np.zeros((48, 3), dtype=np.float32)
    y = np.full((48, 2), np.nan)
    y[[30, 34, 38, 42, 46]] = [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6], [0.7, 0.8], [0.9, 1.0]]
    deam = Clip("deam_0", "deam", x, np.zeros(1), y, np.array([30, 34, 38, 42, 46]))
    merp_y = np.stack([np.arange(32) / 32.0, -np.arange(32) / 32.0], axis=1)
    merp = Clip("merp_0", "merp", np.zeros((32, 3), np.float32), np.zeros(1), merp_y, np.arange(0, 32, 4))
    profile = np.arange(9) / 10.0
    emo = Clip("emotify_0", "emotify", np.zeros((20, 3), np.float32), np.zeros(1), None, np.array([4]), profile)
    song = Clip("song_0", "song", np.zeros((16, 3), np.float32), np.zeros(1))
    return deam, merp, emo, song


class RatingTests(unittest.TestCase):
    def test_labels_are_the_mean_over_the_labelled_steps_of_the_window(self):
        deam, merp, emo, song = rated_clips()
        r = r2.segment_ratings([deam, merp, emo, song])
        self.assertEqual(r["va"].shape, (3 + 2 + 1 + 1, 2))
        self.assertTrue(np.isnan(r["va"][0]).all())                       # steps 0-15: no label
        np.testing.assert_allclose(r["va"][1], [0.1, 0.2])                # steps 16-31: one label (step 30)
        np.testing.assert_allclose(r["va"][2], [0.6, 0.7])                # steps 32-47: labels at 34, 38, 42, 46
        np.testing.assert_allclose(r["va"][3], [np.arange(16).mean() / 32, -np.arange(16).mean() / 32])
        np.testing.assert_allclose(r["va"][4], [np.arange(16, 32).mean() / 32, -np.arange(16, 32).mean() / 32])

    def test_segments_without_labels_are_left_out_and_gems_are_separate(self):
        deam, merp, emo, song = rated_clips()
        r = r2.segment_ratings([deam, merp, emo, song])
        np.testing.assert_array_equal(np.isfinite(r["va"]).all(axis=1), [False, True, True, True, True, False, False])
        np.testing.assert_array_equal(np.isfinite(r["gems"]).all(axis=1), [False] * 5 + [True, False])
        np.testing.assert_allclose(r["gems"][5], np.arange(9) / 10.0)
        self.assertTrue(np.isnan(r["gems"][:5]).all())

    def test_a_missing_value_in_one_axis_drops_that_step_not_the_window(self):
        deam, *_ = rated_clips()
        deam.y[34, 1] = np.nan
        r = r2.segment_ratings([deam])
        np.testing.assert_allclose(r["va"][2], [(0.5 + 0.7 + 0.9) / 3, (0.6 + 0.8 + 1.0) / 3])

    def dial(self):
        steps = 32
        return {"song_0": {"energy10": np.repeat(np.arange(steps) / steps, 5), "masks": [(0.0, 4.0)],
                           "light10": np.repeat(np.full(steps, 0.25), 5), "heavy10": np.repeat(np.full(steps, 0.75), 5)}}

    def test_dial_rating_is_three_numbers_masked_steps_left_out(self):
        song = Clip("song_0", "song", np.zeros((32, 3), np.float32), np.zeros(1))
        out = r2.dial_ratings([song], self.dial())
        self.assertEqual(out.shape, (2, 3))
        # steps touching the mask 0-4 s (steps 0..8) are missing from the first window's mean
        energy = r2.c1._dial_steps(self.dial()["song_0"]["energy10"], 32, [(0.0, 4.0)])
        self.assertTrue(np.isnan(energy[:9]).all() and np.isfinite(energy[9:]).all())
        np.testing.assert_allclose(out[0], [energy[9:16].mean(), 0.25, 0.75], atol=1e-9)
        np.testing.assert_allclose(out[1], [energy[16:32].mean(), 0.25, 0.75], atol=1e-9)

    def test_a_song_without_pass_b_has_no_dial_rating(self):
        song = Clip("song_0", "song", np.zeros((32, 3), np.float32), np.zeros(1))
        d = self.dial()
        del d["song_0"]["heavy10"]
        self.assertTrue(np.isnan(r2.dial_ratings([song], d)).all())
        d = self.dial()
        d["song_0"]["masks"] = [(0.0, 100.0)]
        self.assertTrue(np.isnan(r2.dial_ratings([song], d)).all())


class FoldTests(unittest.TestCase):
    def test_unrated_and_failed_segments_leave_the_matrices_and_failed_is_counted(self):
        prep = {"keys_te": ["a", "a", "b", "b", "c", "c"]}
        rendered = {"ok": np.array([True, True, False, True, True, False]), "desc": np.arange(30.0).reshape(6, 5),
                    "desc_mean": np.zeros(5), "desc_std": np.ones(5)}
        ratings = np.array([[0.1, 0.1], [np.nan, 0.2], [0.3, 0.3], [0.4, 0.4], [0.5, 0.5], [np.nan, np.nan]])
        fold = r2.rating_fold(prep, rendered, ratings)
        self.assertEqual(fold["songs"], ["a", "b", "c"])
        np.testing.assert_array_equal(fold["z"], ratings[[0, 3, 4]])
        np.testing.assert_array_equal(fold["desc_z"], rendered["desc"][[0, 3, 4]])
        self.assertEqual((fold["total"], fold["failed"]), (4, 1))


class GateDirectionTests(unittest.TestCase):
    def folds(self, aligned, seed):
        rng = np.random.default_rng(seed)
        out = []
        for f in range(5):
            ratings = rng.normal(size=(40, 2))
            desc = ratings @ rng.normal(size=(2, 9)) if aligned else rng.normal(size=(40, 9))
            out.append({"z": ratings, "desc_z": desc, "songs": [f"f{f}s{i // 2}" for i in range(40)], "total": 40, "failed": 0})
        return out

    def gate2(self, dec_aligned, base_aligned):
        dec, base = self.folds(dec_aligned, 1), self.folds(base_aligned, 2)
        for f in range(5):
            base[f]["songs"] = dec[f]["songs"]
        _, dm = check3.score_map(dec, 1, keep=True)
        _, bm = check3.score_map(base, 1, keep=True)
        return check3.bootstrap_difference(dec, dm, base, bm, 200)

    def test_gate_2_is_decoder_minus_baseline_on_the_ratings(self):
        up, down, same = self.gate2(True, False), self.gate2(False, True), self.gate2(False, False)
        self.assertTrue(up["pass"] and up["difference"][0] > 0)
        self.assertFalse(down["pass"])
        self.assertLess(down["difference"][1], 0)
        self.assertFalse(same["pass"])

    def test_gate_1_passes_for_ratings_that_predict_motion_and_fails_for_noise(self):
        self.assertTrue(check3.score_map(self.folds(True, 3), 100)["pass"])
        self.assertFalse(check3.score_map(self.folds(False, 5), 100)["pass"])


class BoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surrogate = small_surrogate()
        cls.lanes = np.random.default_rng(11).random((300, 4))

    def test_zero_bounds_are_round_ones_map_bit_for_bit(self):
        a = decoder.fit_map(self.lanes, self.surrogate, steps=40)
        zero = {l: 0.0 for l in decoder.links()}
        b = decoder.fit_map(self.lanes, self.surrogate, steps=40, bounds=zero)
        np.testing.assert_array_equal(a.bodies(self.lanes), b.bodies(self.lanes))

    def test_a_bound_is_a_floor_on_the_anchored_weight(self):
        m = decoder.fit_map(self.lanes, self.surrogate, steps=40, bounds={(0, "size"): 4.0, (1, "weight"): 2.0})
        w = m.weights.detach().numpy()
        self.assertGreaterEqual(w[decoder.DIMS.index("size"), 0], 4.0)
        self.assertGreaterEqual(w[decoder.DIMS.index("weight"), 1], 2.0)
        self.assertGreaterEqual(w[decoder.DIMS.index("energy"), 0], 0.0)

    def test_the_bound_makes_the_link_hold_on_the_training_segments(self):
        top = {l: decoder.BOUND_GRID[-1] for l in decoder.links()}
        m = decoder.fit_map(self.lanes, self.surrogate, steps=60, bounds=top)
        for name, r in decoder.link_r(m, self.lanes).items():
            self.assertGreater(r, 0.5, name)

    def test_link_r_is_the_pearson_of_the_lane_and_the_decoded_dimension(self):
        m = decoder.fit_map(self.lanes, self.surrogate, steps=20)
        bodies = m.bodies(self.lanes)
        got = decoder.link_r(m, self.lanes)
        self.assertEqual(sorted(got), ["energy->energy", "energy->size", "energy->time", "power->weight"])
        self.assertAlmostEqual(got["energy->size"], np.corrcoef(self.lanes[:, 0], bodies[:, decoder.DIMS.index("size")])[0, 1], places=12)
        self.assertAlmostEqual(got["power->weight"], np.corrcoef(self.lanes[:, 1], bodies[:, decoder.DIMS.index("weight")])[0, 1], places=12)
        self.assertEqual(len(decoder.link_r(m, self.lanes, power_anchor=False)), 3)

    def test_report_is_consistent_with_the_map(self):
        m, rep = decoder.fit_map_bounded(self.lanes, self.surrogate, steps=40)
        self.assertEqual(rep["trainR"], decoder.link_r(m, self.lanes))
        self.assertEqual(rep["met"], all(r >= 0.55 for r in rep["trainR"].values()))
        self.assertTrue(all(b in decoder.BOUND_GRID for b in rep["bounds"].values()))
        self.assertGreaterEqual(rep["attempts"], 1)
        if rep["met"]:
            self.assertTrue(all(r >= decoder.LINK_TARGET + decoder.LINK_MARGIN for r in rep["trainR"].values()))

    def test_an_unreachable_target_climbs_the_grid_and_reports_unmet(self):
        m, rep = decoder.fit_map_bounded(self.lanes, self.surrogate, target=1.01, steps=20)
        self.assertFalse(rep["met"])
        self.assertTrue(all(b == decoder.BOUND_GRID[-1] for b in rep["bounds"].values()))
        self.assertEqual(rep["attempts"], len(decoder.BOUND_GRID))

    def test_a_met_link_keeps_its_bound_while_others_climb(self):
        calls = []
        real = decoder.link_r
        # the energy links already hold at bound 0; make only power->weight short by asking for more than it can give at 0
        m, rep = decoder.fit_map_bounded(self.lanes, self.surrogate, target=0.5, margin=0.0, steps=30)
        for name, bound in rep["bounds"].items():
            if rep["trainR"][name] >= 0.5 and bound > 0:
                self.assertIn(bound, decoder.BOUND_GRID)
        self.assertEqual(sorted(rep["bounds"]), sorted(rep["trainR"]))

    def test_the_margin_is_added_to_the_target(self):
        _, rep = decoder.fit_map_bounded(self.lanes, self.surrogate, target=-1.0, margin=2.5, steps=10)
        self.assertFalse(rep["met"])
        _, rep = decoder.fit_map_bounded(self.lanes, self.surrogate, target=-1.0, margin=0.0, steps=10)
        self.assertTrue(rep["met"])
        self.assertEqual(rep["attempts"], 1)

    def test_deterministic(self):
        a = decoder.fit_map_bounded(self.lanes, self.surrogate, steps=30)
        b = decoder.fit_map_bounded(self.lanes, self.surrogate, steps=30)
        self.assertEqual(a[1], b[1])
        np.testing.assert_array_equal(a[0].bodies(self.lanes), b[0].bodies(self.lanes))


class RunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surrogate = small_surrogate()
        cls.clips, cls.folds = corpus()
        for c in cls.clips:                      # DEAM labels only on the 2 s grid, as the real ones
            if c.ds == "deam":
                y = np.full_like(c.y, np.nan)
                y[c.rows] = c.y[c.rows]
                c.y = y
        rng = np.random.default_rng(5)
        cls.dial = {c.key: {"energy10": rng.random(600), "masks": [], "light10": rng.random(600), "heavy10": rng.random(600)}
                    for c in cls.clips if c.ds == "song"}

    def once(self, out=None, **kw):
        return r2.run(self.clips, self.folds, self.surrogate, config(bound=True, **kw), self.dial, out, log=lambda s: None)

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            a = self.once(d)
            b = self.once()
            a.pop("seconds"), b.pop("seconds")
            self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
            for tag in range(6):
                z, ratings = np.load(d / f"segments_{tag}.npz"), np.load(d / f"ratings_{tag}.npz")
                n = len(z["decoder/keys"])
                self.assertEqual((ratings["va"].shape, ratings["gems"].shape), ((n, 2), (n, 9)))
                self.assertEqual(("dial" in ratings.files), tag == check3.SIXTH)
            self.assertTrue((d / "results.json").exists())
        self.assertEqual(set(a["maps"]), {"decoder", "baseline49", "library"})
        self.assertEqual(a["maps"]["library"]["links"], {})
        links = a["maps"]["decoder"]["links"]
        self.assertEqual(sorted(links), [str(t) for t in range(6)])
        self.assertEqual(sorted(links["0"]["heldOutR"]), sorted(links["0"]["trainR"]))
        self.assertEqual(a["maps"]["decoder"]["va"]["of"], 30)
        self.assertEqual(a["maps"]["decoder"]["gems"]["of"], 30)
        self.assertEqual(a["maps"]["decoder"]["sixthDial"]["segments"], 18)
        self.assertEqual(a["pass"]["energySign"], a["dial"]["energyPass"])
        self.assertEqual(a["pass"]["baseline"], a["bootstrap"]["pass"])
        self.assertEqual(a["pass"]["shuffle"], a["maps"]["decoder"]["va"]["pass"])
        self.assertEqual(a["check3r2"], all(v is True for v in a["pass"].values()))
        # the first window of a DEAM clip has no label: 30 clips x 2 windows, plus MERP 6 x 6
        self.assertEqual(sum(a["ratedSegments"]["va"]), 30 * 2 + 6 * 6)
        self.assertEqual(sum(a["ratedSegments"]["gems"]), 20 * 3)

    def test_round_one_path_is_unchanged_by_the_bound_flag_default(self):
        self.assertFalse(check3.Config().bound)
        result = check3.run(self.clips, self.folds, self.surrogate, config(), None, None, log=lambda s: None)
        self.assertEqual(set(result["maps"]), {"decoder", "baseline49", "library"})


if __name__ == "__main__":
    unittest.main()
