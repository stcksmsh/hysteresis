"""The SD reference of the bank's running z-score (BRAIN_SPEC 2.2 correction: SD floor = 1e-3 of the corpus SD).

B1 has no training corpus, so the reference is fixed here from a synthetic, training-free source: 5 seeds x 30 s of the
test-suite pulse-and-bed generator (a 120 bpm 70-80 Hz thump plus a noisy tick over a 0.02 RMS noise bed; no test-set
audio). Why not a corpus: the B3 corpus does not exist yet and B1 must not depend on it; a constant fixed now keeps the
floor the same for every clip. The floor only matters where the running SD collapses (digital silence); 1e-3 of an SD
of order 1 dB is far below anything music or noise produces. Run this file to see the numbers behind the constants
in grfnn.py (SD_REF_FLUX, SD_REF_ONSET).
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fast_features as ff  # noqa: E402
from test_gaps import music  # noqa: E402

if __name__ == "__main__":
    cols = [[], []]
    for seed in range(5):
        f = ff.fast_features(music(30.0, seed))
        cols[0].append(f[:, ff.COL_FLUX_LOW])
        cols[1].append(f[:, ff.COL_ONSET])
    print("SD of flux0 (30-200 Hz) over the reference:", float(np.std(np.concatenate(cols[0]))))
    print("SD of onset strength over the reference:  ", float(np.std(np.concatenate(cols[1]))))
