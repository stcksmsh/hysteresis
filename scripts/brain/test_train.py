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


def leaves(seed, B=1, T=600):
    """4 layers of random leaf (mean, logvar) tensors and an x whose features are constant in time, so every valid target is that constant."""
    g = torch.Generator().manual_seed(seed)
    c = torch.randn(core.FEAT, generator=g)
    x = torch.zeros(B, T + train.LOOK, core.N_IN)
    x[..., :core.FEAT] = c
    out = [{"mean": torch.randn(B, T, core.FEAT, generator=g).requires_grad_(), "logvar": (torch.randn(B, T, core.FEAT, generator=g) - 1).requires_grad_()}
           for _ in range(4)]
    return out, x, c


class TestBetaNLL(Base):
    def test_round_two_constants(self):
        self.assertEqual((self.old, train.LOOK, train.BETA, train.EPOCHS, train.PATIENCE, train.CAP_S), (18000, 1600, 0.5, 12, 2, 20 * 3600))

    def test_beta_zero_is_the_plain_nll(self):
        out, x, _ = leaves(0)
        nv = torch.tensor([600])
        b0, plain, _, _ = train.chunk_terms(out, x, nv, beta=0.0)
        for a, b in zip(b0, plain):
            self.assertEqual(float(a), float(b))
        for a, (b, _) in zip(b0, zip(*train.chunk_nll(out, x, nv))):
            self.assertEqual(float(a), float(b))

    def test_beta_half_gradient_weighting(self):
        out, x, c = leaves(1)
        nv = torch.tensor([600])
        sums, plain, _, counts = train.chunk_terms(out, x, nv, beta=0.5)
        sums[0].backward()
        o = out[0]
        valid = torch.tensor([float(t + 2 * core.HORIZONS[0] <= 600) for t in range(600)])[None, :, None]
        var = torch.exp(o["logvar"].detach())
        w = var ** 0.5                                     # sigma ** (2 beta), beta 0.5
        mean_grad = w * (o["mean"].detach() - c) / var / core.FEAT * valid
        logvar_grad = w * 0.5 * (1 - (c - o["mean"].detach()) ** 2 / var) / core.FEAT * valid       # the weight itself carries no gradient
        torch.testing.assert_close(o["mean"].grad, mean_grad, rtol=1e-4, atol=1e-6)
        torch.testing.assert_close(o["logvar"].grad, logvar_grad, rtol=1e-4, atol=1e-6)
        self.assertGreater(float(counts[0]), 0)
        # the value is the weighted NLL, not the plain one
        self.assertNotAlmostEqual(float(sums[0].detach()), float(plain[0].detach()), places=3)

    def test_plain_nll_and_mse_terms_are_unweighted(self):
        out, x, c = leaves(2)
        nv = torch.tensor([600])
        _, plain, mse, counts = train.chunk_terms(out, x, nv, beta=0.5)
        o = out[1]
        valid = torch.tensor([float(t + 2 * core.HORIZONS[1] <= 600) for t in range(600)])[None]
        lv, m = o["logvar"].detach(), o["mean"].detach()
        want_nll = ((0.5 * (lv + (c - m) ** 2 * torch.exp(-lv) + math.log(2 * math.pi))).mean(-1) * valid).sum()
        want_mse = (((c - m) ** 2).mean(-1) * valid).sum()
        self.assertAlmostEqual(float(plain[1]), float(want_nll), places=2)
        self.assertAlmostEqual(float(mse[1]), float(want_mse), places=2)


class TestGradCheckpoint(Base):
    def test_same_loss_and_gradients(self):
        torch.manual_seed(0)
        x = torch.from_numpy(song(300 + train.LOOK, 9))[None]
        res = []
        for flag in (False, True):
            m = core.Core()
            m.grad_checkpoint = flag
            out, _ = m(x[:, :300], m.init_state(1))
            sums, _, _, counts = train.chunk_terms(out, x, torch.tensor([300 + train.LOOK]), chunk=300, beta=0.5)
            loss = sum(a / max(float(c), 1.0) for a, c in zip(sums, counts))
            loss.backward()
            res.append((float(loss), {n: p.grad.clone() for n, p in m.named_parameters()}))
        self.assertGreater(abs(res[0][0]), 0)
        self.assertEqual(res[0][0], res[1][0])
        self.assertEqual(res[0][1].keys(), res[1][1].keys())
        for n in res[0][1]:
            torch.testing.assert_close(res[0][1][n], res[1][1][n], rtol=1e-5, atol=1e-7, msg=n)


class TestEarlyStop(unittest.TestCase):
    def run_curve(self, curve, patience=2):
        meta = {"best_score": None, "best_epoch": 0, "bad_epochs": 0}
        for e, v in enumerate(curve, 1):
            best, stop = train.early_stop_step(meta, e, v, patience)
            if stop:
                return meta, e
        return meta, len(curve)

    def test_picks_the_lowest_and_waits_patience(self):
        meta, ended = self.run_curve([5.0, 4.0, 3.0, 3.5, 3.2, 2.0])
        self.assertEqual((meta["best_epoch"], ended), (3, 5))        # two epochs without improvement end it; epoch 6 is never reached

    def test_improvement_resets_patience(self):
        meta, ended = self.run_curve([5.0, 6.0, 4.0, 4.5, 3.0, 3.1, 3.2])
        self.assertEqual((meta["best_epoch"], ended), (5, 7))

    def test_tie_keeps_the_earlier_epoch(self):
        meta, ended = self.run_curve([5.0, 3.0, 3.0, 3.0, 2.9])
        self.assertEqual((meta["best_epoch"], meta["best_score"], ended), (2, 3.0, 4))
        meta, _ = self.run_curve([4.0, 3.0, 3.0, 2.5])
        self.assertEqual(meta["best_epoch"], 4)

    def test_full_curve_never_stops_while_improving(self):
        meta, ended = self.run_curve([12 - e for e in range(12)])
        self.assertEqual((meta["best_epoch"], ended), (12, 12))


class TestChunking(Base):
    def test_chunked_epoch_equals_one_forward(self):
        T = 1700
        s = song(T, 0)
        tracks, load = tracks_of([s])
        model = core.Core(head_norm=True).eval()
        chunked = train.run_epoch(model, tracks, load, 1, 0, 0, beta=0.0)[0]["nll"]
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

    def test_best_checkpoint_is_the_lowest_validation_epoch(self):
        m, meta = self.fit("best", 3)
        scores = [r["val_score"] for r in meta["log"]]
        self.assertEqual(len(scores), meta["epoch"])
        want = int(np.argmin(scores)) + 1                                      # np.argmin: the earlier epoch on a tie
        self.assertEqual(meta["best_epoch"], want)
        best, bmeta = train.load_model(Path(self.dir) / "best" / "best.pt")
        ep, _ = train.load_model(Path(self.dir) / "best" / f"epoch_{want:03d}.pt")
        for (k, x), (_, y) in zip(best.state_dict().items(), ep.state_dict().items()):
            self.assertTrue(torch.equal(x, y), k)
        self.assertEqual(bmeta["epoch"], want)
        self.assertFalse(bmeta["cut"])
        for r in meta["log"]:
            for k in ("train_beta_nll", "train_nll", "train_mse", "val_beta_nll", "val_nll", "val_mse"):
                self.assertEqual(len(r[k]), 4)
            self.assertAlmostEqual(r["val_score"], sum(r["val_beta_nll"]), places=9)

    def test_wall_cap_keeps_the_best_checkpoint_and_marks_it_cut(self):
        _, first = self.fit("cutrun", 1)
        self.assertFalse(train.load_model(Path(self.dir) / "cutrun" / "best.pt")[1]["cut"])
        m = core.Core()
        meta = train.fit(m, self.tracks, self.tracks[:1], self.load, Path(self.dir) / "cutrun", 3, batch=2, cap_s=first["wall_s"],
                         load_len=lambda t: len(self.songs[int(t.id)]), log=lambda *_: None)
        self.assertTrue(meta["stopped_by_cap"] and meta["cut"])
        self.assertEqual(meta["epoch"], 1)                                     # the epoch cut in the middle does not count
        best, bmeta = train.load_model(Path(self.dir) / "cutrun" / "best.pt")
        self.assertTrue(bmeta["cut"] and bmeta["stopped_by_cap"])
        self.assertEqual(bmeta["best_epoch"], 1)
        ep1, _ = train.load_model(Path(self.dir) / "cutrun" / "epoch_001.pt")
        for (k, x), (_, y) in zip(best.state_dict().items(), ep1.state_dict().items()):
            self.assertTrue(torch.equal(x, y), k)

    def test_fit_needs_validation_tracks(self):
        with self.assertRaises(ValueError):
            train.fit(core.Core(), self.tracks, [], self.load, Path(self.dir) / "noval", 1, batch=2, log=lambda *_: None)

    def test_checkpoint_loads_to_the_same_model(self):
        m, _ = self.fit("load", 1)
        m2, meta = train.load_model(Path(self.dir) / "load" / "epoch_001.pt")
        for (k, x), (_, y) in zip(m.state_dict().items(), m2.state_dict().items()):
            self.assertTrue(torch.equal(x, y), k)
        self.assertEqual(meta["epoch"], 1)


class TestValSplit(unittest.TestCase):
    ROWS = [(100 * a + i, "train" if a < 40 else "heldout", a) for a in range(50) for i in range(1 + a % 3)]

    def test_artist_level_and_disjoint(self):
        import val_split
        arts = val_split.choose(self.ROWS)
        self.assertEqual(len(arts), 4)                                          # round(0.1 * 40 training artists)
        self.assertTrue(set(arts) <= set(range(40)))                            # never a held-out artist
        self.assertEqual(arts, val_split.choose(self.ROWS))                     # fixed seed
        self.assertNotEqual(arts, val_split.choose(self.ROWS, seed=val_split.SEED + 1))
        ids = val_split.track_ids(self.ROWS, arts)
        art_of = {t: a for t, _, a in self.ROWS}
        self.assertEqual({art_of[t] for t in ids}, set(arts))
        self.assertEqual(len(ids), sum(1 + a % 3 for a in arts))
        tracks = [train.Track(str(t), "", "", s) for t, s, _ in self.ROWS]
        fit, val = val_split.split_tracks([t for t in tracks if t.split == "train"], set(ids))
        held = {art_of[int(t.id)] for t in tracks if t.split == "heldout"}
        self.assertFalse({art_of[int(t.id)] for t in val} & {art_of[int(t.id)] for t in fit})
        self.assertFalse({art_of[int(t.id)] for t in val + fit} & held)
        self.assertEqual(len(fit) + len(val), sum(1 for _, s, _ in self.ROWS if s == "train"))

    def test_committed_list_matches_the_corpus(self):
        import val_split
        if not val_split.CORPUS_CSV.exists():
            self.skipTest("corpus list not on this machine")
        rows = val_split.read_rows()
        d = json.loads(val_split.ARTISTS_JSON.read_text())
        held = {a for _, s, a in rows if s == "heldout"}
        train_art = {a for _, s, a in rows if s == "train"}
        self.assertEqual(d["artists"], val_split.choose(rows, d["seed"], d["frac"]))
        self.assertFalse(set(d["artists"]) & held)
        self.assertTrue(set(d["artists"]) <= train_art)
        self.assertEqual(d["track_ids"], val_split.track_ids(rows, d["artists"]))
        self.assertEqual(len(d["artists"]), round(0.1 * len(train_art)))


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
