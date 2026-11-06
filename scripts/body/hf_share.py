"""WO13A: the high-frequency share (e) of a joint trajectory (docs/BRAIN_SPEC.md 7.24, overseer's operational defaults). Body env. Provisional servo model. One arm.

    hf_share(q_deg, hz)   q_deg (n, 5) joint angles in the CSV joint order (base_yaw, shoulder, elbow, wrist_bend, wrist_roll), degrees, sampled at hz
                          -> power of the joint velocity above 3 Hz / power above 0 Hz, summed over the four non-roll joints (columns 0..3)
    hf_share_csv(path)    the same for a `hyst score-csv` / arm_sim.csv_text joint CSV (hz read from its '# hz:' header line)

Definition: velocity = central difference (np.gradient, edge rows one-sided) times hz; Welch power spectrum (scipy.signal.welch) with 4 s Hann segments, 50 % overlap, mean
removed per segment (detrend 'constant'); share = sum over the four joints and over the bins with f > 3 Hz of the power / the same sum over the bins with f > 0 Hz (the DC bin is
excluded; the mean is removed anyway). Powers are added over joints before dividing (one share per trajectory, not a mean of four shares). Needs at least one full 4 s segment.
"""
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch

CUT_HZ = 3.0
SEG_S = 4.0
NON_ROLL = (0, 1, 2, 3)


def hf_share(q_deg, hz):
    q = np.asarray(q_deg, float)
    if q.ndim != 2 or q.shape[1] != 5:
        raise ValueError("q_deg must be (n, 5)")
    nper = int(round(SEG_S * hz))
    if len(q) < nper:
        raise ValueError(f"need at least {SEG_S} s ({nper} rows), got {len(q)}")
    v = np.gradient(q[:, list(NON_ROLL)], axis=0) * hz
    f, p = welch(v, fs=hz, window="hann", nperseg=nper, noverlap=nper // 2, detrend="constant", axis=0)
    p = p.sum(1)
    return float(p[f > CUT_HZ].sum() / p[f > 0].sum())


def read_csv(path):
    """-> (rows (n, 5) degrees, hz) of a joint CSV."""
    hz, rows = None, []
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            if line[1:].strip().startswith("hz:"):
                hz = float(line.split(":", 1)[1])
        elif line and not line.startswith("time_s"):
            rows.append([float(c) for c in line.split(",")][1:])
    if hz is None:
        raise ValueError(f"{path}: no '# hz:' header line")
    return np.array(rows), hz


def hf_share_csv(path):
    q, hz = read_csv(path)
    return hf_share(q, hz)


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(p, f"{hf_share_csv(p):.4f}")
