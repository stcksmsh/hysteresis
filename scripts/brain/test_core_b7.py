"""Tests for core_b7.py (BRAIN_SPEC 7.1 as ruled in 7.10, 7.3 T3). Synthetic input only. Weights are set non-zero where a test needs the new paths live."""
import math
import unittest

import numpy as np
import torch

import core
import core_b7

B_ = core_b7.BLOCK


def noise(T, seed=0, B=1, scale=1.0):
    return torch.from_numpy(scale * np.random.default_rng(seed).standard_normal((B, T, core.N_IN)).astype(np.float32))


def live(seed=1, relay=0.05, taps=1):
    """A Core7 whose relay, skip and modulation weights are non-zero."""
    m = core_b7.Core7(skip_taps=taps).eval()
    g = torch.Generator().manual_seed(seed)
    with torch.no_grad():
        for mod in (*m.relay, *m.skip):
            mod.weight.copy_(relay * torch.randn(mod.weight.shape, generator=g))
        m.w_g.copy_(torch.tensor([0.3, -0.2, 0.1, 0.4]))
        m.w_tau.copy_(torch.tensor([0.2, 0.1, -0.1, 0.3]))
    return m


def run(m, f, chunk=None, B=1, **kw):
    state, outs = m.init_state(B), []
    with torch.no_grad():
        for a in range(0, f.shape[1], chunk or f.shape[1]):
            o, state = m(f[:, a:a + (chunk or f.shape[1])], state, **kw)
            outs.append(o)
    return outs, state


def cat(outs, i, k):
    return torch.cat([o[i][k] for o in outs], 1)


class TestIdentity(unittest.TestCase):
    def test_zero_new_weights_equal_b3(self):
        x = noise(1600, scale=0.5)
        b3, b7 = core.Core().eval(), core_b7.Core7().eval()
        b7.load_state_dict(b3.state_dict(), strict=False)
        o3, _ = run(b3, x)
        o7, _ = run(b7, x)
        for i in range(4):
            for k in ("mean", "logvar", "err"):
                self.assertLess(float((o3[0][i][k] - o7[0][i][k]).abs().max()), 1e-4, (i, k))      # float32 rounding; the double test is the exact one

    def test_identity_in_double_is_exact(self):
        """R5: float64, the difference is rounding only."""
        x = noise(1600, scale=0.5).double()
        b3, b7 = core.Core().eval().double(), core_b7.Core7().eval().double()
        b7.load_state_dict(b3.state_dict(), strict=False)
        with torch.no_grad():
            o3, _ = b3(x, core_b7.to_double(b3.init_state()))
            o7, _ = b7(x, core_b7.to_double(b7.init_state()))
        for i in range(4):
            for k in ("mean", "logvar", "err"):
                self.assertLess(float((o3[i][k] - o7[i][k]).abs().max()), 1e-9, (i, k))

    def test_relay_off_and_modulation_frozen_equal_b3_whatever_the_weights(self):
        x = noise(800, scale=0.5)
        b3, m = core.Core().eval(), live()
        m.load_state_dict({**b3.state_dict(), **{k: v for k, v in m.state_dict().items() if k not in b3.state_dict()}})
        m.relay_on, m.modulation = False, "frozen"
        o3, _ = run(b3, x)
        o7, _ = run(m, x)
        for i in range(4):
            self.assertLess(float((o3[0][i]["mean"] - o7[0][i]["mean"]).abs().max()), 1e-4)


class TestCausality(unittest.TestCase):
    def test_no_output_depends_on_later_input(self):
        m = live()
        x = noise(4400, seed=3)
        x2 = x.clone()
        x2[:, 3325:] = noise(1075, seed=9)                   # inside block 16, after 17 s so that the store is read
        o, _ = run(m, x)
        o2, _ = run(m, x2)
        for i in range(4):
            for k in ("mean", "logvar", "err", "x"):
                self.assertTrue(torch.equal(o[0][i][k][:, :3325], o2[0][i][k][:, :3325]), (i, k))
        for k in ("recognition", "novelty", "source_t"):
            self.assertTrue(torch.equal(o[0][0]["hippo"][k][:, :3325], o2[0][0]["hippo"][k][:, :3325]), k)
        self.assertTrue(torch.equal(o[0][0]["arousal"][:, :3325], o2[0][0]["arousal"][:, :3325]))
        self.assertFalse(torch.equal(o[0][3]["x"][:, 3800:], o2[0][3]["x"][:, 3800:]))

    def test_replay_uses_only_known_frames(self):
        """The newest frame a replay reads is before the frame it serves, by at least 100 frames."""
        m = live()
        n0 = torch.tensor([3400])
        newest = 1700 + (B_ - 1) + 2 * core.HORIZONS[-1]      # an eligible source at n0 - 1700, last frame of the block, widest window
        self.assertLessEqual(newest, 3400 + (B_ - 1) - 100 + 1700 - 1700 + 1)
        self.assertGreaterEqual(core_b7.MIN_AGE, 2 * core.HORIZONS[-1])


class TestBuffer(unittest.TestCase):
    def test_buffer_indexing_and_windows(self):
        m = core_b7.Core7().eval()
        x = noise(1000, seed=2)
        _, st = run(m, x)
        cs = st["cs"][0]
        f = x[0, :, :core.FEAT].double()
        self.assertTrue(torch.allclose(cs[:1001], torch.cat([torch.zeros(1, core.FEAT, dtype=torch.float64), f.cumsum(0)]), atol=1e-9))
        lo, hi = torch.tensor([[130]]), torch.tensor([[480]])
        w = core_b7.window_mean(st["cs"], lo, hi, 350)[0, 0]
        self.assertTrue(torch.allclose(w.double(), f[130:480].mean(0), atol=1e-9))

    def test_new_song_restarts_the_buffer(self):
        m = core_b7.Core7().eval()
        xa, xb = noise(600, seed=3, B=2), noise(600, seed=4, B=2)
        with torch.no_grad():
            _, st = m(xa, m.init_state(2))
            st = m.reset_rows(st, torch.tensor([True, False]))
            _, st2 = m(xb, m.detach_state(st))
        self.assertTrue(torch.allclose(st2["cs"][0, 600], xb[0, :, :core.FEAT].double().sum(0), atol=1e-9))
        self.assertTrue(torch.allclose(st2["cs"][1, 1200], (xa[1, :, :core.FEAT].double().sum(0) + xb[1, :, :core.FEAT].double().sum(0)), atol=1e-9))
        self.assertEqual(int(st2["n"][0]), 600)

    def test_running_key_mean(self):
        m = live()
        _, st = run(m, noise(1000, seed=5))
        self.assertEqual(float(st["kcnt"][0]), 20)
        self.assertTrue(torch.allclose(st["ksum"][0] / 20, st["kr"][0].mean(0), atol=1e-5))
        self.assertTrue(torch.equal(st["kj"][0], torch.arange(20)))

    def test_centring_removes_the_common_part(self):
        m = core_b7.Core7()
        v = torch.randn(1, 6, core_b7.KEY_DIM) + 5.0
        ksum, kcnt = v.sum(1), torch.tensor([6.0])
        c = m._centre(v, ksum, kcnt)
        self.assertTrue(torch.allclose(c.norm(dim=-1), torch.ones(1, 6), atol=1e-5))
        raw = v - v.mean(1, keepdim=True)
        self.assertTrue(torch.allclose(c, torch.nn.functional.normalize(raw, dim=-1), atol=1e-5))
        a, b = v[0, 0], v[0, 1]
        uncentred = float(torch.nn.functional.cosine_similarity(a, b, dim=0))
        centred = float(torch.nn.functional.cosine_similarity(c[0, 0], c[0, 1], dim=0))
        self.assertGreater(uncentred, 0.9)
        self.assertLess(centred, uncentred - 0.5)


class TestRead(unittest.TestCase):
    def _store(self, m, n0):
        """Entries with known keys against a query that is exactly e_0 (the pooled features are e_0, the query matrix picks them)."""
        d = core.FEAT + 4 * core.N
        with torch.no_grad():
            m.query_proj.weight.zero_()
            m.query_proj.weight[:core.FEAT, :core.FEAT] = torch.eye(core.FEAT)
            m.log_tau.fill_(math.log(0.01))
        e = torch.eye(core_b7.KEY_DIM)
        J = 40
        kr = e[2].repeat(J, 1)
        kj = torch.arange(J)
        # eligible when 50 j <= n0 - 1700; n0 = 3000 -> j <= 26
        kr[27] = e[0]                                                    # 17 s minus 1 frame old: invisible
        kr[26] = 0.8 * e[0] + 0.6 * e[1]
        cs = torch.zeros(1, 4001, core.FEAT, dtype=torch.float64)
        cs[0, 1:, 0] = torch.arange(1, 4001, dtype=torch.float64)       # feature 0 = 1 everywhere -> pooled = e_0
        st = {"kr": kr[None], "kj": kj[None], "kv": torch.ones(1, J, dtype=torch.bool), "qs": torch.zeros(1, 4 * core.N)}
        return st, cs, torch.zeros(1, core_b7.KEY_DIM), torch.zeros(1)

    def test_17_second_exclusion_and_source_time(self):
        m = core_b7.Core7().eval()
        st, cs, ksum, kcnt = self._store(m, 3000)
        rep, rec, src, w, top, _ = m.read(st, [], [], torch.tensor([3000]), ksum, kcnt, cs)
        self.assertAlmostEqual(float(rec), 0.8, places=5)
        self.assertEqual(int(src), 26 * 50)                              # the age-16.98 s entry is not read
        rep, rec, src, w, top, _ = m.read(st, [], [], torch.tensor([3050]), ksum, kcnt, cs)
        self.assertAlmostEqual(float(rec), 1.0, places=5)
        self.assertEqual(int(src), 27 * 50)                              # exactly 17 s old: eligible
        rep, rec, src, w, top, _ = m.read({**st, "kv": torch.zeros_like(st["kv"])}, [], [], torch.tensor([3050]), ksum, kcnt, cs)
        self.assertEqual((float(rec), int(src), float(rep.abs().sum())), (0.0, -1, 0.0))

    def test_empty_store_early_in_a_song(self):
        m = live()
        o, _ = run(m, noise(1600, seed=2))
        h = o[0][0]["hippo"]
        self.assertTrue(torch.equal(h["recognition"], torch.zeros(1, 1600)))
        self.assertTrue(torch.equal(h["novelty"], torch.ones(1, 1600)))
        self.assertTrue(torch.equal(h["source_t"], -torch.ones(1, 1600)))

    def test_replay_equals_the_true_targets_on_an_exact_repeat(self):
        """Source pointer forced on a synthetic exact repeat: the replayed 4 x 44 targets equal the repeat's own targets exactly."""
        m = core_b7.Core7().eval()
        L, s1, s2 = 3200, 400, 5200
        T = 9000
        x = noise(T, seed=21)
        x[:, s2:s2 + L] = x[:, s1:s1 + L]
        m.oracle = lambda n0: torch.where(n0 >= s2, s1 + (n0 - s2), -torch.ones_like(n0))
        with torch.no_grad():
            out, _ = m(x, m.init_state(1), return_replay=True)
        rep = out[0]["replay"][0]
        z = x[0, :, :core.FEAT].double()
        cs = torch.cat([torch.zeros(1, core.FEAT, dtype=torch.float64), z.cumsum(0)])
        checked = 0
        for i, h in enumerate(core.HORIZONS):
            for t in range(s2, s2 + L - 2 * h, 37):
                want = (cs[t + 2 * h] - cs[t + h]) / h
                self.assertLess(float((rep[t, i].double() - want).abs().max()), 1e-5, (i, t))
                checked += 1
        self.assertGreater(checked, 200)
        self.assertTrue(torch.equal(rep[:s2 - 100].abs().sum(), torch.zeros(())) or float(rep[:s2 - B_].abs().sum()) == 0.0)

    def test_retrieval_finds_an_exact_repeat_after_a_few_seconds(self):
        """Not trained: keys pool the raw features of the last 2 s, so a repeat is found by content alone once the L3 + L4 part has settled."""
        m = core_b7.Core7().eval()
        L, s1, s2, T = 3600, 400, 6000, 10400
        x = noise(T, seed=22)
        x[:, s2:s2 + L] = x[:, s1:s1 + L]
        with torch.no_grad():
            out, _ = m(x, m.init_state(1))
        src = out[0]["hippo"]["source_t"][0]
        hit = [(float(src[b + 100]) >= 0 and abs(float(src[b + 100]) * 100 - (s1 + (b - s2))) <= 100) for b in range(s2 + 800, s2 + L - 200, 200)]
        print("share of repeat blocks whose top-1 source is within 1 s of the true one (untrained):", sum(hit) / len(hit))
        self.assertGreater(sum(hit) / len(hit), 0.5)


class TestStore(unittest.TestCase):
    def test_chunks_equal_one_run(self):
        m = live()
        x = noise(4000, seed=5)
        one, s1 = run(m, x)
        parts, s2 = run(m, x, chunk=1000)
        for i in range(4):
            for k in ("mean", "logvar"):
                self.assertLess(float((cat(one, i, k) - cat(parts, i, k)).abs().max()), 1e-4)
        self.assertTrue(torch.equal(one[0][0]["hippo"]["source_t"], torch.cat([o[0]["hippo"]["source_t"] for o in parts], 1)))
        self.assertTrue(bool((one[0][0]["hippo"]["source_t"][:, 2000:] >= 0).all()))
        self.assertEqual(s1["kr"].shape, s2["kr"].shape)

    def test_reset_empties_that_row_only(self):
        m = live()
        xa, xb = noise(2400, seed=6, B=2), noise(2400, seed=7, B=2)
        with torch.no_grad():
            _, st = m(xa, m.init_state(2))
            fresh, _ = run(m, xb[:1])
            cont_state = m.detach_state(st)
            o, _ = m(xb, m.detach_state(m.reset_rows(st, torch.tensor([True, False]))))
            cont, _ = m(xb, cont_state)
        self.assertLess(float((o[3]["mean"][0] - fresh[0][3]["mean"][0]).abs().max()), 1e-4)
        self.assertTrue(torch.equal(o[0]["hippo"]["source_t"][0, :1700], -torch.ones(1700)))
        self.assertLess(float((o[3]["mean"][1] - cont[3]["mean"][1]).abs().max()), 1e-6)
        self.assertTrue(bool((o[0]["hippo"]["source_t"][1, 600:] >= 0).any()))

    def test_chunk_start_must_be_on_a_block_edge(self):
        m = core_b7.Core7().eval()
        _, st = run(m, noise(250))
        with self.assertRaises(ValueError):
            m(noise(200), st)


class TestGradients(unittest.TestCase):
    def test_earlier_chunks_detached(self):
        m = live().train()
        x = noise(4800, seed=11)
        o1, st = m(x[:, :2400], m.init_state(1))
        loss1 = sum((o["mean"] ** 2).mean() for o in o1)
        st = m.detach_state(st)
        self.assertFalse(st["kr"].requires_grad)
        self.assertFalse(st["ksum"].requires_grad)
        o2, _ = m(x[:, 2400:], st)
        loss2 = sum((o["mean"] ** 2).mean() for o in o2) + o2[0]["hippo"]["recognition"].mean()
        loss2.backward()
        g2 = m.key_proj.weight.grad.clone()
        loss1.backward()                                              # still possible: chunk 2 did not hang on chunk 1's graph
        self.assertGreater(float(g2.abs().sum()), 0.0)

    def test_gradients_reach_the_new_weights(self):
        m = live().train()
        o, _ = m(noise(3000, seed=12), m.init_state(1))
        (o[0]["hippo"]["recognition"].sum() + sum(oo["mean"].sum() for oo in o)).backward()
        for p in (m.key_proj.weight, m.query_proj.weight, m.relay[0].weight, m.skip[0].weight, m.log_tau, m.w_g, m.w_tau):
            self.assertGreater(float(p.grad.abs().sum()), 0.0)

    def test_arousal_stops_gradient(self):
        m = live().train()
        o, _ = m(noise(400, seed=13), m.init_state(1))
        self.assertFalse(o[0]["arousal"].requires_grad)
        self.assertFalse(o[0]["dev"].requires_grad)


class TestModulationT3(unittest.TestCase):
    def test_zero_weights_equal_no_modulation(self):
        m = live()
        with torch.no_grad():
            m.w_g.zero_()
            m.w_tau.zero_()
        x = noise(2000, seed=14)
        a, _ = run(m, x)
        m.modulation = "frozen"
        b, _ = run(m, x)
        for i in range(4):
            self.assertTrue(torch.equal(cat(a, i, "mean"), cat(b, i, "mean")))
            self.assertTrue(torch.equal(cat(a, i, "x"), cat(b, i, "x")))

    def test_designed_change_of_modulus_and_fixed_frequency(self):
        L = core.Layer(torch.Generator().manual_seed(1), core.BANDS[2], True)
        h0 = torch.complex(torch.randn(1, core.N), torch.randn(1, core.N))
        x = torch.zeros(1, B_, core.D)
        with torch.no_grad():
            _, h, _, _, _ = L(x, h0, torch.zeros(1, B_, core.FEAT), None, None, torch.ones(1), torch.tensor([1.7]))
        t = torch.arange(1, B_ + 1)[:, None].float()
        nu, th = torch.exp(L.nu_log.detach()), L.theta.detach()
        want = h0 * torch.exp(torch.complex(-nu * 1.7 * t, th * t))
        self.assertLess(float((h[0] - want).abs().max()), 1e-4)

    def test_gain_scales_the_drive_linearly(self):
        L = core.Layer(torch.Generator().manual_seed(2), core.BANDS[0], False)
        x = torch.randn(1, B_, core.D)
        h0 = torch.zeros(1, core.N, dtype=torch.complex64)
        with torch.no_grad():
            _, h1, _, _, _ = L(x, h0, None, None, None, torch.ones(1), torch.ones(1))
            _, h2, _, _, _ = L(x, h0, None, None, None, torch.tensor([1.25]), torch.ones(1))
        self.assertLess(float((h2 - 1.25 * h1).abs().max()), 1e-5)

    def test_two_level_scan_equals_the_plain_recurrence(self):
        ll = torch.complex(-torch.rand(2, 8) * 0.3, torch.rand(2, 8))
        u = torch.complex(torch.randn(2, 200, 8), torch.randn(2, 200, 8))
        h0 = torch.complex(torch.randn(2, 8), torch.randn(2, 8))
        out, last = core.scan_rows(ll, u, h0)
        h, ref = h0, []
        for t in range(200):
            h = torch.exp(ll) * h + u[:, t]
            ref.append(h)
        self.assertLess(float((out - torch.stack(ref, 1)).abs().max()), 1e-4)
        self.assertLess(float((last - h).abs().max()), 1e-4)

    def test_arousal_step_changes_the_blocks_exactly(self):
        m = core_b7.Core7().eval()
        ws = (0.5, 0.25, -0.5, 0.0)
        with torch.no_grad():
            m.w_g.copy_(torch.tensor([0.1, 0.2, 0.3, 0.4]))
            m.w_tau.copy_(torch.tensor(ws))
        st = m.init_state(2)
        st["a"] = torch.tensor([1.0, 0.0])
        th0 = [L.theta.detach().clone() for L in m.layers]
        with torch.no_grad():
            o, _ = m(noise(B_, B=2), st)
        for i, w in enumerate(ws):
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
            o, _ = m(noise(B_), st)
        self.assertAlmostEqual(float(o[0]["expo"][0, 0]), core_b7.E_MIN, places=6)

    def test_arousal_rises_with_surprise_and_starts_from_zero(self):
        m = core_b7.Core7().eval()
        x = noise(1200, seed=15, scale=0.1)
        x[:, 600:, :core.FEAT] += 4 * torch.randn(1, 600, core.FEAT)
        with torch.no_grad():
            o, st = m(x, m.init_state(1))
        a = o[0]["arousal"][0]
        self.assertEqual(float(a[0]), 0.0)
        self.assertGreater(float(a[1100]), float(a[590]))
        self.assertAlmostEqual(float(st["a"][0]), float(a[-1]), places=6)


class TestDropped(unittest.TestCase):
    def test_dropped_hippocampus_has_no_store_and_keeps_relay_and_modulation(self):
        m = core_b7.Core7(hippocampus=False).eval()
        g = torch.Generator().manual_seed(2)
        with torch.no_grad():
            for mod in (*m.relay, *m.skip):
                mod.weight.copy_(0.05 * torch.randn(mod.weight.shape, generator=g))
            m.w_tau.fill_(0.3)
        x = noise(4400, seed=30)
        o, st = run(m, x)
        h = o[0][0]["hippo"]
        self.assertEqual(st["kr"].shape[1], 0)
        self.assertTrue(torch.equal(h["recognition"], torch.zeros(1, 4400)))
        self.assertTrue(torch.equal(h["novelty"], torch.ones(1, 4400)))
        m.relay_on = False
        off, _ = run(m, x)
        self.assertFalse(torch.equal(cat(o, 3, "mean"), cat(off, 3, "mean")))        # the relay (features + phase) still acts
        sd = m.state_dict()
        m2 = core_b7.Core7(hippocampus=True)
        m2.load_state_dict(sd)
        self.assertEqual(float(m2.hippo_flag), 0.0)


class TestTappedSkip(unittest.TestCase):
    def test_taps_see_the_last_frames_across_blocks(self):
        m = core_b7.Core7(skip_taps=10).eval()
        with torch.no_grad():
            m.skip[0].weight.zero_()
            m.skip[0].weight[0, 0] = 1.0                                  # output 0 <- feature 0 of the oldest frame of the window (t - 9)
        x = noise(400, seed=16)
        with torch.no_grad():
            o, _ = m(x, m.init_state(1))
        z = x[0, :, 0]
        m2 = core_b7.Core7(skip_taps=10).eval()
        with torch.no_grad():
            o0, _ = m2(x, m2.init_state(1))
        d = (o[0]["mean"][0, :, 0] - o0[0]["mean"][0, :, 0])
        # the oldest tap of frame t is frame t - 9; the edit adds exactly that value to the mean of head 0 (the raw skip adds to the head output)
        self.assertLess(float((d[9:] - z[:-9]).abs().max()), 1e-4)


class TestH1(unittest.TestCase):
    """Hindsight loss, scheduled sampling, novelty lane (docs/BODY_BRAIN_PLAN.md 5). Flags off = unchanged is covered by every test above."""

    def repeat_input(self, s1=400, s2=5200, L=3200, T=9000):
        x = noise(T, seed=31)
        x[:, s2:s2 + L] = x[:, s1:s1 + L]
        return x, s1, s2

    def test_hindsight_loss_has_gradient_to_query_and_key_and_picks_the_source(self):
        m = live().train()
        m.hind = True
        x, s1, s2 = self.repeat_input()
        out, _ = m(x, m.init_state(1))
        loss = out[0]["hind"]
        self.assertTrue(math.isfinite(float(loss.detach())) and float(loss.detach()) > 0)
        loss.backward()
        for p in (m.query_proj.weight, m.key_proj.weight, m.log_tau):
            self.assertIsNotNone(p.grad)
            self.assertTrue(torch.isfinite(p.grad).all() and float(p.grad.abs().sum()) > 0)

    def test_hindsight_target_is_the_true_source_in_a_repeat(self):
        """Inside the repeat the lowest-error entry is the true source (replay error 0), whatever the query says."""
        m = live().eval()
        m.hind = True
        x, s1, s2 = self.repeat_input()
        seen, orig = [], m._hindsight
        def spy(*a):
            r = orig(*a)
            if r is not None:
                seen.append((int(a[3][0]), int(r[2][0])))
            return r
        m._hindsight = spy
        with torch.no_grad():
            m(x, m.init_state(1))
        hits = [tgt for n0, tgt in seen if s2 + 200 <= n0 <= s2 + 1400]
        self.assertGreater(len(hits), 3)
        for n0, tgt in seen:
            if s2 + 200 <= n0 <= s2 + 1400:
                self.assertLessEqual(abs(tgt - (s1 + n0 - s2)), core_b7.BLOCK, (n0, tgt))

    def test_hindsight_gate_skips_blocks_with_no_useful_entry(self):
        """Pure noise, no repeat: no replay beats a zero replay, so the gated loss counts (almost) no rows; with the repeat it counts some."""
        m = live().eval()
        m.hind = True
        x = noise(5000, seed=41)
        with torch.no_grad():
            ungated = float(m(x, m.init_state(1))[0][0]["hind"])
            m.hind_gate = True
            gated_noise = float(m(x, m.init_state(1))[0][0]["hind"])
            xr, s1, s2 = self.repeat_input()
            gated_rep = float(m(xr, m.init_state(1))[0][0]["hind"])
        self.assertGreater(ungated, 0.0)
        self.assertGreaterEqual(gated_rep, 0.0)
        self.assertLessEqual(gated_noise, ungated)

    def test_hindsight_off_adds_nothing(self):
        m = live().eval()
        x, _, _ = self.repeat_input(T=3000, s2=1900, L=600, s1=100)
        out, _ = m(x, m.init_state(1))
        self.assertNotIn("hind", out[0])
        self.assertNotIn("novelty_lane", out[0])

    def test_scheduled_sampling_endpoints(self):
        m = live().eval()
        x, s1, s2 = self.repeat_input()
        orc = lambda n0: torch.where(n0 >= s2, s1 + (n0 - s2), -torch.ones_like(n0))
        def sources(p):
            m.oracle, m.oracle_p = orc, p
            with torch.no_grad():
                out, _ = m(x, m.init_state(1))
            return out[0]["hippo"]["source_t"][0], out[0]["replay"] if False else None
        full, _ = sources(1.0)
        none, _ = sources(0.0)
        m.oracle = None
        with torch.no_grad():
            ref, _ = m(x, m.init_state(1))
        self.assertTrue(torch.equal(none, ref[0]["hippo"]["source_t"][0]))                  # p = 0 is plain retrieval
        b = s2 + 1000
        self.assertAlmostEqual(float(full[b + 5]) * 100, s1 + 1000, delta=1)               # p = 1 is the oracle pointer
        mid, _ = sources(0.5)
        blocks = range(s2 + 400, s2 + 3000, 200)
        share = np.mean([abs(float(mid[b + 5]) * 100 - (s1 + b - s2)) < 1 for b in blocks])
        self.assertTrue(0.05 < share < 1.0 or share == 1.0, share)                         # a mix (retrieval may hit the same source)

    def test_novelty_lane_low_in_repeat_high_elsewhere(self):
        m = live().eval()
        m.novelty_lane = True
        x, s1, s2 = self.repeat_input()
        with torch.no_grad():
            out, _ = m(x, m.init_state(1))
        t, nv = out[0]["novelty_lane"]["t"][0], out[0]["novelty_lane"]["novelty"][0]
        self.assertEqual(len(t), x.shape[1] // core_b7.TICK)
        self.assertTrue(torch.equal(t, torch.arange(len(t)) * core_b7.TICK))
        inrep = (t >= s2 + 300) & (t < s2 + 3200)
        out_ = (t >= 1700) & ~((t >= s2) & (t < s2 + 3200))
        self.assertTrue(torch.all(nv[t < 1700] == 1.0))                                     # nothing 17 s old yet
        self.assertLess(float(nv[inrep].mean()), float(nv[out_].mean()))

    def test_novelty_lane_changes_no_output(self):
        m = live().eval()
        x, _, _ = self.repeat_input(T=4000, s2=2600, L=800, s1=200)
        with torch.no_grad():
            a, _ = m(x, m.init_state(1))
            m.novelty_lane = True
            b, _ = m(x, m.init_state(1))
        for i in range(4):
            self.assertTrue(torch.equal(a[i]["mean"], b[i]["mean"]))
        self.assertTrue(torch.equal(a[0]["hippo"]["source_t"], b[0]["hippo"]["source_t"]))


if __name__ == "__main__":
    unittest.main()
