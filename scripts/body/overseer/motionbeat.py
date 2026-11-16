# Overseer independent check: does lamp motion (whole-song realised, V1/V2) carry the music's beat period and phase?
import json, glob, numpy as np, librosa
from scipy.signal import find_peaks, welch
rng=np.random.default_rng(1)
def R(ev,b):
    b=np.asarray(b); ev=ev[(ev>b[0])&(ev<b[-1])]
    if len(ev)<10: return np.nan
    i=np.searchsorted(b,ev)-1; ph=(ev-b[i])/(b[i+1]-b[i]); return abs(np.exp(2j*np.pi*ph).mean())
rows=[]
songs=sorted({p.split('/')[-1].split('__')[0] for p in glob.glob('/secondary/hyst-data/body/metric/q50/finedance/*__V2.npz')})
for s in rng.choice(songs,25,replace=False):
    n=s.split('_')[1]
    y,sr=librosa.load(f'/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/{n}.wav',sr=22050)
    env=librosa.onset.onset_strength(y=y,sr=sr,hop_length=441)       # 50 Hz
    _,lb=librosa.beat.beat_track(onset_envelope=env,sr=sr,hop_length=441,units='time')
    if len(lb)<20: continue
    fb=1/np.median(np.diff(lb))
    out=[s,fb*60]
    for cp in ('V1','V2'):
        z=np.load(f'/secondary/hyst-data/body/metric/q50/finedance/{s}__{cp}.npz'); L=z['lamp']
        sp=np.linalg.norm(np.gradient(L,axis=0)*50,axis=1)
        m=min(len(sp),len(env)); a=sp[:m]-sp[:m].mean(); e=env[:m]-env[:m].mean()
        f,P=welch(a,fs=50,nperseg=1024)
        def band(fr): return P[(f>fr*0.97)&(f<fr*1.03)].mean()/np.median(P[(f>0.3)&(f<8)])
        # cross-correlation lamp speed vs onset envelope, lags -1..1 s
        xc=[np.corrcoef(a[max(0,-k):m-max(0,k)],e[max(0,k):m-max(0,-k)])[0,1] for k in range(-50,51)]
        mins,_=find_peaks(-np.convolve(sp,np.ones(5)/5,'same'),prominence=0.05,distance=10); ev=mins/50
        sh=np.concatenate([[lb[0]],lb[0]+np.cumsum(rng.permutation(np.diff(lb)))])
        Rw=[];Rws=[]
        for t0 in np.arange(lb[0],lb[-1]-20,20):
            bb=lb[(lb>=t0)&(lb<t0+20)]; ee=ev[(ev>=t0)&(ev<t0+20)]
            if len(bb)<8 or len(ee)<10: continue
            Rw.append(R(ee,bb)); d=np.diff(bb); sb=np.concatenate([[bb[0]],bb[0]+np.cumsum(rng.permutation(d))]); Rws.append(R(ee,sb+rng.uniform(0,d.mean())))
        out+= [band(fb),band(fb*1.13),band(fb/2),band(fb/2*1.13), max(xc), R(ev,lb), R(ev,sh), np.nanmean(Rw), np.nanmean(Rws)]
    rows.append(out)
A=np.array([r[1:] for r in rows],float)
names=['BPM']+[f'{c} {k}' for c in ('V1','V2') for k in ('P@beat','P@1.13beat(ctl)','P@halfbeat','P@1.13half(ctl)','max xcorr','R whole','R whole shuffled','R per20s','R per20s shifted')]
for i,nm in enumerate(names): print('%-22s median %.3f  [p25 %.3f p75 %.3f]'%(nm,*np.nanpercentile(A[:,i],[50,25,75])))
