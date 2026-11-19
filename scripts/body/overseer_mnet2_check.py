"""Overseer's own recompute for motor-network toy round 2 (BRAIN_SPEC 7.47): gates, PR per population, ranges, drift, stop rule.
Reads the round-2 work CSVs (50 Hz, degrees) and activity arrays (columns 0-99 slow, 100-199 fast)."""
import sys, glob, numpy as np
sys.path.insert(0, "/secondary/Programming/Github/Hysteresis/.claude/worktrees/body/scripts/body")
import make_arm, m3f_report

L = np.array(make_arm.LIMITS)
W = sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/body/motornet_toy2/work"


def pr(r):
    lam = np.clip(np.linalg.eigvalsh(np.cov(r.T)), 0, None)
    return lam.sum() ** 2 / (lam ** 2).sum()


rng = lambda a: np.percentile(a, 95, 0) - np.percentile(a, 5, 0)
stop = True
for f in sorted(glob.glob(W + "/*.csv")):
    name = f.split("/")[-1][:-4]
    d = np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0] == "-"], float)
    t, q = d[:, 0], d[:, 1:6]
    v = np.gradient(q, axis=0) * 50; a = np.gradient(v, axis=0) * 50
    r = np.load(f[:-4] + ".activity.npy").astype(float)
    ps, pf = pr(r[:, :100]), pr(r[:, 100:])
    h = m3f_report.fk_points(q); hp = h[:, 5]
    hv = np.linalg.norm(np.gradient(hp, axis=0) * 50, axis=1)
    m3 = np.convolve(hv, np.ones(150) / 150, "valid").min()
    yaw = q[:, 0]; ma = np.convolve(yaw, np.ones(150) / 150, "valid")
    if name.startswith("A_"):
        stop &= bool(ps < 3 and pf < 3 and rng(yaw) < 20)
    print(name.ljust(8), f"dur {t[-1]-t[0]:.2f} n {len(q)}", "| PR slow/fast", round(ps, 2), round(pf, 2),
          "| p5-95", np.round(rng(q), 1), "| drift", round(yaw[-150:].mean() - yaw[:150].mean(), 1), "MA range", round(ma.max() - ma.min(), 1),
          "| ext", np.round(rng(hp), 3), "| hand v mean", round(hv.mean(), 3), "min3s", round(m3, 3),
          "| min link z", round(h[:, 1:5, 2].min(), 3), "hand z", round(hp[:, 2].min(), 3),
          "| v/lim max", round((np.abs(v) / L[:, 0]).max(), 2), "a/lim max", round((np.abs(a) / L[:, 1]).max(), 2))
print("STOP RULE 7.47.4.8 (all A: PR<3 both AND yaw<20):", stop)
