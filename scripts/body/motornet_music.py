"""WO29A Part 3 path, tested on a synthetic click track only (no real audio until the overseer releases it). Rules: docs/MOTORNET_RULES.md (a).

    motornet_music.py click OUTDIR                                  write the synthetic 100 BPM click wav (40 s) + beats json
    motornet_music.py lanes WAV BEATS_JSON OUT.npz                  brain env: cortex lanes of a song outside the corpus (k5_video_lanes format)
    motornet_music.py clip LANES.npz START_S "c1,c2,c3,c4" OUTDIR   body env: simulate + gate one music clip (10 s warm-up from the song), write csv/activity/json
    motornet_music.py excerpt WAV START_S OUT.m4a                   the 12 s of audio to mux into the clip
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

LANES = "/secondary/hyst-data/body/k5/danced/lanes/{}.npz"
SONGS3 = ("instant-crush", "five-years", "presence")
BLOCK_S = 0.5


def arousal_norm():
    """fixed mean and sd of arousal_b7 pooled over the three danced songs' lanes"""
    a = np.concatenate([np.load(LANES.format(s))["arousal_b7"] for s in SONGS3])
    return float(a.mean()), float(a.std())


def music_input(lanes, start_s, warm_s=10.0):
    """lanes: y (blocks, 8; l3_cos col 2, l3_sin col 3, 0.5 s blocks) and arousal_b7 (10 Hz). -> u_fn(t), t = network time; t = 0 is song time start_s - warm_s."""
    y, ar = np.asarray(lanes["y"]), np.asarray(lanes["arousal_b7"])
    mu, sd = arousal_norm()
    tb = (np.arange(len(y)) + 0.5) * BLOCK_S
    ta = (np.arange(len(ar)) + 0.5) * 0.1

    def u(t):
        s = start_s - warm_s + t
        return np.array([np.interp(s, tb, y[:, 2]), np.interp(s, tb, y[:, 3]), float(np.clip((np.interp(s, ta, ar) - mu) / sd, -3, 3))])
    return u


def cmd_click(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    sr, dur = 22050, 40.0
    x = np.zeros(int(sr * dur), np.float32)
    beats = np.arange(0.5, dur - 0.1, 0.6)
    t = np.arange(int(0.05 * sr)) / sr
    burst = (np.sin(2 * np.pi * 1000 * t) * np.exp(-t * 80)).astype(np.float32)
    for b in beats:
        i = int(b * sr)
        x[i:i + len(burst)] += burst
    from scipy.io import wavfile
    wavfile.write(out / "click100.wav", sr, (x * 32000).astype(np.int16))
    (out / "click100.beats.json").write_text(json.dumps({"beats": beats.tolist()}))
    print("click track", len(beats), "beats")


def cmd_lanes(wav, beats_json, out):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import k5_video_lanes as V
    import braindump as bd
    import b2
    import fast_features as ff
    mean, std = bd.stats()
    feats = ff.fast_features(ff.load_mono(wav))
    x = b2.build_inputs(feats, json.loads(Path(beats_json).read_text())["beats"], mean, std)
    V.save(Path(out), V.lanes_of(V.load_model(), x))
    print("lanes", len(x) / 100, "s ->", out)


def cmd_clip(lanes, start, c, out):
    import arm_sim
    import dialstudy as D
    import motornet as M
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    c = [float(v) for v in c.split(",")]
    q, r, g = M.run_setting(c, u_fn=music_input(np.load(lanes), float(start), M.WARM_S))
    (out / "music_test.csv").write_text(arm_sim.csv_text(q, D.HZ, name="music_test"))
    np.save(out / "music_test.activity.npy", r)
    (out / "music_test.json").write_text(json.dumps(dict(setting_values=c, start_s=float(start), gates=g), indent=1))
    print("passed", g["passed"], g["parts"], g["values"])


def cmd_excerpt(wav, start, out):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", start, "-t", "12", "-i", wav, "-c:a", "aac", out], check=True)


if __name__ == "__main__":
    a = sys.argv[1:]
    {"click": cmd_click, "lanes": cmd_lanes, "clip": cmd_clip, "excerpt": cmd_excerpt}[a[0]](*a[1:])
