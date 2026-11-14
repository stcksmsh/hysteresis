import glob, numpy as np
def load(f):
    d=np.array([l.split(",") for l in open(f) if l[0].isdigit() or l[0]=="-"],float); return d[:,1:6]
def share(q, f0=2.0):
    v=np.gradient(q,axis=0)*50; P=np.abs(np.fft.rfft(v*np.hanning(len(v))[:,None],axis=0))**2; fr=np.fft.rfftfreq(len(v),1/50)
    return P[fr>f0].sum(0)/P[fr>0].sum(0)
def rev(q):  # velocity sign changes per s per joint
    v=np.gradient(q,axis=0)*50; return (np.diff(np.sign(v),axis=0)!=0).sum(0)/(len(q)/50)
rows=[("R2 "+f.split("/")[-1][:-4], f) for f in sorted(glob.glob("/secondary/hyst-data/body/motornet_toy2/work/*.csv"))]
rows+=[("R1 "+f.split("/")[-1][:-4], f) for f in sorted(glob.glob("/secondary/hyst-data/body/motornet_toy/work/P1_*.csv"))+sorted(glob.glob("/secondary/hyst-data/body/motornet_toy/clips/P3_*.csv"))]
print("joints: yaw shoulder elbow wristbend roll | share of velocity power >2 Hz | velocity sign changes per s")
for n,f in rows:
    q=load(f); print(n.ljust(14), np.round(share(q),3), np.round(rev(q),1))
