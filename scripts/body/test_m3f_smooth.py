"""WO17: tests of the --smooth-u option (cfg["smooth_u"]). Provisional servo model (Feetech STS3215 12 V assumed).

    python -m unittest -v test_m3f_smooth        # from scripts/body, body env
The strongest bit-identity check (option absent, WO15A/WO16 checkpoints) is `m3f_park_diag.py SEEDDIR OUTDIR`: its default re-simulation must stay max |dq| = 0 against the saved rollouts.
"""
import unittest

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3e_jax as M
import m3f
import m3f_jax as F

TOY = "/secondary/hyst-data/body/m3d/toy.npz"
CFG = dict(body="v2f", obs_lp=True, phase_lp=True, xfade=True, ctc=0.006, plane=0.053, clip=True)


class Map(unittest.TestCase):
    def test_gradient_nonzero_at_and_beyond_the_old_bounds(self):
        g = jax.vmap(jax.grad(F.smooth_u))(jnp.asarray([-0.2, 0.0, 0.5, 1.0, 1.2]))
        self.assertTrue(bool((g > 0.05).all()), np.asarray(g))
        self.assertAlmostEqual(float(g[2]), 1.0, places=6)                        # slope 1 at 0.5
        # the hard clip it replaces has zero gradient beyond the bounds
        self.assertEqual(float(jax.grad(lambda s: jnp.clip(s, 0, 1))(1.2)), 0.0)

    def test_strictly_monotone_inside_the_open_interval(self):
        s = jnp.linspace(-0.2, 1.2, 1001)
        u = np.asarray(F.smooth_u(s))
        self.assertTrue(bool((np.diff(u) > 0).all()))
        self.assertTrue(bool((u > 0).all() and (u < 1).all()))

    def test_bend_centres_never_reach_the_100_deg_bound_and_the_amplitude_cap_stays_open(self):
        s = jnp.linspace(-0.2, 1.2, 1001)
        for sc in (s, s[::-1]):
            u = jnp.stack([F.smooth_u(sc)] * 4)[:, :, None] * jnp.ones((1, 1, 5))                # (4, N, 5)
            cmd = jax.vmap(F.smooth_command, in_axes=1)(u)
            c = np.asarray(cmd["centre"])[:, 1:4]
            self.assertTrue(bool((np.abs(c) < 100.0).all()), np.abs(c).max())
            amax = 110.0 - np.abs(c)
            self.assertTrue(bool((amax >= 10.0).all()))
        # centre gradient w.r.t. the unclipped sum is non-zero at and beyond the old bounds
        gc = jax.vmap(jax.grad(lambda x: F.smooth_command(jnp.stack([F.smooth_u(x)] * 5).reshape(1, 5).repeat(4, 0))["centre"][2]))(jnp.asarray([-0.2, 0.0, 1.0, 1.2]))
        self.assertTrue(bool((jnp.abs(gc) > 1.0).all()), np.asarray(gc))

    def test_continuous_joints_keep_their_range(self):
        cmd = F.smooth_command(jnp.ones((4, 5)) * jnp.asarray([0.0, 0.5, 0.5, 0.5, 1.0]))
        self.assertAlmostEqual(float(cmd["centre"][0]), float(F.J.CLO[0]), places=6)
        self.assertAlmostEqual(float(cmd["centre"][4]), float(F.J.CHI[4]), places=6)


class Chunk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.toy = m3f.ToyF(TOY)
        cls.C = M.load_cb()
        cls.P = M.init_policy(jax.random.PRNGKey(0))

    def run_chunk(self, cfg, nb=8):
        idx = np.arange(0, 2)
        chunk = jax.jit(F.make_chunk(cfg), static_argnums=(2,))
        inps = self.toy.inputs(idx, jax.random.PRNGKey(1))
        carry = jax.vmap(lambda q: F.init_carry(cfg, q, self.C))(jnp.asarray(m3d.start_poses(2, 5)))
        _, o = chunk(self.C, self.P, "argmax", 0.0, carry, m3d.take(inps, 0, nb))
        return {k: np.asarray(v) for k, v in o.items()}

    def test_option_off_is_bit_identical_and_on_changes_the_rollout(self):
        a, b = self.run_chunk(CFG), self.run_chunk({**CFG, "smooth_u": False})
        for k in a:
            self.assertTrue(np.array_equal(a[k], b[k]), k)
        c = self.run_chunk({**CFG, "smooth_u": True, "diag": True})
        self.assertTrue(np.isfinite(c["q"]).all())
        self.assertFalse(np.array_equal(a["q"], c["q"]))
        self.assertTrue(bool((np.abs(c["dg_centre"][..., 1:4]) < 100.0).all()))        # the generator's bend centres (slewed from the neutral pose) stay inside +-100


if __name__ == "__main__":
    unittest.main()
