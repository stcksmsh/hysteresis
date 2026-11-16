# Overseer: grids vs raw audio (librosa onset envelope + librosa's own beat tracker) on FineDance songs.
import json, numpy as np, librosa, sys
def R(ev,b):
    b=np.asarray(b); ev=ev[(ev>b[0])&(ev<b[-1])]
    i=np.searchsorted(b,ev)-1; ph=(ev-b[i])/(b[i+1]-b[i])
    z=np.exp(2j*np.pi*ph).mean(); return abs(z), (np.angle(z)/(2*np.pi))%1
for n in ('001','014','043','077','129','161','176','200'):
    try: b=np.array(json.load(open(f'/secondary/hyst-data/body/t1b/cortex/beats/fd_{n}.json'))['beats'])
    except FileNotFoundError: print(n,'no grid'); continue
    y,sr=librosa.load(f'/secondary/hyst-data/datasets/finedance/data/finedance/music_wav/{n}.wav',sr=22050,duration=120)
    env=librosa.onset.onset_strength(y=y,sr=sr); on=librosa.onset.onset_detect(onset_envelope=env,sr=sr,units='time')
    tempo,lb=librosa.beat.beat_track(onset_envelope=env,sr=sr,units='time')
    b=b[b<120]
    r_grid=R(on,b); r_lib=R(on,lb)
    print(n,'grid BPM %.1f lib BPM %.1f | onset R vs grid %.2f@%.2f vs librosa %.2f@%.2f | grid first beats'%(60/np.median(np.diff(b)),float(np.atleast_1d(tempo)[0]),*r_grid,*r_lib), np.round(b[:3],2), 'lib', np.round(lb[:3],2))
