import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diag_lib as D  # noqa: E402


def toy(s):
    r = np.random.default_rng(s)
    return dict(c1=r.integers(0, 9, 12), c2=r.integers(0, 9, 12), v=r.integers(0, 4, 12), p=r.integers(0, 5, (12, 5)))


class T(unittest.TestCase):
    def test_self_swap_identity(self):
        a = toy(1)
        s = D.swap(a, a)
        for k in a:
            np.testing.assert_array_equal(s[k], a[k])

    def test_complementary(self):
        a, b = toy(1), toy(2)
        hp, hg = D.swap(a, b), D.swap(b, a)
        np.testing.assert_array_equal(hp["p"], a["p"])
        np.testing.assert_array_equal(hg["p"], b["p"])
        for k in D.GESTURE:
            np.testing.assert_array_equal(hp[k], b[k])
            np.testing.assert_array_equal(hg[k], a[k])

    def test_length_mismatch(self):
        a = toy(1)
        b = dict(toy(2), p=toy(2)["p"][:5])
        with self.assertRaises(AssertionError):
            D.swap(b, a)


class TJ(unittest.TestCase):
    def test_hj_equals_wo44_rows(self):
        """a fresh A1 rebuild of one song's human tokens matches WO44's stored (float noise < 1e-3 deg) HJ|blocks|V1 rows"""
        import join_lib as J
        import join_run as JR
        import t1a2_train as TR2
        import t1b_t2 as T2
        import t1b_t2b as B
        import torch
        k = JR.songs()[0][0]
        w = np.load(JR.OUT / "rows" / f"{k}.npz")
        vq = TR2.make("B")
        vq.load_state_dict(torch.load("/secondary/hyst-data/body/t1a2/runB/best.pt"))
        vq.eval()
        h = T2.human_window(k)["V1"]
        r = J.build_rows(h["tok"], h["post0"], T2.vocab(), vq, B.sd_scale(), "blocks")
        np.testing.assert_allclose(r, w["HJ|blocks|V1"], atol=1e-3)


if __name__ == "__main__":
    unittest.main()
