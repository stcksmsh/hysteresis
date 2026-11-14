"""report6.py SWEEP.json: the round-2 sweep reports of docs/BODY_STUDY.md addendum 8.

Reports only, never gates: mean joint speed over bodies (histogram, p10, p90, their
ratio), per-joint shares of motion, still time, rejections by rule and by parameter
decile. Mean joint speed of a clip = mean over the five joints of each joint's mean
speed (descriptors 0, 6, 12, 18, 24), deg/s, on the shown 8 s at 60 fps.
"""
import json, sys
import numpy as np

d = json.load(open(sys.argv[1]))
P = d["params"]; clips = d["clips"]
J = ["yaw", "shoulder", "elbow", "wrist", "roll"]
print("attempts", d["attempts"], "passed", d["passed"], "body dimensions", len(P))
print("rejected, first rule at stretch 1.95:", d["rejectReasonAtTopOfLadder"])
print("rejected, every rule broken at stretch 1:", d["rejectRulesAtStretch1"])
print("rejected by parameter decile (rejected/attempted):")
for i, p in enumerate(P):
    print(f"  {p:22s}", " ".join(f"{d['rejectedByDecile'][i][k]}/{d['attemptedByDecile'][i][k]}" for k in range(10)))
print("stretch histogram 1.1^0..7:", d["stretchHistogram"])

B = np.array([c["b"] for c in clips]); D = np.array([c["desc"] for c in clips])
M = np.array([c["motion"] for c in clips])
S = D[:, [6 * j for j in range(5)]]
ms = S.mean(1)
p10, p50, p90 = np.percentile(ms, [10, 50, 90])
print(f"mean joint speed deg/s: min {ms.min():.1f} p10 {p10:.1f} median {p50:.1f} p90 {p90:.1f} max {ms.max():.1f}; p90/p10 {p90 / p10:.2f}")
h, e = np.histogram(ms, bins=12)
print("  histogram:", " ".join(f"{e[k]:.1f}-{e[k+1]:.1f}:{h[k]}" for k in range(12)))
for j, n in enumerate(J):
    print(f"  {n:8s} mean speed p10 {np.percentile(S[:, j], 10):.1f} median {np.median(S[:, j]):.1f} p90 {np.percentile(S[:, j], 90):.1f}")
print("mean joint speed by parameter decile (median per decile; Spearman rho):")
for i, p in enumerate(P):
    dec = np.minimum((B[:, i] * 10).astype(int), 9)
    med = [np.median(ms[dec == k]) for k in range(10)]
    rb = np.argsort(np.argsort(B[:, i])); rm = np.argsort(np.argsort(ms))
    rho = np.corrcoef(rb, rm)[0, 1]
    print(f"  {p:22s} rho {rho:+.2f} ", " ".join(f"{v:.1f}" for v in med))
Sh = M / M.sum(1, keepdims=True)
print("share of total joint motion (median, p10, p90):")
for j, n in enumerate(J):
    print(f"  {n:8s} {np.median(Sh[:, j]):.3f} {np.percentile(Sh[:, j], 10):.3f} {np.percentile(Sh[:, j], 90):.3f}")
run = np.array([c["stillRun"] for c in clips]); share = np.array([c["stillShare"] for c in clips])
print(f"all joints still, longest run s: median {np.median(run):.2f} p90 {np.percentile(run, 90):.2f} max {run.max():.2f}")
print(f"all joints still, share of clip: median {np.median(share):.3f} p90 {np.percentile(share, 90):.3f} max {share.max():.3f}; clips with any still frame {int((share > 0).sum())}")
mv = np.array([c["movement"] for c in clips])
for k, n in enumerate(["hand path m", "hand box m", "base turn deg"]):
    print(f"{n}: p10 {np.percentile(mv[:, k], 10):.2f} median {np.median(mv[:, k]):.2f} p90 {np.percentile(mv[:, k], 90):.2f}")
