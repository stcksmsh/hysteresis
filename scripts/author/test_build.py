"""build.py's self_error lane: mean over arms and horizons, three 30 Hz bins per 0.1 s bin, NaN ignored, padded to n."""
import tempfile
import unittest
from pathlib import Path

import numpy as np

import build


class SelfError(unittest.TestCase):
    def test_lane(self):
        d = Path(tempfile.mkdtemp())
        z = np.zeros((6, 7, 3), np.float32)
        z[:, :3] = 2.0               # first 0.1 s bin
        z[:, 3:6, 0] = 4.0           # second: horizon 0 is 4, others 0 -> mean 4/3
        z[0, 0, 0] = np.nan          # one undefined value is left out of the mean, not counted as 0
        np.savez(d / "s.npz", nll=z)
        old, build.SELF = build.SELF, d
        try:
            lane = build.self_error("s", 4)
        finally:
            build.SELF = old
        self.assertEqual(len(lane), 4)
        self.assertAlmostEqual(lane[0], 2.0, 4)
        self.assertAlmostEqual(lane[1], 4 / 3, 4)
        self.assertEqual(lane[2:], [0.0, 0.0])      # data ends after two full bins; the 7th 30 Hz bin is a partial and dropped


if __name__ == "__main__":
    unittest.main()
