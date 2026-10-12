"""Baseline features: the sidecar's mix and stem signals, computed from audio.

Same signals and constants as the base sidecar (20 Hz envelope, 2048-point FFT,
band edges 20/80/250/2000/6000/20000 Hz, centroid, flatness, log-magnitude
flux) and as scripts/dance_stems.py (absolute RMS and flux per estimated stem),
summarised per 4 s window. See docs/DANCE_HANDOFF.md "Emotion stage 1".
"""
from __future__ import annotations

import numpy as np
from scipy.signal import find_peaks

from common import WINDOW_SECONDS

RATE = 20.0
FFT = 2048
BAND_EDGES_HZ = (20, 80, 250, 2000, 6000, 20000)
SOURCES = ("vocals", "drums", "bass", "other")
MIX_NAMES = ("rms", "sub", "low", "mid", "presence", "air", "centroid", "flatness", "flux")


def _frames(audio, sr):
    """(n_frames, FFT) windowed blocks centred on each 20 Hz frame, channels averaged in power."""
    audio = audio.reshape(len(audio), -1)
    n = int(np.ceil(len(audio) / sr * RATE))
    window = np.hanning(FFT).astype(np.float32)
    centre = np.round((np.arange(n) + 0.5) * sr / RATE).astype(int)
    padded = np.pad(audio, ((FFT // 2, FFT), (0, 0)))
    spectra = np.empty((n, FFT // 2 + 1), dtype=np.float32)
    for i, c in enumerate(centre):
        block = padded[c:c + FFT] * window[:, None]
        spectra[i] = np.sqrt(np.mean(np.abs(np.fft.rfft(block, axis=0)) ** 2, axis=1))
    return spectra


def _block_rms_db(audio, sr):
    audio = audio.reshape(len(audio), -1)
    n = int(np.ceil(len(audio) / sr * RATE))
    edges = np.round(np.arange(n + 1) * sr / RATE).astype(int)
    out = np.empty(n, dtype=np.float32)
    for i in range(n):
        block = audio[edges[i]:min(edges[i + 1], len(audio))]
        out[i] = np.sqrt(np.mean(block ** 2)) if len(block) else 0.0
    return 20 * np.log10(out + 1e-5)


def _flux(spectra):
    mag = np.log1p(spectra)
    flux = np.zeros(len(mag), dtype=np.float32)
    flux[1:] = np.maximum(0.0, mag[1:] - mag[:-1]).sum(axis=1)
    return flux


def mix_frames(audio, sr):
    """(n, 9) per-frame mix features, columns = MIX_NAMES."""
    spectra = _frames(audio, sr)
    bins = np.fft.rfftfreq(FFT, 1 / sr)
    cols = [_block_rms_db(audio, sr)]
    for lo, hi in zip(BAND_EDGES_HZ[:-1], BAND_EDGES_HZ[1:]):
        sel = (bins >= lo) & (bins < hi)
        cols.append(20 * np.log10(np.sqrt(np.mean(spectra[:, sel] ** 2, axis=1)) + 1e-6))
    mags = spectra[:, 1:]
    total = mags.sum(axis=1)
    cent = np.where(total > 1e-9, (mags * bins[1:]).sum(axis=1) / np.maximum(total, 1e-9), 0.0)
    cols.append(np.minimum(cent, 8000.0) / 8000.0)
    positive = mags > 1e-9
    logm = np.where(positive, np.log(np.maximum(mags, 1e-9)), 0.0)
    n = positive.sum(axis=1)
    geo = np.exp(logm.sum(axis=1) / np.maximum(n, 1))
    arith = np.where(n > 0, mags.sum(axis=1, where=positive) / np.maximum(n, 1), 0.0)
    cols.append(np.where(arith > 1e-9, geo / np.maximum(arith, 1e-9), 0.0))
    cols.append(_flux(spectra))
    return np.stack(cols, axis=1).astype(np.float32)


def stem_frames(stems, sr):
    """(n, 8): rms dB then flux for vocals, drums, bass, other. `stems` = {name: (samples, ch)}."""
    cols = []
    for name in SOURCES:
        cols.append(_block_rms_db(stems[name], sr))
        cols.append(_flux(_frames(stems[name], sr)))
    return np.stack(cols, axis=1).astype(np.float32)


def _slice(centre, n, window=WINDOW_SECONDS):
    lo = max(0, int(round((centre - window / 2) * RATE)))
    hi = min(n, int(round((centre + window / 2) * RATE)))
    return lo, max(hi, lo + 1)


def _onset_stats(flux, floor):
    peaks, _ = find_peaks(flux, height=floor, distance=3)
    density = len(peaks) / (len(flux) / RATE)
    f = flux - flux.mean()
    ac = np.correlate(f, f, mode="full")[len(f) - 1:]
    ac = ac / max(ac[0], 1e-9)
    period = float(ac[5:21].max()) if len(ac) > 21 else 0.0   # lags 0.25-1.0 s
    return density, period


def window_vector(mix, stems, centre, flux_floor):
    """One 4 s window summary: mix (27+2) then stems (16+4) when `stems` is given."""
    lo, hi = _slice(centre, len(mix))
    seg = mix[lo:hi]
    out = [seg.mean(axis=0), seg.std(axis=0), seg.max(axis=0), np.array(_onset_stats(seg[:, 8], flux_floor))]
    if stems is not None:
        s = stems[lo:hi]
        db, flux = s[:, 0::2], s[:, 1::2]
        power = (10 ** (db / 10)).mean(axis=0)
        share = power / max(power.sum(), 1e-12)
        leader = np.eye(len(SOURCES))[int(np.argmax(share))]
        out += [db.mean(axis=0), db.std(axis=0), flux.mean(axis=0), share, leader]
    return np.concatenate(out).astype(np.float32)


def window_matrix(mix, stems, centres):
    floor = float(np.percentile(mix[:, 8], 75))
    return np.stack([window_vector(mix, stems, c, floor) for c in centres])
