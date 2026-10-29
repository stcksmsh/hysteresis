"""Tests of the spread fix and the spread check (quantile.py, spread.py, their hooks). Synthetic data only."""
import pathlib
import tempfile
import unittest

import numpy as np

import a1
import bodytrack
import decoder
import spread
from quantile import QuantileMap
from test_decoder import small_surrogate


class QuantileMapTests(unittest.TestCase):
    def setUp(self):
        self.values = np.linspace(-3.0, 7.0, 101)[:, None] * np.array([[1.0, -1.0]])    # col 1 runs backwards

    def test_5th_goes_to_005_and_95th_to_095(self):
        q = QuantileMap(self.values)
        got = q(np.array([[self.values[5, 0], 0.0], [self.values[95, 0], 0.0]]))[:, 0]
        np.testing.assert_allclose(got, [0.05, 0.95], atol=1e-12)

    def test_linear_in_rank_between_and_clipped_outside(self):
        q = QuantileMap(self.values)
        np.testing.assert_allclose(q(np.array([[self.values[50, 0], 0.0]]))[0, 0], 0.5, atol=1e-12)
        np.testing.assert_allclose(q(np.array([[self.values[0, 0], 0.0], [self.values[100, 0], 0.0], [-50.0, 0.0], [50.0, 0.0]]))[:, 0],
                                   [0.0, 1.0, 0.0, 1.0], atol=1e-12)

    def test_order_is_kept_and_a_reversed_column_stays_reversed(self):
        rng = np.random.default_rng(1)
        train = rng.normal(size=(200, 3)) * [1, 5, 0.1]
        q = QuantileMap(train)
        x = rng.normal(size=(50, 3)) * [1, 5, 0.1]
        y = q(x)
        for j in range(3):
            order = np.argsort(x[:, j])
            self.assertTrue((np.diff(y[order, j]) >= 0).all())
        self.assertTrue(((y >= 0) & (y <= 1)).all())

    def test_equal_training_values_share_their_mean_rank(self):
        q = QuantileMap(np.array([[0.0], [1.0], [1.0], [1.0], [2.0]]))
        got = q(np.array([[0.0], [1.0], [2.0]]))[:, 0]
        np.testing.assert_allclose(got, [0.0 - 0.0, 0.5, 1.0], atol=1e-12)     # ranks 0, (1+3)/2 / 4, 1; anchors 0.05/0.95 -> identity
        self.assertEqual(got[1], 0.5)

    def test_it_is_deterministic_and_the_saved_map_gives_the_same_values(self):
        rng = np.random.default_rng(2)
        train, x = rng.normal(size=(300, 15)), rng.normal(size=(40, 15))
        a, b = QuantileMap(train), QuantileMap(train)
        np.testing.assert_array_equal(a(x), b(x))
        with tempfile.TemporaryDirectory() as tmp:
            a.save(pathlib.Path(tmp) / "q.npz")
            np.testing.assert_array_equal(QuantileMap.load(pathlib.Path(tmp) / "q.npz")(x), a(x))

    def test_other_anchors_move_the_ends_symmetrically(self):
        q = QuantileMap(self.values, p_low=0.10, p_high=0.90, out_low=0.10, out_high=0.90)
        np.testing.assert_allclose(q(np.array([[self.values[10, 0], 0.0], [self.values[90, 0], 0.0]]))[:, 0], [0.10, 0.90], atol=1e-12)
        wide = QuantileMap(self.values, p_low=0.05, p_high=0.95, out_low=0.0, out_high=1.0)
        np.testing.assert_allclose(wide(np.array([[self.values[5, 0], 0.0], [self.values[95, 0], 0.0]]))[:, 0], [0.0, 1.0], atol=1e-12)

    def test_bad_input_is_refused(self):
        with self.assertRaises(ValueError):
            QuantileMap(np.zeros((1, 2)))
        with self.assertRaises(ValueError):
            QuantileMap(np.zeros((5, 2)), p_low=0.9, p_high=0.1)

    def test_a_saturated_map_is_spread_out(self):
        # values that a sigmoid would squeeze to 0.98..0.99: after the fix they cover the range, in the same order
        z = np.linspace(4.0, 4.6, 200)[:, None]
        sig = 1 / (1 + np.exp(-z))
        self.assertLess(sig.max() - sig.min(), 0.01)
        fixed = QuantileMap(z)(z)
        self.assertGreater(fixed.max() - fixed.min(), 0.99)
        self.assertTrue((np.diff(fixed[:, 0]) > 0).all())


class MapHookTests(unittest.TestCase):
    def test_bodies_are_the_sigmoid_until_a_quantile_is_attached_and_fitting_is_untouched(self):
        rng = np.random.default_rng(3)
        lanes = rng.random((120, 3))
        fitted = decoder.fit_map(lanes, small_surrogate(), steps=3, batch=60)
        before = fitted.bodies(lanes)
        np.testing.assert_allclose(before, 1 / (1 + np.exp(-(lanes @ fitted.weights.detach().numpy().T + fitted.b.detach().numpy()))), atol=1e-6)
        fitted.fit_quantile(lanes)
        after = fitted.bodies(lanes)
        for j in range(15):
            self.assertTrue((np.argsort(before[:, j], kind="stable") == np.argsort(after[:, j], kind="stable")).all() or
                            np.allclose(np.sort(before[:, j]), before[:, j].mean()))
        np.testing.assert_allclose(np.sort(after, axis=0)[[0, -1]], [[0.0] * 15, [1.0] * 15], atol=1e-9)
        np.testing.assert_allclose(np.percentile(after, 50, axis=0), 0.5, atol=0.02)
        fitted.quantile = None
        np.testing.assert_array_equal(fitted.bodies(lanes), before)

    def test_the_forward_used_for_fitting_does_not_see_the_quantile(self):
        import torch
        rng = np.random.default_rng(4)
        lanes = rng.random((60, 3))
        fitted = decoder.fit_map(lanes, small_surrogate(), steps=2, batch=30)
        x = torch.tensor(lanes, dtype=torch.float32)
        want = fitted.forward(x).detach().numpy()
        fitted.fit_quantile(lanes)
        np.testing.assert_array_equal(fitted.forward(x).detach().numpy(), want)


class BodyTrackQuantileTests(unittest.TestCase):
    def test_bodies_of_with_a_quantile_is_that_map_of_the_pre_sigmoid_value(self):
        rng = np.random.default_rng(5)
        w, b = rng.normal(size=(15, 4)), rng.normal(size=15)
        lanes = rng.random((60, 4))
        q = QuantileMap(lanes @ w.T + b)
        np.testing.assert_array_equal(bodytrack.bodies_of(lanes[:7], w, b, q), q(lanes[:7] @ w.T + b))
        np.testing.assert_allclose(bodytrack.bodies_of(lanes[:7], w, b), 1 / (1 + np.exp(-(lanes[:7] @ w.T + b))))

    def test_a_saved_map_carries_its_quantile_beside_it(self):
        rng = np.random.default_rng(6)
        lanes = rng.random((80, 3))
        fitted = decoder.fit_map(lanes, small_surrogate(), steps=2, batch=40)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "m.npz"
            bodytrack.save_map(path, fitted, "plain")
            self.assertIsNone(bodytrack.load_quantile(path))
            fitted.fit_quantile(lanes)
            bodytrack.save_map(path, fitted, "fixed")
            q = bodytrack.load_quantile(path)
            w, b, _ = bodytrack.load_map(path)
            np.testing.assert_allclose(bodytrack.bodies_of(lanes, w, b, q), fitted.bodies(lanes), atol=1e-4)   # float32 in the map, float64 here


class RegionTests(unittest.TestCase):
    def setUp(self):
        # a sweep of 10 values per descriptor: 0..9, so a value v has midrank (v+0.5)/10 for integer v
        self.sorted = np.tile(np.arange(10.0), (37, 1))

    def test_midrank_counts_values_below_plus_half_the_equal(self):
        got = spread.midrank(self.sorted, np.array([[-1.0] * 37, [3.0] * 37, [3.5] * 37, [20.0] * 37]))
        np.testing.assert_allclose(got[:, 0], [0.0, 0.35, 0.4, 1.0])
        self.assertEqual(got.shape, (4, 37))

    def test_midrank_of_a_repeated_value(self):
        col = np.tile(np.array([1.0, 1.0, 1.0, 2.0]), (37, 1))
        np.testing.assert_allclose(spread.midrank(col, np.full((1, 37), 1.0))[0, 0], (0 + 3 / 2) / 4)

    def test_the_region_is_the_nearest_position_and_the_distance_is_euclidean(self):
        positions = np.array([np.full(37, 0.2), np.full(37, 0.8), np.full(37, 0.5)])
        ranks = np.array([np.full(37, 0.25), np.full(37, 0.9), np.concatenate([np.full(36, 0.5), [0.5 + 0.3]])])
        region, dist = spread.assign(ranks, positions)
        self.assertEqual(region.tolist(), [0, 1, 2])
        np.testing.assert_allclose(dist, [0.05 * np.sqrt(37), 0.1 * np.sqrt(37), 0.3])

    def test_a_tie_goes_to_the_first_region(self):
        positions = np.array([np.full(37, 0.4), np.full(37, 0.6)])
        region, _ = spread.assign(np.full((1, 37), 0.5), positions)
        self.assertEqual(region.tolist(), [0])

    def test_failed_bodies_get_no_region(self):
        def fake(bodies):
            ok = np.array([True, False, True])
            desc = np.where(ok[:, None], np.array([[2.0], [0.0], [8.0]]), np.nan) * np.ones((3, 37))
            return {"ok": ok, "desc": desc, "stretch": np.full((3, 3), 1.0)}
        positions = np.array([np.full(37, 0.30), np.full(37, 0.80)])
        got = spread.regions_of(np.zeros((3, 15)), (self.sorted, positions), renderer=fake)
        self.assertEqual(got["region"].tolist(), [0, -1, 1])
        self.assertTrue(np.isnan(got["distance"][1]) and np.isnan(got["ranks"][1]).all())
        np.testing.assert_allclose(got["distance"][[0, 2]], [0.05 * np.sqrt(37), 0.05 * np.sqrt(37)])


def bodies(n, edge_dims=(), edge_share=0.0, value=0.5):
    b = np.full((n, 15), value)
    for d in edge_dims:
        b[: int(round(edge_share * n)), d] = 0.0
    return b


class ScoreTests(unittest.TestCase):
    def songs(self, a, b, c, edge=None):
        mk = lambda regions, bod=None: {"region": np.array(regions), "bodies": bodies(len(regions)) if bod is None else bod}
        return {"a": mk(a, edge), "b": mk(b), "c": mk(c)}

    def test_all_three_rules_pass(self):
        r = spread.score(self.songs([0, 0, 1], [2, 2, 3], [4, 5, 5]))
        self.assertEqual((r["rule1"], r["rule2"], r["pass"]), ({"a": True, "b": True, "c": True}, True, True))
        self.assertEqual(r["songs"]["a"]["counts"], [2, 1, 0, 0, 0, 0, 0, 0])
        self.assertEqual(r["songs"]["c"]["mostVisited"], [5])

    def test_rule_1_a_song_in_one_region_fails(self):
        r = spread.score(self.songs([0, 0, 0], [2, 3], [4, 5]))
        self.assertEqual(r["rule1"], {"a": False, "b": True, "c": True})
        self.assertFalse(r["pass"])

    def test_rule_2_two_songs_with_the_same_most_visited_region_fail(self):
        r = spread.score(self.songs([0, 0, 1], [2, 0, 0], [4, 5]))
        self.assertEqual(r["rule2SharedPairs"], [("a", "b")])
        self.assertFalse(r["rule2"] or r["pass"])

    def test_rule_2_a_tie_for_most_visited_counts_when_the_tied_sets_meet(self):
        r = spread.score(self.songs([0, 1], [1, 2, 2], [4, 5]))
        self.assertEqual(r["songs"]["a"]["mostVisited"], [0, 1])
        self.assertEqual(r["rule2SharedPairs"], [])             # a's {0, 1} and b's {2} do not meet
        r = spread.score(self.songs([0, 1], [1, 1, 2, 2], [4, 5, 6]))
        self.assertEqual(r["rule2SharedPairs"], [("a", "b")])

    def test_rule_3_exactly_20_percent_passes_and_over_fails(self):
        ok = spread.score(self.songs([0, 1] * 5, [2, 3], [4, 5], edge=bodies(10, (3,), 0.2)))
        self.assertEqual(ok["songs"]["a"]["edgeShare"][3], 0.2)
        self.assertTrue(ok["rule3"]["a"] and ok["pass"])
        bad = spread.score(self.songs([0, 1] * 5, [2, 3], [4, 5], edge=bodies(10, (3, 7), 0.3)))
        self.assertEqual(bad["songs"]["a"]["dimensionsOver"], [3, 7])
        self.assertFalse(bad["rule3"]["a"] or bad["pass"])

    def test_within_005_of_the_ends_counts_on_both_sides_and_the_edge_is_inclusive(self):
        b = np.full((4, 15), 0.5)
        b[:, 0] = [0.05, 0.95, 0.0501, 0.9499]
        np.testing.assert_allclose(spread.edge_share(b)[[0, 1]], [0.5, 0.0])

    def test_failed_phrases_are_counted_and_left_out_of_the_regions_only(self):
        r = spread.score(self.songs([0, -1, 1], [2, 3], [4, 5]))
        self.assertEqual((r["songs"]["a"]["failed"], r["songs"]["a"]["visited"], r["songs"]["a"]["phrases"]), (1, 2, 3))


class LinkTableTests(unittest.TestCase):
    def test_the_links_below_half_are_the_misses(self):
        row = lambda e, s, t, w: {"heldOutR": {"energy->energy": e, "energy->size": s, "energy->time": t, "power->weight": w}}
        results = {"maps": {"core2b": {"links": {"0": row(0.9, 0.5, 0.6, 0.7), "4": row(0.9, 0.487, 0.6, 0.7), "5": row(0.9, 0.9, 0.378, 0.7)}}}}
        got = a1.link_table(results)
        self.assertEqual((got["reach"], got["of"]), (10, 12))
        self.assertEqual(got["misses"], [("4", "energy->size", 0.487), ("5", "energy->time", 0.378)])


if __name__ == "__main__":
    unittest.main()
