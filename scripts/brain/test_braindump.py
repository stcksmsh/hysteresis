import unittest

import numpy as np
import torch

import braindump as bd
import core
import core_b7
import toy_b7


class TestPure(unittest.TestCase):
    def test_order_parameter(self):
        ph = np.zeros((3, 256))
        h = np.exp(1j * ph) * np.random.default_rng(0).uniform(0.5, 2, (3, 256))
        self.assertTrue(np.allclose(bd.order_parameter(h), 1.0))
        rng = np.random.default_rng(1)
        h2 = np.exp(1j * rng.uniform(0, 2 * np.pi, (50, 256)))
        self.assertLess(bd.order_parameter(h2).mean(), 0.15)
        h3 = np.concatenate([np.ones((1, 4)), -np.ones((1, 4))], 1) + 0j          # two opposite phases, equal weight: 0
        self.assertAlmostEqual(float(bd.order_parameter(h3)[0]), 0.0)
        h4 = np.array([[3.0, -1.0]]) + 0j                                          # magnitude-weighted: |3 - 1| / 4
        self.assertAlmostEqual(float(bd.order_parameter(h4)[0]), 0.5)

    def test_windows_and_crossings(self):
        r = np.stack([np.arange(250, dtype=np.float32)] * 4, 1)
        w = bd.window_means(r)
        self.assertEqual(len(w), (250 - 100) // 10 + 1)
        self.assertAlmostEqual(float(w[0, 0]), 49.5, places=3)
        self.assertAlmostEqual(float(w[1, 0]), 59.5, places=3)
        self.assertEqual(len(bd.window_means(r[:99])), 0)
        coh = np.array([[1, 1, 1, 0], [1, 1, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0.0]])
        th = np.array([0.5, 0.5, 0.5, 0.5])
        self.assertEqual(bd.crossings(coh, th).tolist(), [True, False, True, False])
        self.assertEqual(bd.crossings(coh, th, 2).tolist(), [True, True, True, False])

    def test_sample_frames(self):
        f = bd.sample_frames(1000)
        self.assertEqual(f[:4].tolist(), [0, 3, 6, 10])
        self.assertEqual(len(f), 300)
        self.assertTrue((f < 1000).all())

    def test_target_alignment(self):
        z = np.random.default_rng(0).standard_normal((300, 44)).astype(np.float32)
        t = bd.targets(z, 50)
        self.assertTrue(np.allclose(t[7], z[57:107].mean(0), atol=1e-5))
        self.assertTrue(np.isnan(t[201:]).all() and not np.isnan(t[:201]).any())

    def test_surprisal_stamp(self):
        T, h = 400, 10
        err = np.ones((T, 44), np.float32)
        lv = np.zeros((T, 44), np.float32)
        lv[100] = 2.0
        s = bd.surprisal(err, lv, h)
        self.assertTrue(np.isnan(s[:2 * h - 1]).all())
        base = 0.5 * (1.0 + np.log(2 * np.pi))
        self.assertAlmostEqual(float(s[50]), base, places=5)
        t = 100 + 2 * h - 1                                             # the prediction made at 100 is scored at 119
        self.assertAlmostEqual(float(s[t]), 0.5 * (2.0 + np.exp(-2.0) + np.log(2 * np.pi)), places=5)

    def test_selfsim_lane(self):
        rng = np.random.default_rng(0)
        base = rng.standard_normal((40, 64))
        base /= np.linalg.norm(base, axis=1, keepdims=True)
        ticks = np.arange(40) * 50
        codes = base.copy()
        codes[36:] = base[0:4]                                           # entries 36..39 repeat 0..3, > 17 s earlier
        lane = bd.selfsim_lane(codes.astype(np.float32), ticks, 40 * 50)
        self.assertTrue(np.isnan(lane[:1700]).all())                     # the first entry is 17 s old at tick 34 (frame 1700)
        self.assertFalse(np.isnan(lane[1700]))
        self.assertAlmostEqual(float(lane[36 * 50 + 1]), 0.0, places=5)
        self.assertGreater(float(lane[35 * 50 + 1]), 0.3)
        self.assertEqual(lane[36 * 50 + 1], lane[36 * 50 + 49])           # held between ticks

    def test_pooled_matches_core(self):
        z = np.random.default_rng(1).standard_normal((600, 44)).astype(np.float32)
        p = bd.pooled(z, np.array([0, 100, 300, 500]))
        self.assertTrue(np.allclose(p[0], 0))
        self.assertTrue(np.allclose(p[1], z[:100].sum(0) / 200, atol=1e-5))
        self.assertTrue(np.allclose(p[3], z[300:500].mean(0), atol=1e-5))


class TestRun(unittest.TestCase):
    def test_small_model_end_to_end(self):
        with toy_b7.small():
            torch.manual_seed(0)
            model = core_b7.Core7(seed=0, phase=True, hippocampus=False, skip_taps=10).eval()
            x = np.random.default_rng(0).standard_normal((1300, 46)).astype(np.float32)
            res = bd.run_song(model, x, chunk=600)
            arr, meta = bd.export_arrays(res, x[:, :core.FEAT])
            n = len(bd.sample_frames(1300))
            self.assertEqual(arr["modes"].shape, (n, 4, core.N, 2))
            with torch.no_grad():
                out, _ = model(torch.from_numpy(x[:600])[None], model.init_state(1))
        self.assertEqual(arr["pred_mean"].shape, (n, 4, 44))
        self.assertEqual(arr["surprisal"].shape, (n, 4))
        self.assertEqual(arr["gain"].shape, (n, 4))
        self.assertEqual(len(arr["coherence"]), (1300 - 100) // 10 + 1)
        self.assertEqual(arr["modes"].dtype, np.float16)
        self.assertTrue(np.isfinite(arr["coherence"].astype(np.float32)).all())
        self.assertTrue(np.isnan(arr["selfsimilarity"].astype(np.float32)).all())      # nothing is 17 s old in 13 s
        want = out[0]["arousal"][0].numpy()[bd.sample_frames(600)]
        self.assertTrue(np.allclose(arr["arousal"][:len(want)].astype(np.float32), want, rtol=2e-3, atol=2e-3))

    def test_brain_field(self):
        import json
        import brain_mindstate as bm
        with toy_b7.small():
            torch.manual_seed(0)
            model = core_b7.Core7(seed=0, phase=True, hippocampus=False, skip_taps=10).eval()
            x = np.random.default_rng(0).standard_normal((1300, 46)).astype(np.float32)
            res = bd.run_song(model, x)
            f = bm.brain_field(res, x[:, :core.FEAT])
        nb = 130
        for k in ("smoothedSurprisal", "arousalSignal", "l4PredictedVariance", "surprisalSlope30s", "selfSimilarity"):
            self.assertEqual(len(f[k]), nb, k)
        for k in ("surprisal", "bandPower", "gain", "exponent", "coherence"):
            self.assertTrue(all(len(v) == nb for v in f[k].values()), k)
        self.assertEqual(set(f["surprisal"]), {"L1", "L2", "L3", "L4", "total"})
        self.assertIsNone(f["surprisal"]["L1"][0])                      # nothing scored before frame 2h - 1 = 19
        self.assertIsNotNone(f["surprisal"]["L1"][2])                   # bin 2 is stamped at frame 29
        self.assertIsNone(f["coherence"]["L1"][8])
        self.assertIsNotNone(f["coherence"]["L1"][9])
        json.dumps(f, allow_nan=False)                                  # strict JSON: no NaN anywhere
        v1 = {"mindState": {"version": 1, "hopSeconds": 0.5, "bands": [], "surprise": [], "neuromod": [], "mood": {"energy": [0.5]}, "brain": f}}
        v2 = bm.to_v2(v1)["mindState"]
        self.assertEqual((v2["version"], v2["brainHopSeconds"], "brain" in v2), (2, 0.1, False))
        self.assertEqual(v2["mood"], v1["mindState"]["mood"])
        self.assertEqual(v2["bands"]["power.L3"], f["bandPower"]["L3"])
        self.assertEqual(v2["surprise"]["total"], f["surprisal"]["total"])
        self.assertEqual(v2["neuromod"]["gain.L2"], f["gain"]["L2"])
        self.assertEqual(len(v2["bands"]) + len(v2["surprise"]) + len(v2["neuromod"]), 9 + 8 + 9)
        self.assertEqual(v1["mindState"]["version"], 1)                 # the input is not changed
        with self.assertRaises(ValueError):
            bm.to_v2(bm.to_v2(v1))
        json.dumps(v2, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
