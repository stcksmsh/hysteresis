"""Tests for the corpus side of prep_corpus.py: list, hash list, hash and statistics checks (no audio decoding)."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

import prep_corpus as P
import train


def make_corpus(d):
    d = Path(d)
    (d / "features").mkdir()
    (d / "audio").mkdir()
    hashes = []
    for tid in ("000001", "000002"):
        np.save(d / "features" / f"{tid}.npy", np.ones((10, 44), np.float32) * int(tid))
        (d / "audio" / f"{tid}.mp3").write_bytes(b"audio" + tid.encode())
        for p in (d / "features" / f"{tid}.npy", d / "audio" / f"{tid}.mp3"):
            hashes.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(d)}")
    (d / "hashes.txt").write_text("\n".join(hashes) + "\n")
    (d / "list.csv").write_text("id,split\n1,train\n2,heldout\n")
    np.savez(d / "feature_stats.npz", mean=np.zeros(44), sd=np.ones(44) * 2)
    (d / "feature_stats.json").write_text(json.dumps({"sha256_npz": P.sha256(d / "feature_stats.npz")}))
    return d


class TestCorpusChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = make_corpus(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_list_and_hashes_read(self):
        self.assertEqual(P.read_list(self.d / "list.csv"), [("000001", "train"), ("000002", "heldout")])
        h = P.read_hashes(self.d / "hashes.txt")
        self.assertEqual(set(h), {"000001.npy", "000001.mp3", "000002.npy", "000002.mp3"})

    def test_list_sha256_column_is_used(self):
        (self.d / "final.csv").write_text("id,split,sha256\n1,train,%s\n2,heldout,%s\n" % (P.sha256(self.d / "audio" / "000001.mp3"), "0" * 64))
        h = P.list_hashes(self.d / "final.csv")
        self.assertEqual(set(h), {"000001.mp3", "000002.mp3"})
        rows = P.read_list(self.d / "final.csv")
        with self.assertRaisesRegex(ValueError, "hash mismatch 000002.mp3"):
            P.verify(rows, h, self.d)
        self.assertEqual(P.list_hashes(self.d / "list.csv"), {})

    def test_bad_split_is_refused(self):
        (self.d / "bad.csv").write_text("id,split\n1,test\n")
        with self.assertRaises(ValueError):
            P.read_list(self.d / "bad.csv")

    def test_verify_passes_and_counts(self):
        rows = P.read_list(self.d / "list.csv")
        self.assertEqual(P.verify(rows, P.read_hashes(self.d / "hashes.txt"), self.d), 4)

    def test_verify_catches_a_changed_file_a_missing_hash_and_missing_features(self):
        rows = P.read_list(self.d / "list.csv")
        hashes = P.read_hashes(self.d / "hashes.txt")
        (self.d / "audio" / "000002.mp3").write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "hash mismatch 000002.mp3"):
            P.verify(rows, hashes, self.d)
        (self.d / "audio" / "000002.mp3").write_bytes(b"audio000002")
        del hashes["000001.mp3"]
        with self.assertRaisesRegex(ValueError, "no hash for 000001.mp3"):
            P.verify(rows, hashes, self.d)
        (self.d / "features" / "000002.npy").unlink()
        with self.assertRaisesRegex(ValueError, "missing features 000002"):
            P.verify(rows, P.read_hashes(self.d / "hashes.txt"), self.d)

    def test_stats_hash_and_key_names(self):
        P.verify_stats(self.d)
        mean, std = train.load_stats(self.d / "feature_stats.npz")       # the builder's key `sd`
        np.testing.assert_array_equal(std, 2.0)
        np.savez(self.d / "feature_stats.npz", mean=np.zeros(44), sd=np.ones(44))
        with self.assertRaises(ValueError):
            P.verify_stats(self.d)
        np.savez(self.d / "s2.npz", mean=np.zeros(44), std=np.full(44, 3.0))
        self.assertEqual(float(train.load_stats(self.d / "s2.npz")[1][0]), 3.0)


if __name__ == "__main__":
    unittest.main()
