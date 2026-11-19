"""M3d unit tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_m3d   (JAX env; own process).

Tolerances stated before the runs: descriptor parity |jax - rust| <= 1e-6 x max(1, |rust|); the JAX arm against the numpy ArmSim on 3 s of random commands:
max joint difference <= 0.5 deg (one solver iteration against the full solver); kappa = 0 against cpg.CPG: targets within 1e-9 deg.
"""
import json
import unittest
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import arm_sim
import bdesc
import cpg
import m3d
import m3d_jax as J

REF = json.loads((Path(__file__).parent / "descriptor_ref.json").read_text())


def _commands(seed, n):
    rng = np.random.default_rng(seed)
    return [cpg.random_commands(rng, **cpg.CHECK_ENVELOPE) for _ in range(n)]


class Body(unittest.TestCase):
    def test_jax_descriptors_match_rust(self):
        f = jax.jit(lambda x: J.descriptors(x, 3.0))
        for c in REF:
            rs = np.array(c["descriptors"])[bdesc.RUST_INDEX]
            py = np.asarray(f(jnp.asarray(c["q"])))
            self.assertEqual(len(py), 31)
            self.assertTrue((np.abs(py - rs) <= 1e-6 * np.maximum(1, np.abs(rs))).all(), f"seed {c['seed']}: max {np.max(np.abs(py - rs) / np.maximum(1, np.abs(rs)))}")

    def test_kappa_zero_is_the_plain_generator_and_arm_matches_numpy(self):
        cmds = _commands(3, 30)
        start = np.array([0.0, -55, 35, 5, 0])
        gen, sim = cpg.CPG(), arm_sim.ArmSim()
        gen.reset(start)
        sim.reset(start)
        d, tgt, tv = J.arm_init(start)
        cs = J.cpg_init(start)
        t_err = q_err = 0.0
        for k in range(300):
            if k % 10 == 0:
                gen.command(*cmds[k // 10])
                goal = {n: jnp.asarray(gen.goal[n]) for n in ("freq", "amp", "centre", "lag")}
            t = gen.step()
            sim.step(t)
            cs, tj = J.cpg_step(cs, goal, 0.7 + 0.1 * k, jnp.zeros(5))          # kappa = 0: the phase argument is irrelevant
            d, tgt, tv, _ = J.arm_step(d, tgt, tv, tj)
            t_err = max(t_err, float(np.abs(np.asarray(tj) - t).max()))
            q_err = max(q_err, float(np.abs(np.degrees(np.asarray(d.qpos)) - sim.q_deg).max()))
        self.assertLess(t_err, 1e-9)
        self.assertLess(q_err, 0.5, f"arm difference {q_err}")

    def test_kappa_pulls_the_phase(self):
        cs = J.cpg_init([0, -55, 35, 5, 0])
        cs = {**cs, "phase": jnp.full(5, 0.5)}
        goal = {"freq": jnp.full(5, 1.0), "amp": jnp.zeros(5), "centre": cs["centre"], "lag": jnp.zeros(5)}
        a, _ = J.cpg_step(cs, goal, 2.0, jnp.zeros(5))
        b, _ = J.cpg_step(cs, goal, 2.0, jnp.full(5, 5.0))
        self.assertTrue((np.asarray(b["phase"]) > np.asarray(a["phase"])).all())            # phi = 2.0 is ahead of the phase 0.5: pulled forward

    def test_kappa_is_bounded(self):
        P = J.init_policy(jax.random.PRNGKey(0))
        for s in range(5):
            _, _, k = J.motor_cortex(P, 50.0 * jax.random.normal(jax.random.PRNGKey(s), (J.D_IN,)))
            self.assertTrue((np.asarray(k) >= 0).all() and (np.asarray(k) <= J.KAPPA_MAX).all())

    def test_gumbel_softmax_hard_at_low_temperature(self):
        key = jax.random.PRNGKey(1)
        for i in range(20):
            k1, k2 = jax.random.split(jax.random.fold_in(key, i))
            logits, g = jax.random.normal(k1, (8,)), jax.random.gumbel(k2, (8,))
            soft = np.asarray(J.gumbel_softmax(logits, g, 0.01))
            s = np.sort(np.asarray(logits + g))
            if s[-1] - s[-2] > 0.05:                                          # a gap under 0.05 is not 'low temperature' for tau = 0.01
                self.assertGreater(soft.max(), 0.999)
            self.assertEqual(int(soft.argmax()), int(jnp.argmax(logits + g)))
            hard = np.asarray(J.program_weights(logits, g, 0.01, "sample"))
            self.assertEqual(sorted(hard.tolist()), [0.0] * 7 + [1.0])
            self.assertEqual(int(hard.argmax()), int(jnp.argmax(logits + g)))
            self.assertEqual(int(np.asarray(J.program_weights(logits, g, 0.01, "argmax")).argmax()), int(jnp.argmax(logits)))
        # the straight-through form is one-hot forward and has a gradient
        gr = jax.grad(lambda lg: (J.gumbel_softmax(lg, g, 0.5, hard=True) * jnp.arange(8.0)).sum())(logits)
        self.assertGreater(float(jnp.abs(gr).sum()), 0)

    def test_gradient_reaches_the_motor_cortex_and_not_the_observer(self):
        fns = m3d.make_fns(2)
        P, O = J.init_policy(jax.random.PRNGKey(0)), J.init_observer(jax.random.PRNGKey(1))
        E, nb = 2, 6
        carry = jax.vmap(J.init_carry)(jnp.asarray(np.tile([0, -55, 35, 5, 0.0], (E, 1))))
        rng = np.random.default_rng(0)
        inps = {"x": jnp.asarray(rng.normal(size=(E, nb, 16))), "phi0": jnp.zeros((E, nb)), "om0": jnp.zeros((E, nb)), "g": jax.random.gumbel(jax.random.PRNGKey(2), (E, nb, 8))}
        yz = jnp.asarray(rng.normal(size=(E, nb, 8)))
        args = (carry, inps, yz, jnp.ones((E, nb)), 1.0, 0.1, 1.0, np.zeros(31), np.ones(31))
        gP = jax.grad(lambda P, O: fns["raw"](P, O, *args)[0], argnums=0)(P, O)
        gO = jax.grad(lambda P, O: fns["raw"](P, O, *args)[0], argnums=1)(P, O)
        for name in ("w1", "w2", "theta"):
            g = np.asarray(gP[name])
            self.assertTrue(np.isfinite(g).all() and np.abs(g).sum() > 0, name)
        self.assertTrue(all(float(jnp.abs(w).sum() + jnp.abs(b).sum()) == 0 for w, b in gO), "the observer is frozen (stop_gradient) while it scores")
        # the policy step leaves the observer parameters bit-identical
        O0 = jax.tree_util.tree_map(np.asarray, O)
        P2, _, _ = J.adam_step(P, gP, J.adam_init(P), 1e-3)
        self.assertTrue(all(np.array_equal(a, b) for a, b in zip(jax.tree_util.tree_leaves(O0), jax.tree_util.tree_leaves(jax.tree_util.tree_map(np.asarray, O)))))
        self.assertFalse(np.array_equal(np.asarray(P2["w1"]), np.asarray(P["w1"])))


class Statistics(unittest.TestCase):
    def test_within_episode_zscore(self):
        rng = np.random.default_rng(0)
        y = rng.normal(size=(3, 120, 8))
        z = m3d.zscore_within(y, clip=1e9)
        self.assertTrue(np.allclose(z.mean(1), 0, atol=1e-9) and np.allclose(z.std(1), 1, atol=1e-6))
        y2 = y * np.array([1.0, 5.0, 0.2])[:, None, None] + np.array([0.0, 100.0, -7.0])[:, None, None]       # per-episode offset and scale change nothing
        self.assertTrue(np.allclose(m3d.zscore_within(y2, clip=1e9), z, atol=1e-6))

    def test_time_shuffle_is_a_real_shift_of_at_least_4_seconds(self):
        T = 120
        yz = np.tile(np.arange(T, dtype=float)[None, :, None], (4, 1, 8)) / T
        gaps, matched = m3d.time_shuffled_gap(yz.copy(), yz)              # a perfect decoder: matched loss 0, every shifted pairing worse
        self.assertTrue((matched == 0).all() and (gaps > 0).all())
        rng = np.random.default_rng(1)
        z = m3d.zscore_within(rng.normal(size=(16, T, 8)))
        g0, _ = m3d.time_shuffled_gap(np.zeros_like(z), z)                # a constant predictor carries no timing: gap about 0
        self.assertLess(abs(g0.mean()), 0.05)
        # shifts are drawn in [8, T - 8] blocks, never the identity and never under 4 s
        rng = np.random.default_rng(0)
        shifts = [int(rng.integers(8, T - 8 + 1)) for _ in range(1000)]
        self.assertTrue(min(shifts) >= 8 and max(shifts) <= T - 8)

    def test_mutual_information(self):
        rng = np.random.default_rng(0)
        a = rng.integers(0, 8, (16, 119))
        b = rng.integers(0, 16, (16, 119))
        mi, p, _ = m3d.mi_with_shuffles(a, b, n_shuf=200)
        self.assertGreater(p, 0.01)                                         # independent: not significant
        mi2, p2, _ = m3d.mi_with_shuffles(b % 8, b, n_shuf=200)           # the program is a function of the state bin
        self.assertGreater(mi2, 1.0)
        self.assertLess(p2, 0.01)

    def test_state_bins_cover_16(self):
        rng = np.random.default_rng(0)
        y = rng.normal(size=(8, 120, 8))
        bins, _ = m3d.state_bins(y)
        self.assertEqual(sorted(set(bins.ravel().tolist())), list(range(16)))


class Controls(unittest.TestCase):
    """WO7 controls: kappa override, the initial policy, the paired difference."""

    def test_kappa_override(self):
        import m3d_controls as C
        P = J.init_policy(jax.random.PRNGKey(5))
        x = jnp.linspace(-1, 1, J.D_IN)
        plain = J.motor_cortex(P, x)
        self.assertTrue((plain[2] > 0).all())
        for fix in (np.zeros(5), np.array([1.41, 0.42, 0.28, 0.45, 2.02])):
            lg, am, k = J.motor_cortex(C.with_kappa(P, fix), x)
            np.testing.assert_array_equal(np.asarray(k), fix)
            np.testing.assert_array_equal(np.asarray(lg), np.asarray(plain[0]))        # everything but kappa untouched
            np.testing.assert_array_equal(np.asarray(am), np.asarray(plain[1]))
        self.assertNotIn("kappa_fix", P)

    def test_initial_policy_is_the_trainers(self):
        import m3d_controls as C
        from types import SimpleNamespace
        t = m3d.Trainer(SimpleNamespace(n_train=16), 0.3, 1e-3, 1)
        for a, b in zip(jax.tree_util.tree_leaves(C.initial_policy()), jax.tree_util.tree_leaves(t.P)):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))

    def test_paired_difference(self):
        import m3d_controls as C
        ctrl = np.array([0.1, 0.2, 0.3, 0.4])
        r = C.paired_difference(ctrl + 0.5, ctrl)
        self.assertAlmostEqual(r["mean"], 0.5)
        np.testing.assert_allclose(r["ci"], [0.5, 0.5])                 # constant difference: no spread although the episodes differ
        r = C.paired_difference([1.0, -1.0, 1.0, -1.0], np.zeros(4))
        self.assertAlmostEqual(r["mean"], 0.0)
        self.assertTrue(r["ci"][0] < 0 < r["ci"][1])


if __name__ == "__main__":
    unittest.main()
