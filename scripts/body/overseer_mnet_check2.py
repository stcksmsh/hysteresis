import sys, glob, numpy as np
sys.path.insert(0, "/secondary/Programming/Github/Hysteresis/.claude/worktrees/body/scripts/body")
import make_arm, m3f_report
L = np.array(make_arm.LIMITS); F0 = 100/60; allbeat = True
for f in sorted(glob.glob("/secondary/hyst-data/body/motornet_toy/work/P*.csv")):
    d = np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0]=="-"], float); q = d[:,1:6]
    v = np.gradient(q,axis=0)*50; a = np.gradient(v,axis=0)*50
    x = (q-q.mean(0))*np.hanning(len(q))[:,None]; P = np.abs(np.fft.rfft(x,axis=0))**2; fr = np.fft.rfftfreq(len(q),1/50)
    pk = fr[np.argmax(P[1:],0)+1]; beat = np.all(np.abs(pk-F0) <= 1/12+1e-9)
    r = np.load(f[:-4]+".activity.npy").astype(float); lam = np.clip(np.linalg.eigvalsh(np.cov(r.T)),0,None); pr = lam.sum()**2/(lam**2).sum()
    if f.split("/")[-1].startswith("P1"): allbeat &= bool(beat and pr < 3)
    h = m3f_report.fk_points(q); hp = h[:,5]; ext = np.percentile(hp,95,0)-np.percentile(hp,5,0)
    print(f.split("/")[-1][:-4].ljust(12), "peaks", np.round(pk,2), "allbeat" if beat else "", "| PR", round(pr,2),
      "| range", np.round(np.percentile(q,95,0)-np.percentile(q,5,0),1), "| ext", np.round(ext,3),
      "| min link z", round(h[:,1:5,2].min(),3), "hand z", round(hp[:,2].min(),3),
      "| v/lim max", round((np.abs(v)/L[:,0]).max(),2), "a/lim p99", round(np.percentile(np.abs(a)/L[:,1],99),2))
print("STOP RULE 7.45.5 triggered (all P1 beat-locked and PR<3):", allbeat)
