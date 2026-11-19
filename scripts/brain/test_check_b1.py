"""check_b1.py on synthetic clips only (never on a test set): the whole pipeline runs, results have the committed structure."""
import os
import subprocess
import sys
import tempfile
import time
import unittest

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(__file__))
import check_b1  # noqa: E402
import fast_features as ff  # noqa: E402


def synth_clip(path, bpm, seconds=30.0, seed=0):
    rng = np.random.default_rng(seed)
    n = int(seconds * ff.SR)
    y = 0.02 * rng.standard_normal(n).astype(np.float32)
    t = np.arange(int(0.2 * ff.SR)) / ff.SR
    hit = (0.6 * np.sin(2 * np.pi * 70 * t) * np.exp(-t * 25) + 0.2 * rng.standard_normal(len(t)) * np.exp(-t * 60)).astype(np.float32)
    period, beats, k = 60.0 / bpm, [], 0
    while 0.3 + k * period + 0.2 < seconds:
        a = int((0.3 + k * period) * ff.SR)
        y[a:a + len(hit)] += hit
        beats.append(0.3 + k * period)
        k += 1
    sf.write(path, y, ff.SR, subtype="PCM_16")
    return np.array(beats)


class CheckB1(unittest.TestCase):
    def test_pipeline_on_synthetic_clips(self):
        if not os.path.exists(check_b1.PLL_BIN):
            subprocess.run(["cargo", "build", "--release", "-p", "hyst-audio", "--example", "beat_pll"], cwd=check_b1.REPO, check=True)
        with tempfile.TemporaryDirectory() as d:
            clips = []
            for i, (set_, style, bpm) in enumerate([("ballroom", "Waltz", 90), ("ballroom", "Tango", 120), ("ballroom", "Jive", 110),
                                                    ("gtzan", "rock", 120), ("gtzan", "pop", 100), ("gtzan", "disco", 124)]):
                path = os.path.join(d, f"c{i}.wav")
                beats = synth_clip(path, bpm, seed=i)
                clips.append({"id": f"{set_}/c{i}", "set": set_, "style": style, "audio": path, "beats": beats})
            clips.append({"id": "gtzan/missing", "set": "gtzan", "style": "x", "audio": os.path.join(d, "nope.wav"), "beats": np.array([1.0, 2.0])})
            out = os.path.join(d, "out")
            t = time.time()
            r = check_b1.run(clips, out, workers=2, do_analyze=True, log=lambda m: None)
            seconds = time.time() - t
            self.assertEqual(r["meta"]["clips"], {"ballroom": 3, "gtzan": 3})
            self.assertEqual(len(r["meta"]["skipped"]), 1)
            for key in ("gate1", "gate1_reported", "gate2", "gate2_pass", "gate3", "gate3_reported", "missing_pulse", "pass"):
                self.assertIn(key, r)
            self.assertEqual(sorted(r["gate1"]["rows"]), ["ballroom.amlt", "ballroom.f", "gtzan.amlt", "gtzan.f"])
            self.assertEqual(sorted(r["gate2"]), ["2s", "4s", "8s"])
            for kind in ("noise", "silence"):
                ex = r["gate2_exclusions"]["4s"][kind]
                self.assertEqual(ex["gaps"], 6)
                scored = r["gate2"]["4s"][kind]["clips"] if kind in r["gate2"]["4s"] else 0
                self.assertEqual(scored + ex["excluded"], 6)
                self.assertIn("mean", r["gate2_readout_switches"]["4s"][kind])
            self.assertEqual(r["gate2_exclusions"]["4s"]["silence"]["excluded"], 0)        # silence is valid by definition
            self.assertIn("alpha = 0 (critical)", r["notes"]["alpha"])
            self.assertEqual(r["gate2"]["4s"]["silence"]["pll_variant"] in ("raw", "centred"), True)
            if "noise" in r["gate2"]["4s"]:
                self.assertIn("not informative", r["gate2"]["4s"]["noise"]["criterion2_note"])
            self.assertIn("8s", r["gate2_exclusions_after_linear_detrending_reported_only"])
            self.assertEqual(sorted(r["half_double_per_ballroom_style"]), ["Jive", "Tango", "Waltz"])
            self.assertIn("4-second gaps of silence or beatless noise", r["claims"]["claim2"])
            self.assertIn("AMLt", r["claims"]["claim1"])
            self.assertEqual(len(r["meta"]["commit"]), 40)
            self.assertTrue(all("readout_hz" in row for row in r["missing_pulse"]))
            for g in r["gate2"].values():
                for res in g.values():
                    self.assertIn(res["pll_variant"], ("raw", "centred"))
                    self.assertLessEqual(res["median_pll_ms"], max(res["raw"]["median_pll_ms"], res["centred"]["median_pll_ms"]))
            # the PLL baseline really ran, and the offline reference too
            self.assertIn("offline_analyze", r["gate1_reported"]["metrics"]["gtzan"])
            self.assertIn("offline_regularised_grid", r["gate1_reported"]["metrics"]["gtzan"])
            self.assertIn("pll_variant", r["gate1"]["rows"]["gtzan.f"])
            m = r["gate1_reported"]["metrics"]["gtzan"]
            self.assertGreater(max(m["pll_raw"]["f"], m["pll_centred"]["f"]), 0.2)
            self.assertEqual(r["gate3"]["clips"], 3)
            self.assertEqual(r["gate3"]["triple"], 1)
            self.assertEqual(len(r["missing_pulse"]), 11)
            # a second call comes from the cache and gives the same numbers
            r2 = check_b1.run(clips, out, workers=2, do_analyze=True, log=lambda m: None)
            self.assertEqual(r["gate1"], r2["gate1"])
            self.assertEqual(r["gate3"], r2["gate3"])
            print(f"\nsynthetic pipeline, 6 clips with 6 gap variants each: {seconds:.1f} s")


if __name__ == "__main__":
    unittest.main()
