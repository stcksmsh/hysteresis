"""WO23: --acc-share / --speed-share default to today's values, and the defaults leave the generator bit-identical to origin/body.
Run from scripts/body with the body env: python -m unittest test_acc_share"""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

import cpg
import m3d_jax

HERE = Path(__file__).resolve().parent


def origin_cpg():
    """cpg.py exactly as on origin/body (literal 0.8 speed share), loaded under another name."""
    src = subprocess.check_output(["git", "show", "origin/body:scripts/body/cpg.py"], cwd=HERE).decode()
    d = Path(tempfile.mkdtemp())
    (d / "cpg_origin.py").write_text(src)
    spec = importlib.util.spec_from_file_location("cpg_origin", d / "cpg_origin.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class Defaults(unittest.TestCase):
    def test_constants(self):
        self.assertEqual((cpg.ACC_SHARE, cpg.SPEED_SHARE), (0.25, 0.8))

    def test_numpy_generator_bit_identical(self):
        o = origin_cpg()
        rng = np.random.default_rng(0)
        a, b = cpg.CPG(), o.CPG()
        a.reset(); b.reset()
        for k in range(3000):
            if k % 200 == 0:
                cmd = cpg.random_commands(rng)
                a.command(*cmd); b.command(*cmd)
            qa, qb = a.step(), b.step()
            self.assertTrue(np.array_equal(qa, qb), k)

    def test_jax_step_equals_numpy_reference_at_defaults(self):
        """m3d_jax.cpg_step's cap line with the module constants == the old literal 0.8 line (same float ops, same order)."""
        am = np.array([1.0, 5.0, 20.0, 60.0, 120.0])
        w = 2 * np.pi * (1 + cpg.COUPLING)
        V = np.array([v for v, _ in cpg.LIMITS]); A = np.array([x for _, x in cpg.LIMITS])
        self.assertTrue(np.array_equal(cpg.SPEED_SHARE * V / am / w, 0.8 * V / am / w))
        self.assertTrue(np.array_equal(np.sqrt(cpg.ACC_SHARE * A / am) / w, np.sqrt(0.25 * A / am) / w))


if __name__ == "__main__":
    unittest.main()
