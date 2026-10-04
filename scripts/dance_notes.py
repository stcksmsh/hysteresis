#!/usr/bin/env python3
"""Add a rough note track of one estimated stem (keys/guitar) to a sidecar.

Usage: python3 scripts/dance_notes.py INPUT_SIDECAR STEM_WAV OUTPUT_SIDECAR

Adds `noteTrack`: onsets with a rough pitch, grouped into phrases. The stem is a
source-separation estimate and usually polyphonic, so `pitch` is the strongest
harmonic series near each onset (often the chord root), not a transcription.
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
# MIDI range searched for the strongest harmonic series, half-semitone steps.
PITCHES = np.arange(43, 88.5, 0.5)
# A pause this long (beats) between onsets ends a phrase.
GAP_BEATS = 1.25
# A phrase also ends where the pitch settles this far (semitones) from before.
SHIFT_SEMITONES = 1.5
MIN_PHRASE_NOTES = 4


def track(audio, sample_rate, beat):
    """Return (notes, phrases). notes: [time, midi pitch, strength 0..1]."""
    hop = round(HOP_SECONDS * sample_rate)
    # ponytail: whole-song STFT in memory (about 0.6 GB for six minutes); chunk if songs get long.
    freqs, times, spectrum = stft(
        audio, sample_rate, nperseg=FFT, noverlap=FFT - hop, padded=False, boundary=None
    )
    magnitude = np.abs(spectrum)
    # Onsets: rising log-spectrum between 150 Hz and 5 kHz (drops bass bleed and
    # hiss), from a short window: the long pitch window reports onsets early.
    short_freqs, onset_times, short = stft(
        audio, sample_rate, nperseg=FFT // 4, noverlap=FFT // 4 - hop, padded=False, boundary=None
    )
    band = np.log1p(200 * np.abs(short[(short_freqs >= 150) & (short_freqs <= 5000)]))
    flux = np.maximum(0, np.diff(band, axis=1, prepend=band[:, :1])).sum(0)
    scale = np.percentile(flux, 99)
    if scale <= 0:
        return [], []
    flux /= scale
    floor = 1.5 * uniform_filter1d(flux, round(1 / HOP_SECONDS)) + 0.05
    peaks, _ = find_peaks(flux, height=floor, distance=round(0.08 / HOP_SECONDS))
    # Same onsets as frame indices of the long window.
    frames = np.searchsorted(times, onset_times[peaks])

    salience = np.zeros((len(PITCHES), magnitude.shape[1]), dtype=np.float32)
    fundamental = 440 * 2 ** ((PITCHES - 69) / 12)
    for harmonic in range(1, 6):
        bins = np.round(fundamental * harmonic * FFT / sample_rate).astype(int)
        salience += 0.8 ** (harmonic - 1) * magnitude[np.clip(bins, 0, len(freqs) - 1)]

    notes = []
    for peak, a, b in zip(peaks, frames, [*frames[1:], magnitude.shape[1]]):
        # Skip the attack; listen for at most 250 ms or until the next onset.
        held = salience[:, a + 5 : max(a + 6, min(b, a + 25))].mean(1)
        notes.append([float(onset_times[peak]), float(PITCHES[np.argmax(held)]), float(min(1.0, flux[peak]))])

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


def main(argv):
    if len(argv) != 4:
        raise SystemExit(__doc__)
    sidecar_path, stem_path, output_path = map(pathlib.Path, argv[1:])
    if output_path.resolve() in (sidecar_path.resolve(), stem_path.resolve()):
        raise SystemExit("output must differ from inputs")
    sidecar = json.loads(sidecar_path.read_text())
    beat = float(sidecar["musicalMemory"]["beatPeriod"])
    audio, sample_rate = sf.read(stem_path, dtype="float32", always_2d=True)
    if abs(len(audio) / sample_rate - float(sidecar["duration"])) > 0.1:
        raise SystemExit("stem and sidecar duration mismatch (>100 ms)")
    notes, phrases = track(audio.mean(1), sample_rate, beat)
    sidecar["noteTrack"] = {
        "version": 1,
        "method": "stem_flux_onsets_harmonic_sum_pitch_v1",
        "stem": stem_path.name,
        "groundTruth": False,
        "notes": notes,
        "phrases": phrases,
    }
    output_path.write_text(json.dumps(sidecar, separators=(",", ":")))
    print(f"{len(notes)} notes, {len(phrases)} phrases → {output_path}")


if __name__ == "__main__":
    main(sys.argv)
