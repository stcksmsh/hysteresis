"""Descriptor parity against Rust body.rs `descriptors` (reference values exported once by a scratch crate outside the repo calling hyst_compile::body::{clip,
frames,descriptors} on 3 fixed clips: body [0.5]*15 seed 7, [0.2]*15 seed 11, [0.85]*15 seed 23; descriptor_ref.json holds each clip's 481 frames of joint angles
and Rust's 37 descriptors). Tolerance stated before the comparison: |python - rust| <= 1e-6 * max(1, |rust|) for each of the 31 shared descriptors
(float64 both; the frames are rounded to 1e-12 deg in the file). cd scripts/body && /secondary/hyst-env/brain/bin/python -m unittest -v test_bdesc"""
import json
import unittest
from pathlib import Path

import numpy as np

import bdesc

REF = json.loads((Path(__file__).parent / "descriptor_ref.json").read_text())


class Parity(unittest.TestCase):
    def test_31_descriptors_match_rust_on_three_clips(self):
        for c in REF:
            py = bdesc.descriptors(np.array(c["q"]), max_lag_s=3.0)
            rs = np.array(c["descriptors"])[bdesc.RUST_INDEX]
            self.assertEqual(len(py), bdesc.N_DESC)
            tol = 1e-6 * np.maximum(1.0, np.abs(rs))
            bad = np.where(np.abs(py - rs) > tol)[0]
            self.assertEqual(len(bad), 0, f"seed {c['seed']}: {[(int(i), py[i], rs[i]) for i in bad]}")

    def test_roll_is_excluded(self):
        q = np.array(REF[0]["q"])
        q2 = q.copy()
        q2[:, 4] += 100 * np.sin(np.arange(len(q)) / 3.0)             # a violent roll changes nothing
        self.assertTrue(np.array_equal(bdesc.descriptors(q), bdesc.descriptors(q2)))

    def test_two_second_window_is_defined(self):
        q = np.array(REF[1]["q"])[:121]
        d = bdesc.descriptors(q)
        self.assertTrue(np.isfinite(d).all() and len(d) == 31)

    def test_window_resampling_is_exact_on_a_ramp(self):
        t = np.arange(201)[:, None] / 100.0
        f = bdesc.window_frames(np.concatenate([t * 10] * 5, 1))
        self.assertTrue(np.allclose(f[:, 0], np.arange(121) / 60.0 * 10))


if __name__ == "__main__":
    unittest.main()
