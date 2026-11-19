"""WO15B: one-arm camera clips of the WO15A trained policies (seed 0 and seed 1, argmax) on two held-out toy episodes. Provisional servo model (Feetech STS3215 12 V assumed).

    m3f_clips.py [--episodes 0 1] [--seeds 0 1]

For each seed and episode: the 50 Hz joint CSV (`arm_sim.csv_text`) from the scored held-out rollout (`rerun3/seed{S}/try1/rollouts/trained_argmax_4.npz`: the 100 Hz joint positions of the 16 held-out
episodes, argmax, the raised-plane body); row 0 is the episode's start pose (`m3d.start_poses(16, 4242)[episode]`), then every second 100 Hz sample (3001 rows = 60 s, t = 0 to 60 s of the episode).
The toy episodes are synthetic feature streams with no song, so the clips carry a SILENT audio track (60 s of silence). Page = `ensemble_preview --joint-csv` (same page, camera and rig geometry as the
WO12 K5 videos), 1080p = `scripts/author/record_ensemble.cjs`, 720p = the size loop of k5_render.sh (< 30 MiB), side-by-side per episode = seed 0 left, seed 1 right, 2560x720 (< 30 MiB).
Resume-safe: a finished file is kept. Output /secondary/hyst-data/body/m3f/rerun3/clips/.
"""
import argparse
import json
import os
import subprocess
from pathlib import Path

import numpy as np

import arm_sim
import m3d

R3 = Path(os.environ.get("M3F_CLIPS_ROOT", "/secondary/hyst-data/body/m3f/rerun3"))      # WO17: M3F_CLIPS_ROOT=.../rerun4
OUT = R3 / "clips"
ROOT = Path(__file__).resolve().parents[2]
PREVIEW = Path("/secondary/hyst-data/cargo-target-wo12/release/examples/ensemble_preview")
LIMIT = 31457280
HELD_SEED0 = 900                       # toy.build: seeds = 100 + i (train) and 900 + i (held-out)


def run(*cmd, **kw):
    r = subprocess.run(list(map(str, cmd)), capture_output=True, text=True, **kw)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} failed: {r.stderr[-1500:]}")
    return r.stdout


def dur(p):
    return float(run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p))


def mp4_720(src, dst):
    vk = int(27 * 8388.6 / dur(src) - 96)
    while True:
        run("ffmpeg", "-v", "error", "-y", "-i", src, "-vf", "scale=1280:720", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k", "-maxrate", f"{vk * 3 // 2}k", "-bufsize", f"{vk * 3}k",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", dst)
        if os.path.getsize(dst) < LIMIT:
            return
        vk = vk * 9 // 10


def side_by_side(a, b, dst):
    vk = int(27 * 8388.6 / dur(a) - 96)
    while True:
        run("ffmpeg", "-v", "error", "-y", "-i", a, "-i", b, "-filter_complex", "[0:v][1:v]hstack=inputs=2[v]", "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k",
            "-maxrate", f"{vk * 3 // 2}k", "-bufsize", f"{vk * 3}k", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", dst)
        if os.path.getsize(dst) < LIMIT:
            return
        vk = vk * 9 // 10


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episodes", type=int, nargs="+", default=[0, 1])
    ap.add_argument("--seeds", type=int, nargs="+", default=[0, 1])
    a = ap.parse_args()
    for d in ("work", "audio", "csv"):
        (OUT / d).mkdir(parents=True, exist_ok=True)
    silent = OUT / "audio" / "silent60.m4a"
    if not silent.exists():
        run("ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "60", "-c:a", "aac", "-b:a", "64k", silent)
    starts = m3d.start_poses(16, 4242)
    info = {"episodes": {}, "note": "toy episodes have no song: silent audio track; row 0 = start pose, then every second 100 Hz sample; argmax; scored held-out rollout"}
    for ep in a.episodes:
        info["episodes"][str(ep)] = {"held_out_index": ep, "toy_seed": HELD_SEED0 + ep, "start_s": 0.0, "duration_s": 60.0, "start_pose_deg": starts[ep].tolist()}
        for s in a.seeds:
            name = f"seed{s}-ep{ep}"
            csv = OUT / "csv" / f"{name}.csv"
            q = np.load(R3 / f"seed{s}" / "try1" / "rollouts" / "trained_argmax_4.npz")["q"].reshape(16, -1, 5)[ep]
            rows = np.concatenate([starts[ep][None], q[1::2]])
            csv.write_text(arm_sim.csv_text(rows, hz=50, name=f"m3f-{R3.name}-seed{s}-held{ep}"))
            page = OUT / "work" / f"{name}.html"
            if not page.exists():
                run(PREVIEW, page, "../audio/silent60.m4a", "--joint-csv", csv)
            mp4 = OUT / f"{name}.mp4"
            if not mp4.exists():
                part = OUT / f"{name}.part.mp4"
                env = {k: v for k, v in os.environ.items() if k != "HYST_FAST"}
                run("node", ROOT / "scripts" / "author" / "record_ensemble.cjs", page, silent, part, env=env)
                part.rename(mp4)
            if not (OUT / f"{name}-720p.mp4").exists():
                mp4_720(mp4, OUT / f"{name}-720p.mp4")
            print(name, "done", flush=True)
        if len(a.seeds) == 2:
            sbs = OUT / f"ep{ep}-side-by-side-720p.mp4"
            if not sbs.exists():
                side_by_side(OUT / f"seed0-ep{ep}-720p.mp4", OUT / f"seed1-ep{ep}-720p.mp4", sbs)
            print(f"ep{ep} side-by-side done", flush=True)
    (OUT / "clips.json").write_text(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
