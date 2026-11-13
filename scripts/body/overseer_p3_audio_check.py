import sys,glob,subprocess,numpy as np
sys.path.insert(0,"/secondary/Programming/Github/Hysteresis/.claude/worktrees/body/scripts/body")
import m3f_report
C="/secondary/hyst-data/body/motornet_toy/clips/"
src={"1":("Blue Lagoon - Masayoshi Takanaka.mp3",20),"2":("King Crimson - 21st Century Schizoid Man (Including Mirrors) - King Crimson.mp3",58),
"3":("King Crimson - Epitaph (Including March For No Reason and Tomorrow And Tomorrow) - King Crimson.mp3",345),"4":("Pink Floyd - Breathe (In The Air) (2023 Remaster) - Pink Floyd.mp3",77),
"5":("Pink Floyd - One Of These Days (Official Audio) - Pink Floyd.mp3",237)}
def pcm(args):
    return np.frombuffer(subprocess.run(["ffmpeg","-v","error"]+args+["-ac","1","-ar","8000","-f","f32le","-"],capture_output=True).stdout,np.float32)
for f in sorted(glob.glob(C+"P3_*.mp4")):
    k=f.split("P3_")[1][0]; mp3,t0=src[k]
    q=np.array([l.split(",") for l in open(f[:-4]+".csv") if l[0].isdigit() or l[0]=="-"],float)[:,1:6]
    h=m3f_report.fk_points(q)[:,5]; v=np.linalg.norm(np.gradient(h,axis=0),axis=1)*50
    st=np.convolve(v,np.ones(150)/150,"valid").min()
    a=pcm(["-i",f]); b=pcm(["-ss",str(t0-1),"-t","14","-i","/secondary/hyst-data/audio/checkset/"+mp3])
    x=np.correlate(b,a[:8000*10],"valid"); lag=(np.argmax(x)/8000)-1
    dur=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f],capture_output=True,text=True).stdout.strip()
    print(f.split("/")[-1], "dur",dur,"audio s",round(len(a)/8000,2),"offset vs excerpt start s",round(lag,3),"| hand v mean",round(v.mean(),3),"min 3s-mean",round(st,3))
