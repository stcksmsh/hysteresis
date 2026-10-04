#!/usr/bin/env python3
"""Add an estimated melodic-height contour per pitched stem to a sidecar.

Usage: python3 scripts/dance_melody.py INPUT_SIDECAR STEM_DIR OUTPUT_SIDECAR

STEM_DIR must contain other.wav and vocals.wav (source-separation estimates).
Adds `melodyContour` (additive): per stem, `height` 0..1 (low..high pitch,
calibrated over the whole track) and `salience` 0..1 at stemInterpretation's
envelope rate. Height follows the strongest spectral peak, not a true f0.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.ndimage import gaussian_filter1d, median_filter

STEMS = ("other", "vocals")
WINDOW = 4096
LOW_HZ, HIGH_HZ = 110.0, 2500.0


def contour(mono: np.ndarray, sample_rate: int, rate: float, frames: int):
    """Return (height, salience) arrays of length `frames`."""
    # ponytail: strongest-peak proxy; swap for a real f0 tracker if octave jumps show.
    hop = sample_rate / rate
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sample_rate)
    band = (freqs >= LOW_HZ) & (freqs <= HIGH_HZ)
    window = np.hanning(WINDOW)
    padded = np.concatenate([np.zeros(WINDOW // 2), mono, np.zeros(WINDOW)])
    pitch = np.zeros(frames)
    level = np.zeros(frames)
    for i in range(frames):
        start = int(round(i * hop))
        spectrum = np.abs(np.fft.rfft(padded[start:start + WINDOW] * window))[band]
        level[i] = float(np.sqrt(np.mean(spectrum ** 2)))
        pitch[i] = np.log2(freqs[band][int(np.argmax(spectrum))])
    salience = np.clip(level / max(np.percentile(level, 95), 1e-12), 0.0, 1.0)
    voiced = salience > 0.15
    if not voiced.any():
        return np.full(frames, 0.5), salience
    # Unvoiced frames hold the last voiced pitch so the contour never jumps to noise.
    index = np.maximum.accumulate(np.where(voiced, np.arange(frames), -1))
    pitch = np.where(index >= 0, pitch[np.maximum(index, 0)], pitch[voiced][0])
    pitch = median_filter(pitch, size=max(3, int(rate * 0.35) | 1), mode="nearest")
    low, high = np.percentile(pitch[voiced], [5, 95])
    height = np.clip((pitch - low) / max(high - low, 1e-9), 0.0, 1.0)
    return gaussian_filter1d(height, rate * 0.25, mode="nearest"), salience


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    sidecar_path, stem_dir, output_path = map(pathlib.Path, argv[1:])
    sidecar = json.loads(sidecar_path.read_text())
    stems = sidecar["stemInterpretation"]
    rate = float(stems["envelopeRate"])
    frames = len(stems["sources"]["other"]["absoluteRms"])
    sources = {}
    for name in STEMS:
        audio, sample_rate = sf.read(stem_dir / f"{name}.wav", always_2d=True)
        if abs(len(audio) / sample_rate - sidecar["duration"]) > 0.05:
            raise SystemExit(f"{name}.wav duration does not match sidecar")
        height, salience = contour(audio.mean(axis=1), sample_rate, rate, frames)
        sources[name] = {
            "height": [round(float(v), 4) for v in height],
            "salience": [round(float(v), 4) for v in salience],
        }
    sidecar["melodyContour"] = {
        "version": 1,
        "method": "strongest_spectral_peak_110_2500hz_v1",
        "envelopeRate": rate,
        "sources": sources,
    }
    output_path.write_text(json.dumps(sidecar))


def _self_check():
    sample_rate, rate, seconds = 22050, 20.0, 4
    t = np.arange(sample_rate * seconds) / sample_rate
    # Rising glide 220 Hz -> 880 Hz must give a rising height.
    glide = np.sin(2 * np.pi * 220.0 * seconds / np.log(4) * (4 ** (t / seconds) - 1))
    height, salience = contour(glide, sample_rate, rate, int(seconds * rate))
    assert height[-5] - height[5] > 0.7, (height[5], height[-5])
    assert np.all(np.diff(height[5:-5]) > -0.02)
    assert salience.min() > 0.15
    silent_height, silent = contour(np.zeros_like(t), sample_rate, rate, 80)
    assert silent.max() == 0.0 and np.all(silent_height == 0.5)
    print("dance_melody self-check passed")


if __name__ == "__main__":
    _self_check() if sys.argv[1:] == ["--self-check"] else main(sys.argv)
