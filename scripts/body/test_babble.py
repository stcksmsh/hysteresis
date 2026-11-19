"""M1 babbling tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_babble"""
import unittest

import numpy as np

import babble


class Babble(unittest.TestCase):
    def test_reproducible_from_a_seed(self):
        a, b = babble.trajectory(7, 3.0), babble.trajectory(7, 3.0)
        self.assertTrue(np.array_equal(a[0], b[0]) and np.array_equal(a[1], b[1]))
        c = babble.trajectory(8, 3.0)
        self.assertFalse(np.array_equal(a[1], c[1]))

    def test_ou_time_constant_and_range(self):
        u = babble.ou_commands(np.random.default_rng(0), 20000)
        self.assertTrue(0 <= u.min() and u.max() <= 1)
        x = u[:, 0, 0] - u[:, 0, 0].mean()
        r = (x[:-10] * x[10:]).mean() / x.var()                # lag 1 s: ~exp(-1) in latent space, a little different after the CDF squash
        self.assertTrue(0.2 < r < 0.5, r)

    def test_generate_shapes_and_own_start_pose(self):
        o, t = babble.generate(3, 5, secs=2.0, procs=1)
        self.assertEqual((o.shape, t.shape), ((3, 200, 15), (3, 200, 5)))
        self.assertGreater(np.abs(t[0, 0] - t[1, 0]).max(), 1.0)


if __name__ == "__main__":
    unittest.main()
