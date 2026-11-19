"""cd scripts/body && OMP_NUM_THREADS=3 taskset -c 12-14 /secondary/hyst-env/body/bin/python -m unittest -v test_k5p2_eval    (JAX env; compiles the pass2 body, minutes)
Reads (never writes) /secondary/hyst-data/body/k5p2/run/best.pkl; writes only to temp directories."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import k5p2_eval as X
import k5p2_train as P2
import k5_video_roll as VR
import m3d
import m3e_jax as M
import m3f_controls as MFC

HERE = Path(__file__).resolve().parent


class Pure(unittest.TestCase):
    def test_report_lines_on_synthetic_rollout(self):
        t = np.arange(240 * 50) / 100.0
        q = np.zeros((2, 240, 50, 5))
        for j in range(5):
            q[..., j] = (20 * np.sin(0.7 * t + j)).reshape(240, 50)[None]
        q[0, 10:30, :, 1] = 110.0                       # shoulder held on the stop
        with tempfile.TemporaryDirectory() as d:
            r = X.report_lines(q, d, "syn")
        self.assertGreater(r["parking"]["share_on_stop"]["shoulder"], 0.0)
        self.assertGreater(r["shoulder_at_limit_share"], 0.0)
        self.assertEqual(r["end_stops"]["summary"]["events_total"]["shoulder"], 1)
        self.assertIn("50", {str(h) for h in (50,)})
        self.assertEqual(len(r["eprime"]["acc_p99"]), 2)

    def test_pad_chunks(self):
        inps = {"x": jnp.ones((1, 13, 3)), "R": jnp.ones((1, 13))}
        p, nb = X.pad_chunks(inps, 8)
        self.assertEqual((p["x"].shape[1], p["R"].shape[1], nb), (16, 16, 13))


class Rollout(unittest.TestCase):
    def test_continuous_first_60s_equals_windowed_rollout(self):
        """The full-song rollout over its first 120 blocks is bit-identical to the K5 window rollout of the same blocks (same start seed 4242, chunk 8)."""
        C = M.load_cb()
        cfg = P2.CFG
        P = MFC.initial_policy(cfg)
        fns = X.make_fns(C, cfg)
        z = np.load(VR.DANCED / "lanes" / "presence.npz")
        inps, _ = X.episode_inputs(z["y"], z["phi_end"], z["omega"])
        inps = {k: v[:, :128] for k, v in inps.items()}
        cont = X.rollout_song(fns, cfg, C, P, inps)
        toy = P2.WindowToyF(z["y"][None, :120], z["phi_end"][None, :120], z["omega"][None, :120])
        toy._r()
        win = P2.rollout_batched(fns, cfg, C, P, toy, slice(0, 1), "argmax", jax.random.PRNGKey(0), VR.START_SEED, batch=1)
        for k in ("q", "desc", "idesc", "pi", "kappa"):
            np.testing.assert_array_equal(cont[k][:120], win[k][0], err_msg=k)


class EndToEnd(unittest.TestCase):
    def test_small_check_songs_summary_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            base = [sys.executable, "-u", str(HERE / "k5p2_eval.py")]
            common = ["--policy", "/secondary/hyst-data/body/k5p2/run/best.pkl", "--out", d]
            run = lambda *args: subprocess.run(base + list(args) + common, capture_output=True, text=True, cwd=str(HERE))
            r = run("check", "--max-windows", "6", "--modes", "argmax")
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            chk = json.loads((Path(d) / "check.json").read_text())
            self.assertIn("report_only_heldout_windows_trained_argmax", chk)
            self.assertIn("paired_vs_trained_kappa0", chk["modes"]["argmax"]["ext"])
            r = run("songs", "--max-blocks", "24", "--songs", "presence")
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            s = json.loads((Path(d) / "songs" / "presence.json").read_text())
            self.assertIn("accepted", s["check_csv"])
            self.assertEqual(s["audio_blocks"], 24)
            self.assertIn("e1_pass", s["eprime_vs_v47"])
            self.assertTrue((Path(d) / "songs" / "presence.pass2.csv").exists())
            r2 = run("songs", "--max-blocks", "24", "--songs", "presence")                 # resume: kept, same file
            self.assertIn("kept", r2.stdout)
            r = run("summary")
            self.assertEqual(r.returncode, 0, r.stdout[-2000:] + r.stderr[-2000:])
            sm = json.loads((Path(d) / "summary.json").read_text())
            self.assertIn("pass2_bar", sm)


if __name__ == "__main__":
    unittest.main()
