import sys, glob, numpy as np
sys.path.insert(0, "/secondary/Programming/Github/Hysteresis/.claude/worktrees/body/scripts/body")
import make_arm, m3f_report
L = np.array(make_arm.LIMITS)
for f in sorted(glob.glob("/secondary/hyst-data/body/motornet_toy/work/P*.csv")):
    d = np.loadtxt(f, delimiter=",", comments="#", skiprows=0, usecols=range(6), converters=None, ndmin=2) if False else np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0]=="-"], float)
    t = d[:,0]; q = d[:,1:6]; cols=("",)
    hz = 1 / np.median(np.diff(t))
    v = np.gradient(q, axis=0) * hz; a = np.gradient(v, axis=0) * hz
    sat = (np.abs(v) > 0.9 * L[:, 0]).mean(0)
    rng = np.percentile(q, 95, 0) - np.percentile(q, 5, 0)
    pts = m3f_report.fk_points(q); h = pts[:, 5]
    ext = np.percentile(h, 95, 0) - np.percentile(h, 5, 0)
    hs = np.linalg.norm(np.gradient(h, axis=0), axis=1) * hz
    print(f.split("/")[-1][:-4].ljust(12), "\n  range deg", np.round(rng, 1), "| v>0.9lim share", np.round(sat, 2),
          "| ext m", np.round(ext, 3), "| hand v mean", round(hs.mean(), 3), "| min z", round(pts[:, 1:, 2].min(), 3), round(h[:, 2].min(), 3))
print("--- acc share >0.9 lim, joint dominant freq, activity PR")
import json
for f in sorted(glob.glob("/secondary/hyst-data/body/motornet_toy/work/P1_*.csv")):
    d = np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0]=="-"], float); q = d[:,1:6]
    v = np.gradient(q, axis=0)*50; a = np.gradient(v, axis=0)*50
    accs = (np.abs(a) > 0.9*L[:,1]).mean(0)
    x = (q-q.mean(0))*np.hanning(len(q))[:,None]; P = np.abs(np.fft.rfft(x,axis=0))**2; fr = np.fft.rfftfreq(len(q),1/50)
    r = np.load(f[:-4]+".activity.npy").astype(float); lam = np.clip(np.linalg.eigvalsh(np.cov(r.T)),0,None)
    print(f.split("/")[-1][:-4], "acc>0.9 share", np.round(accs,2), "| joint peak Hz", np.round(fr[np.argmax(P[1:],0)+1],2), "| PR", round(lam.sum()**2/(lam**2).sum(),2), "| r sd", round(r.std(),3), "| mean|r|", round(np.abs(r).mean(),3))
