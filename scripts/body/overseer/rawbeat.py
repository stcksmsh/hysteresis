# Overseer: beat locking of RAW FineDance mocap (body angular speed from 6D rotations, 30 fps), vs librosa beats.
import glob, numpy as np, librosa
from scipy.signal import find_peaks, welch
rng=np.random.default_rng(2)
def rot6(x):
    a=x[...,0:3]; b=x[...,3:6]
    a=a/np.linalg.norm(a,axis=-1,keepdims=True); b=b-(a*b).sum(-1,keepdims=True)*a; b=b/np.linalg.norm(b,axis=-1,keepdims=True)
    return np.stack([a,b,np.cross(a,b)],-1)
def R(ev,b):
    b=np.asarray(b); ev=ev[(ev>b[0])&(ev<b[-1])]
    if len(ev)<10: return np.nan
    i=np.searchsorted(b,ev)-1; ph=(ev-b[i])/(b[i+1]-b[i]); return abs(np.exp(2j*np.pi*ph).mean())
D='/secondary/hyst-data/datasets/finedance/data/finedance/'
rows=[]
for n in rng.choice([f'{i:03d}' for i in range(1,212)],30,replace=False):
    try: m=np.load(D+f'motion/{n}.npy')
    except FileNotFoundError: continue
    Rm=rot6(m[:,3:].reshape(len(m),-1,6)[:,:22])            # body joints
    dR=np.einsum('tjab,tjac->tjbc',Rm[:-1],Rm[1:]); ang=np.arccos(np.clip((np.trace(dR,axis1=2,axis2=3)-1)/2,-1,1))
    sp=ang.sum(1)*30; sp=np.r_[sp,sp[-1]]                    # rad/s, 30 fps
    y,sr=librosa.load(D+f'music_wav/{n}.wav',sr=22050)
    env=librosa.onset.onset_strength(y=y,sr=sr,hop_length=735)  # 30 Hz
    _,lb=librosa.beat.beat_track(onset_envelope=env,sr=sr,hop_length=735,units='time')
    if len(lb)<20: continue
    fb=1/np.median(np.diff(lb)); M=min(len(sp),len(env)); a=sp[:M]-sp[:M].mean(); e=env[:M]-env[:M].mean()
    f,P=welch(a,fs=30,nperseg=512)
    band=lambda fr: P[(f>fr*0.97)&(f<fr*1.03)].mean()/np.median(P[(f>0.3)&(f<8)])
    xc=max(np.corrcoef(a[max(0,-k):M-max(0,k)],e[max(0,k):M-max(0,-k)])[0,1] for k in range(-30,31))
    mins,_=find_peaks(-np.convolve(sp,np.ones(3)/3,'same'),distance=6,prominence=np.std(sp)*0.2); ev=mins/30
    sh=np.concatenate([[lb[0]],lb[0]+np.cumsum(rng.permutation(np.diff(lb)))])
    rows.append([fb*60,band(fb),band(fb*1.13),band(2*fb),band(2*fb*1.13),xc,R(ev,lb),R(ev,sh)])
A=np.array(rows)
for i,nm in enumerate(['BPM','P@beat','P@1.13beat ctl','P@2beat','P@2.26beat ctl','max xcorr w/ onset','R minima vs beats','R minima vs shuffled']):
    print('%-22s median %.3f [p25 %.3f p75 %.3f]'%(nm,*np.nanpercentile(A[:,i],[50,25,75])))
print('songs',len(A))
