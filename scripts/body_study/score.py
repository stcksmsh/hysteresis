"""score.py ANSWERS.json KEY.json: check 2b of docs/BODY_STUDY.md, round 2 (addendum 8).

Only the counted answers of the 32 scored triplets are scored; practice is data only.
Pass at >= 20 of 32 correct. Reported: per region (found as the odd one, of 4; pair
of a correct triplet, of 4); per odd position (confusion table); first against second
half of the shown order; hits on the 16 triplets whose two regions differ most in mean
joint speed against the other 16; descriptors that separate found from missed (per
descriptor, the odd region's position m in found minus missed triplets, and the same
for |m_odd - m_pair|). Second answers, times, pauses and replays are data only.
"""
import json, sys
from math import comb
import numpy as np

N, PASS = 32, 20
# answer.html saves {"practice": [...], "answers": [{"shown": n, "counted", ...}]}; shown n is tNN
data = json.load(open(sys.argv[1]))
ans = {f"t{a['shown']:02d}": a for a in data["answers"]}
key = json.load(open(sys.argv[2]))
T = key["triplets"]
M, S = np.array(key["m"]), np.array(key["speed"])
NAMES = ([f"{j} {q} {s}" for j in ["base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll"]
          for q in ["speed", "accel", "jerk"] for s in ["mean", "p90"]]
         + ["hand height", "extension", "curl", "lag base>shoulder", "lag shoulder>elbow",
            "lag elbow>wrist", "periodicity"])
assert len(NAMES) == M.shape[1] and len(T) == N

missing = [t["shown"] for t in T if t["shown"] not in ans or ans[t["shown"]]["counted"] not in ("A", "B", "C")]
assert not missing, f"no counted answer for {missing}"
hit = np.array([ans[t["shown"]]["counted"] == t["odd"] for t in T])
n = int(hit.sum())
p = sum(comb(N, i) * (1 / 3) ** i * (2 / 3) ** (N - i) for i in range(n, N + 1))
print(f"check 2b: {n} of {N} correct -> {'PASS' if n >= PASS else 'FAIL'} "
      f"(pass at >= {PASS}; chance {N / 3:.1f}; P(>= {n} | guessing) = {p:.4f})")

print("per region, found as the odd one (of 4) / pair region in a correct triplet (of 4):")
for r in range(8):
    found = sum(h for t, h in zip(T, hit) if t["oddRegion"] == r)
    as_pair = sum(h for t, h in zip(T, hit) if t["pairRegion"] == r)
    print(f"  region {r} (centre {key['centres'][r]}, mean joint speed {S[r]:.1f} deg/s): odd {found}/4, pair {as_pair}/4")

print("per k (odd region = pair region + k mod 8):",
      {k: f"{sum(h for t, h in zip(T, hit) if t['k'] == k)}/8" for k in (1, 3, 5, 7)})

print("odd position (rows) against counted answer (columns):")
print("        A   B   C   correct")
for o in "ABC":
    row = [sum(1 for t in T if t["odd"] == o and ans[t["shown"]]["counted"] == c) for c in "ABC"]
    print(f"  odd {o} {row[0]:3d} {row[1]:3d} {row[2]:3d}   {row['ABC'.index(o)]}/{sum(row)}")

half = N // 2
print(f"first half (shown 1-{half}): {int(hit[:half].sum())}/{half}; second half: {int(hit[half:].sum())}/{half}")

# 16 triplets with the largest |speed_odd - speed_pair| (stable sort on shown order)
gap = np.array([abs(S[t["oddRegion"]] - S[t["pairRegion"]]) for t in T])
far = np.zeros(N, bool)
far[np.argsort(-gap, kind="stable")[:half]] = True
print(f"speed difference between the two regions: largest 16 (gap {gap[far].min():.1f}-{gap[far].max():.1f} deg/s) "
      f"{int(hit[far].sum())}/16; other 16 (gap {gap[~far].min():.1f}-{gap[~far].max():.1f}) {int(hit[~far].sum())}/16")

if hit.all() or not hit.any():
    print("all found or all missed: no separating descriptors")
else:
    odd = np.array([M[t["oddRegion"]] for t in T])
    dm = np.abs(odd - np.array([M[t["pairRegion"]] for t in T]))
    for label, X in (("odd region position m", odd), ("|m_odd - m_pair|", dm)):
        d = X[hit].mean(0) - X[~hit].mean(0)
        print(f"{label}, found minus missed (rank units), largest 8:")
        for k in np.argsort(-np.abs(d))[:8]:
            print(f"  {NAMES[k]:28s} {d[k]:+.3f}")

print("data only, not scored:")
pr = data.get("practice", [])
print(f"  practice: {sum(bool(x.get('correct')) for x in pr)} of {len(pr)} right")
sec = [(t, ans[t["shown"]].get("second")) for t in T]
given = [(t, x) for t, x in sec if x in ("A", "B", "C")]
print(f"  second answers given {len(given)} of {N}: correct {sum(x == t['odd'] for t, x in given)}, "
      f"changed from the counted answer {sum(x != ans[t['shown']]['counted'] for t, x in given)}")
for field in ("timeToCountedS", "totalS", "pausesFirstPass"):
    v = [ans[t["shown"]].get(field) for t in T if ans[t["shown"]].get(field) is not None]
    if v:
        print(f"  {field}: median {np.median(v):.1f}, min {min(v):.1f}, max {max(v):.1f}")
pre = [sum(ans[t["shown"]].get("replaysBeforeCounted", {}).values()) for t in T]
print(f"  replays before the counted answer per triplet: 0: {pre.count(0)}, 1: {pre.count(1)}, 2: {pre.count(2)}; "
      f"found with any {sum(h for h, r in zip(hit, pre) if r)} of {sum(1 for r in pre if r)}, "
      f"without {sum(h for h, r in zip(hit, pre) if not r)} of {pre.count(0)}")
rp = [sum(ans[t["shown"]].get("replays", {}).values()) for t in T]
print(f"  replays after the counted answer per triplet: median {np.median(rp):.1f}, total {sum(rp)}")
print("notes:")
for t, h in zip(T, hit):
    a = ans[t["shown"]]
    if a.get("text"):
        print(f"  {t['shown']} ({'found' if h else 'missed'}, odd region {t['oddRegion']}): {a['text']}")
