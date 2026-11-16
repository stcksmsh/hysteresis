# Overseer recompute of WO47 V1: 8-beat line residual per grid; yaw-velocity-peak local locking vs librosa lines (FineDance V1/V2 realised).
import json, glob, numpy as np
from scipy.signal import find_peaks
rng=np.random.default_rng(5)
def fit(b): k=np.arange(len(b)); T,t0=np.polyfit(k,b,1); return t0,T,np.sqrt(np.mean((b-(t0+T*k))**2))
def Rw(ev,t0,T): ph=((ev-t0)/T)%1; return abs(np.exp(2j*np.pi*ph).mean())
res={'proj':[], 'lib':[]}; ex={'V1':[],'V2':[]}
songs=sorted(glob.glob('/secondary/hyst-data/body/beatv/librosa/fd_*.json'))
for f in rng.choice(songs,40,replace=False):
    key=f.split('/')[-1][:-5]
    lib=np.array(json.load(open(f))['beats'] if isinstance(json.load(open(f)),dict) else json.load(open(f)))
    proj=np.array(json.load(open(f'/secondary/hyst-data/body/t1b/cortex/beats/{key}.json'))['beats'])
    for nm,b in (('proj',proj),('lib',lib)):
        r=[fit(b[i:i+8])[2] for i in range(0,len(b)-8,2)]; res[nm].append(np.median(r)*1000)
    for cp in ('V1','V2'):
        p=f'/secondary/hyst-data/body/metric/q50/finedance/{key}__{cp}.npz'
        try: q=np.load(p)['q50']
        except FileNotFoundError: continue
        w=np.abs(np.gradient(q[:,0])*50); w=np.convolve(w,np.ones(5)/5,'same')
        pk,_=find_peaks(w,prominence=0.25*np.percentile(w,90),distance=10); ev=pk/50
        d=[]
        for i in range(0,len(lib)-8,2):
            bb=lib[i:i+8]; e=ev[(ev>=bb[0])&(ev<bb[-1])]
            if len(e)<6: continue
            t0,T,_=fit(bb); d.append(Rw(e,t0,T)-0.5*(Rw(e,t0,1.13*T)+Rw(e,t0,0.87*T)))
        if d: ex[cp].append(np.median(d))
print('8-beat line residual ms, median over songs: project %.0f [p25 %.0f p75 %.0f], librosa %.1f'%(np.median(res['proj']),*np.percentile(res['proj'],[25,75]),np.median(res['lib'])))
for cp in ex:
    a=np.array(ex[cp]); bs=[np.median(rng.choice(a,len(a))) for _ in range(2000)]
    print(cp,'yaw peaks local excess vs librosa lines: median %.3f [%.3f, %.3f], n %d'%(np.median(a),*np.percentile(bs,[2.5,97.5]),len(a)))
