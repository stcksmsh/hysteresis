"""WO12: count the breaches of `hyst check-csv` by kind for the three joint CSVs (the Rust checker prints only the first 10). Same rules as crates/hyst-compile/src/score_csv.rs `check`:
joint position range, joint speed (|diff| x hz), joint acceleration (|2nd diff| x hz^2), floor margin, hand speed and jolt. Body env. Report only.
    k5_video_breaches.py [CSV ...]  -> /secondary/hyst-data/body/k5/danced/breaches.json
"""
import json
import sys
from pathlib import Path

import numpy as np

import arm_sim as A
import make_arm as M

DANCED = Path("/secondary/hyst-data/body/k5/danced")
HAND_MPS, JOLT, FLOOR, DISC = 1.2, 9.0, 0.05, 0.06


def count(path, hz=50.0):
    rows = np.array([[float(c) for c in l.split(",")] for l in Path(path).read_text().splitlines() if l and not l.startswith("#") and not l.startswith("time_s")])
    q = rows[:, 1:]
    n = len(q)
    kinds = {}
    pos = np.zeros(n, bool)
    for j in range(5):
        r = M.RANGE_DEG[j]
        if r:
            pos |= (q[:, j] < r[0]) | (q[:, j] > r[1])
    kinds["joint position"] = pos
    for j, name in enumerate(M.JOINTS):
        v = np.zeros(n, bool)
        v[:-1] = np.abs(np.diff(q[:, j])) * hz > M.LIMITS[j][0]
        kinds[f"{name} speed"] = v
        a = np.zeros(n, bool)
        a[1:-1] = np.abs(q[2:, j] - 2 * q[1:-1, j] + q[:-2, j]) * hz * hz > M.LIMITS[j][1]
        kinds[f"{name} acceleration"] = a
    pts = np.array([A.fk(r) for r in q])
    margin = np.minimum(pts[:, 1:5, 2].min(1) - FLOOR, pts[:, 5, 2] - FLOOR - DISC)
    kinds["floor margin"] = margin < 0
    sp = np.linalg.norm(np.diff(pts[:, 5], axis=0), axis=1) * hz
    h = np.zeros(n, bool)
    h[:-1] = sp > HAND_MPS
    kinds["hand speed"] = h
    jl = np.zeros(n, bool)
    jl[1:-1] = np.abs(np.diff(sp)) * hz > JOLT
    kinds["hand jolt"] = jl
    any_ = np.zeros(n, bool)
    for v in kinds.values():
        any_ |= v
    return {"rows": n, "seconds": (n - 1) / hz, "rows_with_any_breach": int(any_.sum()), "by_kind_rows": {k: int(v.sum()) for k, v in kinds.items() if v.any()},
            "worst_floor_margin_m": float(margin.min()), "max_hand_mps": float(sp.max()), "max_hand_jolt": float(np.abs(np.diff(sp)).max() * hz)}


if __name__ == "__main__":
    files = sys.argv[1:] or [str(DANCED / f"{s}.k5.csv") for s in ("instant-crush", "five-years", "presence")]
    res = {Path(f).name: count(f) for f in files}
    if len(sys.argv) == 1:
        (DANCED / "breaches.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
