"""report.py SWEEP.json: sweep numbers for docs/BODY_STUDY.md step 1."""
import json, sys, collections
import numpy as np
d = json.load(open(sys.argv[1]))
P = d["params"]; clips = d["clips"]
print("attempts", d["attempts"], "passed", d["passed"])
print("rejected, first rule at stretch 1.95:", d["rejectReasonAtTopOfLadder"])
print("rejected, every rule broken at stretch 1:", d["rejectRulesAtStretch1"])
c1 = collections.Counter(k for c in clips for k in c["fail1"])
print("passing clips that failed at stretch 1 (rule: count):", dict(c1),
      "clean at 1:", sum(1 for c in clips if not c["fail1"]))
print("stretch histogram 1.1^0..7:", d["stretchHistogram"])
print("rejection rate by parameter decile (rejected/attempted):")
for i, p in enumerate(P):
    print(f"  {p:22s}", " ".join(f"{d['rejectedByDecile'][i][k]}/{d['attemptedByDecile'][i][k]}" for k in range(10)))
B = np.array([c["b"] for c in clips]); D = np.array([c["desc"] for c in clips]); M = np.array([c["motion"] for c in clips])
J = ["yaw", "shoulder", "elbow", "wrist", "roll"]
p90 = D[:, [6 * j + 1 for j in range(5)]]
for name in ["time", "weight", "flow", "space"]:
    k = P.index(name); lo = B[:, k] < 0.2; hi = B[:, k] > 0.8
    print(f"{name}: n low {lo.sum()} high {hi.sum()}")
    print("  p90 joint speed deg/s low :", dict(zip(J, np.median(p90[lo], 0).round(1))))
    print("  p90 joint speed deg/s high:", dict(zip(J, np.median(p90[hi], 0).round(1))))
    print("  total motion deg low :", dict(zip(J, np.median(M[lo], 0).round(0))), "sum", round(float(np.median(M[lo].sum(1))), 0))
    print("  total motion deg high:", dict(zip(J, np.median(M[hi], 0).round(0))), "sum", round(float(np.median(M[hi].sum(1))), 0))
