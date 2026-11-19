"""Exclusion rates of the gap verification on synthetic audio (no test-set audio): per kind and gap length, over many seeds.
The synthetic clips are the test-suite pulse-and-bed generator (30 s, seeds 0..N-1 give N different clips and N different gaps).
  python synthetic_exclusion.py [N]      default 60 clips
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fast_features as ff  # noqa: E402
import gaps  # noqa: E402
import grfnn  # noqa: E402
from test_gaps import music  # noqa: E402

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    rows = {}
    for seed in range(n):
        y = music(30.0, seed)
        for g in gaps.GAPS:
            for kind in gaps.KINDS:
                cid = f"synthetic/{seed}"
                t0 = gaps.gap_start(cid, g, kind, 30.0)
                f = ff.fast_features(gaps.make_gap(y, ff.SR, t0, g, kind, clip_id=cid))
                p = grfnn.pulse(f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET])
                valid, _, _ = gaps.gap_valid(p["input"], t0, g, cid, kind)
                rows.setdefault((g, kind), []).append(valid)
        if seed == 0:
            # for reference: the gap not cut at all (music kept inside the "gap")
            f = ff.fast_features(y)
            p = grfnn.pulse(f[:, ff.COL_FLUX_LOW], f[:, ff.COL_ONSET])
            uncut = [gaps.gap_valid(p["input"], 12.0, g, "synthetic/0", "noise")[0] for g in gaps.GAPS]
    for (g, kind), v in sorted(rows.items()):
        print(f"gap {g:g} s {kind:8s}: {len(v)} gaps, excluded {len(v) - sum(v)} = {100 * (1 - np.mean(v)):.1f} %")
    print("music left in the gap (clip 0, 2/4/8 s): valid =", uncut)
