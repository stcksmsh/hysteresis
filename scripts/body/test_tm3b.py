"""M3b tests (toy world; imports tm3_world, which patches core.N = 16 and core_b7.BLOCK = 50, so run this module on its own).
    cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_tm3b
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import tm3
import tm3_world as W
import tm3b
from test_tm3 import CAL, tiny_bundle

torch.set_num_threads(2)


def noisy_relays(cortex, seed=0):
    g = torch.Generator().manual_seed(seed)
    for m in cortex.prop:
        m.weight.data = 0.05 * torch.randn(m.weight.shape, generator=g)


class Pieces(unittest.TestCase):
    def test_delay_is_a_shift_with_zeros_before(self):
        p = torch.arange(10.0).reshape(1, 10, 1).repeat(2, 1, 3)
        out = tm3b.delay(p, np.array([3, 0]))
        self.assertEqual(out[0, :, 0].tolist(), [0, 0, 0, 0, 1, 2, 3, 4, 5, 6])
        self.assertEqual(out[1, :, 0].tolist(), list(range(10)))

    def test_shifts_in_2_to_8_s_and_fixed_by_seed(self):
        a = tm3b.make_shifts(tm3b.SHIFT_SEED_A, 64)
        self.assertTrue(((a >= 200) & (a <= 800)).all())
        self.assertTrue((a == tm3b.make_shifts(tm3b.SHIFT_SEED_A, 64)).all())
        self.assertFalse((a == tm3b.make_shifts(tm3b.SHIFT_SEED_B, 64)).all())

    def test_nonroll_stats_ignore_a_fast_roll(self):
        vel = np.zeros((2, 500, 5), np.float32)
        vel[..., tm3b.ROLL] = 500.0                              # the roll alone moves fast
        vel[0, :, 1] = 10.0
        vel[1, :, 2] = 20.0
        rms, per, dom = tm3b.nonroll_stats(vel)
        self.assertAlmostEqual(rms, float(np.sqrt((10.0 ** 2 + 20.0 ** 2) / 8)), places=4)    # four joints, two episodes: mean of squares
        self.assertAlmostEqual(per[tm3b.ROLL], 500.0, places=3)                              # still reported, not used
        self.assertEqual(dom, [1, 2])                                                         # never the roll

    def test_d_on_a_synthetic_choice_sequence(self):
        ks = torch.tensor([[0] * 40 + [1] * 30 + [2] * 20 + [3] * 10, [0] * 40 + [1] * 30 + [2] * 20 + [3] * 10])    # shares 0.4 / 0.3 / 0.2 / 0.1
        s = tm3b.selection_stats(ks)
        self.assertEqual(s["program_counts"][:4], [80.0, 60.0, 40.0, 20.0])
        self.assertEqual(s["programs_above_5pct"], 4)
        self.assertTrue(s["d_pass"])
        self.assertAlmostEqual(s["selection_entropy_nats"], -sum(p * np.log(p) for p in (0.4, 0.3, 0.2, 0.1)), places=5)
        self.assertAlmostEqual(s["switches_per_min"], 3 / (100 * 0.5 / 60.0), places=5)
        ks2 = torch.tensor([[0] * 95 + [1] * 3 + [2] * 2 + [3] * 0] * 2)                       # 4 programs would need 3 below 5 %: only one is above
        self.assertFalse(tm3b.selection_stats(ks2)["d_pass"])
        ks3 = torch.tensor([[0] * 30 + [1] * 30 + [2] * 30 + [3] * 4 + [4] * 6])               # a fourth program at 4 % does not count
        s3 = tm3b.selection_stats(ks3)
        self.assertEqual(s3["programs_above_5pct"], 4)
        self.assertFalse(tm3b.selection_stats(torch.tensor([[0] * 30 + [1] * 30 + [2] * 36 + [3] * 4]))["d_pass"])


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.bundle = str(Path(cls.tmp) / "b.pt")
        tiny_bundle(cls.bundle)

    def cortex(self):
        return tm3b.CortexB(W.make_cortex(0))

    def test_identity_at_step_0_shifted_equals_moving(self):
        run = tm3b.RunB(tm3.Config(E=2, seed=3), self.cortex(), self.bundle, CAL)
        for _ in range(3):
            res = run.block()
            self.assertEqual(float(res["d"].abs().max()), 0.0)

    def test_roll_is_absent_from_the_relay_input(self):
        cx = self.cortex()
        noisy_relays(cx)
        f = W.cortex_input(torch.randn(2, 50, 44))
        prop = torch.randn(2, 50, 30)
        a, _ = cx(f, prop, cx.core.init_state(2))
        changed = prop.clone()
        changed[..., tm3b.ROLL_COLS] += 10.0                        # change only the roll's columns
        b, _ = cx(f, changed, cx.core.init_state(2))
        self.assertEqual(float((a[0]["mean"] - b[0]["mean"]).abs().max()), 0.0)
        other = prop.clone()
        other[..., 0] += 10.0                                       # a non-roll column does reach the output
        c, _ = cx(f, other, cx.core.init_state(2))
        self.assertGreater(float((a[0]["mean"] - c[0]["mean"]).abs().max()), 0.0)
        self.assertEqual(sorted(tm3b.ROLL_COLS), [4, 9, 14, 19, 24, 29])

    def test_shifted_row_is_the_same_episodes_proprioception_delayed_by_the_stated_shift(self):
        run = tm3b.RunB(tm3.Config(E=2, seed=4), self.cortex(), self.bundle, CAL)
        rec = []
        for _ in range(int(9.0 / 0.5)):                              # 9 s: past the longest possible shift
            run.block(record=rec)
        prop = torch.cat([r["prop"] for r in rec], 1)
        sh = torch.cat([r["prop_shifted"] for r in rec], 1)
        self.assertTrue(torch.equal(sh, tm3b.delay(prop, run.shifts)))
        e = 0
        s = int(run.shifts[e])
        self.assertTrue(torch.equal(sh[e, s:], prop[e, :prop.shape[1] - s]))

    def test_reward_is_zero_until_the_shifted_row_has_history_then_moves(self):
        cx = self.cortex()
        noisy_relays(cx)
        run = tm3b.RunB(tm3.Config(E=2, seed=5), cx, self.bundle, CAL)
        shortest = int(run.shifts.min())
        ds = [run.block()["d"] for _ in range(int(9.0 / 0.5))]
        early = torch.cat(ds[:shortest // 50], 1)
        self.assertEqual(float(early.abs().max()), 0.0)
        self.assertGreater(float(torch.cat(ds[-4:], 1).abs().max()), 0.0)

    def test_entropy_bonus_enters_the_loss(self):
        def first_grad(ent):
            torch.manual_seed(0)
            run = tm3b.RunB(tm3.Config(E=2, H=20, seed=6, ent=ent), self.cortex(), self.bundle, CAL)
            torch.manual_seed(1)
            roll = tm3.collect(run, 20)
            got = []

            class Stop(Exception):
                pass

            class Opt:
                def zero_grad(self):
                    pass

                def step(self):
                    got.append(run.pol.go[-1].weight.grad.clone())
                    raise Stop

            run.opt = Opt()
            torch.manual_seed(2)
            try:
                tm3.ppo_update(run, roll)
            except Stop:
                pass
            return got[0]
        g0, g0b, g1 = first_grad(0.0), first_grad(0.0), first_grad(1.0)
        self.assertEqual(float((g0 - g0b).abs().max()), 0.0)
        self.assertGreater(float((g0 - g1).abs().max()), 0.0)

    def test_one_iteration_runs_and_updates_the_policy(self):
        run = tm3b.RunB(tm3.Config(E=2, H=20, seed=7), self.cortex(), self.bundle, CAL)
        before = run.pol.theta.detach().clone()
        info, _ = tm3.iteration(run)
        self.assertTrue(np.isfinite(info["relay_loss"]))
        self.assertFalse(torch.equal(before, run.pol.theta.detach()))


if __name__ == "__main__":
    unittest.main()
