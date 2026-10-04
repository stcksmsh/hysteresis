import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from dance_stems import SOURCES, analyze, enrich


class DanceStemTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.stems = self.root / "stems"
        self.stems.mkdir()
        self.sidecar = {
            "schema": 3,
            "duration": 2.0,
            "envelopeRate": 10.0,
            "stemPresence": {"vocals": [0.2, 0.4]},
        }

    def tearDown(self):
        self.temp.cleanup()

    def write_all(self, *, sample_rate=8000, frames=16000, vocals=None):
        zeros = np.zeros((frames, 2), dtype=np.float32)
        for source in SOURCES:
            audio = vocals if source == "vocals" and vocals is not None else zeros
            sf.write(self.stems / f"{source}.wav", audio, sample_rate, subtype="FLOAT")

    def test_missing_source_fails_with_name(self):
        with self.assertRaisesRegex(ValueError, "other.wav"):
            analyze(self.sidecar, self.stems)

    def test_mismatched_rate_frames_and_duration_fail(self):
        self.write_all()
        sf.write(self.stems / "bass.wav", np.zeros((16000, 2)), 16000, subtype="FLOAT")
        with self.assertRaisesRegex(ValueError, "sample rates must match"):
            analyze(self.sidecar, self.stems)

        self.write_all()
        sf.write(self.stems / "other.wav", np.zeros((15900, 2)), 8000, subtype="FLOAT")
        with self.assertRaisesRegex(ValueError, "frame counts must match"):
            analyze(self.sidecar, self.stems)

        self.write_all(frames=12000)
        with self.assertRaisesRegex(ValueError, "duration mismatch"):
            analyze(self.sidecar, self.stems)

    def test_zero_stems_are_finite_and_keep_existing_sidecar_fields(self):
        self.write_all()
        enriched = enrich(self.sidecar, self.stems)
        self.assertEqual(enriched["stemPresence"], self.sidecar["stemPresence"])
        interpretation = enriched["stemInterpretation"]
        self.assertFalse(interpretation["provenance"]["groundTruth"])
        self.assertEqual(interpretation["provenance"]["producer"], "unspecified")
        self.assertIsNone(interpretation["provenance"]["separationRun"])
        self.assertEqual(interpretation["envelopeRate"], 10.0)
        for source in SOURCES:
            features = interpretation["sources"][source]
            for key in ("absoluteRms", "wholeTrackActivity", "spectralFlux", "transientDensity"):
                values = np.asarray(features[key])
                self.assertEqual(len(values), 20)
                self.assertTrue(np.isfinite(values).all())
            self.assertTrue(np.allclose(features["absoluteRms"], 0))
            self.assertTrue(np.allclose(features["wholeTrackActivity"], 0))
            self.assertEqual(features["candidates"], [])

    def test_known_vocal_entry_gets_local_candidate_without_song_label(self):
        rate, frames = 8000, 16000
        time = np.arange(frames, dtype=np.float32) / rate
        signal = np.where(time >= 0.8, 0.35 * np.sin(2 * np.pi * 440 * time), 0).astype(np.float32)
        vocals = np.stack([signal, signal], axis=1)
        self.write_all(sample_rate=rate, frames=frames, vocals=vocals)
        interpretation, evidence = analyze(self.sidecar, self.stems)
        features = interpretation["sources"]["vocals"]
        self.assertGreater(max(features["absoluteRms"]), 0.2)
        self.assertTrue(max(features["spectralFlux"]) > 0)
        entries = [candidate for candidate in features["candidates"] if candidate["kind"] == "activity_entry"]
        self.assertTrue(entries)
        self.assertAlmostEqual(entries[0]["time"], 0.8, delta=0.2)
        self.assertIn("confidence", entries[0])
        self.assertIn("evidence", entries[0])
        self.assertIn("sources", evidence)
        self.assertNotIn("verse", str(interpretation).lower())
        self.assertNotIn("chorus", str(interpretation).lower())
        self.assertTrue(all(candidate["scope"] == "local_activity_only" for candidate in features["candidates"]))

    def test_manifest_provenance_and_near_full_scale_samples_are_reported(self):
        rate, frames = 8000, 16000
        vocals = np.zeros((frames, 2), dtype=np.float32)
        vocals[:100, :] = 1.0
        self.write_all(sample_rate=rate, frames=frames, vocals=vocals)
        manifest = {
            "model": "example-model",
            "demucsVersion": "example-version",
            "device": "cpu",
            "shifts": 0,
            "clipMode": "clamp",
            "inputSha256": "abc123",
            "unrecognized": "discarded",
        }
        (self.stems / "separation.json").write_text(json.dumps(manifest))
        interpretation, evidence = analyze(self.sidecar, self.stems)
        provenance = interpretation["provenance"]
        self.assertEqual(provenance["producer"], "example-model")
        self.assertEqual(provenance["separationRun"]["shifts"], 0)
        self.assertNotIn("unrecognized", provenance["separationRun"])
        self.assertFalse(provenance["groundTruth"])
        fraction = interpretation["sources"]["vocals"]["sampleDiagnostics"]["sampleFractionAtOrAbove0_99FullScale"]
        self.assertAlmostEqual(fraction, 100 / frames)
        self.assertAlmostEqual(evidence["sources"]["vocals"]["sampleFractionAtOrAbove0_99FullScale"], fraction)
        self.assertIn("clamp-mode", provenance["clippingNote"])


if __name__ == "__main__":
    unittest.main()
