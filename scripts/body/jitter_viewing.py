"""WO34: one jitter VIEWING video for Kosta (view only, not a test). 2x2 panels, clips C05_V1 then C04_V2, 6 s slice at 1x with music then 0.5x without.
Panels: (1) FineDance stick figure, (2) stage 1 raw command (kinematic), (3) stage 4 as shown, (4) H1 realised. Reuses the look-test renderer (ensemble_preview page, retarget_page patch,
record_ensemble.cjs) for the robot panels; the stick figure is a canvas page recorded by the same recorder. Resume-safe: existing outputs are kept.
Run (body env): python -u jitter_viewing.py        -> /secondary/hyst-data/body/retarget_look/jitter/viewing/{jitter_viewing.mp4, viewing.json, contact_sheet.png}
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402
import retarget_page as RP  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LOOK = Path("/secondary/hyst-data/body/retarget_look")
VIEW = LOOK / "jitter" / "viewing"
WORK = VIEW / "work"
ENS = "/secondary/hyst-data/cargo-target-dial/release/examples/ensemble_preview"
CLIPS = ("C05_V1", "C04_V2")                       # fixed by the overseer (WO34)
SLICE_S = 6.0
FPS = 30
PARENT = [-1, 0, 0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 12, 13, 14, 16, 17, 18, 19]
# canonical T-pose offsets (m, y up, +x the subject's left, +z forward) from each joint's parent; plain human proportions, no SMPL model file
OFF = np.array([[0, 0, 0], [.09, -.09, 0], [-.09, -.09, 0], [0, .11, 0], [0, -.40, 0], [0, -.40, 0], [0, .13, 0], [0, -.40, 0], [0, -.40, 0], [0, .05, 0], [0, -.06, .14], [0, -.06, .14],
                [0, .20, 0], [.04, .19, 0], [-.04, .19, 0], [0, .13, 0], [.12, 0, 0], [-.12, 0, 0], [.26, 0, 0], [-.26, 0, 0], [.25, 0, 0], [-.25, 0, 0]], float)
DRIVER = {"V1": {14, 17, 19, 21}, "V2": {3, 6, 9, 12, 15}}         # joints (bone to the parent) coloured gold: the ones that drive the robot in that variant
LABELS = {1: ("human (FineDance), stick figure", "centred on the root; gold = joints that drive the robot"),
          2: ("stage 1: raw retargeted command (kinematic, no limiter, no servo)", "range limits and the column are not enforced"),
          3: ("stage 4: as shown in the look test", "realised, limiter + servo + body"),
          4: ("H1: spinal layer before the limiter (realised)", "round-1 spinal 3 Hz, zeta 0.7; limiter + servo + body")}


def sh(cmd, **kw):
    subprocess.run(cmd, check=True, **kw)


# ------------------------------------------------------------------------------------------------ slice
def pick_slice(q50):
    """6 s window (starts every 0.1 s) with the most realised wrist-bend acceleration sign changes (jitter_diag counting rule); earliest on a tie -> (start_s, count, all counts)"""
    x, n, step = q50[:, 3], round(SLICE_S * 50), 5
    counts = []
    for i in range(0, len(x) - n, step):
        w = x[i:i + n + 1]
        counts.append(int(round(J.measures(w, 50.0)["acc_sign_changes_per_s"] * (len(w) / 50.0))))
    k = int(np.argmax(counts))                                 # argmax returns the first (earliest) maximum
    return k * step / 50.0, counts[k], counts


# ------------------------------------------------------------------------------------------------ human stick figure
def human_frames(seq, t0, t1):
    """FineDance joints (22, world metres, y up, root-centred horizontally) at dataset frames covering [t0, t1] seconds of the sequence -> (times, (n, 22, 3))"""
    a = np.load(RR.FD / "motion" / f"{seq}.npy").astype(np.float64)
    k0, k1 = max(0, int(np.floor(t0 * FPS))), min(len(a) - 1, int(np.ceil(t1 * FPS)))
    R = RT.six_to_matrix(a[k0:k1 + 1, 3:].reshape(-1, 52, 6)[:, :22])
    n = len(R)
    G = np.zeros((n, 22, 3, 3))
    P = np.zeros((n, 22, 3))
    for j in range(22):
        p = PARENT[j]
        if p < 0:
            G[:, j] = R[:, j]
            P[:, j] = np.array([0, 0.95, 0]) + a[k0:k1 + 1, :3] * np.array([0, 1, 0])
        else:
            G[:, j] = G[:, p] @ R[:, j]
            P[:, j] = P[:, p] + np.einsum("tij,j->ti", G[:, p], OFF[j])
    root = P[:, 0].copy()
    P[:, :, 0] -= root[:, None, 0]
    P[:, :, 2] -= root[:, None, 2]
    return np.arange(k0, k1 + 1) / FPS, P


def stick_page(path, seq, var, start_s, a, label):
    t, P = human_frames(seq, start_s + a - 0.3, start_s + a + SLICE_S + 0.3)
    W = np.stack([P[..., 2], P[..., 0], P[..., 1]], -1)          # world: X forward (human z), Y left (human x), Z up (human y)
    yaw, pitch = -0.6, 0.35
    zc = float((W[..., 2].min() + 0.0 + W[..., 2].max()) / 2)
    ext = np.abs(W[..., :2]).max()
    dist = 5.0
    for d in np.arange(2.5, 12.0, 0.1):                          # smallest distance that holds every joint (and the floor) inside the 1280x720 frame with a margin
        eye = np.array([0, 0, zc]) + d * np.array([np.cos(pitch) * np.cos(yaw), np.cos(pitch) * np.sin(yaw), np.sin(pitch)])
        fw = -(eye - np.array([0, 0, zc])) / d
        rt = np.cross(fw, [0, 0, 1])
        rt /= np.linalg.norm(rt)
        up = np.cross(rt, fw)
        pts = np.concatenate([W.reshape(-1, 3), np.array([[2, 2, 0], [-2, -2, 0], [2, -2, 0], [-2, 2, 0]], float)])
        v = pts - eye
        dep = v @ fw
        sx, sy = 640 + (v @ rt) * 1800 / dep, 315 - (v @ up) * 1800 / dep
        if sx.min() > 60 and sx.max() < 1220 and sy.min() > 80 and sy.max() < 690:
            dist = float(d)
            break
    gold = sorted(DRIVER[var])
    html = f"""<!doctype html><meta charset="utf-8"><title>stick</title><body style="margin:0;background:#070b10"><canvas id="ensemble" width="1280" height="720"></canvas><script>
const T={json.dumps([round(float(x), 5) for x in t])}, P={json.dumps(np.round(W, 4).tolist())}, PARENT={json.dumps(PARENT)}, GOLD=new Set({json.dumps(gold)}), START={start_s!r};
const ctx=document.getElementById('ensemble').getContext('2d'), yaw={yaw}, pitch={pitch}, dist={dist}, zc={zc};
const target=[0,0,zc], eye=[target[0]+dist*Math.cos(pitch)*Math.cos(yaw),target[1]+dist*Math.cos(pitch)*Math.sin(yaw),target[2]+dist*Math.sin(pitch)];
const sub=(a,b)=>a.map((v,i)=>v-b[i]), dot=(a,b)=>a.reduce((s,v,i)=>s+v*b[i],0), cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]], norm=a=>a.map(v=>v/Math.hypot(...a));
const fw=norm(sub(target,eye)), rt=norm(cross(fw,[0,0,1])), up=cross(rt,fw);
function pr(p){{const v=sub(p,eye),d=dot(v,fw),s=1800/Math.max(d,.1);return [640+dot(v,rt)*s,315-dot(v,up)*s,d];}}
function pose(ts){{let i=0;while(i<T.length-2&&T[i+1]<ts)i++;const a=Math.min(1,Math.max(0,(ts-T[i])/(T[i+1]-T[i])));return P[i].map((p,j)=>p.map((v,k)=>v+(P[i+1][j][k]-v)*a));}}
function draw(t){{
  const g=ctx.createLinearGradient(0,0,0,720);g.addColorStop(0,'#070b10');g.addColorStop(1,'#111b25');ctx.fillStyle=g;ctx.fillRect(0,0,1280,720);
  const fl=[[-2,-2,0],[2,-2,0],[2,2,0],[-2,2,0]].map(pr);ctx.fillStyle='#16242d';ctx.beginPath();fl.forEach((q,i)=>i?ctx.lineTo(q[0],q[1]):ctx.moveTo(q[0],q[1]));ctx.closePath();ctx.fill();
  const J=pose(START+t);ctx.lineCap='round';
  const order=[...Array(22).keys()].slice(1).sort((a,b)=>pr(J[b])[2]-pr(J[a])[2]);
  for(const j of order){{const a=pr(J[PARENT[j]]),b=pr(J[j]);ctx.strokeStyle=GOLD.has(j)?'#efb869':'#aebcc4';ctx.lineWidth=GOLD.has(j)?9:6;ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.stroke();}}
  for(const j of order){{const b=pr(J[j]);ctx.fillStyle=GOLD.has(j)?'#efb869':'#dfe8ec';ctx.beginPath();ctx.arc(b[0],b[1],GOLD.has(j)?7:5,0,6.3);ctx.fill();}}
  const h=pr([J[15][0],J[15][1],J[15][2]+0.14]),hd=pr(J[15]);ctx.strokeStyle='#dfe8ec';ctx.lineWidth=4;ctx.beginPath();ctx.arc(h[0],h[1],Math.abs(h[1]-hd[1])*0.9,0,6.3);ctx.stroke();
  ctx.font='bold 27px system-ui';ctx.fillStyle='#e6eef2';ctx.fillText({json.dumps(label[0] + " - " + label[2])},24,40);
  ctx.font='19px system-ui';ctx.fillStyle='#9fb3bb';ctx.fillText({json.dumps(label[1])},24,68);ctx.textAlign='right';ctx.fillText('clip '+t.toFixed(2)+' s',1256,40);ctx.textAlign='left';
}}
window.__ENSEMBLE_PREVIEW__={{draw}};draw(0);
</script>"""
    Path(path).write_text(html)
    return dict(distance_m=dist, target_z=zc, frames=len(t))


# ------------------------------------------------------------------------------------------------ robot panels
def label_patch(html, l1, l2):
    old1 = "ctx.font='15px system-ui';ctx.fillStyle='#c7d6db';ctx.fillText(`${state.agents.length} ${state.agents.length===1?'arm':'arms'} · ${v.formation} · ${v.character}`,24,34);"
    assert html.count(old1) == 1
    new1 = f"ctx.font='bold 27px system-ui';ctx.fillStyle='#e6eef2';ctx.fillText({json.dumps(l1)},24,40);ctx.font='19px system-ui';ctx.fillStyle='#9fb3bb';ctx.fillText({json.dumps(l2)},24,68);"
    old2 = "ctx.textAlign='right';ctx.fillText(`Score ${state.time.toFixed(2)}s`,1256,34);ctx.textAlign='left';"
    assert html.count(old2) == 1
    return html.replace(old1, new1).replace(old2, "ctx.textAlign='right';ctx.fillText(`clip ${state.time.toFixed(2)} s`,1256,40);ctx.textAlign='left';")


def robot_page(csv, out, silent, label):
    raw = Path(str(out) + ".raw")
    sh([ENS, str(raw), str(silent), "--implement", "lamp", "--joint-csv", str(csv)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    s = raw.read_text().replace("K5 policy", "").replace("joint CSV", "")
    Path(out).write_text(label_patch(RP.patch(s), label[0] + " - " + label[2], label[1]))


def record(page, silent, out, start, dur, tempo=None):
    import os
    env = dict(os.environ, HYST_FAST="1")
    if tempo:
        tm = WORK / "tempo.json"
        tm.write_text(json.dumps({"map": tempo}))
        env["HYST_TEMPO_MAP"] = str(tm)
    # the tempo map file is read at start, so a per-call name is not needed; calls run one after another per page
    sh(["node", str(ROOT / "scripts" / "author" / "record_ensemble.cjs"), str(page), str(silent), str(out), str(start), str(dur)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    import dialstudy as D
    import arm_sim
    VIEW.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(exist_ok=True)
    silent = WORK / "silence40.wav"
    if not silent.exists():
        sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", "40", str(silent)])
    picks = {p["clip"]: p for p in json.loads((LOOK / "work" / "picks.json").read_text())["picks"]}
    nums = json.loads((LOOK / "jitter" / "numbers.json").read_text())["variants"]["baseline"]
    info = {"clips": {}, "layout": "2x2, 1920x1080, 960x540 per panel: [1 human | 2 stage 1] over [3 stage 4 | 4 H1]", "timing": "per clip: 1 s card, 6 s at 1x with music, 1 s card, 6 s at 0.5x (12 s) without music"}
    segs = []
    for cid in CLIPS:
        clip, var = cid.split("_")
        c = picks[clip]
        shown = J.read_csv(LOOK / "work" / f"{cid}.csv")                                      # stage 4 as shown
        a, cnt, counts = pick_slice(shown)
        print(cid, "slice start", a, "sign changes", cnt, flush=True)
        # panel sources
        v = RR.human(c["seq"])[0 if var == "V1" else 1]
        i0 = round(c["start_s"] * RT.FPS)
        y = RT.to_commands(RT.referenced(v, i0), var)                                         # stage 1, whole sequence, 30 fps
        tt = np.arange(len(y)) / 30.0 - c["start_s"]
        grid = np.arange(1001) / 50.0
        s1 = np.stack([np.interp(grid, tt, y[:, j]) for j in range(5)], 1)                    # 50 Hz rows of the 30 fps command (the page interpolates linearly)
        h1 = J.run_variant(c, var, "H1")["s4"]
        sources = {1: f"FineDance seq {c['seq']} (motion/{c['seq']}.npy), joints 0-21, canonical T-pose offsets",
                   2: f"retarget.to_commands(referenced(...), '{var}') at 30 fps, linearly drawn at 50 Hz, no limits enforced",
                   3: f"{LOOK}/work/{cid}.csv", 4: "jitter_diag.run_variant(c, var, 'H1')['s4']"}
        csvs = {2: WORK / f"{cid}_s1.csv", 3: LOOK / "work" / f"{cid}.csv", 4: WORK / f"{cid}_h1.csv"}
        csvs[2].write_text(arm_sim.csv_text(s1, 50, name=f"{cid}_s1"))
        csvs[4].write_text(arm_sim.csv_text(h1, 50, name=f"{cid}_h1"))
        pages = {}
        for p in (2, 3, 4):
            pages[p] = WORK / f"{cid}_p{p}.html"
            robot_page(csvs[p], pages[p], silent, (*LABELS[p], cid))
        pages[1] = WORK / f"{cid}_p1.html"
        frame = stick_page(pages[1], c["seq"], var, c["start_s"], a, (*LABELS[1], cid))
        for p in (1, 2, 3, 4):
            for mode, (start, dur, tempo) in (("n", (a, SLICE_S, None)), ("s", (0, 2 * SLICE_S, [[a, 0], [a + SLICE_S, 2 * SLICE_S]]))):
                out = WORK / f"{cid}_p{p}_{mode}.mp4"
                if not out.exists():
                    record(pages[p], silent, out, start, dur, tempo)
                    print("recorded", out.name, flush=True)
        # compose the 2x2 segments
        music = LOOK / "work" / f"{clip}.m4a"
        for mode, dur in (("n", SLICE_S), ("s", 2 * SLICE_S)):
            seg = WORK / f"{cid}_seg_{mode}.mp4"
            ins = []
            for p in (1, 2, 3, 4):
                ins += ["-i", str(WORK / f"{cid}_p{p}_{mode}.mp4")]
            if mode == "n":
                ins += ["-ss", f"{a:.3f}", "-t", f"{dur}", "-i", str(music)]
                amap = ["-map", "4:a"]
            else:
                ins += ["-f", "lavfi", "-t", f"{dur}", "-i", "anullsrc=r=48000:cl=stereo"]
                amap = ["-map", "4:a"]
            fc = "".join(f"[{i}:v]scale=960:540,setsar=1[v{i}];" for i in range(4)) + "[v0][v1][v2][v3]xstack=inputs=4:layout=0_0|960_0|0_540|960_540[v]"
            sh(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", fc, "-map", "[v]", *amap, "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k", "-t", f"{dur}", str(seg)])
        for mode, text in (("n", f"{cid}, seconds {a:g}-{a + SLICE_S:g}, normal speed"), ("s", f"{cid}, seconds {a:g}-{a + SLICE_S:g}, 0.5x, no music")):
            card = WORK / f"{cid}_card_{mode}.mp4"
            png = WORK / f"{cid}_card_{mode}.png"
            Path(str(png) + ".html").write_text(f"<body style='margin:0;background:#000;color:#e6eef2;font:64px system-ui;display:flex;align-items:center;justify-content:center;height:100vh'>{text}</body>")
            sh(["/usr/bin/google-chrome", "--headless", "--no-sandbox", "--disable-gpu", f"--screenshot={png}", "--window-size=1920,1080", f"file://{png}.html"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            sh(["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", "30", "-t", "1", "-i", str(png), "-f", "lavfi", "-t", "1", "-i", "anullsrc=r=48000:cl=stereo", "-r", "30", "-c:v", "libx264",
                "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k", "-t", "1", str(card)])
        segs += [WORK / f"{cid}_card_n.mp4", WORK / f"{cid}_seg_n.mp4", WORK / f"{cid}_card_s.mp4", WORK / f"{cid}_seg_s.mp4"]
        info["clips"][cid] = dict(clip=clip, variant=var, seq=c["seq"], genre=c["genre"], window_start_s=c["start_s"], slice_start_s=a, slice_end_s=a + SLICE_S, slice_wrist_bend_sign_changes=cnt,
                                  max_possible_windows=len(counts), realised_wrist_bend_sign_changes_per_s_full_clip=nums[cid]["stages"]["s4"]["own"]["wrist_bend"]["acc_sign_changes_per_s"],
                                  panel_sources=sources, stick_figure=frame, panel_frames=dict(normal=round(SLICE_S * 30), slow=round(2 * SLICE_S * 30)), music=f"{music} from {a:g} s")
    lst = WORK / "concat.txt"
    lst.write_text("".join(f"file '{s}'\n" for s in segs))
    final = VIEW / "jitter_viewing.mp4"
    sh(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)])
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(final)], capture_output=True, text=True).stdout)
    info["output"] = dict(file=str(final), duration_s=dur, size="1920x1080", fps=30, codecs="h264 + aac", note="stage 1 panel is the raw command drawn kinematically: no limiter, no servo, no range limits, no column constraint; "
                          "H1 is shown realised; stage 4 panel is the shown look-test clip's CSV")
    (VIEW / "viewing.json").write_text(json.dumps(info, indent=1))
    # contact sheet: 4 frames (each clip normal and 0.5x), 2x2 of the composed frames
    t0 = 0.0
    picks_t = []
    for cid in CLIPS:
        picks_t += [t0 + 1 + 3.0, t0 + 1 + 6 + 1 + 5.0]                                          # 3 s into the 1x part, 5 s into the 0.5x part
        t0 += 1 + 6 + 1 + 12
    for k, tm in enumerate(picks_t):
        sh(["ffmpeg", "-v", "error", "-y", "-ss", f"{tm:.2f}", "-i", str(final), "-frames:v", "1", "-vf", "scale=960:540", str(WORK / f"cs{k}.png")])
    sh(["ffmpeg", "-v", "error", "-y", *sum([["-i", str(WORK / f"cs{k}.png")] for k in range(4)], []), "-filter_complex", "xstack=inputs=4:layout=0_0|960_0|0_540|960_540", str(VIEW / "contact_sheet.png")])
    print("done", dur)


if __name__ == "__main__":
    main()
