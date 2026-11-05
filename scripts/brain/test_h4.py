import unittest

import numpy as np
import torch

import core
import core_b7
import hippo_h3
import hippo_h4 as h4
import toy_b7


def synth(T=900, hz=10, seed=0, window=100):
    g = torch.Generator().manual_seed(seed)
    err_c = torch.randn(1, T, 44, generator=g)
    mu_c = torch.randn(1, T, 44, generator=g)
    rep = torch.randn(1, T, 44, generator=g)
    has = torch.ones(1, T, dtype=torch.bool)
    return err_c, mu_c, rep, has, hz, window


class TestArbitration(unittest.TestCase):
    def test_equal_errors_give_one_half(self):
        err_c, mu_c, _, has, hz, win = synth()
        w, e_c, e_h = h4.arbitrate_layer(err_c, mu_c, mu_c.clone(), has, hz, win)           # replay == cortex mean: both systems make the same error
        t = slice(2 * hz - 1 + 5, None)
        self.assertTrue(torch.allclose(w[:, t], torch.full_like(w[:, t], 0.5), atol=1e-6))
        self.assertTrue(torch.allclose(e_c, e_h, atol=1e-6) or bool((e_c - e_h)[:, t].abs().max() < 1e-6))

    def test_hippocampus_error_to_zero_gives_w_one(self):
        err_c, mu_c, _, has, hz, win = synth()
        rep = mu_c + err_c                                                                    # err_h = err_c + mu_c - rep = 0 on the shifted frames
        rep_shift = torch.zeros_like(rep)
        rep_shift[:, :-(2 * hz - 1)] = mu_c[:, :-(2 * hz - 1)] + err_c[:, 2 * hz - 1:]
        w, e_c, e_h = h4.arbitrate_layer(err_c, mu_c, rep_shift, has, hz, win)
        t = slice(2 * hz - 1 + 5, None)
        self.assertGreater(float(w[:, t].min()), 1 - 1e-4)
        self.assertLess(float(e_h[:, t].max()), 2e-6)

    def test_no_source_no_weight(self):
        err_c, mu_c, rep, has, hz, win = synth()
        w, _, _ = h4.arbitrate_layer(err_c, mu_c, rep, torch.zeros_like(has), hz, win)
        self.assertEqual(float(w.abs().max()), 0.0)
        has2 = has.clone()
        has2[:, :400] = False                                                                  # the window only ever sees sourceless predictions until frame ~400 + 2h
        w2, _, _ = h4.arbitrate_layer(err_c, mu_c, rep, has2, hz, win)
        self.assertEqual(float(w2[:, :400].abs().max()), 0.0)
        self.assertGreater(float(w2[:, 600:].min()), 0.0)

    def test_causal(self):
        """Nothing after frame t0 (errors, means, replay, source flags) changes w at or before t0."""
        err_c, mu_c, rep, has, hz, win = synth(T=1200)
        w, e_c, e_h = h4.arbitrate_layer(err_c, mu_c, rep, has, hz, win)
        t0 = 700
        e2, m2, r2, h2 = err_c.clone(), mu_c.clone(), rep.clone(), has.clone()
        e2[:, t0 + 1:] += 5.0
        m2[:, t0 + 1:] *= -3.0
        r2[:, t0 + 1:] = 0.0
        h2[:, t0 + 1:] = ~h2[:, t0 + 1:]
        w2, c2, hh2 = h4.arbitrate_layer(e2, m2, r2, h2, hz, win)
        self.assertTrue(torch.equal(w[:, :t0 + 1], w2[:, :t0 + 1]))
        self.assertTrue(torch.equal(e_c[:, :t0 + 1], c2[:, :t0 + 1]))
        self.assertTrue(torch.equal(e_h[:, :t0 + 1], hh2[:, :t0 + 1]))
        self.assertFalse(torch.equal(w[:, t0 + 1:], w2[:, t0 + 1:]))

    def test_window_is_the_last_second(self):
        q = torch.arange(300, dtype=torch.float32)[None]
        m, n = h4.running_mean(q, torch.ones(1, 300, dtype=torch.bool), 100)
        self.assertAlmostEqual(float(m[0, 250]), float(q[0, 151:251].mean()), places=3)
        self.assertEqual(float(n[0, 250]), 100.0)
        self.assertAlmostEqual(float(m[0, 10]), float(q[0, :11].mean()), places=4)


class TestModel(unittest.TestCase):
    def setUp(self):
        self.ctx = toy_b7.small()
        self.ctx.__enter__()
        torch.manual_seed(0)
        self.m = h4.Core7H4(seed=0, phase=False).freeze_all()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_nothing_is_trained(self):
        self.assertFalse(any(p.requires_grad for p in self.m.parameters()))
        x, _ = toy_b7.t1_sequence(np.random.default_rng(1), "C")
        out, _ = self.m(torch.from_numpy(x)[None][:, :6000], self.m.init_state(1))
        for o in out:
            for k in ("mean", "logvar", "err", "w"):
                self.assertFalse(o[k].requires_grad, k)
        self.assertEqual({n for n, _ in self.m.named_parameters()}, {n for n, _ in core_b7.Core7(seed=0, phase=False).named_parameters()})   # no new parameter

    def test_off_switch_recovers_the_cortex_exactly(self):
        x, _ = toy_b7.t1_sequence(np.random.default_rng(2), "A")
        x = torch.from_numpy(x)[None][:, :6500]
        with torch.no_grad():
            self.m.arbitrate = False
            out, _ = self.m(x, self.m.init_state(1))
        for o in out:
            self.assertEqual(float(o["w"].abs().max()), 0.0)
            self.assertTrue(torch.equal(o["mean"], o["mean_c"]))
            self.assertTrue(torch.equal(o["err"], o["err_c"]))

    def test_w_is_causal_in_the_model(self):
        """Changing the features after frame t0 leaves w up to t0 as it was."""
        x, _ = toy_b7.t1_sequence(np.random.default_rng(3), "C")
        x = torch.from_numpy(x)[None][:, :7000]
        x2 = x.clone()
        t0 = 5000
        x2[:, t0 + 1:, :core.FEAT] += 3.0
        with torch.no_grad():
            o1, _ = self.m(x, self.m.init_state(1))
            o2, _ = self.m(x2, self.m.init_state(1))
        for i in range(4):
            self.assertTrue(torch.equal(o1[i]["w"][:, :t0 + 1], o2[i]["w"][:, :t0 + 1]), i)

    def test_storage_one_shot_and_eligibility(self):
        x = torch.from_numpy(toy_b7.pad46(toy_b7.passage(np.random.default_rng(5), 4000, "C")))[None]
        with torch.no_grad():
            out, st = self.m(x, self.m.init_state(1))
            kr = st["kr"].clone()
            for p in self.m.parameters():
                p.add_(0.1)
            _, st2 = core_b7.Core7.forward(self.m, torch.from_numpy(toy_b7.pad46(toy_b7.passage(np.random.default_rng(6), 400, "C")))[None], core_b7.Core7.detach_state(st))
        self.assertEqual(kr.shape[1], 4000 // core_b7.TICK)
        self.assertTrue(torch.equal(st2["kr"][:, :kr.shape[1]], kr))
        src = out[0]["hippo"]["source_t"][0].numpy() * 100
        n = np.arange(len(src))
        self.assertTrue(((src < 0) | (src <= n - core_b7.MIN_AGE)).all())

    def test_blend_formula_is_h3s(self):
        x, (s1, s2) = toy_b7.t1_sequence(np.random.default_rng(7), "C")
        with torch.no_grad():
            out, _ = self.m(torch.from_numpy(x)[None], self.m.init_state(1))
        o, t = out[0], s2 + 600
        w = o["w"][0, t]
        rep = o["replay_true"][0, t, 0] if "replay_true" in o else None
        mu = (1 - w) * o["mean_c"][0, t] + w * rep
        self.assertTrue(torch.allclose(o["mean"][0, t], mu, atol=1e-6))
        var = (1 - w) * torch.exp(o["logvar_c"][0, t]) + w * hippo_h3.VAR_H + w * (1 - w) * (o["mean_c"][0, t] - rep) ** 2
        self.assertTrue(torch.allclose(torch.exp(o["logvar"][0, t]), var, rtol=1e-4))


if __name__ == "__main__":
    unittest.main()
