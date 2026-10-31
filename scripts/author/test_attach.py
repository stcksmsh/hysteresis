"""Export format tests: the exporter's output is read by attach.py's checks (mirror of body_track.rs parse) and attached."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import attach

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parents[1] / "crates/hyst-compile/tests/fixtures/bodytrack_author.json"
NODE = r"""
const A = require(process.argv[1] + "/author_core.cjs"), {exportTrack} = require(process.argv[1] + "/export_cli.cjs");
const n = 200, ramp = (f) => Array.from({length: n}, (_, i) => f(i));
const song = {name: "t", n_bins: n, duration: 20, arousal: ramp(i => i), tension: ramp(i => 200 - i), familiarity: ramp(i => (i % 10)),
  surprisal_total: ramp(i => (i % 50 === 0 ? 30 : 1)), band_power: [ramp(i => i), ramp(i => i), ramp(i => i), ramp(i => i)],
  mood_energy: Array.from({length: 40}, (_, i) => 0.3 + i / 100), phrases: [[0, 8], [8, 16], [16, 20]], beats: [0.5, 1, 1.5, 2]};
const m = A.neutralMapping(); m.name = "fixture";
m.weights[12][0] = 0.6; m.weights[1][1] = -0.5; m.weights[5][4] = 0.7;
process.stdout.write(JSON.stringify(exportTrack(m, song, process.argv[2])));
"""


def export(kind):
    out = subprocess.run(["node", "-e", NODE, str(HERE), kind], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


class TestExport(unittest.TestCase):
    def test_phrase_export_passes_the_body_track_checks(self):
        t = attach.check(export("phrase")["bodyTrack"])
        self.assertEqual([(p["start"], p["end"]) for p in t["phrases"]], [(0, 8), (8, 16), (16, 20)])
        self.assertEqual(t["source"], "authored-state")
        self.assertEqual(t["map"], "authored:fixture")
        # size = 0.5 + 0.6 * normalised arousal (a ramp: mean of normalised values over a phrase is exact to 1e-6)
        self.assertTrue(all(0.0 <= v <= 1.0 for p in t["phrases"] for v in p["body"]))
        sizes = [p["body"][12] for p in t["phrases"]]
        self.assertEqual(sizes, sorted(sizes))
        self.assertLess(sizes[0], sizes[-1])

    def test_beat_export_is_ordered_and_contiguous(self):
        t = attach.check(export("beat")["bodyTrack"])
        ph = t["phrases"]
        self.assertEqual((ph[0]["start"], ph[0]["end"]), (0, 0.5))
        for a, b in zip(ph, ph[1:]):
            self.assertEqual(a["end"], b["start"])

    def test_committed_fixture_matches_the_exporter(self):
        self.assertEqual(json.loads(FIXTURE.read_text()), export("phrase"))

    def test_bad_tracks_are_rejected(self):
        base = export("phrase")["bodyTrack"]
        for key, value in [("version", 2), ("dims", ["size"]), ("authored", [{}]), ("source", ""), ("phrases", [])]:
            bad = dict(base, **{key: value})
            with self.assertRaises((ValueError, KeyError), msg=key):
                attach.check(bad)
        bad = json.loads(json.dumps(base))
        bad["phrases"][0]["body"][0] = 1.5
        with self.assertRaises(ValueError):
            attach.check(bad)

    def test_attach_adds_the_field_and_refuses_overwrites(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            sc, out = d / "s.json", d / "o.json"
            sc.write_text(json.dumps({"duration": 20, "musicalMemory": {"phrases": []}}))
            attach.attach(sc, FIXTURE, out)
            got = json.loads(out.read_text())
            self.assertEqual(got["bodyTrack"], json.loads(FIXTURE.read_text())["bodyTrack"])
            self.assertEqual(got["duration"], 20)
            with self.assertRaises(ValueError):
                attach.attach(sc, FIXTURE, sc)
            with self.assertRaises(ValueError):
                attach.attach(out, FIXTURE, d / "o2.json")


if __name__ == "__main__":
    unittest.main()
