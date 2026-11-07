"""Z1/Z2 tests: --device guard, and SIGTERM mid-epoch then resume == uninterrupted run (toy: tiny songs, short chunks).

The kill test runs `fit` in child processes (this file with `child OUT_DIR`), so a real SIGTERM hits a real mid-epoch run.
Tolerance: parameters equal to atol 1e-6 / rtol 1e-5 (same as test_train's resume test); the run reports the max abs difference it got.
"""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import torch

import core
import train

HERE = Path(__file__).resolve().parent
EPOCHS = 2
SONGS = [np.random.default_rng(i).standard_normal((n, core.N_IN)).astype(np.float32) for i, n in enumerate((30000, 27000, 24000, 21000))]


def child(out_dir, ckpt_every_s):
    train.CHUNK = 400
    tracks = [train.Track(str(i), "", "", "train") for i in range(len(SONGS))]
    torch.manual_seed(0)
    model = core.Core()
    meta = train.fit(model, tracks, tracks[:1], lambda t: SONGS[int(t.id)], out_dir, EPOCHS, batch=2, cap_s=1e9,
                     load_len=lambda t: len(SONGS[int(t.id)]), ckpt_every_s=ckpt_every_s)
    if not meta.get("terminated"):
        torch.save(model.state_dict(), Path(out_dir) / "final.pt")


def spawn(out_dir, ckpt_every_s):
    return subprocess.Popen([sys.executable, "-u", str(Path(__file__)), "child", str(out_dir), str(ckpt_every_s)], cwd=HERE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


class TestDevice(unittest.TestCase):
    def test_cpu_touches_no_cuda(self):
        boom = mock.Mock(side_effect=AssertionError("cuda path called on cpu"))
        with mock.patch.object(torch, "set_default_device", boom), mock.patch.object(torch.Tensor, "cuda", boom):
            m = core.use_device(core.Core(), "cpu")
        self.assertEqual(next(m.parameters()).device.type, "cpu")
        boom.assert_not_called()

    @unittest.skipIf(torch.cuda.is_available(), "cuda present")
    def test_cuda_without_a_device_is_a_clear_error(self):
        with self.assertRaises(SystemExit):
            core.use_device(core.Core(), "cuda")

    @unittest.skipUnless(torch.cuda.is_available(), "no cuda")
    def test_cuda_forward_matches_cpu(self):
        x = torch.from_numpy(SONGS[0][:300])[None]
        torch.manual_seed(0)
        cpu = core.Core().eval()
        with torch.no_grad():
            ref, _ = cpu(x, cpu.init_state())
        gpu = core.use_device(core.Core().eval(), "cuda")
        with torch.no_grad():
            out, _ = gpu(x.cuda(), gpu.init_state())
        torch.testing.assert_close(out[0]["mean"].cpu(), ref[0]["mean"], atol=1e-3, rtol=1e-3)
        torch.set_default_device("cpu")


class TestKillAndResume(unittest.TestCase):
    def test_sigterm_mid_epoch_then_resume_equals_uninterrupted(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "straight", Path(d) / "killed"
            p = spawn(a, 1e9)
            self.assertEqual(p.wait(timeout=900), 0, p.stdout.read())
            q = spawn(b, 0.5)                         # a mid-epoch checkpoint every half second
            t0 = time.time()
            while not (b / "mid.pt").exists():
                self.assertLess(time.time() - t0, 600, "no mid-epoch checkpoint appeared")
                if q.poll() is not None:
                    self.fail(f"child ended before a mid-epoch checkpoint: {q.stdout.read()}")
                time.sleep(0.2)
            q.send_signal(signal.SIGTERM)
            out = q.communicate(timeout=120)[0]
            self.assertIn("SIGTERM: mid-epoch checkpoint written", out)
            self.assertFalse((b / "final.pt").exists())
            mid = torch.load(b / "mid.pt", weights_only=False)["mid"]
            self.assertGreater(mid["batch"], 0)
            r = spawn(b, 1e9)
            out2 = r.communicate(timeout=900)[0]
            self.assertEqual(r.returncode, 0, out2)
            self.assertIn("resumed inside epoch", out2)
            self.assertFalse((b / "mid.pt").exists())
            sa, sb = torch.load(a / "final.pt"), torch.load(b / "final.pt")
            worst = max(float((sa[k] - sb[k]).abs().max()) for k in sa if sa[k].is_floating_point())
            print(f"\nmax abs parameter difference, killed+resumed vs straight: {worst:.3e}")
            for k in sa:
                torch.testing.assert_close(sa[k], sb[k], atol=1e-6, rtol=1e-5, msg=k)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        child(sys.argv[2], float(sys.argv[3]))
    else:
        unittest.main()
