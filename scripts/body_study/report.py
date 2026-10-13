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
V = np.array([c["movement"] for c in clips])
J = ["yaw", "shoulder", "elbow", "wrist", "roll"]
VN = ["path m", "box m", "turn deg"]
p90 = D[:, [6 * j + 1 for j in range(5)]]
for name in ["time", "weight", "flow", "space"]:
    k = P.index(name); lo = B[:, k] < 0.2; hi = B[:, k] > 0.8
    print(f"{name}: n low {lo.sum()} high {hi.sum()}")
    for tag, m in (("low ", lo), ("high", hi)):
        print(f"  {tag} p90 joint speed deg/s:", dict(zip(J, np.median(p90[m], 0).round(1))))
        print(f"  {tag} total motion deg:", dict(zip(J, np.median(M[m], 0).round(0))), "sum", round(float(np.median(M[m].sum(1))), 0))
        print(f"  {tag} movement:", dict(zip(VN, np.median(V[m], 0).round(2))))
for i, n in enumerate(VN):
    h, e = np.histogram(V[:, i], bins=10)
    print(f"histogram {n}:", " ".join(f"{e[k]:.2f}-{e[k+1]:.2f}:{h[k]}" for k in range(10)))
