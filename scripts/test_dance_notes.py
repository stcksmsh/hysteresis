import unittest

import numpy as np

from dance_notes import beat_levels, track


class NoteTrackTest(unittest.TestCase):
    def test_pause_and_pitch_split_phrases(self):
        rate, beat = 44100, 0.5

        def burst(midi, count):
            t = np.arange(round(0.25 * rate)) / rate
            f = 440 * 2 ** ((midi - 69) / 12)
            tone = sum(np.sin(2 * np.pi * f * h * t) / h for h in (1, 2, 3)) * np.exp(-30 * t)
            return np.tile(tone, count)

        silence = np.zeros(round(2 * beat * rate))
        audio = np.concatenate([silence, burst(57, 6), silence, burst(64, 6), burst(60, 6), silence])
        notes, phrases = track(audio.astype(np.float32), rate, beat)
        self.assertEqual(len(notes), 18)
        self.assertEqual([p["notes"] for p in phrases], [6, 6, 6])
        self.assertEqual([p["pitchMedian"] for p in phrases], [57, 64, 60])
        self.assertEqual([p["endsWith"] for p in phrases], ["pause", "pitch", "pause"])
        self.assertAlmostEqual(phrases[0]["start"], 1.0, delta=0.015)
        # Loud while the bursts play, near silent in the opening pause.
        levels = beat_levels(audio.astype(np.float32), rate, beat, 0.0, len(audio) / rate)
        self.assertGreater(levels[3] - levels[0], 40)


if __name__ == "__main__":
    unittest.main()
