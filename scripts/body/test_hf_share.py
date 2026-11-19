"""hf_share tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_hf_share"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

import arm_sim
import hf_share as H

HZ = 50.0
T = np.arange(0, 60, 1 / HZ)


def traj(f_hz, amp=20.0):
    """A sine of f_hz on all five joints (the roll joint must not matter)."""
    return np.tile((amp * np.sin(2 * np.pi * f_hz * T))[:, None], (1, 5))


class Share(unittest.TestCase):
    def test_1hz_near_zero(self):
        self.assertLess(H.hf_share(traj(1.0), HZ), 0.01)

    def test_6hz_near_one(self):
        self.assertGreater(H.hf_share(traj(6.0), HZ), 0.97)

    def test_equal_power_mix_near_half(self):
        # velocity power of a sine is amp^2 (2 pi f)^2 / 2: equal velocity power needs amp ~ 1/f
        q = traj(1.0, 30.0) + traj(6.0, 5.0)
        v1, v6 = 30.0 * 2 * np.pi * 1.0, 5.0 * 2 * np.pi * 6.0
        self.assertAlmostEqual(v1 / v6, 1.0, places=6)
        self.assertAlmostEqual(H.hf_share(q, HZ), 0.5, delta=0.05)

    def test_roll_joint_ignored(self):
        q = traj(1.0)
        q[:, 4] = 40 * np.sin(2 * np.pi * 8 * T)
        self.assertLess(H.hf_share(q, HZ), 0.01)

    def test_mean_removed_and_scale_free(self):
        a = H.hf_share(traj(6.0) + 90.0, HZ)
        self.assertAlmostEqual(a, H.hf_share(traj(6.0), HZ), places=6)
        self.assertAlmostEqual(H.hf_share(3.0 * (traj(1.0) + traj(6.0, 5.0)), HZ), H.hf_share(traj(1.0) + traj(6.0, 5.0), HZ), places=9)

    def test_too_short_rejected(self):
        with self.assertRaises(ValueError):
            H.hf_share(traj(1.0)[:100], HZ)

    def test_csv_roundtrip(self):
        q = traj(6.0)[:1001]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_text(arm_sim.csv_text(q, hz=50, name="t"))
            self.assertAlmostEqual(H.hf_share_csv(p), H.hf_share(q, HZ), places=4)       # csv_text prints 6 decimals


if __name__ == "__main__":
    unittest.main()
