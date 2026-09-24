#!/usr/bin/env python3
"""Add per-element activity (drums/bass/vocals/synth) + melody contour to a sidecar.

Usage: python3 scripts/arm_elements.py audio.wav input.sidecar.json output.sidecar.json

Needs numpy + scipy. Heuristic DSP, NOT neural stem separation (Demucs weights
were unreachable in the cloud session that wrote this):
  - harmonic/percussive split by median filtering the STFT magnitude (HPSS)
  - mid (L+R) vs side (L-R): lead vocals are usually centred, pads/synths wide
  drums  = percussive energy (mid, 40 Hz-12 kHz)
  bass   = harmonic mid energy 30-160 Hz
  vocals = harmonic mid energy 250-3000 Hz, weighted by how centred it is
  synth  = harmonic side energy 200-8000 Hz + harmonic mid 3-8 kHz
Each element is normalised to its own range (dB, p10..p95 -> 0..1), so values
say "this element is at its own loud level", not absolute loudness.
melody = height (0..1) of the strongest harmonic mid peak 100-1000 Hz where
vocals are active, else -1. Existing sidecar fields are unchanged.
"""
import json
import pathlib
import sys

import numpy as np
from scipy.ndimage import median_filter
from scipy.io import wavfile
from scipy.signal import stft, find_peaks


def band(freqs, lo, hi):
    return (freqs >= lo) & (freqs < hi)


def normalise_db(power):
    db = 10.0 * np.log10(power + 1e-10)
    lo, hi = np.percentile(db, 10), np.percentile(db, 95)
    return np.clip((db - lo) / max(hi - lo, 1e-6), 0.0, 1.2)


def resample(frame_values, frame_times, rate, count):
    out = np.zeros(count)
    idx = np.minimum((frame_times * rate).astype(int), count - 1)
    sums = np.bincount(idx, weights=frame_values, minlength=count)
    counts = np.bincount(idx, minlength=count)
    nz = counts > 0
    out[nz] = sums[nz] / counts[nz]
    # Fill any empty slot from its left neighbour.
    for i in range(1, count):
        if not nz[i]:
            out[i] = out[i - 1]
    return out


def analyse(wav_path, sidecar):
    sr, audio = wavfile.read(wav_path)
    audio = audio.astype(np.float64)
    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)
    audio /= np.max(np.abs(audio)) + 1e-9
    mid = (audio[:, 0] + audio[:, 1]) / 2
    side = (audio[:, 0] - audio[:, 1]) / 2
    nfft, hop = 2048, 512
    freqs, times, m = stft(mid, sr, nperseg=nfft, noverlap=nfft - hop, boundary=None)
    _, _, sd = stft(side, sr, nperseg=nfft, noverlap=nfft - hop, boundary=None)
    mm, sm = np.abs(m), np.abs(sd)
    harm = median_filter(mm, size=(1, 17))
    perc = median_filter(mm, size=(17, 1))
    mask_h = harm**2 / (harm**2 + perc**2 + 1e-12)
    hm, pm = mm * mask_h, mm * (1 - mask_h)
    hs = sm * (sm**2 / (sm**2 + median_filter(sm, size=(17, 1)) ** 2 + 1e-12))

    def energy(mag, lo, hi):
        return (mag[band(freqs, lo, hi)] ** 2).sum(axis=0)

    vocal_band = band(freqs, 250, 3000)
    centred = np.clip(
        1.0 - (sm[vocal_band] ** 2).sum(axis=0) / ((mm[vocal_band] ** 2).sum(axis=0) + 1e-12), 0, 1
    )
    raw = {
        "drums": energy(pm, 40, 12000),
        "bass": energy(hm, 30, 160),
        "vocals": energy(hm, 250, 3000) * centred,
        "synth": energy(hs, 200, 8000) + energy(hm, 3000, 8000),
    }
    rate = float(sidecar["envelopeRate"])
    count = int(np.ceil(float(sidecar["duration"]) * rate))
    elements = {k: resample(normalise_db(v), times, rate, count) for k, v in raw.items()}

    # Melody: strongest harmonic peak 100-1000 Hz, voiced where vocals active.
    mel_band = band(freqs, 100, 1000)
    peak_hz = freqs[mel_band][np.argmax(hm[mel_band], axis=0)]
    pitch = np.log2(np.maximum(peak_hz, 1.0))
    vocal_frame = normalise_db(raw["vocals"])
    voiced = vocal_frame > 0.45
    if voiced.any():
        lo, hi = np.percentile(pitch[voiced], 5), np.percentile(pitch[voiced], 95)
    else:
        lo, hi = 0.0, 1.0
    height = np.where(voiced, np.clip((pitch - lo) / max(hi - lo, 1e-6), 0, 1), np.nan)
    height = median_filter(np.nan_to_num(height, nan=-1.0), size=9)
    melody = resample(height, times, rate, count)
    melody[melody < 0] = -1.0

    # Melodic onsets: harmonic spectral flux in the vocal band.
    flux = np.maximum(np.diff(hm[vocal_band], axis=1), 0).sum(axis=0)
    flux = np.concatenate([[0.0], flux]) * (vocal_frame > 0.35)
    med = np.median(flux)
    mad = np.median(np.abs(flux - med)) + 1e-12
    peaks, _ = find_peaks(flux, height=med + 4 * mad, distance=int(0.15 * sr / hop))
    onsets = [round(float(times[p]), 4) for p in peaks]

    rounded = {k: [round(float(x), 4) for x in v] for k, v in elements.items()}
    rounded["melody"] = [round(float(x), 4) for x in melody]
    rounded["melodyOnsets"] = onsets
    rounded["source"] = "HPSS + mid/side heuristic (not neural stems)"
    return dict(sidecar, elements=rounded)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    wav, src, dst = map(pathlib.Path, sys.argv[1:])
    data = analyse(wav, json.loads(src.read_text()))
    dst.write_text(json.dumps(data))
    e = data["elements"]
    print(f"elements -> {dst}: {len(e['drums'])} samples, {len(e['melodyOnsets'])} melodic onsets")
