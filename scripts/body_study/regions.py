"""regions.py SWEEP.json OUT.json: regions of the body study (docs/BODY_STUDY.md,
addendum 2026-10-13). Rank-normalise the 37 descriptors, keep the denser half of the
clips (distance to the 9th nearest other clip at or under the median) as candidate
centres, pick 8 by farthest-point sampling over candidates (first: farthest from the
mean), choose r, assign members."""
import json, sys
import numpy as np

sweep = json.load(open(sys.argv[1]))
clips = sweep["clips"]
D = np.array([c["desc"] for c in clips])
N = len(D)
srt = np.sort(D, axis=0)  # kept in OUT: new clips are ranked against these
Z = np.stack([(np.searchsorted(srt[:, k], D[:, k], "left") + 1 - 0.5) / N for k in range(D.shape[1])], 1)
pair = np.linalg.norm(Z[:, None] - Z[None], axis=2)
d9 = np.sort(pair, axis=1)[:, 9]  # column 0 is the clip itself
cand = np.flatnonzero(d9 <= np.median(d9))
dm = np.linalg.norm(Z - Z.mean(0), axis=1)
centres = [int(cand[np.argmax(dm[cand])])]
for _ in range(7):
    d = np.min([np.linalg.norm(Z[cand] - Z[c], axis=1) for c in centres], axis=0)
    centres.append(int(cand[np.argmax(d)]))
C = Z[centres]
cc = np.linalg.norm(C[:, None] - C[None], axis=2)
off = cc[np.triu_indices(8, 1)]
dist = np.linalg.norm(Z[:, None] - C[None], axis=2)
nearest = dist.argmin(1)

def members(r):
    return [np.flatnonzero((nearest == k) & (dist[:, k] <= r)) for k in range(8)]

def within(idx):
    if len(idx) < 2:
        return 0.0
    P = Z[idx]
    d = np.linalg.norm(P[:, None] - P[None], axis=2)
    return d[np.triu_indices(len(idx), 1)].mean()

quarter = off.mean() / 4
best = 0.0
for r in np.linspace(0, off.min(), 201)[1:]:
    if all(within(m) < quarter for m in members(r)):
        best = r
mem = members(best)
out = {
    "sorted": srt.T.tolist(), "centres": centres, "candidates": cand.tolist(), "r": best,
    "meanCentreDistance": float(off.mean()), "minCentreDistance": float(off.min()),
    "quarterOfMeanCentreDistance": float(quarter),
    "regions": [{
        "centre": centres[k], "members": m.tolist(),
        "meanWithinDistance": float(within(m)),
        "stretchMedian": float(np.median([clips[i]["s"] for i in m])) if len(m) else None,
        "stretchMax": float(max([clips[i]["s"] for i in m])) if len(m) else None,
        "bMean": np.mean([clips[i]["b"] for i in m], axis=0).tolist() if len(m) else None,
    } for k, m in enumerate(mem)],
}
json.dump(out, open(sys.argv[2], "w"))
print(f"within-region mean distances", [round(r_["meanWithinDistance"], 3) for r_ in out["regions"]])
print(f"r={best:.3f} (centre-to-centre min {off.min():.3f}, mean {off.mean():.3f}, quarter of mean {quarter:.3f})")
for k, m in enumerate(mem):
    reg = out["regions"][k]
    print(k, len(m), f"within {reg['meanWithinDistance']:.2f}", "stretch med/max",
          None if not len(m) else f"{reg['stretchMedian']:.2f}/{reg['stretchMax']:.2f}")
print("stretch of all 2000: median", np.median([c["s"] for c in clips]))
print("descriptor spread: rank-space distance to mean, 5/50/95 pct", np.percentile(dm, [5, 50, 95]).round(3))
print("d9 median", round(float(np.median(d9)), 3), "candidates", len(cand), "centres", centres)
