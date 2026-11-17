"""AIST++ music (BRAIN_SPEC 7.78 1.1 cross-check): one c01 video per music ID (+ a second for 5 IDs), audio -> mono 22050 Hz wav, video deleted.
Plain HTTPS, sequential, 1 s pause. Output /secondary/hyst-data/datasets/aist/music/<mID>.wav, pairs' second take music/pairs/<mID>_b.wav.
    aist_music.py            download + extract
    aist_music.py align      cross-correlation of the 5 pairs
    aist_music.py sha        sha256 of every wav"""
import hashlib
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

A = Path("/secondary/hyst-data/datasets/aist")
KP = A / "data/keypoints3d"
M = A / "music"
VID = A / "dl_video"
URL = "https://aistdancedb.ongaaccel.jp/v1.0.0/video/10M/{}.mp4"
SR = 22050
PAIRS = 5


def seqs():
    return sorted(p.stem for p in KP.glob("*.pkl"))


def c01(n):
    g, s, _, d, m, ch = n.split("_")
    return f"{g}_{s}_c01_{d}_{m}_{ch}", m


def fetch(name):
    dst = VID / f"{name}.mp4"
    with urllib.request.urlopen(urllib.request.Request(URL.format(name), headers={"User-Agent": "research-fetch"}), timeout=120) as r, open(dst, "wb") as f:
        while b := r.read(1 << 20):
            f.write(b)
    return dst


def extract(mp4, wav):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vn", "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", str(wav)], check=True)


def try_names(cands, wav):
    for n in cands:
        name, _ = c01(n)
        try:
            mp4 = fetch(name)
            extract(mp4, wav)
            mp4.unlink()
        except Exception as e:
            print("fail", name, e, flush=True)
            time.sleep(1)
            continue
        print("ok", name, flush=True)
        time.sleep(1)
        return name
    return None


def download():
    (M / "pairs").mkdir(parents=True, exist_ok=True)
    VID.mkdir(parents=True, exist_ok=True)
    by = {}
    for n in seqs():
        by.setdefault(c01(n)[1], []).append(n)
    used = {}
    for i, (mid, ns) in enumerate(sorted(by.items())):
        wav = M / f"{mid}.wav"
        if not wav.exists():
            used[mid] = try_names(ns, wav)
        if i < PAIRS:
            wb = M / "pairs" / f"{mid}_b.wav"
            if not wb.exists():
                others = [n for n in ns[::-1] if c01(n)[0] != used.get(mid)]
                used[mid + "_b"] = try_names(others, wb)
    print(used)
    print("music ids", len(by), "missing", [m for m in by if not (M / f"{m}.wav").exists()])


def align():
    import numpy as np
    import soundfile as sf
    from scipy.signal import fftconvolve
    for wb in sorted((M / "pairs").glob("*_b.wav")):
        a, _ = sf.read(M / wb.name.replace("_b", ""))
        b, _ = sf.read(wb)
        n = min(len(a), len(b), 60 * SR)
        a, b = a[:n], b[:n]
        a, b = a - a.mean(), b - b.mean()
        c = fftconvolve(a, b[::-1], "full") / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-12)
        k = int(np.argmax(c)) - (n - 1)
        print(wb.stem, "lag_ms", round(1000 * k / SR, 2), "peak_corr", round(float(c.max()), 4))


def sha():
    for p in sorted(M.glob("*.wav")):
        print(hashlib.sha256(p.read_bytes()).hexdigest(), p.name)


if __name__ == "__main__":
    {"": download, "align": align, "sha": sha}[sys.argv[1] if len(sys.argv) > 1 else ""]()
