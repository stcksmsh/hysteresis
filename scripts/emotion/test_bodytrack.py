"""Tests of the bodyTrack writer (bodytrack.py). Synthetic data only."""
import json
import os
import pathlib
import tempfile
import unittest

import numpy as np

import bodytrack
from decoder import DIMS

FIXTURE = pathlib.Path(__file__).resolve().parents[2] / "crates" / "hyst-compile" / "tests" / "fixtures" / "bodytrack_writer.json"
PHRASES = [(0.0, 0.5), (0.5, 4.5), (4.5, 8.5)]


def mind(steps=18, k=2, source="stage1-smooth8"):
    t = np.arange(steps)
    lanes = np.column_stack([t / (steps - 1), 1 - t / (steps - 1), np.sin(t / 3) * 0.4 + 0.5, np.cos(t / 5) * 0.4 + 0.5][:2 + k])
    return {"version": 1, "source": source, "hopSeconds": 0.5,
            "mood": {"energy": lanes[:, 0].tolist(), "power": lanes[:, 1].tolist(), "rest": lanes[:, 2:].tolist()}}


def small_map(width=4, seed=3):
    rng = np.random.default_rng(seed)
    return rng.normal(size=(15, width)), rng.normal(size=15)


class BodyTrackTests(unittest.TestCase):
    def test_a_body_is_the_sigmoid_of_the_phrase_mean_lanes(self):
        m, (w, b) = mind(), small_map()
        field = bodytrack.body_track(m, w, b, "test", PHRASES)
        lanes = bodytrack.lane_matrix(m)
        # phrase 1 holds the step centres 0.5 .. 4.0, steps 1..8
        want = 1 / (1 + np.exp(-(lanes[1:9].mean(axis=0) @ w.T + b)))
        np.testing.assert_allclose(field["phrases"][1]["body"], want, atol=1e-6)
        self.assertEqual(field["dims"], list(DIMS))
        self.assertEqual((field["version"], field["source"], field["map"], field["authored"]),
                         (1, "stage1-smooth8", "test", []))
        self.assertEqual([(p["start"], p["end"]) for p in field["phrases"]], PHRASES)

    def test_a_pickup_with_no_step_centre_takes_the_nearest_step(self):
        lanes = bodytrack.lane_matrix(mind())
        got = bodytrack.phrase_lanes(lanes, 0.5, [(0.1, 0.3)])
        np.testing.assert_array_equal(got[0], lanes[0])

    def test_values_are_in_range_and_the_output_is_deterministic(self):
        w, b = small_map()
        a = bodytrack.body_track(mind(), 5 * w, b, "m", PHRASES)
        self.assertEqual(a, bodytrack.body_track(mind(), 5 * w, b, "m", PHRASES))
        for p in a["phrases"]:
            self.assertEqual(len(p["body"]), 15)
            self.assertTrue(all(0.0 <= v <= 1.0 for v in p["body"]))

    def test_a_map_of_the_wrong_width_is_an_error(self):
        w, b = small_map(width=3)
        with self.assertRaises(ValueError):
            bodytrack.body_track(mind(), w, b, "m", PHRASES)

    def test_write_keeps_every_other_field_and_refuses_overwrites(self):
        w, b = small_map()
        with tempfile.TemporaryDirectory() as d:
            d = pathlib.Path(d)
            notes = {"duration": 8.5, "keep": [1, 2], "musicalMemory": {"phrases": [{"start": s, "end": e} for s, e in PHRASES]}}
            (d / "notes.json").write_text(json.dumps(notes))
            (d / "mind.json").write_text(json.dumps({"mindState": mind()}))
            np.savez(d / "map.npz", W=w, b=b, id="test")
            with self.assertRaises(ValueError):
                bodytrack.write(d / "notes.json", d / "mind.json", d / "map.npz", d / "notes.json")
            with self.assertRaises(ValueError):
                bodytrack.write(d / "notes.json", d / "mind.json", d / "map.npz", d / "mind.json")
            bodytrack.write(d / "notes.json", d / "mind.json", d / "map.npz", d / "out.json")
            out = json.loads((d / "out.json").read_text())
            self.assertEqual({k: v for k, v in out.items() if k != "bodyTrack"}, notes)
            with self.assertRaises(ValueError):
                bodytrack.write(d / "out.json", d / "mind.json", d / "map.npz", d / "again.json")
            (d / "bare.json").write_text(json.dumps(notes))
            with self.assertRaises(ValueError):
                bodytrack.write(d / "notes.json", d / "bare.json", d / "map.npz", d / "x.json")

    def test_fixture_read_by_the_rust_tests_is_what_the_writer_makes(self):
        """crates/hyst-compile/tests/fixtures/bodytrack_writer.json is a sidecar this writer produced from
        synthetic data; the Rust reader parses it. Regenerate with REGENERATE_FIXTURE=1."""
        w, b = small_map()
        text = json.dumps({"duration": 8.5, "bodyTrack": bodytrack.body_track(mind(), w, b, "synthetic", PHRASES[1:])}, indent=1)
        if os.environ.get("REGENERATE_FIXTURE"):
            FIXTURE.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE.write_text(text + "\n")
        self.assertEqual(FIXTURE.read_text(), text + "\n")


if __name__ == "__main__":
    unittest.main()
