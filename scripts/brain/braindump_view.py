"""Static trace viewer for one brainDump (phase 4; a debugging view for the overseer, not the monitor design).

  braindump_view.py SONG [--dump DIR] [--audio FILE]
Reads <dump>/<song>.braindump.{npz,json}, writes <dump>/<song>.view.html (data inlined) and symlinks the audio into <dump>/audio/. Serve the folder with
scripts/author/serve.py (HTTP Range, so seeking works) and open <song>.view.html. Nothing derived from a song or its audio goes into git.
Rows: an 8 s strip per layer (mean over modes of Re h at 100 Hz, ending at the playhead) and whole-song lines for surprisal per layer, arousal,
self-similarity and cross-band coherence per layer (dashed = the layer's threshold, ticks = crossings). Click a whole-song row to seek. Playhead = audio.currentTime.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import b2  # noqa: E402
import braindump as bd  # noqa: E402

TEMPLATE = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>brainDump __SONG__</title>
<style>
:root{--bg:#07080a;--fg:#8a98a6;--dim:#3a4450;--ln:#b9ccdc}
body{margin:0;background:var(--bg);color:var(--fg);font:11px/1.4 ui-monospace,Menlo,Consolas,monospace}
header{display:flex;gap:16px;align-items:center;padding:8px 16px}
audio{height:28px;filter:invert(.85) grayscale(1)}canvas{display:block;width:100%}
</style>
<header><span>__SONG__ &nbsp;B7 epoch 6 &nbsp;data only, no claims</span><audio id="a" controls preload="auto" src="audio/__AUDIO__"></audio><span id="t"></span></header>
<canvas id="c"></canvas>
<script>
const D=__DATA__;
const cv=document.getElementById('c'),g=cv.getContext('2d'),a=document.getElementById('a');
const W=()=>cv.clientWidth,STRIP=8,L=['L1','L2','L3','L4'];
const rows=[...L.map((n,i)=>({k:'eeg',i,h:56,label:n+' mean Re h (8 s)'})),
 ...L.map((n,i)=>({k:'sur',i,h:34,label:'surprisal '+n})),{k:'aro',h:34,label:'arousal'},{k:'ss',h:34,label:'self-similarity'},
 ...L.map((n,i)=>({k:'coh',i,h:34,label:'cross-band coherence '+n}))];
const H=rows.reduce((s,r)=>s+r.h+6,0)+10;
function dpr(){const r=devicePixelRatio||1;cv.width=W()*r;cv.height=H*r;cv.style.height=H+'px';g.setTransform(r,0,0,r,0,0)}
function line(x0,x1,y,h,ys,lo,hi,col,fx){g.beginPath();let on=false;
 for(let j=0;j<ys.length;j++){const v=ys[j];if(v===null||v===undefined){on=false;continue}
  const x=fx(j),y1=y+h-(Math.min(Math.max((v-lo)/(hi-lo),0),1))*h;if(!on){g.moveTo(x,y1);on=true}else g.lineTo(x,y1)}
 g.strokeStyle=col;g.lineWidth=1;g.stroke()}
function draw(){const w=W(),t=a.currentTime||0,dur=D.duration;g.clearRect(0,0,w,H);g.font='10px ui-monospace,monospace';
 let y=6;const px=Math.round(t/dur*w);
 for(const r of rows){g.fillStyle='#3a4450';g.fillText(r.label,4,y+9);
  if(r.k==='eeg'){const x=D.eeg[r.i],n=Math.min(Math.floor(t*100),x.length),m=STRIP*100,s=Math.max(0,n-m);
   const sd=D.eegsd[r.i]*3;line(0,w,y,r.h,x.slice(s,n),-sd,sd,'#b9ccdc',j=>w-(n-s-j)/m*w)}
  else{const xs=r.k==='sur'?D.sur[r.i]:r.k==='aro'?D.aro:r.k==='ss'?D.ss:D.coh[r.i],hz=r.k==='coh'||r.k==='sur'||r.k==='aro'||r.k==='ss'?D.hz:10;
   const hi=r.k==='coh'?1:D.hi[r.k+(r.i===undefined?'':r.i)];
   line(0,w,y,r.h,xs,0,hi,'#8aa2b8',j=>j/hz/dur*w);
   if(r.k==='coh'){g.setLineDash([3,3]);g.strokeStyle='#3a4450';const ty=y+r.h-D.thr[r.i]*r.h;g.beginPath();g.moveTo(0,ty);g.lineTo(w,ty);g.stroke();g.setLineDash([]);
    g.strokeStyle='#d8e6f2';for(const c of D.cross){const x=c/dur*w;g.beginPath();g.moveTo(x,y+r.h-5);g.lineTo(x,y+r.h);g.stroke()}}}
  if(r.k!=='eeg'){g.strokeStyle='#4a5866';g.beginPath();g.moveTo(px+.5,y);g.lineTo(px+.5,y+r.h);g.stroke()}
  y+=r.h+6}
 document.getElementById('t').textContent=t.toFixed(1)+' s';requestAnimationFrame(draw)}
cv.addEventListener('click',e=>{const y=e.offsetY;let o=6;for(const r of rows){if(y>=o&&y<o+r.h&&r.k!=='eeg'){a.currentTime=e.offsetX/W()*D.duration;break}o+=r.h+6}});
addEventListener('resize',dpr);dpr();draw();
</script>"""


def lane10(a):
    """Series -> a list with NaN as null, 3 decimals."""
    return [None if not np.isfinite(v) else round(float(v), 3) for v in a]


def build(song, dump=bd.OUT, audio=None):
    dump = Path(dump)
    z = np.load(dump / f"{song}.braindump.npz")
    meta = json.loads((dump / f"{song}.braindump.json").read_text())
    f = lambda k: z[k].astype(np.float32)
    sur, aro, ss = f("surprisal"), f("arousal"), f("selfsimilarity")
    eeg = f("layer_mean_re")
    pct = lambda a: float(np.nanpercentile(a, 99.5)) if np.isfinite(a).any() else 1.0
    data = {"duration": meta["duration_s"], "hz": bd.HZ, "eeg": [[round(float(v), 4) for v in eeg[:, i]] for i in range(4)],
            "eegsd": [float(eeg[:, i].std()) or 1.0 for i in range(4)],
            "sur": [lane10(sur[:, i]) for i in range(4)], "aro": lane10(aro), "ss": lane10(ss),
            "coh": [lane10(f("coherence")[:, i]) for i in range(4)], "thr": meta["thresholds"],
            "cross": [round((m + 10) / 10, 1) for m in np.flatnonzero(z["crossing"])],
            "hi": {**{f"sur{i}": pct(sur[:, i]) for i in range(4)}, "aro": pct(aro), "ss": 1.0}}
    # coherence is on its own 10 Hz axis; the page treats every row but the strips as hz = 30, so resample coherence to 30 Hz by hold
    n30 = len(aro)
    for i in range(4):
        c = f("coherence")[:, i]
        idx = np.clip((np.arange(n30) / bd.HZ * 10 - 10).astype(int), -1, len(c) - 1)
        data["coh"][i] = lane10(np.where(idx >= 0, c[np.maximum(idx, 0)], np.nan))
    audio = Path(audio) if audio else b2.SONGS / b2.SONG_FILES[song][0]
    (dump / "audio").mkdir(exist_ok=True)
    link = dump / "audio" / audio.name
    if not link.exists():
        link.symlink_to(audio)
    html = TEMPLATE.replace("__SONG__", song).replace("__AUDIO__", audio.name).replace("__DATA__", json.dumps(data, separators=(",", ":"), allow_nan=False))
    out = dump / f"{song}.view.html"
    out.write_text(html)
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("song")
    ap.add_argument("--dump", default=str(bd.OUT))
    ap.add_argument("--audio")
    a = ap.parse_args()
    print(build(a.song, a.dump, a.audio))
