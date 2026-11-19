import unittest

import numpy as np
import torch

import core
import core_b7
import hippo_h2
import toy_b7


def run(model, x):
    with torch.no_grad():
        return model(x, model.init_state(x.shape[0]))


class TestH2(unittest.TestCase):
    def setUp(self):
        self.ctx = toy_b7.small()
        self.ctx.__enter__()
        torch.manual_seed(0)
        self.model = hippo_h2.Core7H2(seed=0, phase=False)

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def test_projection_fixed_no_gradient(self):
        m = self.model
        self.assertFalse(m.dg_proj.requires_grad)
        self.assertNotIn("dg_proj", [n for n, _ in m.named_parameters()])
        x = torch.from_numpy(toy_b7.pad46(toy_b7.passage(np.random.default_rng(0), 800, "C")))[None]
        before = m.dg_proj.clone()
        out, _ = m(x, m.init_state(1))
        sum(o["mean"].sum() for o in out).backward()
        self.assertTrue(torch.equal(before, m.dg_proj))
        for p in (m.key_proj.weight, m.query_proj.weight, m.log_tau):
            self.assertIsNone(p.grad)
        self.assertAlmostEqual(float(m.log_tau.exp()), hippo_h2.TAU_H2, places=6)

    def test_code_is_sparse_and_unit(self):
        c = self.model._code(torch.randn(5, core.FEAT + 4 * core.N, requires_grad=True))
        self.assertEqual(c.shape, (5, hippo_h2.DG_DIM))
        self.assertTrue(((c != 0).sum(-1) <= hippo_h2.K_SPARSE).all())
        self.assertTrue(torch.allclose(c.norm(dim=-1), torch.ones(5), atol=1e-5))
        self.assertFalse(c.requires_grad)

    def test_storage_one_shot_and_age(self):
        m = self.model
        rng = np.random.default_rng(1)
        x = torch.from_numpy(toy_b7.pad46(toy_b7.passage(rng, 4000, "C")))[None]
        out, st = m(x, m.init_state(1))
        self.assertEqual(st["kr"].shape[1], 4000 // core_b7.TICK)
        self.assertFalse(st["kr"].requires_grad)
        kr0 = st["kr"].clone()
        for p in m.parameters():                                   # change every weight: stored entries must not move
            p.data.add_(0.1 * torch.randn_like(p))
        x2 = torch.from_numpy(toy_b7.pad46(toy_b7.passage(rng, 400, "C")))[None]
        _, st2 = m(x2, core_b7.Core7.detach_state(st))
        self.assertTrue(torch.equal(st2["kr"][:, :kr0.shape[1]], kr0))
        # eligibility: a read at block start n0 may only point at entries with 50 j <= n0 - 1700
        src = out[0]["hippo"]["source_t"][0].numpy() * 100
        n = np.arange(len(src))
        self.assertTrue(((src < 0) | (src <= n - core_b7.MIN_AGE)).all())

    def test_novelty_lane_every_half_second(self):
        m = self.model
        m.novelty_lane = True
        x = torch.from_numpy(toy_b7.pad46(toy_b7.passage(np.random.default_rng(2), 3000, "C")))[None]
        out, _ = run(m, x)
        t = out[0]["novelty_lane"]["t"][0].numpy()
        self.assertTrue((np.diff(t) == core_b7.TICK).all())
        self.assertEqual(len(t), 3000 // core_b7.TICK)

    def test_exact_repeat_is_found(self):
        m = self.model
        rng = np.random.default_rng(3)
        x, (s1, s2) = toy_b7.t1_sequence(rng, "C")
        out, _ = run(m, torch.from_numpy(x)[None])
        src = out[0]["hippo"]["source_t"][0].numpy()
        hits = [s1 <= src[b] * 100 <= s1 + toy_b7.T1_S for b in range(s2 + 200, s2 + toy_b7.T1_S, 200)]
        self.assertGreaterEqual(np.mean(hits), 0.5)


if __name__ == "__main__":
    unittest.main()
