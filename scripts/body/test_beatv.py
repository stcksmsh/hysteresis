import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import beatv_lib as B  # noqa: E402


class V1(unittest.TestCase):
    def test_local_phase_with_drifting_tempo(self):
        rng = np.random.default_rng(1)
        n = 400
        ibi = 0.5 * (1 + 0.04 * np.sin(np.linspace(0, 6 * np.pi, n)))                  # +-4 % tempo drift
        beats = np.concatenate([[0.0], np.cumsum(ibi)])
        ev = beats[:-1] + 0.3 * np.diff(beats)                                          # exactly phase 0.3 of each interval
        w = B.local_windows(ev, beats, rng)
        R = np.array([x["R"] for x in w])
        self.assertGreater(np.median(R), 0.95)
        ph = (np.angle(np.mean([x["vec"] for x in w])) / (2 * np.pi)) % 1
        self.assertAlmostEqual(ph, 0.3, delta=0.04)
        rc = np.median([x["R113"] for x in w])
        self.assertLess(rc, 0.7)                                                         # a 13 % wrong period over 7 beats cannot keep R high
        # the single whole-song line smears the same events
        T, t0 = np.polyfit(np.arange(len(beats)), beats, 1)
        whole = abs(np.exp(2j * np.pi * (((ev - t0) / T) % 1)).mean())
        self.assertLess(whole, np.median(R))

    def test_uniform_events_chance(self):
        rng = np.random.default_rng(2)
        beats = np.arange(0, 200, 0.5)
        ev = np.sort(rng.uniform(0, 199, 3000))
        w = B.local_windows(ev, beats, rng)
        self.assertLess(abs(np.mean([x["R"] for x in w]) - np.mean([x["R113"] for x in w])), 0.05)


class V3(unittest.TestCase):
    def test_offset_recovered_and_drift(self):
        rng = np.random.default_rng(3)
        n = 3000
        e = np.convolve(rng.normal(size=n), np.ones(3) / 3, "same")
        a = np.roll(e, -7) + 0.3 * rng.normal(size=n)                                    # e[t + 7] ~ a[t]  -> best offset +7
        k, c, z, p95, _ = B.sync_scan(a, e, 30, np.random.default_rng(4))
        self.assertEqual(k, 7)
        self.assertGreater(z, 5)
        a2 = np.concatenate([np.roll(e, -7)[:1500], np.roll(e, 4)[1500:]])               # piecewise: +7 first half, -4 second half
        k1, *_ = B.sync_scan(a2[:1500], e[:1500], 30, np.random.default_rng(5))
        k2, *_ = B.sync_scan(a2[1500:], e[1500:], 30, np.random.default_rng(5))
        self.assertEqual((k1, k2), (7, -4))


class V2(unittest.TestCase):
    def test_bas_on_beat_is_max_and_chance_is_low(self):
        music = np.arange(0.5, 60, 0.5)
        speed_t = np.arange(0, 60, 1 / 30)
        speed = 1 + np.cos(2 * np.pi * speed_t / 0.5 + np.pi)                            # minima exactly on the beats (phase 0 of each 0.5 s)
        kin = B.kin_beats(speed, 30)
        self.assertGreaterEqual(B.bas(music, kin, 60), 0.95)
        self.assertGreaterEqual(B.bas(music, kin, 60, mode="kin"), 0.95)
        ch = B.bas_chance(music, kin, 60, np.random.default_rng(6))
        self.assertLess(ch, 0.9)                                                         # shifted by 0.125-0.5 s: sigma 0.1 s
        r = np.random.default_rng(7)
        self.assertLess(B.bas(music, np.sort(r.uniform(0, 60, 40)), 60), 0.9)

    def test_fk_zero_rotation_t_pose(self):
        R = np.tile(np.eye(3), (2, 22, 1, 1))
        P = B.fk(R, np.zeros((2, 3)))
        self.assertAlmostEqual(P[0, 20, 0], 0.08 + 0.10 + 0.28 + 0.26, places=6)         # left wrist along +x: collar + shoulder + upper arm + forearm
        self.assertAlmostEqual(P[0, 7, 1], -0.05 - 0.40 - 0.40, places=6)         # left ankle below the pelvis: hip + thigh + shank

    def test_angle_speed(self):
        th = np.linspace(0, 1, 31)
        c, s = np.cos(th), np.sin(th)
        a = np.stack([c, s, 0 * c, -s, c, 0 * c], 1)[:, None]                            # rotation about z by th, as rows
        R = B.rot6(np.tile(a, (1, 22, 1)))
        sp = B.angle_speed(R, 30)
        self.assertAlmostEqual(float(sp[5, 0]), 1.0, places=3)                           # 1 rad over 30 steps at 30 fps = 1 rad/s


if __name__ == "__main__":
    unittest.main()
