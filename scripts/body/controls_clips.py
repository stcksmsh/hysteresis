"""WO43 clip candidates for Step 0b' (rules section 8). Brain env. Out: controls/look/{work,clips,manifest.json,selection.json}. Nothing is served and no answers file is opened.

    controls_clips.py select      seeded pairs from FineDance validation + test (V1/V2) -> look/selection.json
    controls_clips.py work        look/work/C<nn>_V<1|2>.{csv,json}, C<nn>.m4a from the stored realised q50
    (render: RETARGET_ROOT=/secondary/hyst-data/body/controls/look HYST_BATTERY_OK=1 scripts/body/retarget_render.sh)
    controls_clips.py manifest    look/manifest.json for dialstudy_session.py (kind "pair", per-item question)
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = Path("/secondary/hyst-data/body/controls")
LOOK = OUT / "look"
FD = Path("/secondary/hyst-data/datasets/finedance/data/finedance")
CONTROLS = ("vigour", "height", "sharp", "pause_prob", "accent_mean")
NAMES = {"vigour": "vigour", "height": "height", "sharp": "sharpness", "pause_prob": "continuity", "accent_mean": "accent density"}
QUESTION = {"vigour": "Which looks bigger / faster?", "height": "Which looks higher?", "sharp": "Which looks sharper?", "pause_prob": "Which looks more continuous?", "accent_mean": "Which looks more accented?"}
CLIP_TOK, STEP, SHORTLIST, PAIRS, MAXNAN = 16, 4, 20, 3, 0.25


def candidates():
    t = np.load(OUT / "tables" / "finedance.npz")
    m = np.flatnonzero(np.isin(t["split"], (1, 2)) & np.isin(t["copy"], (0, 1)))
    key = t["file"][m] * 100000 + t["win"][m]
    out = []
    for kk in np.unique(key):
        r = m[key == kk]
        if len(r) != 40:
            continue
        for s in range(0, 40 - CLIP_TOK + 1, STEP):
            x = np.stack([t[c][r[s:s + CLIP_TOK]] for c in CONTROLS], 1)
            if (np.isnan(x).mean(0) > MAXNAN).any():
                continue
            out.append(dict(file=int(t["file"][r[0]]), win=int(t["win"][r[0]]), start=s, copy=int(t["copy"][r[0]]), group=str(t["group"][r[0]]), lane=str(t["lane"][r[0]]), val=np.nanmean(x, 0)))
    return out


def cmd_select():
    cand = candidates()
    V = np.stack([c["val"] for c in cand])
    p10, p90, sd = np.nanpercentile(V, 10, 0), np.nanpercentile(V, 90, 0), np.nanstd(V, 0)
    grp = np.array([c["group"] for c in cand])
    cp = np.array([c["copy"] for c in cand])
    used_clip, pairs = set(), []
    for ci, c in enumerate(CONTROLS):
        used_groups = set()
        for i in range(PAIRS):
            lo = np.flatnonzero(V[:, ci] <= p10[ci])
            hi = np.flatnonzero(V[:, ci] >= p90[ci])
            lo = [a for a in lo if (cand[a]["file"], cand[a]["win"]) not in used_clip and grp[a] not in used_groups]
            hi = [b for b in hi if (cand[b]["file"], cand[b]["win"]) not in used_clip and grp[b] not in used_groups]
            other = [j for j in range(len(CONTROLS)) if j != ci]
            best = []
            for a in lo:
                for b in hi:
                    if cp[a] == cp[b] and grp[a] != grp[b]:
                        best.append((float((np.abs(V[a, other] - V[b, other]) / sd[other]).sum()), a, b))
            best.sort()
            top = best[:SHORTLIST]
            r = np.random.default_rng(4302 + 10 * ci + i)
            res, a, b = top[int(r.integers(len(top)))]
            used_groups |= {grp[a], grp[b]}
            used_clip |= {(cand[a]["file"], cand[a]["win"]), (cand[b]["file"], cand[b]["win"])}
            pairs.append(dict(control=c, name=NAMES[c], index=i, residual=res, high_first=bool(r.integers(2)), shortlist=len(top),
                              low=dict({k: cand[a][k] for k in ("file", "win", "start", "copy", "group", "lane")}, values=dict(zip(CONTROLS, V[a].tolist()))),
                              high=dict({k: cand[b][k] for k in ("file", "win", "start", "copy", "group", "lane")}, values=dict(zip(CONTROLS, V[b].tolist()))),
                              residual_sd_units={CONTROLS[j]: float(abs(V[a, j] - V[b, j]) / sd[j]) for j in range(len(CONTROLS)) if j != ci}))
    LOOK.mkdir(parents=True, exist_ok=True)
    (LOOK / "selection.json").write_text(json.dumps(dict(pool=len(cand), p10=dict(zip(CONTROLS, p10.tolist())), p90=dict(zip(CONTROLS, p90.tolist())), sd=dict(zip(CONTROLS, sd.tolist())), pairs=pairs), indent=1))
    print("pool", len(cand), "pairs", len(pairs), flush=True)


def clip_ids():
    sel = json.loads((LOOK / "selection.json").read_text())
    out = []
    for n, p in enumerate(sel["pairs"]):
        out.append((2 * n + 1, p, "low"))
        out.append((2 * n + 2, p, "high"))
    return sel, out


def cmd_work():
    import arm_sim
    import dialstudy as D
    files = sorted((OUT / "finedance").glob("*.npz"))
    W = LOOK / "work"
    W.mkdir(parents=True, exist_ok=True)
    sel, ids = clip_ids()
    for n, p, side in ids:
        c = p[side]
        f = files[c["file"]]
        z = np.load(OUT / "q50" / "finedance" / f.name)
        wi = int(np.flatnonzero(z["win"] == c["win"])[0])
        a = 25 * c["start"]
        q = z["q50"][wi][a:a + 25 * CLIP_TOK + 1].astype(float)
        var = ("V1", "V2")[c["copy"]]
        cid = f"C{n:02d}"
        (W / f"{cid}_{var}.csv").write_text(arm_sim.csv_text(q, 50, name=f"{cid}_{var}"))
        (W / f"{cid}_{var}.json").write_text(json.dumps(dict(id=f"{cid}_{var}", clip=cid, variant=var, gates=dict(passed=True, note="window passed the T0 gates; this excerpt is its realised q50"), pick=dict(c, side=side, control=p["control"]))))
        t0 = c["win"] * 20.0 + c["start"] * 0.5
        seq = c["lane"].split("_", 1)[1]
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{CLIP_TOK * 0.5}", "-i", str(FD / "music_wav" / f"{seq}.wav"), "-ac", "2", "-ar", "48000", "-c:a", "aac", "-b:a", "192k", str(W / f"{cid}.m4a")], check=True)
    print("work files", len(ids), flush=True)


def cmd_manifest():
    sel, ids = clip_ids()
    by = {(n): (p, side) for n, p, side in ids}
    man = []
    for k, p in enumerate(sel["pairs"]):
        nl, nh = 2 * k + 1, 2 * k + 2
        vl, vh = ("V1", "V2")[p["low"]["copy"]], ("V1", "V2")[p["high"]["copy"]]
        low, high = f"clips/C{nl:02d}_{vl}.mp4", f"clips/C{nh:02d}_{vh}.mp4"
        files = [high, low] if p["high_first"] else [low, high]
        man.append(dict(id=f"P{k + 1:02d}_{p['name'].replace(' ', '_')}", kind="pair", files=files, question=QUESTION[p["control"]], control=p["name"], high_first=p["high_first"],
                        variant=vl, genre="finedance"))
    (LOOK / "manifest.json").write_text(json.dumps(man, indent=1))
    print("manifest", len(man), "pairs", flush=True)


if __name__ == "__main__":
    {"select": cmd_select, "work": cmd_work, "manifest": cmd_manifest}[sys.argv[1]]()
