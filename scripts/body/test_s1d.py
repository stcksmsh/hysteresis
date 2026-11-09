"""cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_s1d   (each test module in its own process)"""
import importlib.util
import os
import subprocess
import tempfile
import unittest

import numpy as np

import s1_toy as S

REF = "f8eee240d3faf58728b382e4bdcdb9b4157aa26b"      # origin/body when WO24 started


def old_module():
    src = subprocess.check_output(["git", "show", f"{REF}:scripts/body/s1_toy.py"], text=True)
    path = os.path.join(tempfile.mkdtemp(), "s1_toy_ref.py")
    open(path, "w").write(src)
    spec = importlib.util.spec_from_file_location("s1_toy_ref", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class DHinge(unittest.TestCase):
    def test_update_on_hand_made_sequence(self):
        mu, out = 0.0, []
        for d in [0.2, 0.5, 0.7, 0.9, 0.6]:
            mu, g = S.d_hinge_update(mu, d, eta=0.16)
            out.append((round(mu, 6), round(g, 6)))
        # g = .5, .2, 0 (at target), 0, .1; mu only accumulates (g >= 0)
        self.assertEqual(out, [(0.08, 0.5), (0.112, 0.2), (0.112, 0.0), (0.112, 0.0), (0.128, 0.1)])

    def test_d_est_formula_equals_evaluation(self):
        rng = np.random.default_rng(0)
        pred = rng.standard_normal((16, S.T, 8))
        tgt = pred + 0.5 * rng.standard_normal((16, S.T, 8))
        self.assertEqual(S.shifted_gap_D(pred, tgt, boot=False)[0], S.shifted_gap_D(pred, tgt)[0])

    def test_arm_iii_one_epoch_identical_to_origin_body(self):
        old = old_module()
        dn = S.arm_data(S.build_data(), "iii")
        do = old.arm_data(old.build_data(), "iii")
        _, hn = S.train("iii", 0, 1, 0.0, dn, log=lambda s: None)
        _, ho = old.train("iii", 0, 1, 0.0, do, log=lambda s: None)
        for k in ("loss", "dec", "nce", "g", "mu"):
            self.assertEqual(hn[0][k], ho[0][k], k)

    def test_iii_plus_D_runs_and_logs(self):
        d = S.arm_data(S.build_data(), "iii+D")
        _, h = S.train("iii+D", 0, 2, 0.0, d, log=lambda s: None)
        self.assertAlmostEqual(h[0]["mu_D"], S.ETA_D * max(0.0, 0.7 - h[0]["d_est"]))
        self.assertIn("d_est", h[1])


if __name__ == "__main__":
    unittest.main()
