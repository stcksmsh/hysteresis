"""Tests for core_b7.py (BRAIN_SPEC 7.1, 7.3 T3). Synthetic input only. Weights are set non-zero where a test needs the new paths live."""
import math
import unittest

import numpy as np
import torch

import core
import core_b7


FLOOR = 1e-4     # float32 noise of the random-init deep layers (large activations); the real-song check of the smoke run holds 1e-5


def noise(T, seed=0, B=1, scale=1.0):
    return torch.from_numpy(scale * np.random.default_rng(seed).standard_normal((B, T, core.N_IN)).astype(np.float32))


def live(seed=1, relay=0.05):
    """A Core7 whose relay, skip and modulation weights are non-zero, and whose store is read from 8 s on."""
    m = core_b7.Core7().eval()
    g = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for mod in (*m.relay, *m.skip):
            mod.weight.copy_(relay * torch.randn(mod.weight.shape, generator=g))
        m.w_g.copy_(torch.tensor([0.3, -0.2, 0.1, 0.4]))
        m.w_tau.copy_(torch.tensor([0.2, 0.1, -0.1, 0.3]))
    return m


def run(m, f, chunk=None, B=1):
    state, outs = m.init_state(B), []
    with torch.no_grad():
        for a in range(0, f.shape[1], chunk or f.shape[1]):
            o, state = m(f[:, a:a + (chunk or f.shape[1])], state)
            outs.append(o)
    return outs, state


def cat(outs, i, k):
    return torch.cat([o[i][k] for o in outs], 1)


class TestIdentity(unittest.TestCase):
    def test_zero_new_weights_equal_b3(self):
        x = noise(1200, scale=0.5)
        b3, b7 = core.Core().eval(), core_b7.Core7().eval()
        b7.load_state_dict(b3.state_dict(), strict=False)
        o3, _ = run(b3, x)
        o7, _ = run(b7, x)
        for i in range(4):
            for k in ("mean", "logvar", "err"):
                self.assertLess(float((o3[0][i][k] - o7[0][i][k]).abs().max()), FLOOR, (i, k))
        # B3's own float32 noise floor (the same model, other chunking) is of the same size
        o3b, _ = run(b3, x, chunk=450)
        floor = max(float((cat(o3b, i, "mean") - o3[0][i]["mean"]).abs().max()) for i in range(4))
        print("B3 chunking floor", floor)
        self.assertLess(floor, FLOOR)

    def test_identity_in_double_is_exact(self):
        """float64: the difference is rounding only (1e-13), so B7 at step 0 is B3 in the maths, not just near it."""
        x = noise(1200, scale=0.5).double()
        b3, b7 = core.Core().eval().double(), core_b7.Core7().eval().double()
        b7.load_state_dict(b3.state_dict(), strict=False)
        with torch.no_grad():
            o3, _ = b3(x, core_b7.to_double(b3.init_state()))
            o7, _ = b7(x, core_b7.to_double(b7.init_state()))
        for i in range(4):
            for k in ("mean", "logvar", "err"):
                self.assertLess(float((o3[i][k] - o7[i][k]).abs().max()), 1e-9, (i, k))

    def test_relay_off_with_live_weights_equals_b3_heads_only_through_modulation(self):
        """relay_on False and modulation frozen: B7 is B3 again, whatever the other weights are."""
        x = noise(800, scale=0.5)
        b3, m = core.Core().eval(), live()
        m.load_state_dict({**b3.state_dict(), **{k: v for k, v in m.state_dict().items() if k not in b3.state_dict()}})
        m.relay_on, m.modulation = False, "frozen"
        o3, _ = run(b3, x)
        o7, _ = run(m, x)
        for i in range(4):
            self.assertLess(float((o3[0][i]["mean"] - o7[0][i]["mean"]).abs().max()), FLOOR)


class TestCausality(unittest.TestCase):
    def test_no_output_depends_on_later_input(self):
        m = live()
        x = noise(2000, seed=3)
        x2 = x.clone()
        x2[:, 1525:] = noise(475, seed=9)                    # change everything from frame 1525 on (inside block 30)
        o, _ = run(m, x)
        o2, _ = run(m, x2)
        for i in range(4):
            for k in ("mean", "logvar", "err", "x"):
                self.assertTrue(torch.equal(o[0][i][k][:, :1525], o2[0][i][k][:, :1525]), (i, k))
        for k in ("recognition", "novelty", "source_t"):
            self.assertTrue(torch.equal(o[0][0]["hippo"][k][:, :1525], o2[0][0]["hippo"][k][:, :1525]), k)
        self.assertTrue(torch.equal(o[0][0]["arousal"][:, :1525], o2[0][0]["arousal"][:, :1525]))
        self.assertFalse(torch.equal(o[0][3]["x"][:, 1800:], o2[0][3]["x"][:, 1800:]))       # and the change is felt afterwards


class TestStore(unittest.TestCase):
    def test_chunks_equal_one_run(self):
        m = live()
        x = noise(2000, seed=5)
        one, s1 = run(m, x)
        parts, s2 = run(m, x, chunk=500)
        for i in range(4):
            for k in ("mean", "logvar"):
                self.assertLess(float((cat(one, i, k) - cat(parts, i, k)).abs().max()), 1e-5)
        self.assertTrue(torch.equal(one[0][0]["hippo"]["source_t"], torch.cat([o[0]["hippo"]["source_t"] for o in parts], 1)))
        self.assertTrue(bool((one[0][0]["hippo"]["source_t"][:, 1000:] >= 0).all()))
        self.assertEqual(s1["sk"].shape, s2["sk"].shape)

    def test_reset_empties_that_row_only(self):
        m = live()
        xa, xb = noise(1500, seed=6, B=2), noise(1500, seed=7, B=2)
        with torch.no_grad():
            _, st = m(xa, m.init_state(2))
            st = m.reset_rows(st, torch.tensor([True, False]))
            o, _ = m(xb, m.detach_state(st))
            fresh, _ = run(m, xb[:1])
            cont, _ = m(xb, m.detach_state(m.reset_rows(m(xa, m.init_state(2))[1], torch.tensor([False, False]))))
        self.assertLess(float((o[3]["mean"][0] - fresh[0][3]["mean"][0]).abs().max()), 1e-5)
        self.assertTrue(torch.equal(o[0]["hippo"]["source_t"][0, :800], -torch.ones(800)))           # nothing eligible in the first 8 s of the new song
        self.assertLess(float((o[3]["mean"][1] - cont[3]["mean"][1]).abs().max()), 1e-6)         # row 1 carried on untouched
        self.assertTrue(bool((o[0]["hippo"]["source_t"][1, 800:] >= 0).any()))

    def test_empty_store_values(self):
        m = live()
        o, _ = run(m, noise(700, seed=2))
        h = o[0][0]["hippo"]
        self.assertTrue(torch.equal(h["recognition"][:, :800], torch.zeros(1, 700)))
        self.assertTrue(torch.equal(h["novelty"], torch.ones(1, 700)))
        self.assertTrue(torch.equal(h["source_t"], -torch.ones(1, 700)))

    def test_8_second_exclusion_and_recall_time(self):
        m = core_b7.Core7().eval()
        D = 4 * core.N
        with torch.no_grad():
            m.query_proj.weight.zero_()
            m.query_proj.weight[:3, :3] = torch.eye(3)               # query = normalised first three coordinates of qs
            m.log_tau.fill_(math.log(0.01))
        e = torch.eye(core_b7.KEY_DIM)
        J = 41
        keys = e[2].repeat(J, 1)
        keys[25] = e[0]                                              # age 15 blocks: identical to the query, must stay invisible
        keys[24] = 0.8 * e[0] + 0.6 * e[1]                           # age 16: eligible
        qs = torch.zeros(1, D)
        qs[0, 0] = 1.0
        ms = torch.arange(J, dtype=torch.float32)[None, :, None].expand(1, J, core.FEAT).contiguous()
        st = {"sk": keys[None], "sm": ms, "sj": torch.arange(J)[None], "sv": torch.ones(1, J, dtype=torch.bool), "qs": qs}
        ret, rec, src, _ = m._read(st, [], [], [], torch.tensor([40]))
        self.assertAlmostEqual(float(rec), 0.8, places=6)
        self.assertEqual(float(src), 12.0)                           # entry 24 -> t = 12 s
        self.assertAlmostEqual(float(ret[0, 0]), (24 + 25 + 26 + 27) / 4, places=4)    # its value: mean of blocks 24..27 (2 s)
        ret, rec, src, _ = m._read(st, [], [], [], torch.tensor([41]))
        self.assertAlmostEqual(float(rec), 1.0, places=6)
        self.assertEqual(float(src), 12.5)                           # one block later entry 25 is 8 s old
        ret, rec, src, _ = m._read({**st, "sv": torch.zeros(1, J, dtype=torch.bool)}, [], [], [], torch.tensor([41]))
        self.assertEqual((float(rec), float(src), float(ret.abs().sum())), (0.0, -1.0, 0.0))

    def test_chunk_start_must_be_on_a_block_edge(self):
        m = core_b7.Core7().eval()
        _, st = run(m, noise(70))
        with self.assertRaises(ValueError):
            m(noise(50), st)


class TestGradients(unittest.TestCase):
    def test_earlier_chunks_detached(self):
        m = live().train()
        x = noise(2800, seed=11)
        o1, st = m(x[:, :1400], m.init_state(1))
        loss1 = sum((o["mean"] ** 2).mean() for o in o1)
        st = m.detach_state(st)
        self.assertFalse(st["sk"].requires_grad)
        o2, _ = m(x[:, 1400:], st)
        loss2 = sum((o["mean"] ** 2).mean() for o in o2) + o2[0]["hippo"]["recognition"].mean()
        loss2.backward()                                             # would free chunk 1's buffers if chunk 2 hung on its graph
        g2 = m.key_proj.weight.grad.clone()
        loss1.backward()                                             # still possible
        self.assertGreater(float(g2.abs().sum()), 0.0)

    def test_keys_of_the_current_chunk_get_gradient(self):
        m = live().train()
        o, _ = m(noise(1400, seed=12), m.init_state(1))
        (o[0]["hippo"]["recognition"].sum() + sum(oo["mean"].sum() for oo in o)).backward()
        self.assertGreater(float(m.key_proj.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(m.query_proj.weight.grad.abs().sum()), 0.0)
        self.assertGreater(float(m.relay[0].weight.grad.abs().sum()), 0.0)

    def test_arousal_stops_gradient(self):
        m = live().train()
        o, _ = m(noise(300, seed=13), m.init_state(1))
        self.assertFalse(o[0]["arousal"].requires_grad)
        self.assertFalse(o[0]["dev"].requires_grad)


class TestModulationT3(unittest.TestCase):
    def test_zero_weights_equal_no_modulation(self):
        m = live()
        with torch.no_grad():
            m.w_g.zero_()
            m.w_tau.zero_()
        x = noise(1500, seed=14)
        a, _ = run(m, x)
        m.modulation = "frozen"
        b, _ = run(m, x)
        for i in range(4):
            self.assertTrue(torch.equal(cat(a, i, "mean"), cat(b, i, "mean")))
            self.assertTrue(torch.equal(cat(a, i, "x"), cat(b, i, "x")))

    def test_designed_change_of_gain_and_modulus_and_fixed_frequency(self):
        """h0 only (x = 0, so the drive is 0): |h_t| = |h0| exp(-nu e (t+1)) and arg h_t = arg h0 + theta (t+1), for the exponent e."""
        L = core.Layer(torch.Generator().manual_seed(1), core.BANDS[2], True)
        h0 = torch.complex(torch.randn(1, core.N), torch.randn(1, core.N))
        x = torch.zeros(1, 50, core.D)
        e = torch.tensor([1.7])
        with torch.no_grad():
            _, h, _, _, _ = L(x, h0, torch.zeros(1, 50, core.FEAT), None, None, torch.ones(1), e)
        t = torch.arange(1, 51)[:, None].float()
        nu, th = torch.exp(L.nu_log), L.theta
        want = h0 * torch.exp(torch.complex(-nu * 1.7 * t, th * t))
        self.assertLess(float((h[0] - want).abs().max()), 1e-5)
        with torch.no_grad():
            _, h1, _, _, _ = L(x, h0, torch.zeros(1, 50, core.FEAT), None, None, torch.ones(1), torch.ones(1))
        want1 = h0 * torch.exp(torch.complex(-nu * t, th * t))
        self.assertLess(float((h1[0] - want1).abs().max()), 1e-5)

    def test_gain_scales_the_drive_linearly(self):
        L = core.Layer(torch.Generator().manual_seed(2), core.BANDS[0], False)
        x = torch.randn(1, 50, core.D)
        h0 = torch.zeros(1, core.N, dtype=torch.complex64)
        with torch.no_grad():
            _, h1, _, _, _ = L(x, h0, None, None, None, torch.ones(1), torch.ones(1))
            _, h2, _, _, _ = L(x, h0, None, None, None, torch.tensor([1.25]), torch.ones(1))
        self.assertLess(float((h2 - 1.25 * h1).abs().max()), 1e-5)

    def test_arousal_step_changes_the_blocks_exactly(self):
        m = core_b7.Core7().eval()
        with torch.no_grad():
            m.w_g.copy_(torch.tensor([0.1, 0.2, 0.3, 0.4]))
            m.w_tau.copy_(torch.tensor([0.5, 0.25, -0.5, 0.0]))
        st = m.init_state(2)
        st["a"] = torch.tensor([1.0, 0.0])                              # row 0: arousal 1 above its mean, row 1: no step
        th0 = [L.theta.detach().clone() for L in m.layers]
        with torch.no_grad():
            o, _ = m(noise(50, B=2), st)
        for i, w in enumerate((0.5, 0.25, -0.5, 0.0)):
            self.assertAlmostEqual(float(o[i]["expo"][0, 0]), 1 + w, places=6)
            self.assertAlmostEqual(float(o[i]["expo"][1, 0]), 1.0, places=6)
            base = float(torch.median(core.DT / torch.exp(m.layers[i].nu_log.detach())))
            self.assertAlmostEqual(float(o[i]["tau_eff"][0, 0]), base / (1 + w), places=5)
            self.assertAlmostEqual(float(o[i]["tau_eff"][1, 0]), base, places=5)
            self.assertTrue(torch.equal(m.layers[i].theta.detach(), th0[i]))
        self.assertAlmostEqual(float(o[0]["dev"][0, 0]), 1.0, places=6)

    def test_exponent_clamp_keeps_modulus_below_one(self):
        m = core_b7.Core7().eval()
        with torch.no_grad():
            m.w_tau.fill_(-5.0)
        st = m.init_state(1)
        st["a"] = torch.tensor([1.0])
        with torch.no_grad():
            o, _ = m(noise(50), st)
        self.assertAlmostEqual(float(o[0]["expo"][0, 0]), core_b7.E_MIN, places=6)

    def test_arousal_rises_with_surprise_and_starts_from_zero(self):
        m = core_b7.Core7().eval()
        x = noise(600, seed=15, scale=0.1)
        x[:, 300:, :core.FEAT] += 4 * torch.randn(1, 300, core.FEAT)      # abrupt change
        with torch.no_grad():
            o, st = m(x, m.init_state(1))
        a = o[0]["arousal"][0]
        self.assertEqual(float(a[0]), 0.0)
        self.assertGreater(float(a[550]), float(a[290]))
        self.assertAlmostEqual(float(st["a"][0]), float(a[-1]), places=6)


if __name__ == "__main__":
    unittest.main()
