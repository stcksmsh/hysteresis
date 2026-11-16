# Overseer recompute of WO43 controls from the saved lamp/q50 (independent code, rules section 3)
import numpy as np, json, sys
from scipy.signal import butter, filtfilt
B='/secondary/hyst-data/body/controls/'
T=np.load(B+'tables/finedance.npz',allow_pickle=True)
norm=json.load(open(B+'norm.json'))
names=sys.argv[1:]
for nm in names:
    z=np.load(B+'q50/finedance/'+nm+'.npz')
    m=(T['fidx']==T['fidx'][0])  # placeholder
    song,cp=nm.split('__'); ci=('V1','V2','V1m','V2m').index(cp)
    sel=(T['lane']==song)&(T['copy']==ci)
    rows=np.where(sel)[0]
    errs={k:[] for k in ('vj','vl','height','pause_prob','sharp')}
    b,a=butter(2,3/25,'high')
    for wi,(q,l) in enumerate(zip(z['q50'].astype(float),z['lamp'])):
        w=np.gradient(q,axis=0)*50; v=np.gradient(l,axis=0)*50; acc=np.gradient(v,axis=0)*50
        ahp=filtfilt(b,a,acc,axis=0); sp=np.linalg.norm(v,axis=1); low=sp<0.05
        inp=np.zeros(len(sp),bool); i=0
        while i<len(sp):
            if low[i]:
                j=i
                while j<len(sp) and low[j]: j+=1
                if j-i>=13: inp[i:j]=True
                i=j
            else: i+=1
        win=z['win'][wi]; r=rows[T['win'][rows]==win]
        for k in range(40):
            s=slice(25*k,25*k+25); t=r[T['k'][r]==k]
            if len(t)!=1: continue
            t=t[0]
            mine=dict(vj=np.sqrt((w[s]**2).mean()), vl=np.sqrt((sp[s]**2).mean()),
                      height=np.clip((l[s,2].mean()-0.11)/0.66,0,1), pause_prob=inp[s].mean(),
                      sharp=(ahp[s]**2).sum()/(acc[s]**2).sum() if np.sqrt((acc[s]**2).sum(1).mean())>=0.05 else np.nan)
            for kk,vv in mine.items():
                if not (np.isnan(vv) and np.isnan(T[kk][t])): errs[kk].append(abs(vv-T[kk][t]))
    print(nm,{k:(len(v),float(np.nanmax(v)) if v else None) for k,v in errs.items()})
