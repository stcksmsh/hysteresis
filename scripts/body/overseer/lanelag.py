import numpy as np, librosa
from scipy.signal import correlate
for n in ('001','043','129','200'):
    z=np.load(f'/secondary/hyst-data/body/t0/lanes/fd_{n}.npz'); E=z['ear']
    y,sr=librosa.load(f'/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/{n}.wav',sr=22050,duration=60)
    env=librosa.onset.onset_strength(y=y,sr=sr,hop_length=441)  # 50 Hz
    env=np.interp(np.arange(0,len(env)*2)/2,np.arange(len(env)),env)  # 100 Hz
    best=[]
    for c in range(E.shape[1]):
        a=E[:len(env),c]; m=min(len(a),len(env)); a=(a[:m]-a[:m].mean())/(a[:m].std()+1e-9); b=(env[:m]-env[:m].mean())/(env[:m].std()+1e-9)
        x=correlate(a,b,'full')/m; L=np.arange(-m+1,m); k=np.abs(L)<=300
        i=np.argmax(x[k]); best.append((x[k][i],L[k][i],c))
    best.sort(reverse=True); print(n,'lanes len',len(E),'top cols (corr, lag frames@100Hz, col):',[(round(a,2),l,c) for a,l,c in best[:4]], 'col40:',[(round(a,2),l) for a,l,c in best if c==40])
