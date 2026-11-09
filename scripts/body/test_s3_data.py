"""Tests for s3_slow / s3_eval (work order 26A). Brain env: python -m unittest test_s3_data (needs the data chain's outputs for the data tests)."""
import json
import unittest
from pathlib import Path

import numpy as np

import s3_eval as E
import s3_slow as S

K5, S3 = Path("/secondary/hyst-data/body/k5"), Path("/secondary/hyst-data/body/s3")


class Integral(unittest.TestCase):
    def test_definition(self):
        s = np.arange(1.0, 401.0)
        s[3] = np.nan
        o = S.surprisal_integral(s, 80)
        self.assertAlmostEqual(o[0], 1 + 2 + 3 + 0 + 5)                  # block 0 ends at sample 4; NaN counts as 0
        b = 40                                                             # ends at sample 204: samples 125..204 (80 of them)
        self.assertAlmostEqual(o[b], s[125:205].sum())
        self.assertEqual(len(o), 80)

    def test_causal(self):
        s = np.random.default_rng(0).normal(size=500)
        a = S.surprisal_integral(s, 60)
        s2 = s.copy()
        s2[300:] = 99.0                                                    # changing the future must not change blocks that end before it
        b = S.surprisal_integral(s2, 60)
        self.assertTrue(np.allclose(a[:59], b[:59]))


class Clips(unittest.TestCase):
    def test_interleaved_layout(self):
        q = np.zeros((E.STRIDE_ROWS * 4 + E.CLIP_ROWS, 5))
        q[:, 0] = np.arange(len(q))
        tr, te = E.interleaved_clips(q)
        self.assertEqual((len(tr), len(te)), (3, 2))
        self.assertEqual(tr[1][0, 0], 2 * E.STRIDE_ROWS)                  # 3rd clip starts at 120 s
        self.assertEqual(te[0][0, 0], E.STRIDE_ROWS)                      # 2nd clip at 60 s: 30 s gap after the 1st clip ended at 30 s

    def test_limit_report_flags(self):
        t = np.arange(500) / 50.0
        q = np.stack([np.sin(2 * np.pi * 0.5 * t) * 30] + [np.zeros_like(t)] * 4, 1)
        r = E.limit_report(q)
        self.assertFalse(r["base_yaw"]["flag_speed"])
        q[250, 1] = 200.0                                                  # a one-sample spike flags the shoulder
        self.assertTrue(E.limit_report(q)["shoulder"]["flag_acc"])


@unittest.skipUnless((S3 / "slow" / "norm.json").exists(), "slow lanes not built yet")
class Data(unittest.TestCase):
    def test_block_counts(self):
        sp = json.loads((K5 / "splits.json").read_text())
        for split in ("check", "train", "val"):
            for sid in sp[split]["ids"][:4]:
                n = len(np.load(K5 / "lanes" / split / f"{sid}.npz")["y"])
                z = np.load(S3 / "slow" / split / f"{sid}.npz")["slow"]
                self.assertEqual(z.shape, (n, 13))
                self.assertTrue(np.isfinite(z).all())

    def test_projection_reproduces_on_reload(self):
        sp = json.loads((K5 / "splits.json").read_text())
        sid = sp["train"]["ids"][0]
        a = S.slow_of("train", sid)
        b = S.slow_of("train", sid, S.load_norm())
        self.assertTrue(np.array_equal(a, b))
        self.assertTrue(np.allclose(a, np.load(S3 / "slow" / "train" / f"{sid}.npz")["slow"], atol=1e-5))
        n = json.loads((S3 / "slow" / "norm.json").read_text())
        self.assertEqual(np.array(n["pca_components"]).shape, (8, 512))
        c = np.array(n["pca_components"])
        self.assertTrue(np.allclose(c @ c.T, np.eye(8), atol=1e-6))

    def test_train_columns_standardised(self):
        sp = json.loads((K5 / "splits.json").read_text())
        z = np.concatenate([np.load(S3 / "slow" / "train" / f"{s}.npz")["slow"] for s in sp["train"]["ids"][::40]])
        self.assertLess(np.abs(z.mean(0)).max(), 0.35)                    # a subsample of songs: only roughly standardised
        self.assertTrue(((z.std(0) > 0.5) & (z.std(0) < 2.0)).all())


if __name__ == "__main__":
    unittest.main()
