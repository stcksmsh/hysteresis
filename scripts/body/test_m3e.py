"""M3e unit tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_m3e   (JAX env; own process).

Tolerance stated before the runs: JAX cerebellum against the torch original (float64 against float32): max abs difference of mean and logvar <= 2e-4 over 1,200 continuous steps.
"""
import unittest

import jax
import jax.numpy as jnp
import numpy as np

import m3e_jax as M

PARITY = "/secondary/hyst-data/body/m3e/cb_parity.npz"


class Cerebellum(unittest.TestCase):
    def test_jax_cerebellum_matches_torch(self):
        C = M.load_cb()
        z = np.load(PARITY)

        def run(obs, tgt):
            def f(s, x):
                s, m, l = M.cb_step(C, s, x[0], x[1])
                return s, (m, l)
            return jax.lax.scan(f, M.cb_init(tgt[0]), (jnp.asarray(obs, float), jnp.asarray(tgt, float)))[1]
        worst = 0.0
        for i in range(2):
            m, l = run(z["obs"][i], z["tgt"][i])
            worst = max(worst, float(np.abs(np.asarray(m) - z["mean_cont"][i]).max()), float(np.abs(np.asarray(l) - z["logvar_cont"][i]).max()))
        print(f"cerebellum parity: max abs difference {worst:.2e}")
        self.assertLess(worst, 2e-4)


class Causal(unittest.TestCase):
    def test_future_change_leaves_the_past_unchanged(self):
        import m3e
        rng = np.random.default_rng(0)
        y = rng.standard_normal((3, 120, 8)) * 3 + 1
        z0 = m3e.running_z(y)
        y2 = y.copy()
        y2[:, 70:] += 50.0                                   # change the future from block 70
        z1 = m3e.running_z(y2)
        np.testing.assert_array_equal(z0[:, :70], z1[:, :70])
        self.assertTrue((np.abs(z0[:, 70:] - z1[:, 70:]) > 0).any())

    def test_window_is_30_seconds(self):
        import m3e
        y = np.zeros((1, 120, 8))
        y[:, :40] = 1000.0                                   # a huge old level; at block 100 it is 60 blocks back (outside the window of blocks 41..100)
        a = m3e.running_z(y)
        y[:, :40] = 0.0
        b = m3e.running_z(y)
        np.testing.assert_array_equal(a[:, 100:], b[:, 100:])
        self.assertTrue((a[:, 8:20] == 0).all())             # constant window: SD ~ 0 -> z 0
        self.assertTrue((m3e.running_z(np.random.default_rng(1).standard_normal((1, 20, 8)))[:, :7] == 0).all())      # fewer than 8 blocks: z = 0

    def test_toy_inputs_use_only_the_past(self):
        import m3e
        from types import SimpleNamespace
        toy = m3e.ToyE.__new__(m3e.ToyE)
        rng = np.random.default_rng(2)
        y = rng.standard_normal((2, 120, 8))
        toy.phi = toy.omega = np.zeros((2, 120))
        toy.yz = m3e.running_z(y)
        x0 = np.asarray(toy.inputs(slice(0, 2), jax.random.PRNGKey(0))["x"])
        y2 = y.copy()
        y2[:, 60] += 30.0
        toy.yz = m3e.running_z(y2)
        x1 = np.asarray(toy.inputs(slice(0, 2), jax.random.PRNGKey(0))["x"])
        np.testing.assert_array_equal(x0[:, :61], x1[:, :61])          # block b reads the state of blocks <= b-1: block 60 is unchanged, block 61 is the first to see the change
        self.assertTrue((x0[:, 61] != x1[:, 61]).any())


class Dopamine(unittest.TestCase):
    def test_rate_multiplier(self):
        import m3e
        self.assertAlmostEqual(m3e.rate_multiplier(np.zeros(5), 1.0), 0.5)
        self.assertAlmostEqual(m3e.rate_multiplier(np.ones(5), 1.0), 1.5)
        self.assertAlmostEqual(m3e.rate_multiplier(np.full(5, 10.0), 1.0), 2.5)          # clipped at 2

    def test_realised_legibility_and_mask(self):
        import m3e
        dec = np.arange(10, dtype=float)[None].repeat(2, 0)
        R, mask = m3e.realised_legibility(dec, 8)
        self.assertEqual(R.shape, (2, 7))
        np.testing.assert_allclose(R[0], -np.array([1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5]))
        self.assertTrue(mask.all())
        self.assertFalse(m3e.realised_legibility(dec, 0)[1].all())                        # windows starting before block 8 are not scored

    def test_only_the_logit_path_gets_the_multiplier(self):
        import m3e
        P = m3e.M.init_policy(jax.random.PRNGKey(0))
        mu = m3e.logit_mult(P, 2.0)
        self.assertTrue((np.asarray(mu["w2"])[:, :8] == 2.0).all() and (np.asarray(mu["w2"])[:, 8:] == 1.0).all())
        self.assertTrue((np.asarray(mu["b2"])[:8] == 2.0).all() and (np.asarray(mu["b2"])[8:] == 1.0).all())
        for k in ("w1", "b1", "theta"):
            self.assertTrue((np.asarray(mu[k]) == 1.0).all())
        g = jax.tree_util.tree_map(jnp.ones_like, P)
        st = m3e.J.adam_init(P)
        P1, _, _ = m3e.adam_step_mult(P, g, st, 1e-3, m3e.logit_mult(P, 2.0), clip=1e9)
        d = lambda k: np.abs(np.asarray(P1[k]) - np.asarray(P[k]))
        np.testing.assert_allclose(d("w2")[:, :8], 2 * d("w2")[:, 8:9].repeat(8, 1), rtol=1e-6)      # first Adam step: lr * sign(g), logit columns doubled


class ClosedLoop(unittest.TestCase):
    def test_new_input_weights_start_at_zero(self):
        import m3e
        P = m3e.M.init_policy(jax.random.PRNGKey(0))
        self.assertEqual(P["w1"].shape[0], 41)
        self.assertTrue((np.asarray(P["w1"])[16:] == 0).all())
        P0 = m3e.J.init_policy(jax.random.PRNGKey(0))
        np.testing.assert_array_equal(np.asarray(P["w1"])[:16], np.asarray(P0["w1"]))

    def test_zero_new_weights_give_the_m3d_cortex_output(self):
        import m3e
        P = m3e.M.init_policy(jax.random.PRNGKey(0))
        P0 = m3e.J.init_policy(jax.random.PRNGKey(0))
        x = jnp.linspace(-1, 1, 16)
        out = m3e.J.motor_cortex(P, jnp.concatenate([x, 5 * jnp.ones(25)]))
        ref = m3e.J.motor_cortex(P0, x)
        for a, b in zip(out, ref):
            np.testing.assert_allclose(np.asarray(a), np.asarray(b), atol=1e-12)

    def test_controls_initial_policy_is_the_trainers(self):
        import m3e
        import m3e_controls
        from types import SimpleNamespace
        t = m3e.Trainer(SimpleNamespace(n_train=16), M.load_cb(), 0.3, 1e-3, 1)
        for a, b in zip(jax.tree_util.tree_leaves(m3e_controls.initial_policy()), jax.tree_util.tree_leaves(t.P)):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))

    def test_quantisation_is_straight_through(self):
        q = jnp.array([0.30, -41.37])
        v = M.quantise_st(q)
        self.assertTrue(np.allclose(np.asarray(v) / M.QUANT, np.round(np.asarray(v) / M.QUANT)))
        np.testing.assert_allclose(np.asarray(jax.grad(lambda a: M.quantise_st(a).sum())(q)), 1.0)

    def test_one_closed_loop_block_runs(self):
        """Shapes, finiteness, the proprioception delay (the snapshot used at step k is step k-1's state) and the gradient reaching the cortex's new weights."""
        import m3e
        C = M.load_cb()
        P = m3e.M.init_policy(jax.random.PRNGKey(0))
        q0 = np.array([0.0, -55.0, 35.0, 5.0, 0.0])
        carry = M.init_carry(q0, C)
        inp = {"x": jnp.zeros(16), "phi0": 0.0, "om0": 0.0, "g": jnp.zeros(8)}
        c1, o = M.block_fn(C, P, "argmax", 0.0, carry, inp)
        self.assertEqual(o["idesc"].shape, (37,))
        self.assertEqual(o["feat"].shape, (25,))
        self.assertTrue(np.isfinite(np.asarray(o["feat"])).all() and np.isfinite(np.asarray(o["idesc"])).all())

        def f(P):
            c, o = M.block_fn(C, P, "train", 0.5, carry, inp)
            c2, o2 = M.block_fn(C, P, "train", 0.5, c, inp)              # the second block's cortex input carries the first block's proprioception
            return o2["desc"].sum() + o2["idesc"].sum()
        g = jax.grad(f)(P)
        self.assertGreater(float(jnp.abs(g["w1"][16:26]).max()), 0.0)


class Ablations(unittest.TestCase):
    def test_defaults_reproduce_try1(self):
        """Reference loss and gradient norm recorded with the try-1 code (before the ablation switches existed) at fixed inputs."""
        ref = np.load(REF_LOSS)
        l, gn = _loss_probe()
        self.assertAlmostEqual(l, float(ref["loss"]), delta=1e-9 * abs(float(ref["loss"])))
        self.assertAlmostEqual(gn, float(ref["gnorm"]), delta=1e-9 * float(ref["gnorm"]))

    def test_switches_change_what_they_name(self):
        ref = np.load(REF_LOSS)
        l_noint, _ = _loss_probe(internal=False)
        self.assertLess(l_noint, float(ref["loss"]) - 0.1)                                   # the internal decoding term is gone
        l_open, _ = _loss_probe(loop_gate=0.0)
        self.assertNotAlmostEqual(l_open, float(ref["loss"]), places=6)                       # cutting the loop changes the cortex (non-zero closed-loop weights)
        l_g, gn_g = _loss_probe(gate=False)
        self.assertAlmostEqual(l_g, float(ref["loss"]), delta=1e-9 * abs(float(ref["loss"])))   # gating acts on the update, not on the loss

    def test_cerebellum_error_outputs_are_finite(self):
        C = M.load_cb()
        P = M.init_policy(jax.random.PRNGKey(0))
        c = M.init_carry(np.array([0.0, -55.0, 35.0, 5.0, 0.0]), C)
        inp = {"x": jnp.zeros(16), "phi0": 0.0, "om0": 0.0, "g": jnp.zeros(8)}
        c, o = M.block_fn(C, P, "argmax", 0.0, c, inp)
        c, o = M.block_fn(C, P, "argmax", 0.0, c, inp)
        self.assertTrue(np.isfinite(float(o["cb_sq"])) and np.isfinite(float(o["cb_nll"])))


REF_LOSS = "/secondary/hyst-data/body/m3e/ref_default_loss.npz"


def _loss_probe(loop_gate=None, **flags):
    """Loss and gradient norm of one 8-block chunk of 2 training episodes at fixed fake statistics: the try-1 default path (flags: Trainer's ablation switches)."""
    import m3e
    toy = m3e.ToyE("/secondary/hyst-data/body/m3d/toy.npz")
    C = M.load_cb()
    if loop_gate is not None:
        C = {**C, "loop_gate": jnp.asarray(loop_gate)}
    t = m3e.Trainer(toy, C, 0.03, 1e-3, 40, **flags)
    fns = t.fns
    idx = np.arange(2)
    inps = toy.inputs(idx, jax.random.PRNGKey(3))
    carry = jax.vmap(lambda q: M.init_carry(q, t.C))(jnp.asarray(m3e.m3d.start_poses(2, 100)))
    # a nonzero closed-loop weight so the switch has something to cut
    P = {**t.P, "w1": t.P["w1"].at[16:].set(0.05)}
    S = dict(dmu=np.zeros(31), dsd=np.ones(31), imu=np.zeros(37), isd=np.ones(37))
    (l, _), g = fns["loss"](P, t.obs["A"][0], t.obs["A"][1], carry, m3e.m3d.take(inps, 8, 16), jnp.asarray(toy.yz[idx])[:, 8:16], m3e.valid_mask(8, 8, 2), 0.5, 0.03, 1.0, S["dmu"], S["dsd"], S["imu"], S["isd"])
    gn = float(jnp.sqrt(sum((x ** 2).sum() for x in jax.tree_util.tree_leaves(g))))
    return float(l), gn


def write_ref():
    l, gn = _loss_probe()
    np.savez(REF_LOSS, loss=l, gnorm=gn)


if __name__ == "__main__":
    unittest.main()
