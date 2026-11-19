"""K5 data tests. cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_k5_data   (brain env; the lane test runs B7 on 20 s of one real song)."""
import json
import unittest
from pathlib import Path

import numpy as np

import k5_data as K

OUT = Path("/secondary/hyst-data/body/k5")


class Splits(unittest.TestCase):
    def test_disjoint_and_complete(self):
        s = json.loads((OUT / "splits.json").read_text())
        a = {k: set(s[k]["artists"]) for k in ("train", "val", "check")}
        self.assertFalse(a["train"] & a["check"] or a["train"] & a["val"] or a["val"] & a["check"])
        ids = [i for k in ("train", "val", "check") for i in s[k]["ids"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual((s["check"]["n_songs"], s["check"]["n_artists"]), (357, 73))
        va = json.loads(K.VAL_JSON.read_text())
        self.assertEqual(set(s["val"]["artists"]), set(va["artists"]))
        self.assertEqual({int(i) for i in s["val"]["ids"]}, set(va["track_ids"]))
        # every check artist is held-out in the corpus file, never on the training side
        rows = K.read_rows()
        train_side = {r["artist"] for r in rows if r["split"] == "train"}
        self.assertFalse(a["check"] & train_side)

    def test_make_splits_rejects_overlap(self):
        rows = [{"id": "1", "split": "train", "artist": 1, "hours": 1.0}, {"id": "2", "split": "heldout", "artist": 1, "hours": 1.0}]
        with self.assertRaises(AssertionError):
            K.make_splits(rows, [])


class Windows(unittest.TestCase):
    def test_check_starts(self):
        self.assertEqual(K.check_windows(1000), [(0.25, 250, False), (0.5, 500, False), (0.75, 750, False)])
        self.assertEqual(K.check_windows(200), [(0.25, 50, False), (0.5, 80, True), (0.75, 80, True)])      # 100 > 80 and 150 > 80
        self.assertEqual(K.check_windows(120), [(0.25, 0, True), (0.5, 0, True), (0.75, 0, True)])

    def test_train_starts_fit(self):
        for nb in (120, 179, 180, 1000):
            for b in K.train_windows(nb):
                self.assertLessEqual(b + K.WIN_BLOCKS, nb)
        self.assertEqual(K.train_windows(119), [])
        self.assertEqual(K.train_windows(180), [0, 60])

    def test_windows_file(self):
        w = json.loads((OUT / "windows.json").read_text())
        s = json.loads((OUT / "splits.json").read_text())
        self.assertEqual(len(w["check"]), 3 * (357 - len(w["check_songs_shorter_than_60s"])))
        self.assertTrue({r[0] for r in w["train"]} <= set(s["train"]["ids"]))
        self.assertTrue({r[0] for r in w["check"]} <= set(s["check"]["ids"]))


class Lanes(unittest.TestCase):
    def test_shapes_and_timing(self):
        import torch
        import b2
        import braindump as bd
        import train_b7
        torch.set_num_threads(4)
        sid = json.loads((OUT / "splits.json").read_text())["check"]["ids"][0]
        mean, std = bd.stats()
        feats = np.load(K.CORPUS / "features" / f"{sid}.npy").astype(np.float32)[:2025]                       # 20.25 s: a partial last block
        x = b2.build_inputs(feats, json.loads((K.CORPUS / "grids" / f"{sid}.json").read_text())["beats"], mean, std)
        model, _ = train_b7.load_model7(bd.CKPT)
        z = K.song_lanes(model, x)
        self.assertEqual(z["y"].shape, (40, 8))                      # 2025 // 50 blocks, the toy's 8 numbers per 0.5 s block
        self.assertEqual(z["phi_end"].shape, (40,))
        self.assertEqual(z["omega"].shape, (40,))
        self.assertEqual(z["s10"].shape, (202, 5))                   # 2025 // 10 bins of 0.1 s
        self.assertEqual(z["arousal_b7"].shape, (202,))
        self.assertEqual(z["power10"].shape, (202, 4))
        self.assertTrue(np.isfinite(z["y"]).all() and np.isfinite(z["omega"]).all())
        self.assertTrue((np.hypot(z["y"][:, 2], z["y"][:, 3]) <= 1 + 1e-5).all())          # mean of unit vectors
        self.assertTrue((np.abs(z["omega"]) <= 8 * np.pi + 1e-4).all())
        self.assertTrue((z["y"][:, 0] >= 0).all())                   # arousal follows a non-negative surprisal


class Manifest(unittest.TestCase):
    def test_manifest_matches_lanes_and_features(self):
        p = OUT / "lanes_manifest.json"
        if not p.exists():
            self.skipTest("lanes not exported yet")
        m = json.loads(p.read_text())
        s = json.loads((OUT / "splits.json").read_text())
        self.assertEqual(set(m["songs"]), {i for k in ("train", "val", "check") for i in s[k]["ids"]})
        self.assertEqual(m["y_names"], K.Y_NAMES)
        for sid, e in list(m["songs"].items())[::50]:                # every 50th song opened and compared with its feature file length
            z = np.load(OUT / "lanes" / e["split"] / f"{sid}.npz")
            self.assertEqual(int(z["frames"]), K.n_frames(sid))
            self.assertEqual(z["y"].shape, (K.n_frames(sid) // K.BLOCK, 8))
            self.assertEqual(z["s10"].shape[0], K.n_frames(sid) // 10)


if __name__ == "__main__":
    unittest.main()
