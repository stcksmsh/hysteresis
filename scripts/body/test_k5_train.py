"""K5 trainer / eval tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_k5_train   (JAX env; own process; the run tests compile M3e twice, minutes).
Uses the real K5 lanes (/secondary/hyst-data/body/k5) and the frozen cerebellum port."""
import json
import tempfile
import unittest
from pathlib import Path

import jax
import numpy as np

import k5_eval as E
import k5_train as T
import m3d
import m3e

W = json.loads((T.K5 / "windows.json").read_text())
SPL = json.loads((T.K5 / "splits.json").read_text())


class Pure(unittest.TestCase):
    def test_should_stop(self):
        self.assertFalse(T.should_stop([0.5, 0.6]))
        self.assertFalse(T.should_stop([0.5, 0.6, 0.55]))                 # one miss is not enough
        self.assertTrue(T.should_stop([0.5, 0.6, 0.55, 0.6]))             # two in a row not strictly above 0.6
        self.assertFalse(T.should_stop([0.5, 0.6, 0.55, 0.7]))

    def test_order_fixed_and_complete(self):
        o1, o2 = T.train_order(W["train"]), T.train_order(W["train"])
        self.assertEqual(o1, o2)
        self.assertEqual(len(o1), 15624)
        self.assertEqual(sorted(o1), sorted(tuple(w) for w in W["train"]))
        self.assertEqual(-(-len(o1) // T.ROUND), 977)

    def test_obs_windows_distinct_songs(self):
        o = T.obs_windows(T.train_order(W["train"]))
        self.assertEqual(len({s for s, _ in o}), T.N_OBS_WINDOWS)

    def test_per_song_stats(self):
        songs = ["a", "a", "a", "b", "b", "b"]
        order, v = E.per_song([1, 2, 3, 4, 5, 6], songs)
        self.assertEqual(order, ["a", "b"])
        np.testing.assert_allclose(v, [2.0, 5.0])
        p = E.paired_songs([1, 2, 3, 4, 5, 6], [0, 1, 2, 4, 5, 6], songs)
        self.assertAlmostEqual(p["mean"], 0.5)

    def test_no_heldout_artist_in_training_windows(self):
        train_ids = set(SPL["train"]["ids"])
        self.assertTrue({w[0] for w in W["train"]} <= train_ids)
        self.assertFalse({w[0] for w in W["train"]} & set(SPL["check"]["ids"]))


class Windows(unittest.TestCase):
    def test_window_toy_is_an_m3e_episode(self):
        wins = [tuple(w) for w in W["train"][:3]]
        toy = T.build_toy(T.K5, "train", wins)
        self.assertEqual(toy.y.shape, (3, 120, 8))
        raw = np.stack([T.lanes(T.K5, "train", s)[0][b:b + 120] for s, b in wins])
        exp = raw.copy()
        exp[..., :2] = np.arcsinh(exp[..., :2])
        np.testing.assert_allclose(toy.y, exp)
        np.testing.assert_allclose(toy.yz, m3e.running_z(exp))
        self.assertTrue((toy.yz[:, :7] == 0).all())                      # the first 7 blocks hold fewer than 8 blocks of history
        inp = toy.inputs(np.arange(3), jax.random.PRNGKey(0))
        self.assertEqual(inp["x"].shape, (3, 120, 16))
        self.assertEqual(inp["g"].shape, (3, 120, 8))
        np.testing.assert_allclose(np.asarray(inp["phi0"])[:, 1:], toy.phi[:, :-1])       # the loop reads the previous block's phase

    def test_causal_window_ignores_the_future(self):
        wins = [tuple(w) for w in W["train"][:2]]
        a = T.build_toy(T.K5, "train", wins)
        y = a.y.copy()
        y[:, 100:] += 50.0
        np.testing.assert_allclose(m3e.running_z(y)[:, :100], a.yz[:, :100])

    def test_val_windows_fit(self):
        for sid, b in T.val_windows(T.K5, SPL)[::20]:
            self.assertGreaterEqual(b, 0)
            self.assertLessEqual(b + 120, len(T.lanes(T.K5, "val", sid)[0]))


class Run(unittest.TestCase):
    """A kill and resume gives identical parameters; a validation runs and writes best.pkl. Small: 8 windows, rounds of 2."""

    def _run(self, d, max_rounds):
        r = T.K5Run(d, windows=W["train"][:8], round_windows=2, log=lambda s: None)
        r.run(max_rounds)
        return r

    def test_resume_identical_and_validation(self):
        T.EVAL_BATCH = 3
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            straight = self._run(a, 2)
            self._run(b, 1)
            resumed = self._run(b, 2)                                      # new process state: reads ckpt.pkl, round 1 -> 2
            self.assertEqual(resumed.tr.epoch, 2)
            for x, y in zip(jax.tree_util.tree_leaves(straight.tr.P), jax.tree_util.tree_leaves(resumed.tr.P)):
                np.testing.assert_array_equal(np.asarray(x), np.asarray(y))
            np.testing.assert_array_equal(np.asarray(straight.tr.key), np.asarray(resumed.tr.key))
            straight.splits["val"]["ids"] = SPL["val"]["ids"][:3]
            straight.validate()
            self.assertTrue((Path(a) / "best.pkl").exists())
            self.assertEqual(len(straight.extra["val"]), 1)


if __name__ == "__main__":
    unittest.main()
