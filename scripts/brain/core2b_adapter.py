#!/usr/bin/env python3
"""core-2b arousal predictions in the format check_b3.py --core2b reads: an npz with one 0.5 s-step series per clip key.

usage: core2b_adapter.py [PREDICTIONS_HELDOUT.npz] [OUT.npz]
Source: /secondary/hyst-data/emotion/check2b/predictions_heldout.npz, keys `<clip>/core_s` (steps, 2) = core-2b's out-of-fold readout of
(valence, arousal) at 0.5 s steps, smoothed with the tau stage 2b chose (8 s, no lag); `<clip>/core` is the unsmoothed one. Arousal is
column 1. The result uses `core_s`, the form 2b adopted. Clips: 1,744 DEAM (deam_<id>) and 43 MERP (merp_<song>), the same keys
precheck_data.py uses.
"""
import sys

import numpy as np

SRC = "/secondary/hyst-data/emotion/check2b/predictions_heldout.npz"
OUT = "/secondary/hyst-data/brain/b3/core2b_arousal.npz"
AROUSAL = 1


def adapt(src=SRC, out=OUT, field="core_s"):
    z = np.load(src, allow_pickle=True)
    keys = sorted({k.rsplit("/", 1)[0] for k in z.files if k.endswith("/" + field)})
    np.savez(out, **{k: z[f"{k}/{field}"][:, AROUSAL].astype(np.float64) for k in keys})
    return len(keys)


if __name__ == "__main__":
    print(adapt(*sys.argv[1:3]))
