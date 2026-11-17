"""WO47 V4, visual version: the same 20 items (ids, songs, excerpt starts, beat times) as beatv_clicks.py, but the audio is the plain excerpt (no clicks) and a white disc flashes at every beat time.
Brain env.   beatv_clicks_visual.py [check]
-> beatv/clicks_visual/<id>.mp4 (640x360, 60 fps, dark background, disc intensity 1 at the first frame at/after the beat, linear fade to 0 over 120 ms; same look for both grids), manifest.json (question "Is the flash on the beat?",
labels yes / partly / no), key.json. The old audio-click folder is not touched. `check` renders a test excerpt with an audible click AND a flash at one beat and measures flash frame time vs click time after encoding."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

B = Path("/secondary/hyst-data/body")
SRC = B / "beatv" / "clicks"
OUT = B / "beatv" / "clicks_visual"
SR, LEN, FPS, W, H = 44100, 30.0, 60, 640, 360
FADE_S = 0.12
BG = np.array([14, 14, 22], np.float32)


def disc_mask():
    yy, xx = np.mgrid[:H, :W]
    r = np.hypot(xx - W / 2, yy - H / 2)
    return np.clip((110 - r) / 1.5, 0, 1).astype(np.float32)[..., None]


def intensity(t, beats, bright=None):
    """1 at the first frame at/after a beat (frame time t >= beat), linear to 0 over FADE_S; the latest beat at or before t decides.
    bright (optional, one value per beat, WO51): the peak intensity of that beat's flash instead of 1"""
    i = np.searchsorted(beats, t, side="right") - 1
    if i < 0:
        return 0.0
    return max(0.0, 1.0 - (t - beats[i]) / FADE_S) * (1.0 if bright is None else float(bright[i]))


def render(wav, beats_rel, dst, n_frames=int(LEN * FPS), bright=None):
    """beats_rel = beat times in seconds from the excerpt start; wav = audio file; -> mp4 (video from raw frames on stdin, audio from wav)"""
    m = disc_mask()
    bg = np.broadcast_to(BG, (H, W, 3))
    white = np.broadcast_to(np.array([255, 255, 255], np.float32), (H, W, 3))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", str(wav), "-t", f"{LEN}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "14", "-preset", "fast", "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst)]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n_frames):
        v = intensity(f / FPS, beats_rel, bright)
        fr = bg * (1 - m * v) + white * (m * v)
        p.stdin.write(fr.astype(np.uint8).tobytes())
    p.stdin.close()
    if p.wait():
        raise RuntimeError("ffmpeg failed")


def beats_of(song, grid):
    if grid == "lib":
        return np.array(json.loads((B / "beatv/librosa" / f"{song}.json").read_text())["beats"])
    p = B / "t1b/cortex/beats" / f"{song}.json" if song.startswith("fd_") else B / "metric/beats" / f"{song}.json"
    return np.array(json.loads(p.read_text())["beats"])


def excerpt_wav(song, start, dst):
    import librosa
    import soundfile as sf
    man = json.loads((B / "metric/spotcheck/manifest.json").read_text())
    wav = next(s["wav"] for s in man["songs"] if s["song"] == song)
    y, _ = librosa.load(wav, sr=SR, mono=True)
    sf.write(dst, y[int(start * SR):int((start + LEN) * SR)], SR)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    man = json.loads((SRC / "manifest.json").read_text())
    key = json.loads((SRC / "key.json").read_text())
    clips = []
    cache = {}
    for c in man["clips"]:
        song, gn, start = c["song"], c["grid"], c["excerpt_start_s"]
        if (song, start) not in cache:
            w = OUT / f"_{song}.wav"
            excerpt_wav(song, start, w)
            cache[(song, start)] = w
        b = beats_of(song, gn)
        b = b[(b >= start) & (b < start + LEN)] - start
        render(cache[(song, start)], b, OUT / f"{c['id']}.mp4")
        clips.append({**c, "question": "Is the flash on the beat?"})
        print(c["id"], song, gn, f"{len(b)} flashes", flush=True)
    for w in cache.values():
        w.unlink()
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=["yes", "partly", "no"], clips=clips), indent=1))
    (OUT / "key.json").write_text(json.dumps(key, indent=1))
    print("CLICKS VISUAL DONE", len(clips), flush=True)


def check():
    """test excerpt: silence with a 5 ms click at 10.000 s and a flash at 10.000 s; encode; find the click in the decoded audio and the flash in the decoded video"""
    import soundfile as sf
    OUT.mkdir(parents=True, exist_ok=True)
    y = np.zeros(int(LEN * SR), np.float32)
    n = int(0.005 * SR)
    y[10 * SR:10 * SR + n] = np.sin(2 * np.pi * 1500 * np.arange(n) / SR) * np.hanning(n) * 0.9
    w, mp4 = OUT / "_sync_test.wav", OUT / "_sync_test.mp4"
    sf.write(w, y, SR)
    render(w, np.array([10.0, 20.0]), mp4)
    a = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
    a = np.frombuffer(a, np.float32)
    t_click = (np.argmax(np.abs(a) > 0.2)) / SR
    v = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(mp4), "-vf", "scale=64:36,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(v, np.uint8).reshape(-1, 36, 64).mean((1, 2))
    t_flash = int(np.argmax(fr > 40)) / FPS
    pr = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,start_time", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout.split()
    print(f"click at {t_click:.4f} s, first flash frame at {t_flash:.4f} s, difference {(t_flash - t_click) * 1000:+.1f} ms; stream start times {pr}; frames {len(fr)}")
    json.dump(dict(t_click=t_click, t_flash=t_flash, diff_ms=(t_flash - t_click) * 1000, start_times=pr), open(OUT / "sync_check.json", "w"))
    # one frame at the beat, one between beats
    for nm, tt in (("beat", 10.0), ("between", 10.5)):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{tt}", "-i", str(mp4), "-frames:v", "1", str(OUT / f"_frame_{nm}.png")], check=True)
    w.unlink()


if __name__ == "__main__":
    check() if sys.argv[1:] == ["check"] else main()
