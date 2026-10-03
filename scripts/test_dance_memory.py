import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf

from dance_memory import analyze, regularize_beats, _validate_output_paths, with_musical_memory


def fixture_wav(path, patterns, duration=40.0, sample_rate=8000):
    audio = np.zeros(int(duration * sample_rate), dtype=np.float32)
    for phrase_index, pattern in enumerate(patterns):
        phrase_start = 0.1 + phrase_index * 8.0
        for beat in pattern:
            start = int((phrase_start + beat * 0.5) * sample_rate)
            count = int(0.12 * sample_rate)
            t = np.arange(count) / sample_rate
            pulse = np.exp(-t * 32)
            audio[start : start + count] += (0.7 * np.sin(2 * np.pi * 82 * t) + 0.18 * np.sin(2 * np.pi * 3100 * t)) * pulse
    audio = np.clip(audio, -1, 1)
    sf.write(path, audio, sample_rate, subtype="PCM_16")
    beats = [0.1 + 0.5 * i for i in range(78) if 0.1 + 0.5 * i < duration]
    return {"schema": 3, "duration": duration, "tempo": 120, "beats": beats}


class DanceMemoryTests(unittest.TestCase):
    def test_silence_has_finite_zero_profiles_and_explicit_partials(self):
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "silence.wav"
            sf.write(wav, np.zeros(40 * 8000, dtype=np.float32), 8000, subtype="PCM_16")
            sidecar = {"duration": 40.0, "beats": [0.1 + 0.5 * i for i in range(78)]}
            memory, evidence = analyze(wav, sidecar)
            self.assertTrue(memory["phrases"])
            self.assertTrue(evidence["partialCoverage"])
            for phrase in memory["phrases"]:
                self.assertTrue(all(np.isfinite(phrase[key]).all() for key in ("rhythm", "lowRhythm", "highRhythm")))
                self.assertTrue(all(0 <= value <= 1 for key in ("rhythm", "lowRhythm", "highRhythm") for value in phrase[key]))
                self.assertIsNone(phrase["repeatOf"])
            self.assertEqual(memory["events"], [])

    def test_equal_phrase_repeats_but_shuffled_phrase_does_not(self):
        pattern_a = [0, 4, 8, 12]
        pattern_b = [0, 2, 3, 6, 8, 10, 14]
        pattern_shuffled = [1, 2, 5, 7, 9, 11, 13]
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "phrases.wav"
            sidecar = fixture_wav(wav, [pattern_b, pattern_a, pattern_shuffled, pattern_a])
            memory, _ = analyze(wav, sidecar)
            phrases = memory["phrases"]
            repeats = [(i, p["repeatOf"]) for i, p in enumerate(phrases) if p["repeatOf"] is not None]
            self.assertIn((4, 2), repeats)  # second full A phrase links to first full A phrase
            self.assertTrue(all(phrases[i]["similarity"] >= 0.88 for i, _ in repeats))
            shuffled = next(i for i, p in enumerate(phrases) if p["start"] >= 16.0 and p["complete"])
            self.assertIsNone(phrases[shuffled]["repeatOf"])

    def test_phrase_times_and_numeric_contract_are_finite(self):
        with tempfile.TemporaryDirectory() as temp:
            wav = Path(temp) / "finite.wav"
            sidecar = fixture_wav(wav, [[0, 4, 8, 12]] * 4)
            memory, evidence = analyze(wav, sidecar)
            self.assertTrue(np.isfinite(memory["beatPeriod"]))
            self.assertTrue(np.isfinite(memory["beatZero"]))
            for phrase in memory["phrases"]:
                self.assertTrue(0 <= phrase["start"] < phrase["end"] <= sidecar["duration"])
                for key in ("level", "lowRatio", "brightness", "similarity"):
                    self.assertTrue(np.isfinite(phrase[key]))
                self.assertEqual(len(phrase["rhythm"]), 32)
                self.assertEqual(len(phrase["chromaRhythm"]), 384)
                self.assertTrue(np.isfinite(phrase["chromaRhythm"]).all())
            self.assertGreaterEqual(evidence["gridFit"]["within80msFraction"], 0.9)
            phrases = memory["phrases"]
            self.assertAlmostEqual(phrases[0]["start"], 0, delta=1e-8)
            for previous, current in zip(phrases, phrases[1:]):
                self.assertAlmostEqual(previous["end"], current["start"], delta=1e-8)
            self.assertAlmostEqual(phrases[-1]["end"], sidecar["duration"], delta=1e-8)
            self.assertEqual(memory["events"][0]["kind"], "mix_onset")
            self.assertGreater(evidence["measuredFluxGridSupport"]["peakCount"], 0)
            self.assertEqual(evidence["measuredFluxGridSupport"]["timeResolutionMs"], 20)

    def test_long_grid_fit_resists_jitter_and_single_bad_anchor(self):
        period = 0.5013
        beats = [0.127 + i * period + 0.002 * np.sin(i * 0.71) for i in range(520)]
        beats[241] += 0.09
        fit, zero, evidence = regularize_beats(beats, beats[-1] + period)
        self.assertAlmostEqual(fit, period, delta=0.0002)
        self.assertAlmostEqual(zero, 0.127, delta=0.005)
        self.assertGreater(evidence["within80msFraction"], 0.98)

    def test_original_sidecar_fields_and_output_path_safeguards(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wav, source, output, evidence = (root / name for name in ("in.wav", "in.json", "out.json", "evidence.json"))
            source.write_text('{"schema":3,"beats":[],"keep":{"exact":true}}')
            original = __import__("json").loads(source.read_text())
            enriched = with_musical_memory(original, {"version": 1})
            self.assertTrue(all(enriched.get(key) == value for key, value in original.items()))
            _validate_output_paths(wav, source, output, evidence)
            for bad_output, bad_evidence in ((source, evidence), (output, wav), (output, output)):
                with self.assertRaises(ValueError):
                    _validate_output_paths(wav, source, bad_output, bad_evidence)


if __name__ == "__main__":
    unittest.main()
