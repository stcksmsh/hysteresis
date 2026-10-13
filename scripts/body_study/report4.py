"""report4.py REGIONS.json REGIONS.log: the addendum-4 report (docs/BODY_STUDY.md,
addendum 4, step 6) from `body_study regions`, plus the spread of w and of the
worst ratio over every region built."""
import json, re, sys, collections
import numpy as np

rg = json.load(open(sys.argv[1]))
log = open(sys.argv[2]).read().splitlines()
print("rule holds:", rg["holds"], "| replacements:", rg["replacements"],
      "| initial centres:", rg["initialCentres"], "| final centres:", rg["centres"])

builds = [re.match(r"centre (\d+): (\d+) clips, w ([\d.]+), (\d+) seeds tried, skipped (.*)", l)
          for l in log if l.startswith("centre ")]
W = np.array([float(b[3]) for b in builds])
print(f"regions built: {len(builds)}; w over all builds: min {W.min():.3f} "
      f"p10 {np.percentile(W, 10):.3f} median {np.median(W):.3f} p90 {np.percentile(W, 90):.3f} max {W.max():.3f}")
tried = sum(int(b[4]) for b in builds)
skip = collections.Counter()
for b in builds:
    for k, v in re.findall(r'"([^"]+)": (\d+)', b[5]):
        skip[k] += int(v)
print(f"seeds over all builds: tried {tried}, skipped {sum(skip.values())}: {dict(skip)}")
print("regions short of 9 clips:", sum(int(b[2]) < 9 for b in builds))

ratios = [e["replaced"]["ratio"] for e in rg["events"] if "replaced" in e and e["replaced"]["ratio"] is not None]
if ratios:
    r = np.array(ratios)
    print(f"worst-pair ratio at each replacement ({len(r)}): max {r.max():.3f} median {np.median(r):.3f} "
          f"p90 {np.percentile(r, 90):.3f}; at or over 1.2: {(r >= 1.2).sum()}, over 1.0: {(r > 1.0).sum()}")
slots = collections.Counter(e["replaced"]["slot"] for e in rg["events"] if "replaced" in e)
print("replacements per slot:", [slots[k] for k in range(8)])

if "w" in rg:
    print("\nfinal set (the last full set of 8)")
    for k, reg in enumerate(rg["regions"]):
        s = [c["s"] for c in reg["clips"]]
        print(f"  region {k}: centre {reg['centre']}, w {rg['w'][k]:.3f}, seeds tried {reg['seedsTried']}, "
              f"skipped {reg['skipped']}, stretches {' '.join(f'{x:.3f}' for x in s)}")
    print("  pairs (i j |m_i - m_j| ratio), smallest ratio first:")
    for p in sorted(rg["pairs"], key=lambda p: p["ratio"]):
        print(f"    {p['i']} {p['j']} {p['distance']:.3f} {p['ratio']:.3f}{'  < 1.5' if p['ratio'] < 1.5 else ''}")
    print(f"  smallest ratio {rg['smallestRatio']:.3f}; pairs under 1.5: "
          f"{sum(p['ratio'] < 1.5 for p in rg['pairs'])} of {len(rg['pairs'])}")
    allstretch = [c["s"] for reg in rg["regions"] for c in reg["clips"]]
    h = collections.Counter(round(np.log(x) / np.log(1.1)) for x in allstretch)
    print("  stretch histogram of the 72 clips (1.1^0..7):", [h[i] for i in range(8)])
    d = [p["distance"] for p in rg["pairs"]]
    print(f"  |m_i - m_j|: min {min(d):.3f} median {np.median(d):.3f} max {max(d):.3f}; "
          f"1.5 x max w needs {1.5 * max(rg['w']):.3f}")
