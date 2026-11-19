"""WO10 1b: pause, stop and start again without loss, with the real service commands. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_k5_run   (JAX env; minutes).
A tiny run (8 real windows, rounds of 2, 4 rounds) is run (a) uninterrupted in one unit, then (b) in a second unit that is started, frozen, thawed, stopped with `systemctl stop` after
round 1 and started again. The checkpoints after round 3 must agree to 1e-9 (see the finding below; in-process resume is bit-identical). Needs mains: the run waits on battery."""
import json
import os
import pickle
import subprocess
import time
import unittest
from pathlib import Path

import jax
import numpy as np

HERE = Path(__file__).resolve().parent
RUN = str(HERE / "k5_run.sh")
ARGS = "--limit-windows 8 --round-windows 2 --max-rounds 3 --no-chain"


def sh(*a, env=None, check=True):
    return subprocess.run(a, env={**os.environ, **(env or {})}, capture_output=True, text=True, check=check)


def unit_state(unit):
    return dict(l.split("=", 1) for l in sh("systemctl", "--user", "show", unit, "-p", "ActiveState", "-p", "FreezerState", check=False).stdout.split())


def wait(cond, secs, what):
    t = time.time()
    while time.time() - t < secs:
        if cond():
            return
        time.sleep(2)
    raise AssertionError(f"timeout waiting for {what}")


def progress(out):
    try:
        return json.loads((Path(out) / "progress.json").read_text())
    except Exception:
        return {}


class Pause(unittest.TestCase):
    def test_freeze_stop_start_is_lossless(self):
        import tempfile
        with tempfile.TemporaryDirectory() as ta, tempfile.TemporaryDirectory() as tb:
            ea = {"K5_OUT": ta, "K5_UNIT": "hyst-wo10-k5test-a", "K5_ARGS": ARGS}
            eb = {"K5_OUT": tb, "K5_UNIT": "hyst-wo10-k5test-b", "K5_ARGS": ARGS}
            sh(RUN, "start", env=ea)                                       # A runs alone first: two concurrent runs differ at 1e-11 even without any stop (measured), so the
            wait(lambda: unit_state("hyst-wo10-k5test-a").get("ActiveState") == "inactive", 900, "A to finish")        # comparison needs a quiet machine
            sh(RUN, "start", env=eb)
            # B: wait for round 1, freeze, check the clock stands still, thaw, stop right after round 1 or 2, start again
            wait(lambda: progress(tb).get("round", 0) >= 1, 900, "round 1 of B")
            sh(RUN, "pause", env=eb)
            self.assertEqual(unit_state("hyst-wo10-k5test-b").get("FreezerState"), "frozen")
            time.sleep(20)
            r_frozen = progress(tb).get("round")
            sh(RUN, "continue", env=eb)
            self.assertEqual(unit_state("hyst-wo10-k5test-b").get("FreezerState"), "running")
            t0 = time.time()
            sh(RUN, "stop", env=eb)                                        # finishes the round in progress, checkpoints, exits 0
            self.assertLess(time.time() - t0, 175)
            self.assertEqual(unit_state("hyst-wo10-k5test-b").get("ActiveState"), "inactive")
            stopped_at = progress(tb)["round"]
            self.assertGreaterEqual(stopped_at, r_frozen)
            self.assertLess(stopped_at, 4)
            self.assertTrue((Path(tb) / "ckpt.pkl").exists())
            sh(RUN, "start", env=eb)                                       # start again from the checkpoint
            wait(lambda: unit_state("hyst-wo10-k5test-b").get("ActiveState") == "inactive", 900, "B to finish")
            ca, cb = [pickle.loads((Path(d) / "ckpt.pkl").read_bytes()) for d in (ta, tb)]
            self.assertEqual(ca["trainer"]["epoch"], 3)
            self.assertEqual(cb["trainer"]["epoch"], 3)
            # Finding (2026-11-05): two UNINTERRUPTED runs of this same command, in separate processes, give one of two reproducible results that differ by 4.0e-12 (float64
            # summation order in XLA CPU; not caused by stop/resume, and the same with PYTHONHASHSEED fixed). In ONE process a resume is bit-identical (test_k5_train.Run). Across processes
            # the bound is therefore 1e-9, 250 times that noise floor.
            worst = max(float(np.abs(x - y).max()) for x, y in zip(jax.tree_util.tree_leaves(ca["trainer"]["P"]), jax.tree_util.tree_leaves(cb["trainer"]["P"])))
            print(f"max parameter difference, interrupted vs uninterrupted: {worst:.3e}")
            self.assertLess(worst, 1e-9)
            np.testing.assert_array_equal(ca["trainer"]["key"], cb["trainer"]["key"])
            # the 20 s frozen are not in B's compute clock: its spent time is well below the wall time of its two runs
            self.assertGreater(cb["extra"]["spent_s"], 0)
            self.assertLess(progress(tb)["spent_h"] * 3600, ca["extra"]["spent_s"] * 3 + 600)


if __name__ == "__main__":
    unittest.main()
