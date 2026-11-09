"""Stage 3 trainer tests (work order 26B). cd scripts/body && taskset -c 12-17 /secondary/hyst-env/body/bin/python -m unittest -v test_s3_train
(JAX env; the Run tests compile the M3f body with gradients, minutes). 26A's files are replaced by a stub written to a temporary directory."""
import json
import tempfile
import unittest
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

import k5_train as T
import m3d_jax as J
import m3f_jax as F
import s3_data as D
import s3_loss as L
import s3_obs as O
import s3_train as S

W = json.loads((T.K5 / "windows.json").read_text())
SPL = json.loads((T.K5 / "splits.json").read_text())


def first_windows_distinct_songs(n):
    seen, out = set(), []
    for sid, b in W["train"]:
        if sid not in seen:
            seen.add(sid), out.append((sid, b))
        if len(out) == n:
            break
    return out


def write_stub(root, wins, n_val=4):
    """26A's interface with random content: slow/<split>/<id>.npz, tempo_rms.json, thresholds.json."""
    root = Path(root)
    rng = np.random.default_rng(0)
    for split, ids in (("train", sorted({s for s, _ in wins})), ("val", SPL["val"]["ids"][:n_val])):
        (root / "slow" / split).mkdir(parents=True, exist_ok=True)
        for sid in ids:
            nb = len(T.lanes(T.K5, split, sid)[0])
            np.savez(root / "slow" / split / f"{sid}.npz", slow=rng.standard_normal((nb, 13)).astype(np.float32))
    (root / "tempo_rms.json").write_text(json.dumps({s: {"bpm": float(rng.uniform(90, 130)), "log_rms": float(rng.normal(-2.5, 0.3))} for s, _ in wins}))
    (root / "thresholds.json").write_text(json.dumps({"energy": 0.01, "jerk": 1e9, "method": "stub"}))


class Observer(unittest.TestCase):
    def test_lipschitz_bound_measured(self):
        for n_in in (O.N_EXT, 27):
            Ob = O.init_obs(jax.random.PRNGKey(0), n_in)
            Ob = [(5.0 * W_, b) for W_, b in Ob]                          # large weights: the spectral normalisation must bind
            rng = np.random.default_rng(1)
            x = jnp.asarray(rng.standard_normal((400, n_in)))
            y = x + 0.05 * jnp.asarray(rng.standard_normal((400, n_in)))
            ratio = jnp.linalg.norm(O.lip_apply(Ob, x) - O.lip_apply(Ob, y), axis=-1) / jnp.linalg.norm(x - y, axis=-1)
            self.assertLessEqual(float(ratio.max()), O.G_OUT * 1.0001)
            self.assertGreater(float(ratio.max()), 0.05)                  # not trivially zero
            for W_, _ in Ob:                                              # without the normalisation the same net exceeds the bound
                self.assertGreater(float(jnp.linalg.norm(W_, 2)), 1.0)

    def test_chunk_window_equals_whole_episode(self):
        rng = np.random.default_rng(2)
        q = np.cumsum(rng.standard_normal((2, 24, 50, 5)), 2) * 2.0
        full = O.ext_features(q)
        for c0 in (0, 8, 16):
            buf = np.zeros((2, 200, 5))
            if c0:
                prev = q[:, :c0].reshape(2, -1, 5)[:, -200:]
                buf[:, 200 - prev.shape[1]:] = prev
            got = np.asarray(O.ext_features_chunk(jnp.asarray(buf), jnp.asarray(q[:, c0:c0 + 8]), float(c0)))
            np.testing.assert_allclose(got, full[:, c0:c0 + 8], atol=1e-5)
        # zero padding before the episode start: the first block's window has only 5 real samples (the newest ones are first)
        w0 = full[:, 0].reshape(2, O.WIN_N, 9)
        self.assertTrue((w0[:, 5:] == 0).all())
        self.assertTrue((np.abs(w0[:, :5]).sum() > 0))

    def test_shifted_D_hand_made(self):
        rng = np.random.default_rng(3)
        tgt = rng.standard_normal((6, 120, 17))
        self.assertAlmostEqual(O.shifted_D(tgt, tgt, np.arange(4)), 1.0, places=9)
        self.assertLess(abs(O.shifted_D(np.zeros_like(tgt), tgt, np.arange(4, 17))), 0.15)         # a constant prediction carries no timing: D about 0
        slow = np.broadcast_to(rng.standard_normal((6, 1, 17)), tgt.shape).copy()                 # per-window constants: shifting changes nothing
        self.assertAlmostEqual(O.shifted_D(slow + 0.5, slow, np.arange(17)), 0.0, places=9)


class Rules(unittest.TestCase):
    def test_D_multiplier_rising_only(self):
        mu, out = 0.0, []
        for d in (0.2, 0.5, 0.9, 0.7, 0.95, 0.1):
            mu = S.d_update(mu, d)
            out.append(round(mu, 6))
        self.assertEqual(out, [0.08, 0.112, 0.112, 0.112, 0.112, 0.208])
        self.assertTrue(all(b >= a for a, b in zip(out, out[1:])))

    def test_limit_hinges_zero_inside_the_envelope(self):
        thr = {"energy": 1.0, "jerk": 10.0}
        z = jnp.zeros((2, 8))
        inside = {"energy": 0.9 + z, "jerk": 9.0 + z, "hand_v": z, "jolt": z, "acc": z, "floor": z, "lim": z}
        valid = jnp.ones((2, 8))
        self.assertTrue(bool((L.limit_g(inside, valid, thr) == 0).all()))
        out = {**inside, "energy": 2.0 + z, "jerk": 20.0 + z, "hand_v": 0.6 + z, "jolt": 9.0 + z, "acc": 4.8 + z, "floor": 0.05 + z, "lim": 0.3 + z}
        np.testing.assert_allclose(np.asarray(L.limit_g(out, valid, thr)), [1.0, 1.0, 0.5, 1.0, 1.0, 1.0, 0.3], rtol=1e-6)
        part = jnp.asarray(np.broadcast_to((np.arange(8) >= 4).astype(float), (2, 8)).copy())       # only scored blocks count
        self.assertEqual(float(L.limit_g({**inside, "energy": jnp.asarray(np.where(np.arange(8) < 4, 5.0, 0.5)) + z}, part, thr)[0]), 0.0)

    def test_policy_has_zero_rows_and_equals_pass2_initially(self):
        k = jax.random.PRNGKey(5)
        P2_ = F.init_policy(k, {"body": "v2f"})
        P3 = S.init_policy3(k, {"body": "v2f"})
        self.assertEqual(P3["w1"].shape[0], P2_["w1"].shape[0] + 13)
        self.assertTrue(bool((P3["w1"][16:29] == 0).all()))
        np.testing.assert_array_equal(np.asarray(P3["w1"][:16]), np.asarray(P2_["w1"][:16]))
        np.testing.assert_array_equal(np.asarray(P3["w1"][29:]), np.asarray(P2_["w1"][16:]))

    def test_fast_z_floor(self):
        y = np.zeros((1, 120, 4)); y[:, 60:] = 1e-4
        z = D.fast_z(y, np.full(4, 0.5))
        self.assertLess(np.abs(z).max(), 1e-3)                            # a tiny step over a floor of 0.5 stays tiny
        self.assertTrue((z[:, :7] == 0).all())                            # fewer than 8 blocks: 0


class Batches(unittest.TestCase):
    def test_anchor_plus_seven_nearest_no_duplicates(self):
        rng = np.random.default_rng(4)
        songs = [f"s{i:03d}" for i in range(30)]
        tr = {s: {"bpm": float(rng.uniform(80, 140)), "log_rms": float(rng.normal(-2.5, 0.4))} for s in songs}
        wins = [(s, b) for s in songs for b in (0, 60)]
        m = D.Matched(tr, wins, 8)
        a = ("s003", 60)
        b = m.batch_of(a, 5, 0)
        self.assertEqual(len(b), 8)
        self.assertEqual(b[0], a)
        self.assertEqual(len({w[0] for w in b}), 8)
        i = m.pos["s003"]
        d = m.d[i].copy(); d[i] = np.inf
        self.assertEqual({w[0] for w in b[1:]}, {m.songs[j] for j in np.argsort(d, kind="stable")[:7]})
        self.assertEqual(b, m.batch_of(a, 5, 0))                           # deterministic
        rw = m.round_windows([("s001", 0), ("s002", 0)] * 8, 0)
        self.assertEqual(len(rw), 16)


class Run(unittest.TestCase):
    """A round runs without NaN; multipliers rise only; a kill and resume gives identical state; a validation writes best.pkl. 4 songs, batches of 2, rounds of 4 windows."""

    def _run(self, d, wins, s3, max_rounds):
        r = S.Stage3Run(d, s3=s3, batch=2, windows=wins, log=lambda s: None)
        r.run(max_rounds)
        return r

    def test_smoke_resume_identical_and_validation(self):
        T.EVAL_BATCH = 3
        S.N_D_WINDOWS = 3
        wins = first_windows_distinct_songs(8)
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b, tempfile.TemporaryDirectory() as s3:
            write_stub(s3, wins, n_val=4)
            straight = self._run(a, wins, s3, 2)
            self._run(b, wins, s3, 1)
            resumed = self._run(b, wins, s3, 2)
            self.assertEqual(resumed.tr.epoch, 2)
            for t1, t2 in ((straight.tr.P, resumed.tr.P), (straight.tr.enc, resumed.tr.enc), (straight.tr.obs, resumed.tr.obs)):
                for x, y in zip(jax.tree_util.tree_leaves(t1), jax.tree_util.tree_leaves(t2)):
                    np.testing.assert_array_equal(np.asarray(x), np.asarray(y))
            np.testing.assert_array_equal(straight.tr.mu, resumed.tr.mu)
            np.testing.assert_array_equal(straight.tr.muD, resumed.tr.muD)
            np.testing.assert_array_equal(np.asarray(straight.tr.key), np.asarray(resumed.tr.key))
            for x in jax.tree_util.tree_leaves(straight.tr.P) + jax.tree_util.tree_leaves(straight.tr.enc):
                self.assertTrue(np.isfinite(np.asarray(x)).all())
            h = straight.tr.hist
            self.assertEqual(len(h), 2)
            for r in h:
                for k in ("dec_e", "dec_i", "nce", "D_fast", "D_slow"):
                    self.assertTrue(np.isfinite(r[k]), k)
            self.assertTrue(all(h[1]["mu"][k] >= 1.0 for k in h[1]["mu"]))
            self.assertTrue(h[1]["muD"]["fast"] >= h[0]["muD"]["fast"] and h[1]["muD"]["slow"] >= h[0]["muD"]["slow"])
            straight.splits["val"]["ids"] = SPL["val"]["ids"][:3]
            straight.clock = T.Clock(0.0)
            straight.validate()
            import pickle
            best = pickle.loads((Path(a) / "best.pkl").read_bytes())
            self.assertEqual(best["P"]["w1"].shape[0], 16 + 13 + 25)
            self.assertTrue(best["s3"]["slow_inputs"])
            self.assertEqual(len(straight.extra["val"]), 1)


if __name__ == "__main__":
    unittest.main()
