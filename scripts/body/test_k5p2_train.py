"""K5-pass2 trainer tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_k5p2_train   (JAX env; compiles the M3f body, minutes)."""
import json
import tempfile
import unittest
from pathlib import Path

import jax
import numpy as np

import k5_train as T
import k5p2_train as P2

W = json.loads((T.K5 / "windows.json").read_text())
SPL = json.loads((T.K5 / "splits.json").read_text())


class Windows(unittest.TestCase):
    def test_r_input_is_previous_block_order_parameter(self):
        toy = P2.build_toy(T.K5, "train", [tuple(w) for w in W["train"][:2]])
        inp = toy.inputs(np.arange(2), jax.random.PRNGKey(0))
        self.assertEqual(inp["R"].shape, (2, 120))
        np.testing.assert_allclose(np.asarray(inp["R"])[:, 1:], toy.R[:, :-1])
        self.assertTrue((np.asarray(inp["R"])[:, 0] == 0).all())

    def test_combine_keeps_r(self):
        a = P2.build_toy(T.K5, "train", [tuple(w) for w in W["train"][:2]])
        b = P2.build_toy(T.K5, "train", [tuple(w) for w in W["train"][2:3]])
        c = P2.combine(a, b)
        self.assertEqual(c.R.shape, (3, 120))
        c.inputs(np.arange(3), jax.random.PRNGKey(0))


class Run(unittest.TestCase):
    """One round runs; a kill and resume gives identical parameters; a validation writes best.pkl with the cfg. 8 windows, rounds of 2."""

    def _run(self, d, max_rounds):
        r = P2.K5P2Run(d, windows=W["train"][:8], round_windows=2, log=lambda s: None)
        r.run(max_rounds)
        return r

    def test_resume_identical_and_validation(self):
        T.EVAL_BATCH = 3
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            straight = self._run(a, 2)
            self._run(b, 1)
            resumed = self._run(b, 2)
            self.assertEqual(resumed.tr.epoch, 2)
            for x, y in zip(jax.tree_util.tree_leaves(straight.tr.P), jax.tree_util.tree_leaves(resumed.tr.P)):
                np.testing.assert_array_equal(np.asarray(x), np.asarray(y))
            np.testing.assert_array_equal(np.asarray(straight.tr.key), np.asarray(resumed.tr.key))
            straight.splits["val"]["ids"] = SPL["val"]["ids"][:3]
            straight.validate()
            import pickle
            best = pickle.loads((Path(a) / "best.pkl").read_bytes())
            self.assertEqual(best["cfg"], P2.CFG)
            self.assertEqual(len(straight.extra["val"]), 1)


if __name__ == "__main__":
    unittest.main()
