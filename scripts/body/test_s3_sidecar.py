"""Tests for s3_sidecar (work order 27). Body env, cores 12-17: python -m unittest test_s3_sidecar. Synthetic trajectories with known answers; log/checkpoint handling in a temp dir."""
import pickle
import tempfile
import unittest
from pathlib import Path

import numpy as np

import m3d_jax as J
import s3_sidecar as W

THR = {"energy": 0.3747, "jerk": 4.748e6}
E, NB = 2, 120


def still(q5):
    return np.tile(np.asarray(q5, float), (E, NB, 50, 1))


class Shares(unittest.TestCase):
    def blocks(self, e, j=0.0):
        return np.full((E, NB), e), np.full((E, NB), j)

    def test_still_arm_has_no_hand_activity(self):
        q = still([0, 20, 30, 10, 0])
        s = W.share_stats(q, *self.blocks(0.0), THR, 0.053)
        for k in ("hand_v", "jolt", "acc", "lim", "lim_any_bend", "energy", "jerk"):
            self.assertEqual(s[k], 0.0, k)
        self.assertEqual(s["n"]["blocks"], E * (NB - 8))
        self.assertEqual(s["n"]["control_steps"], E * (NB - 8) * 50)
        self.assertEqual(s["n"]["hand_samples_50hz"], E * (NB - 8) * 25)

    def test_on_threshold_counts_as_active(self):
        s = W.share_stats(still([0, 0, 0, 0, 0]), np.full((E, NB), THR["energy"]), np.full((E, NB), THR["jerk"] * 0.999), THR, None)
        self.assertEqual(s["energy"], 1.0)
        self.assertEqual(s["jerk"], 0.0)

    def test_limit_proximity_pairs(self):
        q = still([0, 100.0, 50, 50, 0])                                              # one bend exactly on 100 deg of the three
        s = W.share_stats(q, *self.blocks(0.0), THR, None)
        self.assertAlmostEqual(s["lim"], 1 / 3)
        self.assertEqual(s["lim_any_bend"], 1.0)
        s = W.share_stats(still([0, 99.9, 50, 50, 0]), *self.blocks(0.0), THR, None)
        self.assertEqual(s["lim"], 0.0)

    def test_hand_speed_threshold_from_a_base_rotation(self):
        q0 = np.array([0.0, 40.0, 40.0, 0.0, 0.0])
        h = np.asarray(J.hand_points(np.asarray([q0], np.float32)))[0]
        r = float(np.hypot(h[0], h[1]))                                                  # horizontal radius of the hand: base yaw w rad/s gives r w m/s
        t = np.arange(NB * 50) / 100.0
        for speed, want in ((1.5, 1.0), (0.8, 0.0)):
            w = np.degrees(speed / r)
            q = np.tile(q0, (NB * 50, 1))
            q[:, 0] = w * t
            s = W.share_stats(np.tile(q.reshape(NB, 50, 5), (E, 1, 1, 1)), *self.blocks(0.0), THR, None)
            self.assertEqual(s["hand_v"], want, speed)
            self.assertEqual(s["jolt"], 0.0)

    def test_floor_margin_sign(self):
        s = W.share_stats(still([0, 80, 0, 0, 0]), *self.blocks(0.0), THR, None)       # arm folded through the table: margin negative
        self.assertEqual(s["floor"], 1.0)


class Log(unittest.TestCase):
    def test_validation_lines_and_last_epoch_record(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "train.log"
            f.write_text('[  1s] epoch {"epoch": 0, "D_fast": 0.1}\n[  2s] epoch {"epoch": 199, "D_fast": 0.5, "D_slow": 0.2}\n'
                         "[  3s] validation at round 200: ext a 0.3, best 0.3, bad 0, stop False, compute 4.00 h\n[  4s] epoch {\"epoch\": 200}\n")
            v = W.validations(f)
            self.assertEqual(list(v), [200])
            self.assertEqual(v[200][2]["epoch"], 199)
            self.assertEqual(v[200][2]["D_slow"], 0.2)

    def test_copy_picks_the_epoch_or_reports_missed(self):
        with tempfile.TemporaryDirectory() as d:
            run, rd = Path(d) / "run", Path(d) / "R"
            run.mkdir()
            rd.mkdir()
            mk = lambda n, ep: (run / n).write_bytes(pickle.dumps({"trainer": {"epoch": ep}}))
            mk("ckpt.pkl", 201)
            mk("ckpt.prev.pkl", 200)
            p, _ = W.copy_with_epoch(run, rd, 200)
            self.assertEqual(p.name, "ckpt.prev.pkl")
            mk("ckpt.prev.pkl", 201)
            p, got = W.copy_with_epoch(run, rd, 200)
            self.assertIsNone(p)
            self.assertEqual([e for _, e in got], [201, 201])


if __name__ == "__main__":
    unittest.main()
