"""cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_s1f   (each test module in its own process)"""
import importlib.util
import os
import subprocess
import tempfile
import unittest

import s1_toy as S
import s1f_report

REF = "da9912e"      # origin/body when WO25 started


def old_module():
    src = subprocess.check_output(["git", "show", f"{REF}:scripts/body/s1_toy.py"], text=True)
    path = os.path.join(tempfile.mkdtemp(), "s1_toy_ref.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("s1_toy_ref", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Falling(unittest.TestCase):
    def test_falling_update_hand_made_sequence(self):
        mu, out = 0.0, []
        for d in [0.2, 0.5, 0.9, 0.9, 0.9, 0.7, 0.95]:
            mu, g = S.d_hinge_update(mu, d, eta=0.16, falling=True)
            out.append((round(mu, 6), round(g, 6)))
        # rises while D < .7 (.5 -> .08, .2 -> .112); falls while D > .7 (-.2*.16 = -.032 each); never below 0
        self.assertEqual(out, [(0.08, 0.5), (0.112, 0.2), (0.08, -0.2), (0.048, -0.2), (0.016, -0.2), (0.016, 0.0), (0.0, -0.25)])
        self.assertTrue(all(m >= 0 for m, _ in out))

    def test_rising_default_unchanged(self):
        self.assertEqual(S.d_hinge_update(0.5, 0.9), (0.5, 0.0))

    def test_arm_iii_plus_D_one_epoch_identical_to_origin_body(self):
        old = old_module()
        dn = S.arm_data(S.build_data(), "iii+D")
        do = old.arm_data(old.build_data(), "iii+D")
        _, hn = S.train("iii+D", 4, 1, 0.0, dn, log=lambda s: None)
        _, ho = old.train("iii+D", 4, 1, 0.0, do, log=lambda s: None)
        for k in ("loss", "dec", "nce", "g", "mu", "d_est", "g_D", "mu_D"):
            self.assertEqual(hn[0][k], ho[0][k], k)

    def test_iii_plus_Df_runs_and_logs(self):
        d = S.arm_data(S.build_data(), "iii+Df")
        _, h = S.train("iii+Df", 6, 2, 0.0, d, log=lambda s: None)
        self.assertAlmostEqual(h[0]["mu_D"], max(0.0, S.ETA_D * (0.7 - h[0]["d_est"])))
        self.assertIn("d_est", h[1])


class Rule(unittest.TestCase):
    def runs(self, df6, df7, mf6, mf7, mr6, mr7):
        return {"iii+Df_s6": {"D": df6, "mmd_between": mf6}, "iii+Df_s7": {"D": df7, "mmd_between": mf7},
                "iii+D_s6": {"mmd_between": mr6}, "iii+D_s7": {"mmd_between": mr7}}

    def test_outcomes(self):
        d = s1f_report.decide
        self.assertEqual(d(self.runs(.8, .75, .3, .3, .2, .2), (6, 7))["outcome"], "falling")
        self.assertEqual(d(self.runs(.8, .65, .3, .3, .2, .2), (6, 7))["outcome"], "rising")      # D fails on one seed
        self.assertEqual(d(self.runs(.8, .75, .1, .1, .2, .2), (6, 7))["outcome"], "rising")      # MMD lower
        r = d(self.runs(.8, .75, .5, .1, .2, .25), (6, 7))                                          # mean .3 >= .225, but seed 7 lower
        self.assertEqual((r["outcome"], r["per_seed_reading_outcome"], r["readings_agree"]), ("falling", "rising", False))


if __name__ == "__main__":
    unittest.main()
