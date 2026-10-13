"""regions.py SWEEP.json OUT.json: regions of the body study (docs/BODY_STUDY.md).
Standardise the 37 descriptors over all clips, pick 8 centres by farthest-point
sampling (first: farthest from the mean), choose r, assign members."""
import json, sys
import numpy as np

sweep = json.load(open(sys.argv[1]))
clips = sweep["clips"]
D = np.array([c["desc"] for c in clips])
mu, sd = D.mean(0), D.std(0)
sd[sd < 1e-12] = 1.0
Z = (D - mu) / sd
centres = [int(np.argmax(np.linalg.norm(Z, axis=1)))]
for _ in range(7):
    d = np.min([np.linalg.norm(Z - Z[c], axis=1) for c in centres], axis=0)
    centres.append(int(np.argmax(d)))
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
    "mean": mu.tolist(), "std": sd.tolist(), "centres": centres, "r": best,
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
print(f"r={best:.3f} (min centre dist {off.min():.2f}, mean {off.mean():.2f}, quarter {quarter:.2f})")
for k, m in enumerate(mem):
    reg = out["regions"][k]
    print(k, len(m), f"within {reg['meanWithinDistance']:.2f}", "stretch med/max",
          None if not len(m) else f"{reg['stretchMedian']:.2f}/{reg['stretchMax']:.2f}")
print("stretch of all 2000: median", np.median([c["s"] for c in clips]))
print("descriptor spread: z-dist to mean, 5/50/95 pct", np.percentile(np.linalg.norm(Z, axis=1), [5, 50, 95]).round(2))
