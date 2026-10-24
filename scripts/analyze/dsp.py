"""Ports of src/audio/worklet/{bands,spectral,onset,envelope}.ts and shared/constants.ts.

Per-hop feature math is batched over hops (axis 0). Every JS `sum += x` loop is
reproduced with np.cumsum (strictly sequential), so summation order matches.
"""
import math

import numpy as np

FFT_SIZE = 2048
HOP_SIZE = 512
TEMPO_MIN_BPM = 60
TEMPO_MAX_BPM = 190
BAND_EDGES_HZ = [20, 80, 250, 2000, 6000, 20000]
BAND_NAMES = ['sub', 'low', 'mid', 'presence', 'air']


def js_round(x: float) -> int:
    """Math.round: ties toward +Infinity."""
    return math.floor(x + 0.5)


def seqsum(a: np.ndarray) -> np.ndarray:
    """Sequential sum along the last axis (0 for empty)."""
    if a.shape[-1] == 0:
        return np.zeros(a.shape[:-1])
    return np.cumsum(a, axis=-1)[..., -1]


def compute_band_ranges(fft_size: int, sample_rate: float):
    bin_hz = sample_rate / fft_size
    edge_bins = [js_round(hz / bin_hz) for hz in BAND_EDGES_HZ]
    ranges = {}
    for i, name in enumerate(BAND_NAMES):
        lo = edge_bins[i]
        hi = max(lo + 1, edge_bins[i + 1])
        ranges[name] = (lo, hi)
    return ranges


def band_energies(mags: np.ndarray, ranges) -> np.ndarray:
    """mags (B, bins) f32 -> (B, 5) f64 RMS per band."""
    m = mags.astype(np.float64)
    out = np.zeros((m.shape[0], len(BAND_NAMES)))
    for j, name in enumerate(BAND_NAMES):
        lo, hi = ranges[name]
        end = min(hi, m.shape[1])
        seg = m[:, lo:end]
        count = max(0, end - lo)
        if count > 0:
            out[:, j] = np.sqrt(seqsum(seg * seg) / count)
    return out


def dominant_band_tone(bands) -> float:
    best_index = 0
    best_value = -1
    for i, v in enumerate(bands):
        if v > best_value:
            best_value = v
            best_index = i
    return best_index / (len(BAND_NAMES) - 1)


def spectral_centroid_hz(mags: np.ndarray, sample_rate: float, fft_size: int) -> np.ndarray:
    bin_hz = sample_rate / fft_size
    m = mags[:, 1:].astype(np.float64)
    idx = np.arange(1, mags.shape[1], dtype=np.float64)
    weighted = seqsum((idx * bin_hz) * m)
    mag_sum = seqsum(m)
    return np.where(mag_sum > 1e-9, weighted / np.where(mag_sum > 1e-9, mag_sum, 1), 0.0)


def spectral_flatness(mags: np.ndarray) -> np.ndarray:
    m = mags[:, 1:].astype(np.float64)
    ok = m > 1e-9
    safe = np.where(ok, m, 1.0)
    log_sum = seqsum(np.where(ok, np.log(safe), 0.0))
    s = seqsum(np.where(ok, m, 0.0))
    n = ok.sum(axis=-1)
    valid = (n > 0) & (s != 0)
    nn = np.where(valid, n, 1)
    geo = np.exp(log_sum / nn)
    arith = s / nn
    good = valid & (arith > 1e-9)
    return np.where(good, geo / np.where(good, arith, 1), 0.0)


def spectral_flux(mags: np.ndarray, prev_last: np.ndarray):
    """Batched SpectralFlux.update. Returns (flux (B,), new prev row)."""
    m = mags.astype(np.float64)
    prev = np.vstack([prev_last[None, :], m[:-1]])
    diff = m - prev
    flux = seqsum(np.where(diff > 0, diff, 0.0))
    return flux, m[-1].copy()


class EnvelopeFollower:
    def __init__(self, attack_ms: float, release_ms: float, hop_ms: float):
        self.value = 0.0
        self.initialized = False
        self.attack = math.exp(-hop_ms / attack_ms)
        self.release = math.exp(-hop_ms / release_ms)

    def update(self, x: float) -> float:
        if not self.initialized:
            self.value = x
            self.initialized = True
            return self.value
        c = self.attack if x > self.value else self.release
        self.value = c * self.value + (1 - c) * x
        return self.value


class AdaptiveNormalizer:
    def __init__(self, decay_ms: float, hop_ms: float):
        self.peak = 1e-6
        self.decay = math.exp(-hop_ms / decay_ms)

    def normalize(self, v: float) -> float:
        self.peak = max(v, self.peak * self.decay)
        return min(1, v / self.peak) if self.peak > 1e-6 else 0
