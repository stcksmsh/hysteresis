"""WO32D: the look-test gate verdict (rules (l)): "limits" at 1.25 x, every other gate as 7.44. Run: python -m unittest test_retarget_gates (body env)."""
import unittest

import retarget_run as RR

GOOD = dict(floor_m=0.2, contact_substeps=0, endstop_samples=0, hf_share=0.0, reversals_max=2.0, speed_ratio=0.9, accel_ratio=0.9, finite=True)
MOTION = dict(extent_m=0.5, min_stretch_speed=0.1)


def verdict(**over):
    return RR.judge_v2p({**GOOD, **over}, MOTION, guard_share=0.0)


class Gates(unittest.TestCase):
    def test_all_good_passes(self):
        self.assertTrue(verdict()["passed"])

    def test_acceleration_1_2_passes_at_the_look_test_tolerance(self):
        v = verdict(accel_ratio=1.2)
        self.assertTrue(v["passed"], v["parts"])

    def test_acceleration_1_3_fails(self):
        v = verdict(accel_ratio=1.3)
        self.assertFalse(v["passed"])
        self.assertFalse(v["parts"]["limits"])

    def test_speed_1_2_passes_and_1_3_fails(self):
        self.assertTrue(verdict(speed_ratio=1.2)["passed"])
        self.assertFalse(verdict(speed_ratio=1.3)["passed"])

    def test_other_gates_still_fail(self):
        self.assertFalse(verdict(contact_substeps=3)["passed"])
        self.assertFalse(verdict(endstop_samples=6)["passed"])
        self.assertFalse(verdict(floor_m=-0.01)["passed"])
        self.assertFalse(RR.judge_v2p(GOOD, dict(extent_m=0.05, min_stretch_speed=0.1), 0.0)["passed"])
        self.assertFalse(RR.judge_v2p(GOOD, MOTION, 0.2)["passed"])



class Smoke(unittest.TestCase):
    def test_one_candidate_runs_end_to_end(self):
        """one real candidate through sim_variant (V1 and V2): the whole path imports and returns the five outputs"""
        import numpy as np
        cat = RR.catalogue()
        order = [str(g) for g in np.random.default_rng(RR.SEED).permutation(sorted({v[0] for v in cat.values()}))]
        c = RR.pick(0, order, cat)
        for var in ("V1", "V2"):
            q50, share, g, sh = RR.sim_variant(c, var)
            self.assertEqual(q50.shape, (1001, 5))
            self.assertIn("passed", g)
            self.assertIn("p95", sh["commanded_accel_x_limit"])


if __name__ == "__main__":
    unittest.main()
