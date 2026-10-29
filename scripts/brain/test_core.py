"""Tests for core.py and the lane code in b2.py. Synthetic input only."""
import math
import unittest

import numpy as np
import torch

import b2
import core


def noise(T, seed=0):
    return torch.from_numpy(np.random.default_rng(seed).standard_normal((1, T, core.N_IN)).astype(np.float32))


def run(model, f, chunk=None):
    state, outs = model.init_state(), []
    with torch.no_grad():
        for a in range(0, f.shape[1], chunk or f.shape[1]):
            o, state = model(f[:, a:a + (chunk or f.shape[1])], state)
            outs.append(o)
    return outs


class TestModes(unittest.TestCase):
    def test_init_in_band(self):
        for L, (lo, hi) in zip(core.Core().layers, core.BANDS):
            f = L.freqs_hz()
            self.assertGreaterEqual(float(f.min()), lo * (1 - 1e-5))
            self.assertLessEqual(float(f.max()), hi * (1 + 1e-5))
            self.assertEqual(len(f), core.N)

    def test_init_decay_from_q(self):
        for L in core.Core().layers:
            q = math.pi * L.freqs_hz() * core.DT / torch.exp(L.nu_log.detach())
            self.assertGreaterEqual(float(q.min()), 2 - 1e-3)
            self.assertLessEqual(float(q.max()), 8 + 1e-3)

    def test_clamp_step(self):
        m = core.Core()
        with torch.no_grad():
            for L in m.layers:
                L.theta.mul_(7.0)
                L.theta[0] = 1e-9
        m.clamp_modes()
        for L, (lo, hi) in zip(m.layers, core.BANDS):
            f = L.freqs_hz()
            self.assertGreaterEqual(float(f.min()), lo * (1 - 1e-5))
            self.assertLessEqual(float(f.max()), hi * (1 + 1e-5))
            self.assertLess(float(L.lam_log().real.detach().max()), 0.0)

    def test_param_count(self):
        n = core.Core().n_params()
        self.assertEqual(n, core.Core(phase=False).n_params())
        self.assertTrue(1_000_000 <= n <= 1_500_000, n)


class TestRun(unittest.TestCase):
    def test_tone_raises_l2_more_than_l4(self):
        T = 3000
        t = np.arange(T) / 100.0
        tone = np.zeros((1, T, core.N_IN), np.float32)
        tone[..., :core.FEAT] = np.cos(2 * np.pi * 6.0 * t)[None, :, None]
        m = core.Core()
        base = run(m, torch.zeros(1, T, core.N_IN))[0]
        hot = run(m, torch.from_numpy(tone))[0]
        gain = [float((h["h"][:, 1000:].abs() ** 2).mean() / (b["h"][:, 1000:].abs() ** 2).mean()) for h, b in zip(hot, base)]
        self.assertGreater(gain[1], gain[3])

    def test_state_carry(self):
        f = noise(12000)
        m = core.Core()
        whole, chunks = run(m, f)[0], run(m, f, chunk=6000)
        for i in range(4):
            for k in ("h", "mean", "logvar", "err"):
                a, b = whole[i][k], torch.cat([c[i][k] for c in chunks], 1)
                torch.testing.assert_close(a, b, atol=2e-4, rtol=2e-4)

    def test_odd_chunks_carry(self):
        f = noise(2500, seed=3)
        m = core.Core()
        whole = run(m, f)[0]
        parts = run(m, f, chunk=777)
        torch.testing.assert_close(whole[3]["h"], torch.cat([c[3]["h"] for c in parts], 1), atol=2e-4, rtol=2e-4)

    def test_determinism(self):
        f = noise(3000, seed=1)
        a, b = run(core.Core(), f)[0], run(core.Core(), f)[0]
        for i in range(4):
            self.assertTrue(torch.equal(a[i]["h"], b[i]["h"]))
            self.assertTrue(torch.equal(a[i]["mean"], b[i]["mean"]))
        self.assertFalse(torch.equal(a[0]["h"], run(core.Core(seed=1), f)[0][0]["h"]))

    def test_no_phase_ignores_phase_columns(self):
        f = noise(1000)
        g = f.clone()
        g[..., core.FEAT:] = 5.0
        m = core.Core(phase=False)
        self.assertTrue(torch.equal(run(m, f)[0][3]["h"], run(m, g)[0][3]["h"]))
        self.assertFalse(torch.equal(run(core.Core(), f)[0][3]["h"], run(core.Core(), g)[0][3]["h"]))

    def test_err_zero_until_window_and_causal(self):
        f = noise(1200, seed=2)
        g = f.clone()
        g[:, 700:, :core.FEAT] += 3.0
        m = core.Core()
        a, b = run(m, f)[0], run(m, g)[0]
        self.assertEqual(float(a[0]["err"][:, :19].abs().max()), 0.0)
        self.assertGreater(float(a[0]["err"][:, 19:].abs().max()), 0.0)
        for i in range(4):
            self.assertTrue(torch.equal(a[i]["h"][:, :700], b[i]["h"][:, :700]))
            self.assertTrue(torch.equal(a[i]["err"][:, :700], b[i]["err"][:, :700]))

    def test_coupling_delay(self):
        # a change in layer-1 error at frame t reaches layer 2 at t + 1 and not before
        f = noise(600, seed=4)
        g = f.clone()
        g[:, 300:, :core.FEAT] += 4.0
        m = core.Core()
        a, b = run(m, f)[0], run(m, g)[0]
        # layer 1 input changes at 300, so layer 1 h differs from 300; layer 2 sees the change in its input at 300 too
        self.assertTrue(torch.equal(a[0]["h"][:, :300], b[0]["h"][:, :300]))
        self.assertFalse(torch.equal(a[0]["h"][:, 300], b[0]["h"][:, 300]))


class TestLanes(unittest.TestCase):
    def test_shapes_rates_and_values(self):
        T = 6500                                   # 65 s
        f = noise(T, seed=5)
        m = core.Core()
        r = b2.run_core(m, f[0].numpy())
        nb = T // 10
        self.assertEqual(r["nb"], nb)
        self.assertTrue(r["finite"])
        for i in range(4):
            self.assertEqual(r["states"][i].shape, (nb, 512))
            self.assertEqual(r["power"][i].shape, (nb,))
        rng = np.random.default_rng(0)
        readouts = [{"mu": np.zeros(512), "sd": np.ones(512), "ymu": np.zeros(44), "Wm": np.zeros((512, 44)),
                     "zmu": np.zeros(44), "Wv": np.zeros((512, 44))} for _ in range(4)]
        ln = b2.lanes(r, f[0, :, :44].numpy(), readouts)
        for group in ln.values():
            for v in group.values():
                self.assertEqual(v.shape, (nb,))
        # zero readout: mean 0, logvar 0 -> NLL = 0.5 (y^2 + log 2 pi) averaged over features, exactly
        y, ok = b2.targets(f[0, :, :44].numpy(), 10)
        expect = (0.5 * (y ** 2 + math.log(2 * math.pi))).mean(1)
        np.testing.assert_allclose(ln["surprisal"]["L1"][2:], expect[:nb - 2], rtol=1e-5)
        self.assertTrue(np.isnan(ln["surprisal"]["L1"][:2]).all())
        self.assertTrue(np.isnan(ln["surprisal"]["L4"][:160]).all())
        self.assertTrue(np.isfinite(ln["surprisal"]["L4"][160:]).all() if nb > 160 else True)
        np.testing.assert_allclose(ln["neuromod"]["tension"], 1.0)   # logvar 0 -> variance 1

    def test_one_pole_and_slope(self):
        x = np.r_[np.zeros(50), np.ones(50)]
        y = b2.one_pole(x, 1.0, 8.0)
        self.assertEqual(y[49], 0.0)
        self.assertAlmostEqual(y[50], 1 - math.exp(-0.1))             # rise tau 1 s
        z = b2.one_pole(1 - x, 1.0, 8.0)
        self.assertAlmostEqual(float(z[50]), 1 - (1 - math.exp(-0.1 / 8)))  # decay tau 8 s
        ramp = 2.0 * np.arange(500) * 0.1                              # 2 per s
        np.testing.assert_allclose(b2.slope(ramp)[299:], 2.0, rtol=1e-6)
        self.assertEqual(b2.slope(ramp)[0], 0.0)

    def test_grid_phase(self):
        ph = b2.grid_phase([1.0, 2.0, 3.0], 400)
        self.assertEqual(ph.shape, (400, 2))
        np.testing.assert_allclose(ph[100], [1.0, 0.0], atol=1e-6)       # beat at 1.0 s: phase 0
        np.testing.assert_allclose(ph[150], [-1.0, 0.0], atol=1e-6)      # half way
        np.testing.assert_allclose(ph[0], [1.0, 0.0], atol=1e-6)         # extrapolated one beat back


if __name__ == "__main__":
    unittest.main()
