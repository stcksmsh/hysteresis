"""cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_k5p2_endstop"""
import unittest

import numpy as np

import k5p2_endstop as E
import make_arm as MA


def traj(T=400):
    t = np.arange(T) / 100.0
    q = np.zeros((T, 5))
    q[:, 0] = 30 * np.sin(t)
    q[:, 1] = 20 * np.sin(2 * t)
    return q


class EndStop(unittest.TestCase):
    def test_events_count_entries_not_samples(self):
        q = traj()
        hi = MA.RANGE_DEG[1][1]
        q[100:110, 1] = hi                 # one stay at the limit = one event
        q[200:203, 1] = hi                 # a second
        q[250:260, 2] = MA.RANGE_DEG[2][0]
        ev = E.events(q)
        self.assertEqual(ev["shoulder"].tolist(), [100, 200])
        self.assertEqual(ev["elbow"].tolist(), [250])
        self.assertEqual(len(ev["wrist_bend"]), 0)

    def test_report_window_and_rates(self):
        q = traj()
        q[100:105, 1] = MA.RANGE_DEG[1][1]
        r = E.report(q[None].reshape(1, 8, 50, 5))
        self.assertEqual(r["100"]["events_total"]["shoulder"], 1)
        self.assertEqual(r["50"]["events_total"]["shoulder"], 1)
        self.assertAlmostEqual(r["100"]["seconds_near"], 0.11, places=2)      # +-5 samples around sample 100
        self.assertIn("per_trajectory", r["100"])
        self.assertNotIn("per_trajectory", r["50"])
        self.assertEqual(r["100"]["per_trajectory"]["n"], 1)

    def test_no_events(self):
        r = E.report(traj()[None].reshape(1, 8, 50, 5))
        self.assertEqual(r["100"]["trajectories_with_events"], 0)
        self.assertIsNone(r["100"]["pooled"]["acc_near"])
        self.assertIsNone(r["100"]["per_trajectory"]["acc_ratio_mean"])


if __name__ == "__main__":
    unittest.main()
