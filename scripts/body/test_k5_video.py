"""WO12 tests. cd scripts/body && /secondary/hyst-env/body/bin/python -m unittest -v test_k5_video   (JAX env; compiles M3e, minutes).
Lanes test (brain env): python k5_video_lanes.py check  -> prints the comparison against a stored check-split file.
Uses the real K5 lanes (/secondary/hyst-data/body/k5), the frozen cerebellum port and the trained policy."""
import json
import unittest

import jax
import numpy as np

import k5_train as T
import k5_video_roll as R
import k5_video_seg as S
import m3d
import m3e
import m3e_jax as M

SPL = json.loads((T.K5 / "splits.json").read_text())


class Pure(unittest.TestCase):
    def test_csv_rows_shape_and_mapping(self):
        q = np.arange(2 * 50 * 5, dtype=float).reshape(2, 50, 5)
        q0 = np.full(5, -1.0)
        rows = R.csv_rows(q, q0)
        self.assertEqual(rows.shape, (51, 5))                             # 25 per block + the start row
        self.assertTrue(np.array_equal(rows[0], q0))
        self.assertTrue(np.array_equal(rows[1], q.reshape(-1, 5)[1]))     # t = 0.02 s -> after control step 2 (index 1)
        self.assertTrue(np.array_equal(rows[-1], q.reshape(-1, 5)[-1]))   # t = 1.00 s -> the last step

    def test_segments_split(self):
        self.assertEqual(S.segment_bounds(300), [(0, 120), (120, 240), (240, 300)])
        self.assertEqual(S.segment_bounds(240), [(0, 120), (120, 240)])

    def test_shift_gap_matches_m3d(self):
        rng = np.random.default_rng(3)
        pred, yz = rng.normal(size=(1, 120, 8)), rng.normal(size=(1, 120, 8))
        g, matched = m3d.time_shuffled_gap(pred, yz, start=8)
        per = S.shift_gaps(pred[0], yz[0], 8)
        self.assertEqual(len(per), 20)
        self.assertAlmostEqual(float(per.mean()), float(g[0]), places=12)


class Rollout(unittest.TestCase):
    def test_full_song_first_60s_equals_single_window(self):
        sid = sorted(p.stem for p in (T.K5 / "lanes" / "check").glob("*.npz") if np.load(p)["y"].shape[0] in range(240, 400))[0]
        z = np.load(T.K5 / "lanes" / "check" / f"{sid}.npz")
        C = M.load_cb()
        P, _ = R.load_policy()
        # reference: the K5 eval's own path (WindowToy window at block 0, rollout_batched, same start seed)
        toy = T.build_toy(T.K5, "check", [(sid, 0)])
        ref = T.rollout_batched(m3e.make_fns(C), C, P, toy, slice(0, 1), "argmax", jax.random.PRNGKey(7), R.START_SEED)
        inps, _ = R.episode_inputs(z["y"], z["phi_end"], z["omega"])
        full = R.rollout_song(R.make_chunk_q(C), C, P, inps)
        nb = z["y"].shape[0]
        worst, ident = 0.0, True
        for k in ref:
            a, b = ref[k][0], full[k][:T.NB]
            worst = max(worst, float(np.max(np.abs(a.astype(float) - b.astype(float)))))
            ident &= bool(np.array_equal(a, b))
        print(json.dumps({"song": sid, "blocks": nb, "keys": sorted(ref), "max_abs_diff": worst, "bit_identical": ident}))
        self.assertLess(worst, 1e-9)
        self.assertEqual(full["q"].shape, (nb, 50, 5))
        self.assertTrue(np.isfinite(full["q"]).all())


if __name__ == "__main__":
    unittest.main()
