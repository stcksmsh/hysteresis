"""score.py ANSWERS.json KEY.json: check 2b of docs/BODY_STUDY.md.

Pass at >= 16 of 24 correct. Per region: how often it was found as the odd one (of 3).
Descriptors that separate the regions found from those missed: per descriptor, the
mean rank position m of the odd regions in found triplets minus that in missed ones,
and the same for |m_odd - m_pair| (how far the odd region sat from the pair),
largest first.
"""
import json, sys
import numpy as np

# answer.html saves {"answers": [{"shown": n, "choice", "text", "time"}]}; shown n is test tNN
ans = {f"t{a['shown']:02d}": a for a in json.load(open(sys.argv[1]))["answers"]}
key = json.load(open(sys.argv[2]))
T = key["triplets"]
M = np.array(key["m"])
NAMES = ([f"{j} {q} {s}" for j in ["base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll"]
          for q in ["speed", "accel", "jerk"] for s in ["mean", "p90"]]
         + ["hand height", "extension", "curl", "lag base>shoulder", "lag shoulder>elbow",
            "lag elbow>wrist", "periodicity"])
assert len(NAMES) == M.shape[1]

missing = [t["test"] for t in T if t["test"] not in ans or ans[t["test"]]["choice"] not in ("A", "B", "C")]
assert not missing, f"no answer for {missing}"
hit = [ans[t["test"]]["choice"] == t["odd"] for t in T]
n = sum(hit)
print(f"check 2b: {n} of 24 correct -> {'PASS' if n >= 16 else 'FAIL'} (pass at >= 16; chance 8)")

print("per region, found as the odd one (of 3) / pair region in a correct triplet (of 3):")
for r in range(8):
    found = sum(h for t, h in zip(T, hit) if t["oddRegion"] == r)
    as_pair = sum(h for t, h in zip(T, hit) if t["pairRegion"] == r)
    print(f"  region {r} (centre {key['centres'][r]}): odd {found}/3, pair {as_pair}/3")

print("per k (odd region = pair region + k mod 8):",
      {k: f"{sum(h for t, h in zip(T, hit) if t['k'] == k)}/8" for k in (1, 3, 5)})

f = np.array(hit)
if f.all() or not f.any():
    print("all found or all missed: no separating descriptors")
else:
    odd = np.array([M[t["oddRegion"]] for t in T])
    gap = np.abs(odd - np.array([M[t["pairRegion"]] for t in T]))
    for label, X in (("odd region position m", odd), ("|m_odd - m_pair|", gap)):
        d = X[f].mean(0) - X[~f].mean(0)
        print(f"{label}, found minus missed (rank units), largest 8:")
        for k in np.argsort(-np.abs(d))[:8]:
            print(f"  {NAMES[k]:28s} {d[k]:+.3f}")

print("notes:")
for t, h in zip(T, hit):
    a = ans[t["test"]]
    if a.get("text"):
        print(f"  {t['test']} ({'found' if h else 'missed'}, odd region {t['oddRegion']}): {a['text']}")
