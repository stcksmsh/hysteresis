#!/usr/bin/env python3
"""Numbers per setting for the motor-network toy test (WO29B).  Definitions = 29A's docs/MOTORNET_RULES.md (f); defaults below.

  motornet_measure.py --manifest MANIFEST.json --out measurements.json

Per setting, from its Part 1 clip (CSV at 50 Hz, activity.npy float32 T x N at 50 Hz, 12 s):
  pr          participation ratio (sum lam)^2 / sum lam^2 of the covariance of r
  regime      decays: std of r (over units) in the last 4 s < 0.1 x the first 4 s; cycles: top PC autocorrelation has a peak > 0.5 at a
              lag of 0.3-5 s; else wanders
  freq_hz     peak of the hand-speed power spectrum (mean removed, > 0)
  hand_speed  mean hand speed, m/s
  hand_height mean hand z, m
  straightness mean chord/arc per stroke; stroke = hand path between hand-speed minima (dialstudy_straight.py: arc > 0.05 m counts)
Numbers only: no judgement.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np

HZ = 50
LAG_MIN, LAG_MAX, ACF_PEAK = 0.3, 5.0, 0.5
DECAY_RATIO = 0.1
MIN_ARC = 0.05


def participation_ratio(r):
    lam = np.clip(np.linalg.eigvalsh(np.cov(np.asarray(r, float).T)), 0, None)
    return float((lam.sum() ** 2) / (lam ** 2).sum()) if (lam ** 2).sum() > 0 else 0.0


def regime(r, hz=HZ):
    r = np.asarray(r, float)
    n4 = int(4 * hz)
    first, last = r[:n4].std(), r[-n4:].std()
    if last < DECAY_RATIO * first:
        return "decays"
    x = r - r.mean(0)
    pc = x @ np.linalg.svd(x, full_matrices=False)[2][0]
    ac = np.correlate(pc, pc, "full")[len(pc) - 1:]
    ac = ac / ac[0]
    lo, hi = int(LAG_MIN * hz), min(int(LAG_MAX * hz), len(ac) - 1)
    seg = ac[lo:hi + 1]
    peaks = [i for i in range(1, len(seg) - 1) if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1] and seg[i] > ACF_PEAK]
    return "cycles" if peaks else "wanders"


def hand_speed(h, hz=HZ):
    return np.linalg.norm(np.gradient(h, axis=0), axis=1) * hz


def dominant_freq(h, hz=HZ):
    v = hand_speed(h, hz)
    p = np.abs(np.fft.rfft(v - v.mean())) ** 2
    f = np.fft.rfftfreq(len(v), 1 / hz)
    return float(f[1:][np.argmax(p[1:])])


def straightness(h, hz=HZ):
    """Mean chord/arc over strokes (hand path between hand-speed minima); 1.0 for a straight path."""
    v = hand_speed(h, hz)
    mins = [i for i in range(1, len(v) - 1) if v[i] < v[i - 1] and v[i] <= v[i + 1]]
    cuts = [0] + mins + [len(h) - 1]
    out = []
    for a, b in zip(cuts, cuts[1:]):
        seg = h[a:b + 1]
        arc = np.linalg.norm(np.diff(seg, axis=0), axis=1).sum() if len(seg) > 1 else 0
        if arc > MIN_ARC:
            out.append(np.linalg.norm(seg[-1] - seg[0]) / arc)
    return float(np.mean(out)) if out else None


def read_csv(p):
    lines = [l for l in Path(p).read_text().splitlines() if l and not l.startswith("#")][1:]  # drop comments and the time_s header
    return np.array([[float(x) for x in l.split(",")] for l in lines])[:, 1:]


def hand_path(csv_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import m3f_report as R
    return R.fk_points(read_csv(csv_path))[:, 5]


def measure(r, h, hz=HZ):
    return dict(pr=participation_ratio(r), regime=regime(r, hz), freq_hz=dominant_freq(h, hz),
                hand_speed=float(hand_speed(h, hz).mean()), hand_height=float(h[:, 2].mean()), straightness=straightness(h, hz))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    mp = Path(a.manifest)
    data = json.loads(mp.read_text())
    clips = data["clips"] if isinstance(data, dict) else data
    res = {}
    for c in clips:
        if c.get("part") != 1:
            continue
        r = np.load(mp.parent / c["activity"]).astype(float)
        res[c["setting"]] = measure(r, hand_path(mp.parent / c["csv"]))
    Path(a.out).write_text(json.dumps(res, indent=1))
    print("wrote", a.out, len(res), "settings")


if __name__ == "__main__":
    main()
