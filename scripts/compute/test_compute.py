"""Tests for scripts/compute (stdlib unittest + numpy; no network, no Kaggle account).

    cd scripts/compute && python -m unittest -v test_compute
"""
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "kaggle"))
import code_snapshot  # noqa: E402
import make_kernel  # noqa: E402
import manifest as mf  # noqa: E402
import pack_features  # noqa: E402
import run_job  # noqa: E402

PY = sys.executable


def job(tmp, cmd, **kw):
    j = {"id": "t-1", "cmd": cmd, "wall_limit_s": 30, "idle_limit_s": 30, "grace_s": 2, **kw}
    p = Path(tmp) / "job.json"
    p.write_text(json.dumps(j))
    return p


class RunJob(unittest.TestCase):
    def run_it(self, cmd, prev="", **kw):
        tmp = tempfile.mkdtemp()
        p = job(tmp, cmd, **kw)
        rc = run_job.main([str(p), "--repo", tmp, "--out", f"{tmp}/out", "--ckpt", f"{tmp}/ckpt", "--prev", prev])
        status = json.loads(Path(f"{tmp}/out/status.json").read_text())
        log = Path(f"{tmp}/out/log.txt").read_text()
        return rc, status, log, tmp

    def test_done_and_placeholders(self):
        rc, st, log, tmp = self.run_it([PY, "-c", "import os,sys;print(sys.argv[1], os.environ['HYST_JOB_ID'])", "{OUT}"])
        self.assertEqual((rc, st["state"], st["exit_code"]), (0, "done", 0))
        self.assertIn(f"{tmp}/out t-1", log)

    def test_failed(self):
        rc, st, _, _ = self.run_it([PY, "-c", "raise SystemExit(3)"])
        self.assertEqual((rc, st["state"], st["exit_code"]), (1, "failed", 3))

    def test_wall_limit(self):
        t0 = time.time()
        rc, st, log, _ = self.run_it([PY, "-c", "import time\nwhile True:\n print('x', flush=True); time.sleep(0.2)"],
                                     wall_limit_s=2)
        self.assertEqual((rc, st["state"]), (2, "killed_wall"))
        self.assertLess(time.time() - t0, 15)
        self.assertIn("killed_wall", log)

    def test_idle_limit_and_progress_file(self):
        rc, st, _, _ = self.run_it([PY, "-c", "import time; time.sleep(60)"], idle_limit_s=2)
        self.assertEqual(st["state"], "killed_idle")
        # a job that is silent on stdout but touches its progress file is not idle
        code = ("import time,pathlib,sys\np=pathlib.Path(sys.argv[1])\nfor i in range(8):\n"
                " p.write_text(str(i)); time.sleep(0.5)")
        rc, st, _, _ = self.run_it([PY, "-c", code, "{OUT}/progress.json"], idle_limit_s=2,
                                   progress_file="{OUT}/progress.json")
        self.assertEqual(st["state"], "done")

    def test_sigterm_lets_job_checkpoint(self):
        code = ("import signal,time,pathlib,sys\n"
                "def h(*a):\n pathlib.Path(sys.argv[1]).write_text('saved'); sys.exit(0)\n"
                "signal.signal(signal.SIGTERM, h)\nwhile True: time.sleep(0.1)")
        rc, st, _, tmp = self.run_it([PY, "-c", code, "{CKPT}/last.pt"], wall_limit_s=1)
        self.assertEqual(st["state"], "killed_wall")
        self.assertEqual(Path(f"{tmp}/ckpt/last.pt").read_text(), "saved")

    def test_prev_copied_into_ckpt(self):
        prev = tempfile.mkdtemp()
        Path(prev, "last.pt").write_text("epoch3")
        rc, st, log, _ = self.run_it([PY, "-c", "import sys;print(open(sys.argv[1]).read())", "{CKPT}/last.pt"], prev=prev)
        self.assertEqual(st["copied_from_prev"], 1)
        self.assertIn("epoch3", log)

    def test_bad_job(self):
        tmp = tempfile.mkdtemp()
        p = Path(tmp) / "j.json"
        p.write_text(json.dumps({"id": "bad id", "cmd": ["x"], "wall_limit_s": 1}))
        with self.assertRaises(ValueError):
            run_job.load_job(p)


class Manifest(unittest.TestCase):
    def test_build_verify_tamper(self):
        d = Path(tempfile.mkdtemp())
        (d / "a").mkdir()
        (d / "a" / "x.bin").write_bytes(b"123")
        (d / "y.txt").write_text("hi")
        self.assertEqual(mf.build(d), 2)
        self.assertEqual(mf.verify(d), [])
        (d / "y.txt").write_text("changed")
        (d / "a" / "x.bin").unlink()
        self.assertEqual(sorted(mf.verify(d)), ["changed y.txt", "missing a/x.bin"])

    def test_dataset_metadata_is_skipped(self):
        d = Path(tempfile.mkdtemp())
        (d / "y.txt").write_text("hi")
        (d / "dataset-metadata.json").write_text("{}")
        self.assertEqual(mf.build(d), 1)
        self.assertNotIn("dataset-metadata", (d / mf.NAME).read_text())
        (d / mf.NAME).write_text((d / mf.NAME).read_text() + "0" * 64 + "  dataset-metadata.json\n")    # an older manifest that listed it
        (d / "dataset-metadata.json").write_text('{"changed": 1}')
        self.assertEqual(mf.verify(d), [])


class Pack(unittest.TestCase):
    def test_pack_relative_float16(self):
        src = Path(tempfile.mkdtemp())
        rng = np.random.default_rng(0)
        entries = []
        for i, split in enumerate(["train", "heldout", "train"]):
            x = rng.normal(size=(500, 44)).astype(np.float32)
            np.save(src / f"f{i}.npy", x)
            np.save(src / f"b{i}.npy", np.arange(10, dtype=np.float64))
            entries.append({"id": f"t{i}", "audio": f"/abs/{i}.mp3", "feats": str(src / f"f{i}.npy"),
                            "beats": f"b{i}.npy", "split": split})
        (src / "manifest.json").write_text(json.dumps(entries))
        np.savez(src / "stats.npz", mean=np.zeros(44), std=np.ones(44))
        out = Path(tempfile.mkdtemp()) / "pack"
        n, err = pack_features.pack(src / "manifest.json", src / "stats.npz", out, slug="u/hyst-features",
                                    splits=["train"])
        self.assertEqual(n, 2)
        self.assertLess(err, 1e-2)
        m = json.loads((out / "manifest.json").read_text())
        self.assertEqual([e["feats"] for e in m], ["feats/t0.npy", "feats/t2.npy"])
        self.assertIsNone(m[0]["audio"])
        self.assertEqual(np.load(out / m[0]["feats"]).dtype, np.float16)
        self.assertTrue((out / m[1]["beats"]).is_file())
        self.assertEqual(json.loads((out / "HYST_DATASET.json").read_text())["name"], "hyst-features")
        self.assertEqual(mf.verify(out), [])


    def test_stats_file_with_sd_key_scales_the_cast_error(self):
        src = Path(tempfile.mkdtemp())
        np.save(src / "f.npy", np.random.default_rng(0).normal(size=(500, 44)).astype(np.float32))
        np.save(src / "b.npy", np.arange(10, dtype=np.float64))
        (src / "manifest.json").write_text(json.dumps([{"id": "t", "audio": None, "feats": "f.npy", "beats": "b.npy", "split": "train"}]))
        errs = {}
        for name, key, sd in (("one", "sd", 1.0), ("hundred", "sd", 100.0), ("std_key", "std", 100.0)):
            np.savez(src / "stats.npz", mean=np.zeros(44), **{key: sd * np.ones(44)})
            errs[name] = pack_features.pack(src / "manifest.json", src / "stats.npz", Path(tempfile.mkdtemp()) / "p")[1]
        self.assertAlmostEqual(errs["one"] / errs["hundred"], 100.0, places=3)     # `sd` is read, not ignored (raw units)
        self.assertEqual(errs["hundred"], errs["std_key"])


class Snapshot(unittest.TestCase):
    def test_snapshot_and_dirty_refusal(self):
        repo = Path(tempfile.mkdtemp())
        g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True)  # noqa: E731
        g("init", "-q")
        g("config", "user.email", "t@t")
        g("config", "user.name", "t")
        (repo / "f.py").write_text("print(1)\n")
        g("add", ".")
        g("commit", "-qm", "c")
        out = Path(tempfile.mkdtemp()) / "code"
        full = code_snapshot.snapshot(repo, "HEAD", out, slug="u/hyst-code")
        self.assertEqual(len(full), 40)
        self.assertTrue((out / "code.tar.gz").stat().st_size > 0)
        self.assertEqual(mf.verify(out), [])
        (repo / "f.py").write_text("print(2)\n")
        with self.assertRaises(SystemExit):
            code_snapshot.snapshot(repo, "HEAD", Path(tempfile.mkdtemp()))


class Kernel(unittest.TestCase):
    def test_make_kernel(self):
        tmp = Path(tempfile.mkdtemp())
        meta = make_kernel.make(HERE / "jobs" / "bench_b7.json", "user", tmp, "user/hyst-code", ["user/hyst-features"],
                                prev_kernel="user/hyst-job-prev", pip="mujoco")
        self.assertEqual(meta["id"], "user/hyst-job-bench-b7-001")
        self.assertTrue(meta["is_private"])
        self.assertEqual(meta["kernel_sources"], ["user/hyst-job-prev"])
        loaded = json.loads((tmp / "kernel-metadata.json").read_text())
        self.assertEqual(loaded["code_file"], "run.py")
        py_compile.compile(str(tmp / "run.py"), doraise=True)
        self.assertIn('"bench-b7-001"', (tmp / "run.py").read_text())

    def test_example_jobs_valid(self):
        for p in (HERE / "jobs").glob("*.json"):
            run_job.load_job(p)


if __name__ == "__main__":
    unittest.main()
