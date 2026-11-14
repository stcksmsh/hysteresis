#!/usr/bin/env python3
"""Numbers per setting for the motor-network toy test (WO29B).  Definitions = 29A's docs/MOTORNET_RULES.md (f); defaults below.

  motornet_measure.py --manifest MANIFEST.json --out measurements.json

Per setting, from its Part 1 clip (CSV at 50 Hz, activity.npy float32 T x N at 50 Hz, 12 s):
  pr          participation ratio (sum lam)^2 / sum lam^2 of the covariance of r
  regime      decays: std of r (over units) in the last 4 s < 0.1 x the first 4 s; cycles: top PC autocorrelation has a peak > 0.5 at a
              lag of 0.3-5 s; else wanders
  freq_hz     peak of the summed power spectra of the mean-removed hand x, y, z (DC excluded)
  hand_speed  mean hand speed, m/s
  hand_height mean hand z, m
  straightness mean (and straightness_min) chord/arc per stroke, strokes as in rules (f)
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
    """Peak of the summed power spectra of the mean-removed x, y, z hand coordinates (overseer's correction of rules (f): the speed
    spectrum doubles a back-and-forth frequency). Hann window, whole clip, no zero padding, bins above 0.1 Hz."""
    h = np.asarray(h, float)
    x = (h - h.mean(0)) * np.hanning(len(h))[:, None]
    p = (np.abs(np.fft.rfft(x, axis=0)) ** 2).sum(1)
    f = np.fft.rfftfreq(len(h), 1 / hz)
    ok = f > 0.1
    return float(f[ok][np.argmax(p[ok])])


def straightness(h, hz=HZ):
    """(mean, min) chord/arc over strokes: hand path between local minima of the 0.1 s box-smoothed hand speed, minima >= 0.3 s apart,
    strokes with arc < 0.05 m skipped.  (1.0, 1.0) for a straight path; (None, None) when no stroke qualifies."""
    v = np.convolve(hand_speed(h, hz), np.ones(max(1, round(0.1 * hz))) / max(1, round(0.1 * hz)), "same")
    gap = round(0.3 * hz)
    mins = []
    for i in range(1, len(v) - 1):
        if v[i] < v[i - 1] and v[i] <= v[i + 1] and (not mins or i - mins[-1] >= gap):
            mins.append(i)
    out = []
    for a, b in zip(mins, mins[1:]):
        seg = h[a:b + 1]
        arc = np.linalg.norm(np.diff(seg, axis=0), axis=1).sum()
        if arc >= MIN_ARC:
            out.append(np.linalg.norm(seg[-1] - seg[0]) / arc)
    return (float(np.mean(out)), float(np.min(out))) if out else (None, None)


def read_csv(p):
    lines = [l for l in Path(p).read_text().splitlines() if l and not l.startswith("#")][1:]  # drop comments and the time_s header
    return np.array([[float(x) for x in l.split(",")] for l in lines])[:, 1:]


def hand_path(csv_path):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import m3f_report as R
    return R.fk_points(read_csv(csv_path))[:, 5]


def measure(r, h, hz=HZ):
    return dict(pr=participation_ratio(r), regime=regime(r, hz), freq_hz=dominant_freq(h, hz),
                hand_speed=float(hand_speed(h, hz).mean()), hand_height=float(h[:, 2].mean()), straightness=straightness(h, hz)[0], straightness_min=straightness(h, hz)[1])


def drift(base_yaw, hz=HZ):
    """(mean base yaw over the last 3 s - mean over the first 3 s, range of the 3 s moving mean of base yaw), degrees"""
    n = round(3 * hz)
    q = np.asarray(base_yaw, float)
    ma = np.convolve(q, np.ones(n) / n, "valid")
    return float(q[-n:].mean() - q[:n].mean()), float(ma.max() - ma.min())


def measure2(r, h, q, population, hz=HZ):
    """Round 2 (WO30A, BRAIN_SPEC 7.47.4.7): measure() plus base yaw and shoulder p5-p95 range (deg; q = joint angles, columns 0 and 1),
    facing drift, and the participation ratio per population (population: 0 slow, 1 fast, per unit)."""
    pop = np.asarray(population)
    single = bool((pop == 0).all())  # one population of units (round-1 network): PR of all units goes to pr_slow, pr_fast is None
    q = np.asarray(q, float)
    d, dr = drift(q[:, 0], hz)
    rng = lambda a: float(np.percentile(a, 95) - np.percentile(a, 5))
    return dict(measure(r, h, hz), pr_slow=participation_ratio(r[:, pop == 0]), pr_fast=None if single else participation_ratio(r[:, pop == 1]),
                yaw_range=rng(q[:, 0]), shoulder_range=rng(q[:, 1]), drift=d, drift_range=dr, single_population=single)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--round2", action="store_true", help="round 2 manifest (parts A and B, pairs; keyed by clip file stem, adds yaw/shoulder range, drift, PR per population)")
    a = ap.parse_args()
    mp = Path(a.manifest)
    data = json.loads(mp.read_text())
    clips = data["clips"] if isinstance(data, dict) else data
    res = {}
    if a.round2:
        for c in clips:
            two = isinstance(c["csv"], list)
            pops = c.get("population")  # single item: one list of units; pair item: one list per render
            pops = pops if two else [pops]
            for i, (cs, ac) in enumerate(zip(c["csv"] if two else [c["csv"]], c["activity"] if two else [c["activity"]])):
                q = read_csv(mp.parent / cs)
                n = np.load(mp.parent / ac).shape[1]
                pop = pops[i] if pops and pops[i] is not None else [0] * (n // 2) + [1] * (n // 2)
                res[Path(cs).stem] = measure2(np.load(mp.parent / ac).astype(float), hand_path(mp.parent / cs), q, pop)
        Path(a.out).write_text(json.dumps(res, indent=1))
        print("wrote", a.out, len(res), "clips")
        return
    for c in clips:
        if c.get("part") != 1:
            continue
        r = np.load(mp.parent / c["activity"]).astype(float)
        res[c["setting"]] = measure(r, hand_path(mp.parent / c["csv"]))
    Path(a.out).write_text(json.dumps(res, indent=1))
    print("wrote", a.out, len(res), "settings")


if __name__ == "__main__":
    main()
