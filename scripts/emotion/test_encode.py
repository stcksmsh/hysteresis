import hashlib
import json
import pathlib
import tempfile
import unittest

import numpy as np
import soundfile as sf

import encode


def fake_component(audio_path, duration, centres, **_):
    return np.stack([np.asarray(centres), np.ones(len(centres))], axis=1).astype(np.float32)


class EncodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.audio = self.tmp / "a.wav"
        sf.write(self.audio, np.zeros(44100 * 10, dtype=np.float32), 44100)
        self.sidecar = {"schema": 3, "duration": 10.0, "beats": [0.5, 1.5, 2.5, 8.0], "tempo": 120.0,
                        "extra": {"keep": [1, 2, 3]}}
        self.input = self.tmp / "in.sidecar.json"
        self.input.write_text(json.dumps(self.sidecar))
        encode.COMPONENTS["fake"] = (fake_component, "fake", "0")

    def tearDown(self):
        encode.COMPONENTS.pop("fake", None)

    def digest(self, path):
        return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()

    def test_output_is_additive_and_input_is_unchanged(self):
        before = self.digest(self.input)
        out = self.tmp / "out.sidecar.json"
        encode.encode_file(self.input, self.audio, out, ["fake"])
        self.assertEqual(self.digest(self.input), before)
        result = json.loads(out.read_text())
        enc = result.pop("emotionEncoding")
        self.assertEqual(result, self.sidecar)               # every original field untouched
        self.assertEqual(enc["dims"], 2)
        self.assertEqual(enc["hopSeconds"], 0.5)
        self.assertEqual(len(enc["steps"]), 21)               # 0 .. 10 s at 0.5 s
        self.assertEqual(len(enc["perBeat"]), 4)
        self.assertEqual(enc["steps"][4][0], 2.0)
        for key in ("model", "version", "dims", "hopSeconds", "steps", "perBeat"):
            self.assertIn(key, enc)

    def test_per_beat_is_the_mean_of_steps_inside_each_beat(self):
        out = self.tmp / "out.json"
        enc = encode.encode_file(self.input, self.audio, out, ["fake"])
        # beat 0.5-1.5 covers step centres 0.5, 1.0 -> mean 0.75
        self.assertAlmostEqual(enc["perBeat"][0][0], 0.75, places=4)
        # last beat 8.0-10.0 covers 8.0, 8.5, 9.0, 9.5 -> 8.75
        self.assertAlmostEqual(enc["perBeat"][3][0], 8.75, places=4)

    def test_refuses_to_overwrite_the_input_or_mismatched_audio(self):
        with self.assertRaises(ValueError):
            encode.encode_file(self.input, self.audio, self.input, ["fake"])
        sf.write(self.tmp / "short.wav", np.zeros(44100 * 5, dtype=np.float32), 44100)
        with self.assertRaises(ValueError):
            encode.encode_file(self.input, self.tmp / "short.wav", self.tmp / "o.json", ["fake"])
        with self.assertRaises(ValueError):
            encode.encode_file(self.input, self.audio, self.tmp / "o.json", ["nope"])

    def test_refuses_input_that_already_has_an_encoding(self):
        done = self.tmp / "done.json"
        encode.encode_file(self.input, self.audio, done, ["fake"])
        with self.assertRaises(ValueError):
            encode.encode_file(done, self.audio, self.tmp / "again.json", ["fake"])


if __name__ == "__main__":
    unittest.main()
