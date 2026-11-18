"""Synthetic checks of WO53 part B (docs/RAWRHYTHM_RULES.md section 5): joints at 30 Hz through spline -> speed -> WO52 rhythm -> bin; no human data."""
import unittest

import numpy as np

import rawrhythm as RR
import rhythm_events as RE

BEAT = 0.5
SECS = 3.0


def t30():
    return np.arange(int(SECS * RR.FPS_RAW) + 1) / RR.FPS_RAW


def joints(track):
    """one joint track (T, 3) placed on the left wrist, the other five still -> (T, 6, 3)"""
    P = np.zeros((len(track), 6, 3))
    P[:, 0] = track
    return P


def circle(pulse_period, seed):
    t = t30()
    ph = np.random.default_rng(seed).uniform(0, 2 * np.pi)
    th = t + 0.8 * pulse_period / (2 * np.pi) * (1 - np.cos(2 * np.pi * t / pulse_period + ph))
    return np.stack([0.3 * np.cos(th), 0.3 * np.sin(th), np.full_like(t, 1.0)], 1)


def ratio_bin(P, sig="lwr"):
    sp = RR.speeds50(P)[sig][:int(SECS * RR.FS)]
    p, s = RE.rhythm(sp)
    return p / BEAT, RE.BIN_NAMES[int(RE.bins(np.array([p / BEAT]), np.array([s]))[0])]


class T(unittest.TestCase):
    def test_speed_pulse_at_beat_is_one(self):
        for seed in range(5):
            r, b = ratio_bin(joints(circle(BEAT, seed)))
            self.assertAlmostEqual(r, 1.0, delta=0.05)
            self.assertEqual(b, "1")
            self.assertEqual(ratio_bin(joints(circle(BEAT, seed)), "mean")[1], "1")

    def test_speed_pulse_at_two_beats_is_two(self):
        for seed in range(5):
            r, b = ratio_bin(joints(circle(2 * BEAT, seed)))
            self.assertAlmostEqual(r, 2.0, delta=0.1)
            self.assertEqual(b, "2")

    def test_swing_of_two_beats_gives_one(self):
        t = t30()
        for ph in np.linspace(0, 2, 5):
            tr = np.stack([0.3 * np.sin(2 * np.pi * t / (2 * BEAT) + ph), np.zeros_like(t), np.zeros_like(t)], 1)
            r, b = ratio_bin(joints(tr))
            self.assertEqual(b, "1", r)

    def test_noise_is_none(self):
        for seed in range(5):
            tr = np.random.default_rng(seed).normal(0, 0.01, (len(t30()), 3))
            self.assertEqual(ratio_bin(joints(tr))[1], "none")

    def test_pelvis_relative_removes_common_translation(self):
        t = t30()
        P = np.zeros((len(t), 6, 3))
        P += np.stack([0.5 * np.sin(2 * np.pi * t), np.zeros_like(t), np.zeros_like(t)], 1)[:, None]
        sp = RR.speeds50(P)
        self.assertGreater(sp["lwr"].max(), 1.0)
        self.assertLess(sp["lwr_rel"].max(), 1e-9)
        self.assertEqual(RE.rhythm(sp["pel_rel"][:150])[1], 0.0)

    def test_bvh_two_bone_chain(self):
        text = """HIERARCHY
ROOT Hips
{
  OFFSET 0 0 0
  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation
  JOINT Arm
  {
    OFFSET 10 0 0
    CHANNELS 3 Zrotation Xrotation Yrotation
    JOINT Hand
    {
      OFFSET 20 0 0
      CHANNELS 3 Zrotation Xrotation Yrotation
      End Site
      {
        OFFSET 1 0 0
      }
    }
  }
}
MOTION
Frames: 2
Frame Time: 0.0333333
100 0 0 0 0 0 0 0 0 0 0 0
100 0 0 90 0 0 90 0 0 0 0 0
"""
        P, sd = RR.bvh_positions(text, ("Hips", "Hand"), step=1)
        self.assertEqual(sd, 0.0)
        np.testing.assert_allclose(P[0], [[1, 0, 0], [1.3, 0, 0]], atol=1e-9)
        # root Rz 90: arm at (100, 10, 0) cm; arm Rz 90 more: hand offset (20, 0, 0) -> (-20, 0, 0)
        np.testing.assert_allclose(P[1, 0], [1, 0, 0], atol=1e-9)
        np.testing.assert_allclose(P[1, 1], [1, 0.1, 0] + np.array([-0.2, 0, 0]), atol=1e-9)


if __name__ == "__main__":
    unittest.main()
