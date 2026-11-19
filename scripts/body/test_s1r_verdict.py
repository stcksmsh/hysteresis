import unittest

import s1r_verdict as V


def mk(js, half, D):
    return {"held": {"js_between": js, "js_half": half, "D": D}}


def runs(i_js, i_half, others):
    r = {}
    for s in (2, 3):
        r[("0", s)] = mk(0.5, 0.2, 0.8)
        r[("i", s)] = mk(i_js, i_half, 0.8)
        for n, (js, d) in others.items():
            r[(n, s)] = mk(js, 0.1, d if not isinstance(d, tuple) else d[s - 2])
    return r


class T(unittest.TestCase):
    def test_not_met(self):
        r = runs(0.5, 0.2, {"ii": (0.9, 0.8), "iii": (0.9, 0.8), "iv(0.05)": (0.9, 0.8), "iv(0.5)": (0.9, 0.8)})
        v = V.verdict(r)
        self.assertIsNone(v["reference_arm"])
        self.assertTrue(v["verdict"].startswith("no verdict"))

    def test_met_and_d_rule(self):
        o = {"ii": (0.2, 0.8), "iii": (0.2, (0.8, 0.69)), "iv(0.05)": (0.35, 0.8), "iv(0.5)": (0.1, 0.8)}
        v = V.verdict(runs(0.1, 0.1, o))
        self.assertEqual(v["reference_arm"], "i")
        self.assertTrue(v["arms"]["ii"]["reaches_2x"])
        self.assertFalse(v["arms"]["iii"]["reaches_2x"])  # D 0.69 on one seed
        self.assertEqual(v["smallest_arm_2x"], "ii")
        self.assertTrue(v["iv_reaches_3x"])

    def test_low_d_arm_skipped(self):
        o = {"ii": (0.2, 0.69), "iii": (0.2, 0.8), "iv(0.05)": (0.2, 0.8), "iv(0.5)": (0.1, 0.8)}
        v = V.verdict(runs(0.1, 0.1, o))
        self.assertEqual(v["smallest_arm_2x"], "iii")
        self.assertFalse(v["iv_reaches_3x"])


if __name__ == "__main__":
    unittest.main()
