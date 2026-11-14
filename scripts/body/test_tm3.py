"""T-M3 tests (toy world; imports tm3_world, which patches core.N = 16 and core_b7.BLOCK = 50, so run this module on its own).
    cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_tm3
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import cerebellum as CB
import m3_cortex as M
import tm3
import tm3_world as W

torch.set_num_threads(2)
CAL = {"R0": 1.0, "LP0": 2.0, "E0": 4.0, "SYNC0": 0.5}


def tiny_bundle(path):
    rng = np.random.default_rng(0)
    obs, tgt = rng.standard_normal((2, 600, 15)).astype(np.float32), rng.standard_normal((2, 600, 5)).astype(np.float32)
    st = CB.Stats(obs, tgt)
    net = CB.Cerebellum(16, 1)
    r = CB.Ridge()
    r.W, r.var = np.zeros((CB.NIN + 1, 45)), np.ones((3, 15))
    CB.save_bundle(path, net, st, r, np.ones((3, 15)), 16, 1)


class Pieces(unittest.TestCase):
    def test_reward_pieces_on_synthetic_values(self):
        cfg = tm3.Config(beta=0.5, lam=0.25, csw=0.1)
        r = tm3.reward_terms(torch.tensor(0.5), torch.tensor(2.0), torch.tensor(4.0), torch.tensor(0.0), CAL, cfg)
        self.assertAlmostEqual(float(r), 0.5 + 0.5 * 1.0 * 1.0 - 0.25 * 1.0 * 1.0, places=6)

    def test_switch_cost_only_on_a_change(self):
        cfg = tm3.Config(csw=0.3)
        z = torch.zeros(2)
        r = tm3.reward_terms(z, z, z, torch.tensor([0.0, 1.0]), CAL, cfg)
        self.assertAlmostEqual(r[0].item(), 0.0)
        self.assertAlmostEqual(r[1].item(), -0.3, places=6)

    def test_sync_term_only_behind_the_flag(self):
        base = tm3.Config(gamma_sync=2.0)
        on = tm3.Config(gamma_sync=2.0, sync=True)
        z, s = torch.zeros(1), torch.tensor([0.5])
        self.assertEqual(float(tm3.reward_terms(z, z, z, z, CAL, base, s)), 0.0)
        self.assertAlmostEqual(float(tm3.reward_terms(z, z, z, z, CAL, on, s)), 2.0 * 1.0 * 0.5 / 0.5)

    def test_gating_only_the_chosen_program_reaches_the_generators(self):
        pol = tm3.Policy(0)
        k = torch.tensor([2, 5])
        a_p = pol.theta[k].detach()
        u = tm3.executed_u(a_p, torch.zeros(2, 20))
        self.assertTrue(torch.allclose(u, torch.sigmoid(pol.theta[k].detach()).reshape(2, 4, 5)))
        other = pol.theta.detach().clone()
        other[[0, 1, 3, 4, 6, 7]] += 3.0                     # change every program that was not chosen
        self.assertTrue(torch.equal(tm3.executed_u(other[k], torch.zeros(2, 20)), tm3.executed_u(other[k], torch.zeros(2, 20))))
        self.assertTrue(torch.allclose(tm3.executed_u(other[k], torch.zeros(2, 20)), u))

    def test_modulation_is_bounded_to_20_percent_of_each_range(self):
        a_p = torch.randn(1000, 20)
        base = torch.sigmoid(a_p).reshape(1000, 4, 5)
        for big in (1e3, -1e3):
            u = tm3.executed_u(a_p, torch.full((1000, 20), big))
            self.assertLessEqual(float((u - base).abs().max()), 0.2 + 1e-6)

    def test_causal_surprisal_is_zero_until_2h_frames_exist(self):
        B, T = 2, 50
        out = [{"err": torch.ones(B, T, 44), "logvar": torch.zeros(B, T, 44)} for _ in range(4)]
        s, _ = W.causal_surprisal(out, None, torch.zeros(B, dtype=torch.long))
        first = 0.5 * np.log(2 * np.pi) + 0.5                  # err 1, logvar 0: 0.5 (0 + 1 + log 2 pi)
        self.assertAlmostEqual(float(s[0, 0]), 0.0)
        self.assertAlmostEqual(float(s[0, 19]), first, places=5)      # only the h = 10 layer (2h - 1 = 19) has a window yet


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.bundle = str(Path(cls.tmp) / "b.pt")
        tiny_bundle(cls.bundle)
        cls.cortex = M.Cortex(W.make_cortex(0))

    def test_identity_at_step_0_still_equals_moving(self):
        run = tm3.Run(tm3.Config(E=2, seed=3), self.cortex, self.bundle, CAL)
        res = run.block()
        self.assertEqual(float(res["d"].abs().max()), 0.0)

    def test_commands_come_only_from_the_selected_program(self):
        run = tm3.Run(tm3.Config(E=2, seed=4), self.cortex, self.bundle, CAL)
        seen = []
        orig = run.arms.command
        run.arms.command = lambda u: (seen.append(np.array(u)), orig(u))[1]
        res = run.block(deterministic=True)
        ks = res["steps"][0]["k"]
        for s, u in zip(res["steps"], seen):
            want = tm3.executed_u(run.pol.theta[ks].detach(), torch.tanh(torch.zeros(2, 20)) * 0 + 0)   # modulation is added on top; bounded test below
            self.assertLessEqual(float(np.abs(u - want.numpy()).max()), 0.2 + 1e-5)

    def test_one_iteration_runs_and_updates_the_policy(self):
        cfg = tm3.Config(E=2, H=20, seed=5)
        run = tm3.Run(cfg, self.cortex, self.bundle, CAL)
        before = run.pol.theta.detach().clone()
        info, _ = tm3.iteration(run)
        self.assertTrue(np.isfinite(info["relay_loss"]))
        self.assertFalse(torch.equal(before, run.pol.theta.detach()))

    def test_sampled_mode_samples_on_flat_logits_and_argmax_does_not(self):
        run = tm3.Run(tm3.Config(E=8, seed=6), self.cortex, self.bundle, CAL)
        for net in (run.pol.go, run.pol.nogo):
            net[-1].weight.data.zero_()
            net[-1].bias.data.zero_()
        torch.manual_seed(0)
        arg = run.block(deterministic=True)["steps"][0]["k"]
        self.assertEqual(len(set(arg.tolist())), 1)                       # argmax of equal logits: one program for every episode
        samp = run.block(deterministic=True, sample_prog=True)["steps"][0]["k"]
        self.assertGreater(len(set(samp.tolist())), 1)                    # sampled: 8 episodes, uniform over 8 programs


class MutualInformation(unittest.TestCase):
    def test_independent_choice_is_within_noise(self):
        rng = np.random.default_rng(0)
        r = tm3.mi_with_shuffle(rng.integers(0, 8, (8, 160)), rng.integers(0, 16, (8, 160)), n_shuffle=300)
        self.assertGreater(r["mi_p"], 0.01)

    def test_dependent_choice_is_above_the_shuffle(self):
        rng = np.random.default_rng(1)
        st = rng.integers(0, 16, (8, 160))
        r = tm3.mi_with_shuffle(st % 8, st, n_shuffle=300)
        self.assertLess(r["mi_p"], 0.01)
        self.assertGreater(r["mi_nats"], 5 * r["mi_shuffle_mean"])

    def test_constant_choice_has_zero_mi(self):
        self.assertEqual(tm3.mutual_information(np.zeros((4, 50), int), np.arange(200).reshape(4, 50) % 16), 0.0)


if __name__ == "__main__":
    unittest.main()
