"""Deterministic synthetic WAVs for the TS-vs-Python equivalence check.
usage: gen_synthetic.py OUT_DIR"""
import struct
import sys
from pathlib import Path

import numpy as np

SR = 44100


def write_wav(path, data, bits, fmt):
    """data: (frames, channels) float in [-1,1]. fmt 1=int PCM, 3=float."""
    ch = data.shape[1]
    if fmt == 3:
        raw = data.astype('<f4').tobytes()
    elif bits == 16:
        raw = np.round(np.clip(data, -1, 1) * 32767).astype('<i2').tobytes()
    elif bits == 24:
        v = np.round(np.clip(data, -1, 1) * 8388607).astype(np.int32).reshape(-1)
        raw = b''.join(struct.pack('<i', x)[:3] for x in v.tolist())
    block = ch * bits // 8
    hdr = b'RIFF' + struct.pack('<I', 36 + len(raw)) + b'WAVE'
    hdr += b'fmt ' + struct.pack('<IHHIIHH', 16, fmt, ch, SR, SR * block, block, bits)
    hdr += b'data' + struct.pack('<I', len(raw))
    Path(path).write_bytes(hdr + raw)


def clicks(bpm, secs, rng):
    n = int(SR * secs)
    x = np.zeros(n)
    period = 60 / bpm
    burst = int(0.02 * SR)
    env = np.exp(-np.arange(burst) / (0.004 * SR))
    t = 0.0
    while int(t * SR) + burst < n:
        i = int(t * SR)
        x[i:i + burst] += rng.standard_normal(burst) * env * 0.8
        t += period
    return x


def kick(n, at, amp=0.9):
    t = np.arange(int(0.2 * SR)) / SR
    k = np.sin(2 * np.pi * (50 * t + 60 * (1 - np.exp(-t * 30)) / 30)) * np.exp(-t * 18) * amp
    n_end = min(n, at + len(k))
    return n_end, k[: n_end - at]


def dropbuild(rng):
    secs = 44
    n = SR * secs
    x = np.zeros(n)
    t = np.arange(n) / SR
    # 0-12 s sparse pad
    pad = 0.05 * np.sin(2 * np.pi * 220 * t) * (t < 12)
    x += pad
    # 12-24 s build: noise sweep rising in level + brightness, snare-ish rolls
    b = (t >= 12) & (t < 24)
    ramp = np.clip((t - 12) / 12, 0, 1)
    x += b * ramp * 0.5 * rng.standard_normal(n) * (0.2 + 0.8 * ramp)
    # 24-24.3 s gap
    # 24.3-44 s full: kick 128 bpm, bass, hats
    per = 60 / 128
    tt = 24.3
    while tt < secs - 0.3:
        i = int(tt * SR)
        e, k = kick(n, i)
        x[i:e] += k
        h = int((tt + per / 2) * SR)
        hb = min(n, h + 1500)
        x[h:hb] += 0.25 * rng.standard_normal(hb - h) * np.exp(-np.arange(hb - h) / 400)
        tt += per
    full = t >= 24.3
    x += full * 0.3 * np.sin(2 * np.pi * 55 * t)
    return x


def structure(rng):
    """Quiet intro, loud full section, sparse break, loud again, quiet end; built to make the
    drop and break detectors fire (the other synthetics do not reach them)."""
    secs = 70
    n = SR * secs
    t = np.arange(n) / SR
    x = 0.004 * rng.standard_normal(n)
    loud = ((t >= 10) & (t < 30)) | ((t >= 42) & (t < 62))
    per = 60 / 126
    for a, b in ((10, 30), (42, 62)):
        tt = float(a)
        while tt < b - 0.3:
            i = int(tt * SR)
            e, k = kick(n, i)
            x[i:e] += k
            h = int((tt + per / 2) * SR)
            hb = min(n, h + 2000)
            x[h:hb] += 0.3 * rng.standard_normal(hb - h) * np.exp(-np.arange(hb - h) / 500)
            tt += per
    x += loud * (0.25 * np.sin(2 * np.pi * 55 * t) + 0.15 * np.sin(2 * np.pi * 330 * t) + 0.05 * rng.standard_normal(n))
    return x


def dropstep(rng):
    """Loud 2 s, quiet 12 s, loud 20 s: the one synthetic found to fire the drop detector
    (then the build window, the break pair and the build section paths run)."""
    n = SR * 40
    t = np.arange(n) / SR
    loud = ((t < 2) | ((t >= 14) & (t < 34))).astype(float)
    return 0.001 * rng.standard_normal(n) + loud * (0.5 * np.sin(2 * np.pi * 60 * t)
                                                     + 0.2 * rng.standard_normal(n) + 0.2 * np.sin(2 * np.pi * 500 * t))


def main(out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(12345)
    mono = lambda a: a.reshape(-1, 1)
    write_wav(out / 'clicks120.wav', mono(clicks(120, 30, rng)), 16, 1)
    write_wav(out / 'clicks93.wav', mono(clicks(93, 30, rng)), 16, 1)
    write_wav(out / 'silence.wav', np.zeros((SR * 10, 1)), 16, 1)
    t = np.arange(SR * 10) / SR
    write_wav(out / 'tone440.wav', mono(0.5 * np.sin(2 * np.pi * 440 * t)), 16, 1)
    db = dropbuild(rng)
    write_wav(out / 'dropbuild.wav', np.stack([db, 0.9 * np.roll(db, 7)], axis=1) * 0.8, 16, 1)
    # same material, other container paths: float32 stereo + 24-bit stereo
    write_wav(out / 'dropbuild_f32.wav', np.stack([db, 0.9 * np.roll(db, 7)], axis=1) * 0.8, 32, 3)
    write_wav(out / 'clicks120_24bit.wav', np.stack([clicks(120, 12, rng)] * 2, axis=1) * 0.5, 24, 1)
    write_wav(out / 'tiny.wav', mono(0.3 * np.sin(np.arange(1000) * 0.1)), 16, 1)
    write_wav(out / 'structure.wav', mono(structure(rng) * 0.8), 16, 1)
    write_wav(out / 'dropstep.wav', mono(dropstep(rng) * 0.8), 16, 1)
    # a file just long enough for a few hops
    write_wav(out / 'short.wav', mono(0.3 * rng.standard_normal(SR * 1)), 16, 1)


if __name__ == '__main__':
    main(sys.argv[1])
