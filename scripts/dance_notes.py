#!/usr/bin/env python3
"""Add rough note tracks of the estimated stems to a sidecar.

Usage: python3 scripts/dance_notes.py INPUT_SIDECAR STEM_DIR OUTPUT_SIDECAR

Adds `noteTrack.lanes`, one lane per WAV in STEM_DIR (any separation: four
stems, six stems, or stems split further): onsets with a rough pitch, grouped
into phrases, and a loudness per beat so a reader can tell which lane leads.
Stems are source-separation estimates. `pitch` is the strongest harmonic series
near each onset (often a chord root), not a transcription; drums carry none (0).
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np
import soundfile as sf
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks, stft

HOP_SECONDS = 0.01
FFT = 4096
# stem name: (onset band in Hz, MIDI range searched for pitch or None)
SETTINGS = {
    "vocals": ((150, 5000), (48, 84)),
    "bass": ((40, 1000), (28, 55)),
    "drums": ((30, 10000), None),
}
DEFAULT = ((150, 5000), (40, 88))
# A pause this long (beats) between onsets ends a phrase.
GAP_BEATS = 1.25
# A phrase also ends where the pitch settles this far (semitones) from before.
SHIFT_SEMITONES = 1.5
MIN_PHRASE_NOTES = 4


def track(audio, sample_rate, beat, band=(150, 5000), pitch_range=(43, 88)):
    """Return (notes, phrases). notes: [time, midi pitch, strength 0..1]."""
    hop = round(HOP_SECONDS * sample_rate)
    # ponytail: whole-song STFT in memory (about 0.6 GB for six minutes); chunk if songs get long.
    freqs, times, spectrum = stft(
        audio, sample_rate, nperseg=FFT, noverlap=FFT - hop, padded=False, boundary=None
    )
    magnitude = np.abs(spectrum)
    # Onsets: rising log-spectrum inside the lane's band, from a short window:
    # the long pitch window reports onsets early.
    short_freqs, onset_times, short = stft(
        audio, sample_rate, nperseg=FFT // 4, noverlap=FFT // 4 - hop, padded=False, boundary=None
    )
    band = np.log1p(200 * np.abs(short[(short_freqs >= band[0]) & (short_freqs <= band[1])]))
    flux = np.maximum(0, np.diff(band, axis=1, prepend=band[:, :1])).sum(0)
    scale = np.percentile(flux, 99)
    if scale <= 0:
        return [], []
    flux /= scale
    floor = 1.5 * uniform_filter1d(flux, round(1 / HOP_SECONDS)) + 0.05
    peaks, _ = find_peaks(flux, height=floor, distance=round(0.08 / HOP_SECONDS))
    # Same onsets as frame indices of the long window.
    frames = np.searchsorted(times, onset_times[peaks])

    # Strongest harmonic series, half-semitone steps.
    pitches = np.arange(*pitch_range, 0.5) if pitch_range else np.zeros(1)
    salience = np.zeros((len(pitches), magnitude.shape[1]), dtype=np.float32)
    fundamental = 440 * 2 ** ((pitches - 69) / 12)
    for harmonic in range(1, 6):
        bins = np.round(fundamental * harmonic * FFT / sample_rate).astype(int)
        salience += 0.8 ** (harmonic - 1) * magnitude[np.clip(bins, 0, len(freqs) - 1)]

    notes = []
    for peak, a, b in zip(peaks, frames, [*frames[1:], magnitude.shape[1]]):
        # Skip the attack; listen for at most 250 ms or until the next onset.
        held = salience[:, a + 5 : max(a + 6, min(b, a + 25))].mean(1)
        notes.append([float(onset_times[peak]), float(pitches[np.argmax(held)]), float(min(1.0, flux[peak]))])

    phrases, first = [], 0
    pitch = np.array([n[1] for n in notes])
    for i in range(1, len(notes) + 1):
        last = i == len(notes)
        gap = last or notes[i][0] - notes[i - 1][0] > GAP_BEATS * beat
        ahead = pitch[i : i + 3]
        shift = (
            not last
            and i - first >= MIN_PHRASE_NOTES
            and len(ahead) == 3
            and np.ptp(ahead) <= 1
            and abs(np.median(ahead) - np.median(pitch[max(first, i - 3) : i])) >= SHIFT_SEMITONES
        )
        if not (gap or shift):
            continue
        group = notes[first:i]
        ring = beat if last else min(beat, notes[i][0] - group[-1][0])
        start, end = group[0][0], group[-1][0] + ring
        phrases.append({
            "start": start,
            "end": end,
            "notes": len(group),
            "pitchStart": group[0][1],
            "pitchEnd": group[-1][1],
            "pitchMedian": float(np.median([n[1] for n in group])),
            "notesPerBeat": len(group) / max((end - start) / beat, 1e-9),
            "endsWith": "pause" if gap else "pitch",
        })
        first = i
    return notes, phrases


def beat_levels(audio, sample_rate, beat, beat_zero, duration):
    """A-weighted level in dB (re full scale) for each beat of the grid."""
    freqs, times, spectrum = stft(audio, sample_rate, nperseg=2048, noverlap=1024, padded=False, boundary=None)
    f2 = freqs**2
    weight = (12194**2 * f2**2) / (
        (f2 + 20.6**2) * np.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + 12194**2) + 1e-30
    )
    power = (np.abs(spectrum) ** 2 * (weight / weight.max())[:, None] ** 2).sum(0)
    index = np.floor((times - beat_zero) / beat).astype(int)
    count = int((duration - beat_zero) / beat)
    out = []
    for i in range(count):
        frames = power[index == i]
        out.append(round(float(10 * np.log10(frames.mean() + 1e-12)), 2) if len(frames) else -120.0)
    return out


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    sidecar_path, stem_dir, output_path = map(pathlib.Path, argv[1:])
    if output_path.resolve() == sidecar_path.resolve() or stem_dir.resolve() in output_path.resolve().parents:
        raise SystemExit("output must differ from the input and lie outside the stem directory")
    sidecar = json.loads(sidecar_path.read_text())
    memory = sidecar["musicalMemory"]
    beat, beat_zero, duration = float(memory["beatPeriod"]), float(memory["beatZero"]), float(sidecar["duration"])
    stems = sorted(stem_dir.glob("*.wav"))
    if not stems:
        raise SystemExit(f"no WAV stems in {stem_dir}")
    lanes = {}
    for path in stems:
        audio, sample_rate = sf.read(path, dtype="float32", always_2d=True)
        if abs(len(audio) / sample_rate - duration) > 0.1:
            raise SystemExit(f"{path.name} and sidecar duration mismatch (>100 ms)")
        band, pitch_range = SETTINGS.get(path.stem, DEFAULT)
        mono = audio.mean(1)
        notes, phrases = track(mono, sample_rate, beat, band, pitch_range)
        lanes[path.stem] = {
            "notes": notes,
            "phrases": phrases,
            "levelPerBeat": beat_levels(mono, sample_rate, beat, beat_zero, duration),
        }
        print(f"{path.stem}: {len(notes)} notes, {len(phrases)} phrases")
    sidecar["noteTrack"] = {
        "version": 1,
        "method": "stem_flux_onsets_harmonic_sum_pitch_v1",
        "groundTruth": False,
        "lanes": lanes,
    }
    output_path.write_text(json.dumps(sidecar, separators=(",", ":")))
    print(f"→ {output_path}")


if __name__ == "__main__":
    main(sys.argv)
