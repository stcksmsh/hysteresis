"""Tests for check_b7.py: the pass rules on built numbers, and the model runner on a synthetic song. No real data."""
import unittest

import numpy as np
import torch

import check_b7 as c7
import core
import core_b7


class TestRules(unittest.TestCase):
    def test_tau_rel_top_vs_bottom_quartile(self):
        nblk = 40
        arousal = np.repeat(np.arange(nblk, dtype=float), 200)           # rises with time: the last blocks are the top quartile
        tau = np.ones((4, nblk))
        tau[:, 30:] = 0.5                                                # top quartile (blocks 30..39 start values 29..38) halves tau
        rel = c7.tau_rel(tau, arousal)
        self.assertTrue(np.allclose(rel, -0.5))

    def test_tau_rel_uses_the_arousal_known_at_block_start(self):
        nblk = 8
        a = np.zeros(nblk * 200)
        a[199::200][2] = 5.0                                               # arousal peaks at the end of block 2: block 3 starts high
        tau = np.ones((4, nblk))
        tau[:, 3] = 2.0
        rel = c7.tau_rel(tau, a, frac=0.125)                             # one block per quartile: block 3 on top (block 0 and others tie low)
        self.assertTrue(np.allclose(rel, 1.0))

    def test_c4b_needs_every_layer_one_direction_and_share(self):
        ok = np.full((10, 4), -0.2)
        r = c7.c4b_stats(ok)
        self.assertTrue(r["pass"])
        self.assertEqual(r["direction"], "shorten")
        mixed = ok.copy()
        mixed[:, 3] = 0.2
        self.assertFalse(c7.c4b_stats(mixed)["pass"])
        small = np.full((10, 4), -0.05)
        self.assertFalse(c7.c4b_stats(small)["pass"])
        some = ok.copy()
        some[:4, 0] = 0.3                                                # 6 of 10 songs share the sign: below 0.7
        r = c7.c4b_stats(some)
        self.assertFalse(r["layers"]["L1"]["pass"])
        self.assertTrue(r["layers"]["L2"]["pass"])
        self.assertEqual(c7.c4b_stats(-ok)["direction"], "lengthen")

    def test_c4a_interval(self):
        full = np.zeros(50)
        self.assertTrue(c7.c4a_stats(full, full + 0.1 + 0.01 * np.arange(50) / 50)["pass"])
        self.assertFalse(c7.c4a_stats(full, full - 0.1)["pass"])

    def test_c1_both_conditions(self):
        col = c7.C1Collector()
        for i in range(30):
            col.rec["H"][i], col.rec["N"][i] = 0.6 + 0.01 * (i % 3), 0.3
            col.pointing[i] = (30, 50)
        r = c7.c1_stats(col)
        self.assertTrue(r["pass"])
        self.assertAlmostEqual(r["pointing_share_pooled"], 0.6)
        for i in range(30):
            col.pointing[i] = (20, 50)
        self.assertFalse(c7.c1_stats(col)["pass"])                      # recognition higher but only 40 % point into the first S
        for i in range(30):
            col.pointing[i] = (30, 50)
            col.rec["H"][i] = 0.3
        self.assertFalse(c7.c1_stats(col)["pass"])

    def test_c1_collector_counts_the_first_s_span(self):
        col = c7.C1Collector()
        k = np.arange(600)
        src = np.full(700, -1.0)
        src[460:470] = 3.0                                               # inside the first S (0..16 s)
        src[470:480] = 16.5                                              # just outside
        src[480:490] = 16.0                                              # the end of the span counts
        col("a", "H", {"recognition": np.ones(700), "source_t": src}, 45.9, 61.8)
        hits, n = col.pointing["a"]
        self.assertEqual(n, 159)
        self.assertEqual(hits, 20)

    def test_c2_needs_both_the_rule_and_the_shrink(self):
        rng = np.random.default_rng(0)
        sds = np.ones(40)
        on = 0.5 + 0.05 * rng.standard_normal(40)
        self.assertTrue(c7.c2_stats(on, sds, on - 0.3)["pass"])
        self.assertFalse(c7.c2_stats(on, sds, on + 0.3)["pass"])         # drop grows without retrieval: the mechanism is not the cause
        self.assertFalse(c7.c2_stats(0.1 + 0.01 * rng.standard_normal(40), sds, np.zeros(40))["pass"])    # drop < 0.25 SD

    def test_c3_uses_novelty_z(self):
        rows = [{"cross": [0.1, 0.2], "within": [0.0, 0.0], "cross_novelty": [5.0, 6.0], "within_novelty": [0.5, 0.2]} for _ in range(30)]
        r = c7.c3_stats(rows)
        self.assertTrue(r["novelty"]["pass"])
        self.assertFalse(r["total_surprisal_4_5_rerun"]["pass"])

    def test_c5_mse_margin_is_against_ridge_ar(self):
        rng = np.random.default_rng(1)
        n = 30

        def sc(nll, mse):
            return {"nll": nll + 0.01 * rng.standard_normal((n, 4)), "mse": np.full((n, 4), mse), "n": np.full((n, 4), 100.0)}
        base = {"persistence": sc(np.full((n, 4), 1.0), 0.45), "ar_ridge": sc(np.full((n, 4), 0.5), 0.13), "b2": sc(np.full((n, 4), 0.9), 0.2)}
        self.assertTrue(c7.c5_gate({**base, "b7": sc(np.full((n, 4), 0.1), 0.12)})["pass"])
        r = c7.c5_gate({**base, "b7": sc(np.full((n, 4), 0.1), 0.127)})
        self.assertFalse(r["pass"])
        self.assertAlmostEqual(r["mse_ratio_to_ridge_ar"], 0.127 / 0.13)
        self.assertFalse(c7.c5_gate({**base, "b7": sc(np.full((n, 4), 0.6), 0.1)})["pass"])    # NLL above ridge AR's


class TestRunner(unittest.TestCase):
    def test_bins7_shapes_and_variants(self):
        m = core_b7.Core7().eval()
        x = np.random.default_rng(0).standard_normal((2150, core.N_IN)).astype(np.float32)
        r = c7.bins7(m, x, chunk=1000)
        self.assertEqual(r["mean"][0].shape, (215, core.FEAT))
        self.assertEqual(r["recognition"].shape, (215,))
        self.assertEqual(r["tau"].shape, (4, 11))                        # 10 full blocks and a partial one
        self.assertEqual(r["arousal"].shape, (2150,))
        one = c7.bins7(m, x, chunk=2150)
        for i in range(4):
            self.assertLess(float(np.abs(one["mean"][i] - r["mean"][i]).max()), 1e-5)
        with c7.variant(m, retrieval=False, relay=False, modulation="frozen"):
            self.assertEqual((m.relay_on, m.retrieval_on, m.modulation), (False, False, "frozen"))
        self.assertEqual((m.relay_on, m.retrieval_on, m.modulation), (True, True, "on"))

    def test_retrieval_off_zeroes_the_relay_input_but_keeps_novelty(self):
        m = core_b7.Core7().eval()
        g = torch.Generator().manual_seed(3)
        with torch.no_grad():
            for mod in m.relay:
                mod.weight.copy_(0.05 * torch.randn(mod.weight.shape, generator=g))
        x = np.random.default_rng(2).standard_normal((4000, core.N_IN)).astype(np.float32)
        on = c7.bins7(m, x)
        with c7.variant(m, retrieval=False):
            off = c7.bins7(m, x)
        self.assertTrue(np.array_equal(on["novelty"][:160], off["novelty"][:160]))                # nothing is eligible before 17 s
        self.assertTrue((off["novelty"][220:] < 1.0).any())                                      # still computed once the store is eligible
        self.assertFalse(np.allclose(on["mean"][3][220:], off["mean"][3][220:]))


if __name__ == "__main__":
    unittest.main()
