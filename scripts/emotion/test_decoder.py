"""Tests of the decoder (decoder.py) and the render wrapper (render.py). Synthetic mood; the body generator is the real one."""
import unittest

import numpy as np

import decoder
import render

_SURROGATE = []


def small_surrogate():
    """A surrogate fitted on real renders of 600 uniform bodies (cached for the test run)."""
    if not _SURROGATE:
        render.build()
        bodies = np.random.default_rng(0).random((600, 15))
        out = render.render(bodies)
        ok = out["ok"]
        _SURROGATE.append(decoder.Surrogate(hidden=64).fit(bodies[ok], out["desc"][ok], epochs=40))
    return _SURROGATE[0]


def lanes(n=300, d=4, seed=0):
    return np.random.default_rng(seed).random((n, d))


class RenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        render.build()

    def test_a_body_renders_to_37_descriptors_and_is_deterministic(self):
        bodies = np.random.default_rng(4).random((6, 15))
        a, b = render.render(bodies), render.render(bodies)
        self.assertEqual(a["desc"].shape, (6, 37))
        self.assertTrue(a["ok"].all())
        np.testing.assert_array_equal(a["desc"], b["desc"])
        np.testing.assert_array_equal(a["stretch"], b["stretch"])
        self.assertTrue((a["stretch"] >= 1.0).all() and (a["stretch"] <= 1.95).all())
        self.assertTrue(np.isfinite(a["desc"]).all())

    def test_the_seeds_are_three_and_change_the_descriptor_mean(self):
        body = np.random.default_rng(5).random((1, 15))
        three, one = render.render(body), render.render(body, seeds=render.SEEDS[:1])
        self.assertEqual(three["stretch"].shape, (1, 3))
        self.assertEqual(one["stretch"].shape, (1, 1))
        self.assertFalse(np.allclose(three["desc"], one["desc"]))

    def test_different_bodies_have_different_descriptors(self):
        out = render.render(np.array([[0.1] * 15, [0.9] * 15]))
        self.assertFalse(np.allclose(out["desc"][0], out["desc"][1]))

    def test_input_checks(self):
        for bad in (np.full((1, 15), 1.5), np.zeros((1, 14)), np.full((1, 15), -0.1)):
            with self.assertRaises(ValueError):
                render.render(bad)
        self.assertEqual(render.render(np.zeros((0, 15)))["desc"].shape, (0, 37))


class MapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.surrogate = small_surrogate()

    def test_anchor_mask_is_exactly_the_decided_one(self):
        m = decoder.Map(5)
        on = {(decoder.DIMS[r], int(c)) for r, c in m.positive.nonzero().tolist()}
        self.assertEqual(on, {("energy", 0), ("size", 0), ("time", 0), ("weight", 1)})
        off = decoder.Map(5, power_anchor=False)
        self.assertEqual({(decoder.DIMS[r], int(c)) for r, c in off.positive.nonzero().tolist()},
                         {("energy", 0), ("size", 0), ("time", 0)})
        self.assertFalse(m.positive[decoder.DIMS.index("height")].any())

    def test_anchor_entries_stay_non_negative_after_fitting_on_data_that_pulls_them_down(self):
        z = lanes(seed=1)
        for seed in (1, 2, 3):
            m = decoder.fit_map(z, self.surrogate, steps=60, seed=seed)
            w = m.weights.detach().numpy()
            for dim in ("energy", "size", "time"):
                self.assertGreaterEqual(w[decoder.DIMS.index(dim), 0], 0.0)
            self.assertGreaterEqual(w[decoder.DIMS.index("weight"), 1], 0.0)
        raw = m.raw.detach().clone()
        raw[m.positive] = -3.0
        m.raw.data = raw
        self.assertTrue((m.weights[m.positive] > 0).all())

    def test_bodies_are_in_unit_range_and_deterministic(self):
        z = lanes(seed=2)
        a = decoder.fit_map(z, self.surrogate, steps=40)
        b = decoder.fit_map(z, self.surrogate, steps=40)
        bodies = a.bodies(z)
        self.assertEqual(bodies.shape, (300, 15))
        self.assertTrue(((bodies > 0) & (bodies < 1)).all())
        np.testing.assert_array_equal(bodies, b.bodies(z))

    def test_fitting_raises_the_surrogate_representational_similarity(self):
        z = lanes(seed=3)
        untrained = decoder.fit_map(z, self.surrogate, steps=0)
        trained = decoder.fit_map(z, self.surrogate, steps=150)
        self.assertGreater(decoder.surrogate_rsa(trained, z, self.surrogate),
                           decoder.surrogate_rsa(untrained, z, self.surrogate) + 0.05)

    def test_smooth_in_the_lanes(self):
        z = lanes(seed=4)
        m = decoder.fit_map(z, self.surrogate, steps=30)
        step = 0.01
        near = np.abs(m.bodies(z + step) - m.bodies(z)).max()
        self.assertLess(near, step * m.weights.abs().sum(dim=1).max().item() / 4 + 1e-9)

    def test_energy_anchor_moves_the_energy_dimensions_up_with_mood_energy(self):
        z = lanes(seed=5)
        m = decoder.fit_map(z, self.surrogate, steps=100)
        low, high = np.zeros((1, 4)), np.zeros((1, 4))
        low[0, 0], high[0, 0] = 0.0, 1.0
        for dim in ("energy", "size", "time"):
            i = decoder.DIMS.index(dim)
            self.assertGreaterEqual(m.bodies(high)[0, i], m.bodies(low)[0, i])
        i = decoder.DIMS.index("weight")
        low[0, :], high[0, :] = [0.5, 0.0, 0, 0], [0.5, 1.0, 0, 0]
        self.assertGreaterEqual(m.bodies(high)[0, i], m.bodies(low)[0, i])

    def test_choose_k_stays_in_the_grid_and_prefers_the_smaller_k_on_ties(self):
        z = lanes(n=240, d=2 + 8, seed=6)
        songs = [f"s{i // 4}" for i in range(240)]
        k, scores = decoder.choose_k(z, songs, self.surrogate, grid=(2, 4, 8, 16), steps=25)
        self.assertEqual(sorted(scores), [2, 4, 8])
        self.assertEqual(k, decoder.pick_k(scores))

    def test_ties_go_to_the_smaller_k(self):
        self.assertEqual(decoder.pick_k({4: 0.3, 2: 0.3, 8: 0.1}), 2)
        self.assertEqual(decoder.pick_k({4: 0.31, 2: 0.3, 8: 0.1}), 4)

    def test_inner_folds_never_split_a_song(self):
        songs = [f"s{i // 5}" for i in range(100)]
        g = decoder.inner_groups(songs)
        for s in set(songs):
            self.assertEqual(len(set(g[[i for i, x in enumerate(songs) if x == s]])), 1)
        self.assertEqual(set(g), {0, 1, 2})

    def test_surrogate_fits_its_training_renders_and_round_trips(self):
        import tempfile, pathlib
        bodies = np.random.default_rng(9).random((100, 15))
        out = render.render(bodies)
        pred = self.surrogate(__import__("torch").tensor(bodies, dtype=__import__("torch").float32)).detach().numpy()
        truth = (out["desc"] - self.surrogate.mean) / self.surrogate.std
        self.assertGreater(np.mean([np.corrcoef(pred[:, j], truth[:, j])[0, 1] for j in range(37)]), 0.4)
        with tempfile.TemporaryDirectory() as d:
            self.surrogate.save(pathlib.Path(d) / "s.pt")
            back = decoder.Surrogate.load(pathlib.Path(d) / "s.pt")
        np.testing.assert_array_equal(back.r2(bodies[:50], out["desc"][:50]), self.surrogate.r2(bodies[:50], out["desc"][:50]))


class LibraryTests(unittest.TestCase):
    def test_the_assignment_that_matches_the_geometry_is_found(self):
        rng = np.random.default_rng(7)
        centres = rng.normal(size=(8, 3)) * 5
        lanes_z = np.concatenate([c + 0.05 * rng.normal(size=(20, 3)) for c in centres])
        rotation = np.linalg.qr(rng.normal(size=(3, 3)))[0]
        perm = rng.permutation(8)                      # cluster j sits where region perm[j] does
        regions = np.empty((8, 3))
        regions[perm] = centres @ rotation
        bodies = np.arange(8)[:, None] * np.ones((1, 15)) / 10
        lib = decoder.Library(bodies).fit(lanes_z, regions)
        order = lib.kmeans.predict(centres)            # kmeans cluster id of each true centre
        np.testing.assert_array_equal(lib.assignment[order], perm)
        self.assertGreater(lib.score, 0.999)
        np.testing.assert_array_equal(lib.regions(centres), perm)
        np.testing.assert_array_equal(lib.decode(centres), bodies[perm])

    def test_deterministic(self):
        rng = np.random.default_rng(8)
        z, r = rng.normal(size=(200, 3)), rng.normal(size=(8, 5))
        a, b = decoder.Library(np.zeros((8, 15))).fit(z, r), decoder.Library(np.zeros((8, 15))).fit(z, r)
        np.testing.assert_array_equal(a.assignment, b.assignment)

    def test_regions_of_the_body_study_load(self):
        bodies, ref = decoder.load_regions()
        self.assertEqual(bodies.shape, (8, 15))
        self.assertEqual(ref.shape, (2000, 37))
        self.assertTrue(((bodies >= 0) & (bodies <= 1)).all())


if __name__ == "__main__":
    unittest.main()
