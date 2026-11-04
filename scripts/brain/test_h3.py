import unittest

import numpy as np
import torch

import core
import core_b7
import hippo_h3
import toy_b7
import train


def seq(design="C", T=4000, seed=0):
    return torch.from_numpy(toy_b7.pad46(toy_b7.passage(np.random.default_rng(seed), T, design)))[None]


class TestH3(unittest.TestCase):
    def setUp(self):
        self.ctx = toy_b7.small()
        self.ctx.__enter__()
        torch.manual_seed(0)
        self.m = hippo_h3.Core7H3(seed=0, phase=False).freeze_all_but_blend()

    def tearDown(self):
        self.ctx.__exit__(None, None, None)

    def loss(self, out, x):
        xp = torch.cat([x, torch.zeros(1, train.LOOK, core.N_IN)], 1)
        sums, _, _, counts = train.chunk_terms(out, xp, torch.full((1,), x.shape[1]), chunk=x.shape[1], beta=train.BETA)
        return sum(s / max(float(c), 1.0) for s, c in zip(sums, counts))

    def test_gradient_reaches_only_a_and_b(self):
        x, _ = toy_b7.t1_sequence(np.random.default_rng(1), "C")
        x = torch.from_numpy(x)[None][:, :6000]
        out, _ = self.m(x, self.m.init_state(1))
        self.loss(out, x).backward()
        self.assertEqual({n for n, p in self.m.named_parameters() if p.requires_grad}, set(hippo_h3.TRAINED))
        for n, p in self.m.named_parameters():
            if n in hippo_h3.TRAINED:
                self.assertIsNotNone(p.grad, n)
            else:
                self.assertIsNone(p.grad, n)
        self.assertFalse(self.m.dg_proj.requires_grad)
        self.assertTrue(float(self.m.blend_a.grad.abs().sum() + self.m.blend_b.grad.abs().sum()) > 0)

    def test_w_zero_recovers_the_cortex(self):
        x, _ = toy_b7.t1_sequence(np.random.default_rng(2), "C")
        x = torch.from_numpy(x)[None][:, :6000]
        with torch.no_grad():
            out, _ = self.m(x, self.m.init_state(1))
            self.m.blend_b.fill_(1e3)
            self.m.blend_a.fill_(1.0)
            out0, _ = self.m(x, self.m.init_state(1))
        for i in range(4):
            self.assertEqual(float(out0[i]["w"].abs().max()), 0.0)
            self.assertTrue(torch.equal(out0[i]["mean"], out0[i]["mean_c"]))
            self.assertTrue(torch.equal(out0[i]["err"], out0[i]["err_c"]))
            self.assertTrue(torch.allclose(out0[i]["logvar"], out0[i]["logvar_c"].clamp(core.LOGVAR_MIN, core.LOGVAR_MAX), atol=1e-5))
            self.assertTrue(torch.equal(out[i]["mean_c"], out0[i]["mean_c"]))          # the cortex does not depend on a and b

    def test_w_one_gives_the_replay_and_blend_variance(self):
        x, (s1, s2) = toy_b7.t1_sequence(np.random.default_rng(3), "C")
        x = torch.from_numpy(x)[None]
        with torch.no_grad():
            self.m.blend_b.fill_(-1e3)
            self.m.blend_a.fill_(1.0)
            out, _ = self.m(x, self.m.init_state(1))
        t = s2 + 400                                                    # inside the repeat: a source exists
        has = float(out[0]["w"][0, t])
        self.assertEqual(has, 1.0)
        rep = out[0]["replay_true"][0, t, 0]
        self.assertTrue(torch.equal(out[0]["mean"][0, t], rep))
        self.assertTrue(torch.allclose(torch.exp(out[0]["logvar"][0, t]), torch.full((44,), hippo_h3.VAR_H), atol=1e-6))
        self.assertEqual(float(out[0]["w"][0, 10]), 0.0)                # nothing eligible before 17 s: w is 0 whatever a and b are

    def test_err_is_the_error_of_the_blend(self):
        x, _ = toy_b7.t1_sequence(np.random.default_rng(4), "A")
        x = torch.from_numpy(x)[None]
        with torch.no_grad():
            out, _ = self.m(x, self.m.init_state(1))
        z = x[0, :, :core.FEAT].double()
        cs = torch.cat([torch.zeros(1, core.FEAT, dtype=torch.float64), z.cumsum(0)])
        for i, h in enumerate(core.HORIZONS[:3]):
            for t in (2 * h - 1, 2 * h + 700, 6000):
                win = ((cs[t + 1] - cs[t + 1 - h]) / h).float()
                want = win - out[i]["mean"][0, t - 2 * h + 1]
                self.assertTrue(torch.allclose(out[i]["err"][0, t], want, atol=2e-4), (i, t))
            self.assertEqual(float(out[i]["err"][0, :2 * h - 1].abs().max()), 0.0)

    def test_storage_one_shot_and_eligibility(self):
        x = seq("C", 4000, 5)
        with torch.no_grad():
            out, st = self.m(x, self.m.init_state(1))
        kr = st["kr"].clone()
        self.assertFalse(kr.requires_grad)
        self.assertEqual(kr.shape[1], 4000 // core_b7.TICK)
        with torch.no_grad():
            for p in self.m.parameters():
                p.add_(0.1)
            _, st2 = core_b7.Core7.forward(self.m, seq("C", 400, 6), core_b7.Core7.detach_state(st))
        self.assertTrue(torch.equal(st2["kr"][:, :kr.shape[1]], kr))     # every weight changed, the stored entries did not
        src = out[0]["hippo"]["source_t"][0].numpy() * 100
        n = np.arange(len(src))
        self.assertTrue(((src < 0) | (src <= n - core_b7.MIN_AGE)).all())

    def test_cortex_is_not_changed_by_the_hippocampus_switch(self):
        """The cortex path equals a plain Core7 with the same weights and the hippocampus off (retrieval_on False: the relay sees no replay)."""
        x = seq("B", 2000, 7)
        base = core_b7.Core7(seed=0, phase=False, hippocampus=False)
        sd = {k: v for k, v in base.state_dict().items() if k != "hippo_flag"}
        self.m.load_state_dict(sd, strict=False)
        with torch.no_grad():
            o1, _ = base(x, base.init_state(1))
            o2, _ = self.m(x, self.m.init_state(1))
        for i in range(4):
            self.assertTrue(torch.allclose(o1[i]["mean"], o2[i]["mean_c"], atol=1e-5))


if __name__ == "__main__":
    unittest.main()
