"""cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_s1_toy"""
import unittest

import jax
import jax.numpy as jnp
import numpy as np

import s1_toy as S


class Pieces(unittest.TestCase):
    def test_infonce_correct_pair_scores_highest(self):
        rng = np.random.default_rng(0)
        a = rng.standard_normal((8, 16)); a /= np.linalg.norm(a, axis=1, keepdims=True)
        good = S.info_nce(jnp.asarray(a), jnp.asarray(a))
        bad = S.info_nce(jnp.asarray(a), jnp.asarray(np.roll(a, 1, 0)))
        self.assertLess(float(good), 0.01)
        self.assertGreater(float(bad), float(good) + 5)
        s = a @ a.T
        self.assertTrue((s.argmax(1) == np.arange(8)).all())

    def test_observer_lipschitz_at_most_gain(self):
        p = S.init_params(0)["obs"]
        p = {k: (v * 5 if k.startswith("W") else v) for k, v in p.items()}       # make it clearly expansive unconstrained
        rng = np.random.default_rng(1)
        x = jnp.asarray(rng.standard_normal((400, 2 * S.K_WIN)))
        y = jnp.asarray(rng.standard_normal((400, 2 * S.K_WIN)))
        ratio = lambda lip: float(jnp.max(jnp.linalg.norm(S.observer(p, x, lip) - S.observer(p, y, lip), axis=1) / jnp.linalg.norm(x - y, axis=1)))
        self.assertGreater(ratio(False), S.G_OUT)
        self.assertLessEqual(ratio(True), S.G_OUT + 1e-4)
        # tightest empirical slope via local gradient norms
        J = jax.vmap(jax.jacobian(lambda v: S.observer(p, v[None], True)[0]))(x[:50])
        self.assertLessEqual(float(max(np.linalg.norm(np.asarray(j), 2) for j in J)), S.G_OUT + 1e-4)

    def test_logdet_rises_when_embeddings_spread(self):
        rng = np.random.default_rng(2)
        base = rng.dirichlet(np.ones(64), 1)
        near = base + 0.001 * rng.standard_normal((8, 64))
        far = rng.dirichlet(np.ones(64) * 0.2, 8)
        self.assertGreater(float(S.logdet_K(jnp.asarray(far))), float(S.logdet_K(jnp.asarray(near))) + 1.0)

    def test_posture_embedding_rows_sum_to_one(self):
        h = jnp.asarray(np.random.default_rng(0).uniform(-.5, .5, (3, 100, 2)))
        np.testing.assert_allclose(np.asarray(S.posture_embedding(h)).sum(1), 1, atol=1e-5)

    def test_hinges_zero_inside_envelope(self):
        t = np.arange(S.T) * S.DT
        q = np.stack([0.3 * np.sin(2 * np.pi * 0.25 * t), 0.2 * np.sin(2 * np.pi * 0.25 * t)], 1)[None]
        hand = S.fk(jnp.asarray(q))
        g = np.asarray(S.hinges(jnp.asarray(q), hand))
        np.testing.assert_allclose(g, 0, atol=1e-9)

    def test_hinges_fire_outside(self):
        t = np.arange(S.T) * S.DT
        q = np.stack([1.95 * np.sign(np.sin(2 * np.pi * 2 * t)), 2.3 * np.sign(np.sin(2 * np.pi * 2 * t))], 1)[None]
        g = np.asarray(S.hinges(jnp.asarray(q), S.fk(jnp.asarray(q))))[0]
        self.assertTrue((g > 0).all(), g)

    def test_causal_z_is_causal(self):
        x = np.random.default_rng(0).standard_normal((2, S.T, 8)).astype(np.float32)
        y = x.copy(); y[:, 400:] += 5
        a, b = S.causal_z(x, np.full(8, 0.1)), S.causal_z(y, np.full(8, 0.1))
        np.testing.assert_allclose(a[:, :400], b[:, :400], atol=1e-6)

    def test_arm_i_erases_slow_between_song_difference(self):
        d = S.build_data()
        ti, tii = d["tgt_i_train"], d["tgt_ii_train"]
        sl = lambda t: t[:, S.T_FROM:, 4:6].mean(1).std(0).mean()          # between-song sd of the per-song mean of z1, z2
        print("surviving between-song sd of slow dims, arm i / arm ii target:", sl(ti), sl(tii))
        self.assertLess(sl(ti), 0.6 * sl(tii))

    def test_arm_is_one_when_songs_equal_policy_zero(self):
        # a policy that ignores its input gives identical hands: between-song JS is 0 (and below the half-song control when moving)
        hand = np.tile(np.random.default_rng(0).uniform(-.4, .4, (1, S.T, 2)), (4, 1, 1))
        js, _ = S.between_song_js(hand)
        self.assertAlmostEqual(js, 0.0)
        self.assertAlmostEqual(S.js_div(np.eye(4)[0], np.eye(4)[1]), 1.0)

    def test_matched_batch_includes_anchor_and_is_close(self):
        bpm = np.linspace(90, 130, 64); logg = np.zeros(64)
        idx = S.nearest_batch(bpm, logg, 10)
        self.assertIn(10, idx)
        self.assertLess(np.ptp(bpm[idx]), 8)

    def test_logreg_matches_scipy_minimiser(self):
        from scipy.optimize import minimize
        rng = np.random.default_rng(3)
        X = np.vstack([rng.normal(0, 1, (30, 4)), rng.normal(1.0, 1, (30, 4))]); y = np.r_[np.zeros(30), np.ones(30)]
        f = S.logreg(X, y, C=1.0)
        mu, sd = X.mean(0), X.std(0) + 1e-8
        Xs = (X - mu) / sd
        obj = lambda wb: np.sum(np.logaddexp(0, Xs @ wb[:4] + wb[4]) - y * (Xs @ wb[:4] + wb[4])) + 0.5 * wb[:4] @ wb[:4]
        r = minimize(obj, np.zeros(5), method="Nelder-Mead", options={"xatol": 1e-9, "fatol": 1e-12, "maxiter": 20000, "maxfev": 20000})
        r2 = minimize(obj, np.zeros(5), method="BFGS", options={"gtol": 1e-9})     # numerical gradient: independent of my analytic one
        ref = r2.x if r2.fun < r.fun else r.x
        ours = f(X)
        np.testing.assert_allclose(ours, Xs @ ref[:4] + ref[4], atol=2e-3)

    def test_mmd_zero_for_same_and_positive_for_different(self):
        a = np.random.default_rng(0).normal(0, .1, (3, S.T, 2)); a[2] += 0.4
        m, mh = S.mmd_between(a)
        self.assertGreater(m, 5 * mh)
        same = np.tile(a[:1], (3, 1, 1))
        self.assertAlmostEqual(S.mmd_between(same)[0], 0.0, places=9)

    def test_soft_costs_normalised_to_one_at_untrained(self):
        d = S.build_data(); p = S.init_params(0)
        nrm = S.soft_norm(p, d["train"])
        f = jnp.asarray(d["train"]["feats"][:16]); q = S.rollout(p["pol"], f); h = S.fk(q)
        st = np.asarray(S.soft_terms(q, h, jnp.mean(S.hinges(q, h), 0)) / nrm)
        self.assertTrue(np.all(st <= 1 + 1e-5)); self.assertAlmostEqual(st[0], 1.0, places=4); self.assertAlmostEqual(st[4], 1.0, places=4)

    def test_arm0_has_no_hinge_multipliers_in_loss(self):
        d = S.build_data(); p = S.init_params(0)
        f = jnp.asarray(d["train"]["feats"][:4]); t = jnp.asarray(d["tgt_i_train"][:4])
        nrm = S.soft_norm(p, d["train"])
        l_a, _ = S.loss_fn(p, jnp.ones(3), f, t, jnp.zeros(4, int), 0, 0.0, nrm)
        l_b, _ = S.loss_fn(p, 100 * jnp.ones(3), f, t, jnp.zeros(4, int), 0, 0.0, nrm)
        self.assertAlmostEqual(float(l_a), float(l_b), places=6)       # mu has no effect in arm 0

    def test_occupied_cells_wide_loop_beats_small_repeated_loop(self):
        t = np.arange(S.T) * S.DT
        small = np.stack([0.05 * np.cos(2 * np.pi * 2 * t), 0.05 * np.sin(2 * np.pi * 2 * t)], 1)[None]
        wide = np.stack([0.5 * np.cos(2 * np.pi * 0.1 * t), 0.5 * np.sin(2 * np.pi * 0.1 * t)], 1)[None]
        (cs, es), (cw, ew) = S.occupied_cells(small), S.occupied_cells(wide)
        self.assertGreater(cw, 3 * cs); self.assertGreater(ew, es)
        # equal durations: halves of the same song are compared only with halves
        self.assertLessEqual(S.occupied_cells(wide[:, :S.T // 2])[0], cw)

    def test_logreg_separates(self):
        rng = np.random.default_rng(0)
        X = np.vstack([rng.normal(0, 1, (20, 5)), rng.normal(3, 1, (20, 5))]); y = np.r_[np.zeros(20), np.ones(20)]
        f = S.logreg(X, y)
        self.assertGreater(np.mean((f(X) > 0) == y), 0.95)

    def test_policy_rollout_in_limits_and_differentiable(self):
        p = S.init_params(0)
        f = jnp.asarray(S.make_corpus([1, 2])["feats"])
        q = S.rollout(p["pol"], f)
        self.assertTrue((np.abs(np.asarray(q)) <= S.QMAX + 1e-6).all())
        g = jax.grad(lambda pp: S.fk(S.rollout(pp, f)).sum())(p["pol"])
        self.assertTrue(all(np.isfinite(np.asarray(v)).all() for v in g.values()))


class Smoke(unittest.TestCase):
    def test_one_epoch_each_arm(self):
        d = S.build_data()
        for arm in S.ARMS:
            ad = S.arm_data(d, arm)
            params, hist = S.train(arm, 0, 1, 0.5, ad, log=lambda s: None)
            self.assertTrue(np.isfinite(hist[0]["loss"]))
            if arm == "iv":
                self.assertNotEqual(hist[0]["logdet"], 0.0)
            if arm in ("0", "i"):
                self.assertEqual(hist[0]["nce"], 0.0)
            r = S.evaluate(params, arm, ad, "val")
            self.assertTrue(0 <= r["js_between"] <= 1)


if __name__ == "__main__":
    unittest.main()
