"""WO16: tests of the default-off diag flag (m3f_jax.arm_step_diag) and of the hold finder. Provisional servo model (Feetech STS3215 12 V assumed).

    python -m unittest -v test_m3f_park        # from scripts/body, body env
"""
import unittest

import jax
import jax.numpy as jnp
import numpy as np

import m3d
import m3e_jax as M
import m3f
import m3f_jax as F
import m3f_park_diag as D

TOY = "/secondary/hyst-data/body/m3d/toy.npz"
CFG = dict(body="v2f", obs_lp=True, phase_lp=True, xfade=True, ctc=0.006, plane=0.053, clip=True)


class Diag(unittest.TestCase):
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

    def test_default_has_no_diag_outputs_and_flag_off_is_identical(self):
        a, b = self.run_chunk(CFG), self.run_chunk({**CFG, "diag": False})
        self.assertFalse([k for k in a if k.startswith("dg_")])
        self.assertEqual(sorted(a), sorted(b))
        for k in a:
            self.assertTrue(np.array_equal(a[k], b[k]), k)

    def test_diag_on_leaves_the_rollout_bit_identical_and_adds_outputs(self):
        a, b = self.run_chunk(CFG), self.run_chunk({**CFG, "diag": True})
        for k in a:
            self.assertTrue(np.array_equal(a[k], b[k]), k)
        extra = sorted(k for k in b if k not in a)
        self.assertEqual(extra, sorted("dg_" + k for k in ("hits", "cf", "cn", "tgt_hit", "t_pre", "centre", "amp", "phase", "freq", "tgt")))
        self.assertEqual(b["dg_t_pre"].shape, (2, 8, 50, 5))
        self.assertEqual(b["dg_cf"].shape, (2, 8, 50, len(F.CONTACT_CATS)))
        self.assertTrue((b["dg_hits"] >= 0).all() and (b["dg_hits"] <= F.J.SUB).all())
        self.assertLessEqual(float(b["dg_tgt"][..., 1:4].max()), 110.0 - F.CLIP_MARGIN_DEG + 1e-9)

    def test_hits_fire_when_the_target_is_far_beyond_the_range(self):
        cfg = {**CFG, "diag": True}
        d, tgt, tv = F.arm_init(cfg, np.array([0.0, 100.0, 100.0, 100.0, 0.0]))
        step = jax.jit(lambda d, tgt, tv, t: F.arm_step(cfg, d, tgt, tv, t))
        hits, held = 0.0, 0.0
        for _ in range(300):
            d, tgt, tv, _, info = step(d, tgt, tv, jnp.asarray([0.0, 160.0, 160.0, 160.0, 0.0]))
            hits += float(info["hits"][1:4].sum())
            held = max(held, float(tgt[1:4].max()))
        self.assertLessEqual(held, 110.0 - F.CLIP_MARGIN_DEG + 1e-9)
        self.assertEqual(float(jnp.degrees(d.qpos)[1:4].max()) <= 110.0 + 1e-9, True)

    def test_contact_force_is_logged_when_the_arm_presses_on_the_table(self):
        cfg = {**CFG, "diag": True}
        d, tgt, tv = F.arm_init(cfg, np.array([0.0, 0.0, 0.0, 0.0, 0.0]))
        step = jax.jit(lambda d, tgt, tv, t: F.arm_step(cfg, d, tgt, tv, t))
        cf = np.zeros(len(F.CONTACT_CATS))
        for _ in range(400):
            d, tgt, tv, _, info = step(d, tgt, tv, jnp.asarray([0.0, 100.0, 0.0, 0.0, 0.0]))        # the arm points down at the table
            cf = np.maximum(cf, np.asarray(info["cf"]))
        self.assertGreater(cf[0], 0.01, cf)

    def test_contact_category_matrix(self):
        m = F.body_model(CFG)[0]
        cat = F._contact_cat_matrix(m)
        self.assertEqual(cat[0, 5], 0)                       # table vs link
        self.assertEqual(cat[11, 2], 1)                      # ball vs column
        self.assertEqual(cat[11, 6], 2)                      # ball vs link
        self.assertEqual(cat[4, 2], 3)                       # link vs column
        self.assertEqual(cat[4, 8], 4)                       # link vs link


class Holds(unittest.TestCase):
    def test_finds_only_long_holds_on_the_stops(self):
        q = np.zeros((1, 3000, 5))
        q[0, 100:350, 2] = 110.0                              # 2.5 s on the + stop: a hold
        q[0, 400:500, 2] = 110.0                              # 1 s: too short
        q[0, 1000:1300, 1] = -110.0 + 0.03                    # inside the tolerance, - side
        q[0, 2000:2300, 3] = 109.9                            # outside the 0.05 deg tolerance
        q[0, 2500:2800, 4] = 110.0                            # roll is not ranged
        h = D.find_holds(q)
        self.assertEqual([(x["joint"], x["side"], x["start"], x["end"]) for x in h], [(1, -1, 1000, 1300), (2, 1, 100, 350)])


if __name__ == "__main__":
    unittest.main()
