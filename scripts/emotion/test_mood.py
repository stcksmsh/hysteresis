"""Tests of the mood lanes (mood.py) and the mindState writer (mindstate.py). Synthetic data only."""
import json
import pathlib
import tempfile
import unittest

import numpy as np

import mindstate
import mood

D = 12
FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "crates" / "hyst-compile" / "tests" / "fixtures" / "mindstate_writer.json"


def world(seed=0, clips=40, steps=60):
    """Clips whose encoding is a fixed mix of three latent factors plus noise: arousal, power, other."""
    rng = np.random.default_rng(seed)
    mix = np.random.default_rng(99).normal(size=(3, D))
    data = []
    for _ in range(clips):
        latent = np.cumsum(rng.normal(scale=0.3, size=(steps, 3)), axis=0) + rng.normal(size=3)
        data.append((latent @ mix + rng.normal(scale=0.1, size=(steps, D))).astype(np.float32))
        data[-1] = (data[-1], latent)
    return data


def fit_world(data, **kw):
    xs = [x for x, _ in data]
    rows = np.arange(0, len(data[0][0]), 4)
    arousal = (np.concatenate([x[rows] for x, _ in data]), np.concatenate([l[rows, 0] for _, l in data]),
               np.concatenate([np.full(len(rows), i) for i in range(len(data))]))
    power = (np.stack([x.mean(axis=0) for x in xs]), np.array([l[:, 1].mean() for _, l in data]))
    return mood.fit(xs, arousal, power, **kw)


class MoodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = world()
        cls.model = fit_world(cls.data, k=4)

    def test_lane_count_and_range(self):
        for x, _ in self.data[:5]:
            lanes = self.model.lanes(x)
            self.assertEqual(lanes.shape, (60, 2 + 4))
            self.assertTrue(((lanes >= 0) & (lanes <= 1)).all())

    def test_same_input_same_lanes(self):
        again = fit_world(self.data, k=4)
        x = self.data[0][0]
        np.testing.assert_array_equal(self.model.lanes(x), again.lanes(x))

    def test_energy_lane_follows_the_arousal_it_was_fitted_on(self):
        new = world(seed=7, clips=20)
        energy = np.concatenate([self.model.lanes(x)[:, 0] for x, _ in new])
        truth = np.concatenate([smoothed(l[:, 0]) for _, l in new])
        self.assertGreater(np.corrcoef(energy, truth)[0, 1], 0.9)

    def test_power_lane_follows_the_power_it_was_fitted_on(self):
        new = world(seed=8, clips=20)
        power = np.concatenate([self.model.lanes(x)[:, 1] for x, _ in new])
        truth = np.concatenate([smoothed(l[:, 1]) for _, l in new])
        self.assertGreater(np.corrcoef(power, truth)[0, 1], 0.5)

    def test_rest_directions_are_orthogonal_to_both_anchor_directions(self):
        m = self.model
        np.testing.assert_allclose(m.components[:m.k] @ m.basis.T, 0.0, atol=1e-5)
        np.testing.assert_allclose(m.basis @ m.basis.T, np.eye(2), atol=1e-9)
        self.assertGreater(abs(m.w_energy @ m.w_power) / np.linalg.norm(m.w_energy) / np.linalg.norm(m.w_power), 0.0)

    def test_scaling_is_fixed_not_per_song(self):
        x = self.data[0][0]
        np.testing.assert_array_equal(self.model.lanes(x), self.model.lanes(x))
        # a song that sits far above the training range is clipped at 1, not rescaled to fit
        far = self.model.lanes(x + 50.0 * self.model.w_energy[None, :].astype(np.float32))
        self.assertEqual(far[-1, 0], 1.0)
        self.assertLess(self.model.lanes(x)[:, 0].max(), 1.0 + 1e-12)
        a, b = self.model.lane_scale.copy(), self.model.with_k(2).lane_scale
        np.testing.assert_array_equal(a, b)

    def test_causal(self):
        x = self.data[1][0].copy()
        before = self.model.lanes(x)
        x[30:] += 3.0
        after = self.model.lanes(x)
        np.testing.assert_array_equal(before[:30], after[:30])
        self.assertFalse(np.allclose(before[30:], after[30:]))

    def test_smoothing_constants(self):
        self.assertEqual((mood.TAU_SECONDS, mood.LAG_SECONDS), (8.0, 0.0))

    def test_fit_does_not_read_a_clip_it_was_not_given(self):
        first, second = self.data[:20], self.data[:20] + world(seed=5, clips=5)[:0]
        a, b = fit_world(first, k=2), fit_world(second, k=2)
        np.testing.assert_array_equal(a.lane_scale, b.lane_scale)
        other = fit_world(self.data[20:], k=2)
        self.assertFalse(np.allclose(a.lane_scale, other.lane_scale))

    def test_save_and_load_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            path = pathlib.Path(d) / "m.npz"
            self.model.save(path)
            back = mood.MoodModel.load(path)
        x = self.data[2][0]
        self.assertEqual((back.source, back.k, back.columns), (self.model.source, 4, D))
        np.testing.assert_array_equal(back.lanes(x), self.model.lanes(x))

    def test_columns_restrict_the_input(self):
        narrow = fit_world(self.data, k=2, columns=6, source=mood.SOURCE_BASELINE49)
        x = self.data[0][0]
        np.testing.assert_array_equal(narrow.lanes(x), narrow.lanes(np.hstack([x[:, :6], x[:, 6:] * 100])))

    def test_with_k_bounds(self):
        self.assertEqual(self.model.with_k(0).lanes(self.data[0][0]).shape[1], 2)
        with self.assertRaises(ValueError):
            self.model.with_k(mood.K_MAX + 1)


def smoothed(series):
    import smoothing
    return smoothing.smooth_delay(series, mood.TAU_SECONDS, mood.LAG_SECONDS)


class WriterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = world(clips=12, steps=40)
        cls.model = fit_world(cls.data, k=3)

    def sidecar(self, index=0):
        return {"duration": 19.5, "beats": [0.0, 0.5], "emotionEncoding": {"steps": self.data[index][0].tolist()}}

    def test_field_schema(self):
        f = mindstate.mind_state_field(self.model, self.data[0][0])
        self.assertEqual(sorted(f), sorted(["version", "source", "hopSeconds", "smoothing", "scale", "mood", "events",
                                            "authored", "bands", "pulse", "surprise", "neuromod"]))
        self.assertEqual((f["version"], f["source"], f["hopSeconds"]), (1, mood.SOURCE_STAGE1, 0.5))
        self.assertEqual(f["smoothing"], {"tauSeconds": 8.0, "lagSeconds": 0.0})
        for name in ("events", "authored", "bands", "pulse", "surprise", "neuromod"):
            self.assertEqual(f[name], [])
        self.assertEqual(len(f["mood"]["energy"]), 40)
        self.assertEqual(np.array(f["mood"]["rest"]).shape, (40, 3))
        self.assertEqual(np.array(f["scale"]["rest"]).shape, (3, 2))

    def test_ranges(self):
        f = mindstate.mind_state_field(self.model, self.data[0][0])
        values = np.concatenate([f["mood"]["energy"], f["mood"]["power"], np.ravel(f["mood"]["rest"])])
        self.assertTrue(((values >= 0) & (values <= 1)).all())

    def test_deterministic(self):
        a = json.dumps(mindstate.mind_state_field(self.model, self.data[0][0]))
        b = json.dumps(mindstate.mind_state_field(self.model, self.data[0][0]))
        self.assertEqual(a, b)

    def test_same_scale_constants_for_every_song(self):
        a = mindstate.mind_state_field(self.model, self.data[0][0])
        b = mindstate.mind_state_field(self.model, self.data[1][0] * 3.0)
        self.assertEqual(a["scale"], b["scale"])
        self.assertNotEqual(a["mood"]["energy"], b["mood"]["energy"])

    def test_write_adds_the_field_and_keeps_the_rest(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "in.json").write_text(json.dumps(self.sidecar()))
            self.model.save(d / "m.npz")
            field = mindstate.write(d / "in.json", d / "m.npz", d / "out.json")
            out = json.loads((d / "out.json").read_text())
            self.assertEqual(json.loads((d / "in.json").read_text()), self.sidecar())
        self.assertEqual(out["mindState"], json.loads(json.dumps(field)))
        self.assertEqual({k: v for k, v in out.items() if k != "mindState"}, self.sidecar())

    def test_write_refuses_overwriting_and_double_writing(self):
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            (d / "in.json").write_text(json.dumps(self.sidecar()))
            self.model.save(d / "m.npz")
            with self.assertRaises(ValueError):
                mindstate.write(d / "in.json", d / "m.npz", d / "in.json")
            mindstate.write(d / "in.json", d / "m.npz", d / "out.json")
            with self.assertRaises(ValueError):
                mindstate.write(d / "out.json", d / "m.npz", d / "again.json")
            (d / "bare.json").write_text(json.dumps({"duration": 1.0}))
            with self.assertRaises(ValueError):
                mindstate.write(d / "bare.json", d / "m.npz", d / "x.json")

    def test_fixture_read_by_the_rust_tests_is_what_the_writer_makes(self):
        """crates/hyst-compile/tests/fixtures/mindstate_writer.json is a sidecar this writer produced from
        synthetic data; the Rust reader parses it. Regenerate with REGENERATE_FIXTURE=1."""
        import os
        small = world(clips=8, steps=10)
        model = fit_world(small, k=2)
        text = json.dumps({"duration": 4.5, "mindState": mindstate.mind_state_field(model, small[0][0])}, indent=1)
        if os.environ.get("REGENERATE_FIXTURE"):
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(text + "\n")
        self.assertEqual(FIXTURE.read_text(), text + "\n")


if __name__ == "__main__":
    unittest.main()
