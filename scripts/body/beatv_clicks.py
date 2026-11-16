"""WO47 V4 material (docs/BEATV_RULES.md section 5): 30 s excerpts of the 10 spot-check songs with clicks at the project grid and (separate item) at librosa's beats. Brain env.   beatv_clicks.py
-> beatv/clicks/<id>.mp4 (black picture + audio), beatv/clicks/manifest.json (singles for dialstudy_session.py, question "Are the clicks on the beat?", labels yes / partly / no), beatv/clicks/key.json (which grid)."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

B = Path("/secondary/hyst-data/body")
OUT = B / "beatv" / "clicks"
SR = 44100
LEN = 30.0
CLICK_S, CLICK_HZ, CLICK_LEVEL = 0.005, 1500.0, 0.3


def click():
    n = int(CLICK_S * SR)
    t = np.arange(n) / SR
    return np.sin(2 * np.pi * CLICK_HZ * t) * np.hanning(n)


def mix(y, beats, start):
    out = y.copy()
    c = click() * CLICK_LEVEL * max(np.abs(y).max(), 1e-3)
    for b in beats:
        i = int(round((b - start) * SR))
        if 0 <= i < len(out) - len(c):
            out[i:i + len(c)] += c
    return np.clip(out, -0.98, 0.98)


def pick_start(y, dur, rng):
    """30 s window not in the first / last 10 s whose mean RMS is at or above the song's own median RMS (frame level, 50 ms hop)"""
    hop = int(0.05 * SR)
    rms = np.sqrt(np.convolve(y ** 2, np.ones(hop) / hop, "same"))[::hop]
    med = np.median(rms)
    starts = np.arange(10.0, dur - 10.0 - LEN, 1.0)
    ok = [s for s in starts if rms[int(s / 0.05):int((s + LEN) / 0.05)].mean() >= med]
    if not ok:
        raise ValueError("no 30 s window at or above the median RMS outside the first/last 10 s")
    return float(ok[int(rng.integers(len(ok)))])


def main():
    import librosa
    man = json.loads((B / "metric/spotcheck/manifest.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(47105)
    clips, key, info = [], {}, []
    for si, s in enumerate(man["songs"]):
        lk = s["song"]
        try:
            y, _ = librosa.load(s["wav"], sr=SR, mono=True)
            dur = len(y) / SR
            start = pick_start(y, dur, rng)
            ex = y[int(start * SR):int((start + LEN) * SR)]
            proj = np.array(json.loads((B / "t1b/cortex/beats" / f"{lk}.json").read_text())["beats"]) if lk.startswith("fd_") else np.array(json.loads((B / "metric/beats" / f"{lk}.json").read_text())["beats"])
            lib = np.array(json.loads((B / "beatv/librosa" / f"{lk}.json").read_text())["beats"])
            d = np.abs(proj[:, None] - lib[None]).min(1)
            for gn, g in (("proj", proj), ("lib", lib)):
                cid = f"S{si:02d}{'a' if gn == 'proj' else 'b'}"
                wav = OUT / f"{cid}.wav"
                import soundfile as sf
                sf.write(wav, mix(ex, g, start), SR)
                mp4 = OUT / f"{cid}.mp4"
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "color=c=black:s=320x180:r=10", "-i", str(wav), "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(mp4)], check=True)
                wav.unlink()
                clips.append(dict(id=cid, kind="single", file=f"{cid}.mp4", question="Are the clicks on the beat?", grid=gn, song=lk, dataset=s["dataset"], excerpt_start_s=start))
                key[cid] = dict(song=lk, dataset=s["dataset"], grid=gn, start_s=start, n_clicks=int(((g >= start) & (g < start + LEN)).sum()), local_only=s["dataset"] == "motorica")
            info.append(dict(song=lk, dataset=s["dataset"], start_s=start, median_abs_diff_proj_to_lib_ms=float(np.median(d) * 1000), p90_ms=float(np.percentile(d, 90) * 1000)))
            print(lk, s["dataset"], f"start {start:.0f}s", f"proj-lib median {np.median(d) * 1000:.0f} ms", flush=True)
        except Exception as e:
            with open(B / "beatv/clicks_failed.txt", "a") as f:
                f.write(f"{lk} {type(e).__name__}: {e}\n")
    (OUT / "manifest.json").write_text(json.dumps(dict(labels=["yes", "partly", "no"], clips=clips), indent=1))
    (OUT / "key.json").write_text(json.dumps(dict(items=key, songs=info), indent=1))
    print("CLICKS DONE", len(clips), "items", flush=True)


if __name__ == "__main__":
    main()
