"""WO28A: hand-path straightness per move (chord / arc length of the realised hand path in each 1.2 s move window) for clips given as ids.
    python dialstudy_straight.py A_roundness_low A_neutral A_roundness_high"""
import sys

import numpy as np

import m3f_report as R
import dialstudy as D

W = "/secondary/hyst-data/body/dialstudy/work/"
for cid in sys.argv[1:]:
    q = np.loadtxt(W + cid + ".csv", delimiter=",", skiprows=8)[:, 1:]
    h = R.fk_points(q)[:, 5]
    n = round(D.INTERVAL * D.HZ)
    r = []
    for k in range(D.NPOSE - 2):
        seg = h[k * n:(k + 1) * n + 1]
        if len(seg) < n:
            break
        arc = np.linalg.norm(np.diff(seg, axis=0), axis=1).sum()
        if arc > 0.05:
            r.append(np.linalg.norm(seg[-1] - seg[0]) / arc)
    print(f"{cid:18s} moves {len(r)}  chord/arc mean {np.mean(r):.3f}  min {np.min(r):.3f}")
