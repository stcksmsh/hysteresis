"""M3c tests (toy world; imports tm3_world, which patches core.N = 16 and core_b7.BLOCK = 50, so run this module on its own).
    cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_tm3c
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import bdesc
import cpg
import m3_cortex as M
import tm3
import tm3_world as W
import tm3c
from test_tm3 import CAL, tiny_bundle

torch.set_num_threads(2)


def fresh_run(bundle, E=2, seed=3, **kw):
    cx = M.Cortex(W.make_cortex(0))
    cfg = tm3.Config(E=E, seed=seed, **kw)
    return tm3c.RunC(cfg, cx, bundle, CAL)


class Pieces(unittest.TestCase):
    def test_kappa_zero_is_exactly_the_old_generator(self):
        old, new = cpg.CPG(), tm3c.CPGK()
        goal = (np.array([1.0, 0.8, 1.5, 2.0, 0.5]), np.array([30.0, 20, 25, 15, 40]), np.array([0.0, -50, 35, 5, 0]), np.array([0.0, 0.1, 0.2, 0.3, 0.4]))
        old.command(*goal)
        new.command(*goal)
        for i in range(500):
            a = old.step()
            b = new.step(0.37 * i, np.zeros(5))
            self.assertTrue(np.array_equal(a, b))
        coupled = tm3c.CPGK()
        coupled.command(*goal)
        c = [coupled.step(0.37 * i, np.full(5, 3.0)) for i in range(500)]
        self.assertFalse(np.array_equal(np.array(c)[-1], b))

    def test_kappa_is_bounded_and_zero_for_negative_outputs(self):
        k = tm3c.kappa_of(torch.tensor([-5.0, 0.0, 0.5, 100.0]))
        self.assertEqual(k[0].item(), 0.0)
        self.assertEqual(k[1].item(), 0.0)
        self.assertLessEqual(float(k.max()), tm3c.KAPPA_MAX + 1e-6)
        self.assertAlmostEqual(k[3].item(), tm3c.KAPPA_MAX, places=5)

    def test_coupling_pulls_the_phase_toward_the_brain_phase(self):
        g = tm3c.CPGK()
        g.command(np.full(5, 1.0), np.full(5, 10.0), np.array([0.0, -50, 35, 5, 0]), np.zeros(5))
        for _ in range(300):
            g.step(2.0, np.full(5, tm3c.KAPPA_MAX))
        d = np.angle(np.exp(1j * (g.phase - 2.0)))
        self.assertTrue((np.abs(d[1:]) < 2.5).all())            # not asserting lock for a 1 Hz drifting oscillator, only that the pull acts (see next test)
        a, b = tm3c.CPGK(), tm3c.CPGK()
        for g2 in (a, b):
            g2.command(np.full(5, 1.0), np.full(5, 10.0), np.array([0.0, -50, 35, 5, 0]), np.zeros(5))
        for _ in range(5):
            a.step(2.0, np.zeros(5))
            b.step(2.0, np.full(5, 3.0))
        self.assertFalse(np.array_equal(a.phase, b.phase))

    def test_shuffled_control_pairs_i_with_j_not_i(self):
        for n in (2, 3, 8, 16):
            p = tm3c.shuffle_partner(n)
            self.assertTrue((p != np.arange(n)).all())
            self.assertEqual(sorted(p.tolist()), list(range(n)))
            self.assertTrue((p == tm3c.shuffle_partner(n)).all())
        # the observer predicts each episode's target from its own movement; the control scores episode i's target against episode j's movement
        obs = lambda x: x                                       # identity "observer": prediction = descriptor input
        xd = torch.stack([torch.full((5, 3), float(i)) for i in range(4)])
        y = xd.clone()
        partner = np.array([1, 0, 3, 2])
        matched, shuffled = tm3c.decode_losses(obs, xd, y, partner)
        self.assertTrue(np.allclose(matched, 0.0))
        self.assertTrue(np.allclose(shuffled, 1.0))              # episode i's target i against movement of partner j: (i - j)^2 = 1

    def test_c_on_a_synthetic_choice_sequence(self):
        ks = torch.tensor([[0] * 40 + [1] * 30 + [2] * 20 + [3] * 10] * 2)
        s = tm3c.selection_stats(ks)
        self.assertEqual(s["program_counts"][:4], [80.0, 60.0, 40.0, 20.0])
        self.assertTrue(s["c_pass"])
        self.assertAlmostEqual(s["switches_per_min"], 3 / (100 * 0.5 / 60.0), places=5)
        self.assertFalse(tm3c.selection_stats(torch.tensor([[0] * 30 + [1] * 30 + [2] * 36 + [3] * 4]))["c_pass"])
        self.assertFalse(tm3c.selection_stats(torch.tensor([[0] * 95 + [1] * 3 + [2] * 2]))["c_pass"])

    def test_nonroll_stats_ignore_a_fast_roll(self):
        vel = np.zeros((2, 500, 5), np.float32)
        vel[..., tm3c.ROLL] = 500.0
        vel[0, :, 1] = 10.0
        vel[1, :, 2] = 20.0
        rms, per, dom = tm3c.nonroll_stats(vel)
        self.assertAlmostEqual(rms, float(np.sqrt((10.0 ** 2 + 20.0 ** 2) / 8)), places=4)
        self.assertEqual(dom, [1, 2])


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.bundle = str(Path(cls.tmp) / "b.pt")
        tiny_bundle(cls.bundle)

    def test_observer_input_is_the_movement_only(self):
        run = fresh_run(self.bundle)
        run.stats = {"dmu": np.zeros(31), "dsd": np.ones(31), "ymu": np.zeros(8), "ysd": np.ones(8)}
        rec = []
        for _ in range(6):
            run.block(record=rec)
        r = rec[-1]
        self.assertTrue(r["ready"])
        want = np.stack([bdesc.descriptors(bdesc.window_frames(run.pos_hist[e])) for e in range(2)])
        self.assertTrue(np.allclose(r["desc"], want))            # descriptors = a function of the last 2 s of joint positions
        # and the observer module takes only a (.., 31) tensor
        self.assertEqual(run.obs.net[0].in_features, bdesc.N_DESC)

    def test_roll_motion_does_not_reach_the_observer(self):
        pos = np.random.default_rng(0).uniform(-30, 30, (201, 5))
        pos2 = pos.copy()
        pos2[:, tm3c.ROLL] = 500 * np.sin(np.arange(201))
        a, b = bdesc.descriptors(bdesc.window_frames(pos)), bdesc.descriptors(bdesc.window_frames(pos2))
        self.assertTrue(np.array_equal(a, b))

    def test_brain_state_is_the_song_alone(self):
        # two runs with the same seed give the same targets whatever the policy does (the cortex never sees the arm)
        a, b = fresh_run(self.bundle, seed=9), fresh_run(self.bundle, seed=9)
        b.pol.theta.data += 2.0
        ya, yb = [], []
        for _ in range(3):
            ya.append(a.block()["y"]); yb.append(b.block()["y"])
        self.assertTrue(torch.allclose(torch.cat(ya), torch.cat(yb), atol=1e-5))

    def test_kappa_zero_run_equals_uncoupled_arm(self):
        # a run whose coupling output is 0 gives the same arm trajectory as the same run with the coupling arguments left out (the old generator)
        a, b = fresh_run(self.bundle, seed=11), fresh_run(self.bundle, seed=11)
        for r in (a, b):
            r.pol.mc[-1].bias.data[20:] = -50.0                   # kappa = 0 exactly
        plain = type(b.arms).step
        b.arms.step = lambda n=10, phi=None, omega=None, kappa=None: plain(b.arms, n)
        for _ in range(2):
            ra, rb = a.block(deterministic=True), b.block(deterministic=True)
            self.assertTrue(np.array_equal(ra["obs"], rb["obs"]))
        self.assertEqual(float(ra["kappa"].max()), 0.0)

    def test_iteration_runs_and_observer_trains(self):
        run = fresh_run(self.bundle, seed=5, H=60)
        for _ in range(2):
            run.block()
        raw = np.concatenate([p[0] for p in run.pending]) if run.pending else np.random.default_rng(0).standard_normal((20, 31))
        rawy = np.concatenate([p[1] for p in run.pending]) if run.pending else np.random.default_rng(1).standard_normal((20, 8))
        tm3c.set_stats(run, raw, rawy)
        before = run.obs.net[0].weight.detach().clone()
        before_pol = run.pol.theta.detach().clone()
        info = tm3c.run_iteration(run)
        self.assertTrue(np.isfinite(info["obs_loss"]))
        self.assertFalse(torch.equal(before, run.obs.net[0].weight.detach()))
        self.assertFalse(torch.equal(before_pol, run.pol.theta.detach()))


if __name__ == "__main__":
    unittest.main()
