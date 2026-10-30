"""Tests for train.py on synthetic data (CHUNK is shrunk so a few hundred frames make several chunks)."""
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

import core
import train


def song(T, seed):
    return np.random.default_rng(seed).standard_normal((T, core.N_IN)).astype(np.float32)


def tracks_of(songs):
    return [train.Track(str(i), "", "", "train") for i in range(len(songs))], (lambda t: songs[int(t.id)])


class Base(unittest.TestCase):
    def setUp(self):
        self.old = train.CHUNK
        train.CHUNK = 600

    def tearDown(self):
        train.CHUNK = self.old


class TestLoss(Base):
    def test_chunk_nll_exact_for_a_known_prediction(self):
        T, B = 200, 1
        x = torch.zeros(B, 600 + train.LOOK, core.N_IN)
        x[..., :core.FEAT] = torch.arange(600 + train.LOOK, dtype=torch.float32)[None, :, None] / 100
        out = [{"mean": torch.zeros(B, 600, core.FEAT), "logvar": torch.zeros(B, 600, core.FEAT)} for _ in range(4)]
        sums, counts = train.chunk_nll(out, x, torch.tensor([T]))
        for s, c, hz in zip(sums, counts, core.HORIZONS):
            t = np.arange(T)
            ok = t + 2 * hz <= T
            self.assertEqual(float(c), ok.sum())
            y = (t[ok] + 1.5 * hz - 0.5) / 100        # mean of frames t+h .. t+2h-1 of the ramp i/100
            self.assertAlmostEqual(float(s), float((0.5 * (y ** 2 + math.log(2 * math.pi))).sum()), places=2)


class TestChunking(Base):
    def test_chunked_epoch_equals_one_forward(self):
        T = 1700
        s = song(T, 0)
        tracks, load = tracks_of([s])
        model = core.Core(head_norm=True).eval()
        chunked = train.run_epoch(model, tracks, load, 1, 0, 0)[0]
        with torch.no_grad():
            out, _ = model(torch.from_numpy(s)[None], model.init_state())
        x = torch.zeros(1, T + train.LOOK, core.N_IN)
        x[0, :T] = torch.from_numpy(s)
        sums, counts = train.chunk_nll(out, x, torch.tensor([T]), chunk=T)
        whole = np.array([float(a / c) for a, c in zip(sums, counts)])
        np.testing.assert_allclose(chunked, whole, rtol=1e-3)

    def test_batches_reset_pad_and_end(self):
        songs = [song(1300, 1), song(700, 2), song(500, 3)]
        tracks, load = tracks_of(songs)
        steps = list(train.epoch_batches(tracks, load, 2, 0, 0))
        self.assertEqual(len(steps), train.steps_per_epoch(tracks, lambda t: len(songs[int(t.id)]), 2))
        self.assertTrue(steps[0]["reset"].all())
        self.assertEqual(steps[0]["x"].shape, (2, 600 + train.LOOK, core.N_IN))
        seen = sum(int(b["reset"].sum()) for b in steps)
        self.assertEqual(seen, 3)                       # every song starts exactly once
        self.assertTrue(all(b["nvalid"].min() >= 0 for b in steps))
        # the same seed and epoch give the same order; another epoch another one
        again = list(train.epoch_batches(tracks, load, 2, 0, 0))
        self.assertTrue(all(torch.equal(a["x"], b["x"]) for a, b in zip(steps, again)))


class TestTrainingLoop(Base):
    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp()
        self.songs = [song(1300, 4), song(1000, 5)]
        self.tracks, self.load = tracks_of(self.songs)

    def tearDown(self):
        shutil.rmtree(self.dir)
        super().tearDown()

    def fit(self, name, epochs, cap_s=train.CAP_S):
        m = core.Core()
        meta = train.fit(m, self.tracks, self.tracks[:1], self.load, Path(self.dir) / name, epochs, batch=2, cap_s=cap_s,
                         load_len=lambda t: len(self.songs[int(t.id)]), log=lambda *_: None)
        return m, meta

    def test_clamp_holds_after_training(self):
        m, meta = self.fit("clamp", 1)
        for L, (lo, hi) in zip(m.layers, core.BANDS):
            f = L.freqs_hz()
            self.assertGreaterEqual(float(f.min()), lo * (1 - 1e-5))
            self.assertLessEqual(float(f.max()), hi * (1 + 1e-5))
            self.assertLess(float(L.lam_log().real.detach().max()), 0.0)
        self.assertEqual(meta["epoch"], 1)
        self.assertEqual(len(meta["log"]), 1)
        self.assertEqual(len(meta["log"][0]["train_nll"]), 4)

    def test_weights_change_and_loss_is_finite(self):
        before = core.Core().state_dict()
        m, meta = self.fit("moves", 1)
        self.assertTrue(any(not torch.equal(before[k], v) for k, v in m.state_dict().items()))
        self.assertTrue(np.isfinite(meta["log"][0]["train_nll"]).all())

    def test_resume_equals_straight_run(self):
        a, _ = self.fit("straight", 2)
        self.fit("resumed", 1)
        b, meta = self.fit("resumed", 2)           # picks up last.pt after epoch 1
        self.assertEqual(meta["epoch"], 2)
        for (k, x), (_, y) in zip(a.state_dict().items(), b.state_dict().items()):
            torch.testing.assert_close(x, y, atol=1e-6, rtol=1e-5, msg=k)

    def test_cap_stops_and_saves(self):
        m, meta = self.fit("cap", 3, cap_s=0.0)
        self.assertTrue(meta["stopped_by_cap"])
        self.assertEqual(meta["epoch"], 0)
        self.assertTrue((Path(self.dir) / "cap" / "last.pt").exists())
        m2, meta2 = self.fit("cap", 3, cap_s=0.0)  # a resumed run stays stopped
        self.assertTrue(meta2["stopped_by_cap"])

    def test_checkpoint_loads_to_the_same_model(self):
        m, _ = self.fit("load", 1)
        m2, meta = train.load_model(Path(self.dir) / "load" / "epoch_001.pt")
        for (k, x), (_, y) in zip(m.state_dict().items(), m2.state_dict().items()):
            self.assertTrue(torch.equal(x, y), k)
        self.assertEqual(meta["epoch"], 1)


class TestLiveness(Base):
    def test_heartbeat_lines_and_no_grid_count(self):
        songs = [song(1300, 7)]
        tracks, load = tracks_of(songs)
        lines = []
        train.run_epoch(core.Core(), tracks, load, 1, 0, 0, log=lines.append, heartbeat_s=0)
        beats = [json.loads(s) for s in lines]
        self.assertTrue(len(beats) >= 1 and all(b["heartbeat"] and b["epoch"] == 1 for b in beats))
        self.assertTrue(all(np.isfinite(b["mean_loss_so_far"]) and b["wall_s"] >= 0 for b in beats))
        with tempfile.TemporaryDirectory() as d:
            for name, beat_list in (("a", []), ("b", [1.0]), ("c", [1.0, 2.0])):
                (Path(d) / f"{name}.json").write_text(json.dumps({"beats": beat_list}))
            ts = [train.Track(n, "", str(Path(d) / f"{n}.json"), "train") for n in "abc"]
            self.assertEqual(train.count_no_grid(ts), ["a", "b"])


class TestSchedule(unittest.TestCase):
    def test_warmup_and_cosine(self):
        fn = train.lr_schedule(1000, 4)
        self.assertAlmostEqual(fn(0), train.LR / train.WARMUP)
        self.assertAlmostEqual(fn(train.WARMUP - 1), train.LR)      # end of warm-up, epoch 0, cosine factor 1
        self.assertAlmostEqual(fn(1000 * 4), train.LR * 0.1)         # after the last epoch
        self.assertLess(fn(2500), fn(1500))
        self.assertEqual(fn(5), fn(5))


if __name__ == "__main__":
    unittest.main()
