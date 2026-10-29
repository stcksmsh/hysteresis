"""Gate 2 gaps (docs/BRAIN_SPEC.md 2.2): synthetic gaps of 2, 4 and 8 s cut into a clip after at least 10 s of music,
two kinds. The gap replaces audio; the beat annotations are left alone and continue through it.

  silence  digital zeros
  noise    noise shaped to the average magnitude spectrum of the 2 s before the gap (STFT 2048, hop 512, Hann),
           random phase, RMS equal to that of those 2 s (an onset-free filler; a low-pass would keep the kick)
Each gap has 50 ms raised-cosine crossfades at both ends (music to filler over the first 50 ms of the gap, filler to
music over the last 50 ms). A gap is kept only if its onset strength (fast-feature column 40, frames at least 100 ms
inside the gap) has mean below 5 % of the clip's median onset strength; a clip that fails is reported and left out.
Gap positions come from SEED, fixed here.
"""
import zlib

import numpy as np
import librosa

SEED = 20261029
GAPS = (2.0, 4.0, 8.0)
KINDS = ("silence", "noise")
MIN_MUSIC_S = 10.0
XFADE_S = 0.05
ONSET_FRACTION = 0.05
EDGE_GUARD_S = 0.1
MARGIN_S = 0.5  # the gap ends at least this long before the clip does
N_FFT, HOP = 2048, 512


def rng_for(clip_id, gap_s, kind):
    return np.random.default_rng([SEED, zlib.crc32(clip_id.encode()), int(round(gap_s * 10)), KINDS.index(kind)])


def gap_start(clip_id, gap_s, kind, duration):
    """Start of the gap in seconds (10 ms grid), uniform in [10, duration - gap - 0.5]; None if the clip is too short."""
    hi = duration - gap_s - MARGIN_S
    if hi < MIN_MUSIC_S:
        return None
    return round(float(rng_for(clip_id, gap_s, kind).uniform(MIN_MUSIC_S, hi)), 2)


def shaped_noise(before, n, rng):
    """`n` samples of noise with the average magnitude spectrum and the RMS of `before`."""
    S = np.abs(librosa.stft(before, n_fft=N_FFT, hop_length=HOP, window="hann", center=True, pad_mode="reflect"))
    mag = S.mean(axis=1)                                           # (1025,)
    grid = np.fft.rfftfreq(n, d=1.0) * 2.0                          # 0..1 of Nyquist for the gap's own FFT bins
    shape = np.interp(grid, np.linspace(0.0, 1.0, len(mag)), mag)
    phase = rng.uniform(0.0, 2 * np.pi, size=len(shape))
    phase[0] = 0.0
    x = np.fft.irfft(shape * np.exp(1j * phase), n=n)
    rms_target = float(np.sqrt(np.mean(before.astype(np.float64) ** 2)))
    return (x * (rms_target / max(float(np.sqrt(np.mean(x ** 2))), 1e-12))).astype(np.float32)


def make_gap(y, sr, start_s, gap_s, kind, clip_id=""):
    """Clip with the gap [start, start + gap) replaced. Returns a new float32 array of the same length."""
    a, b = int(round(start_s * sr)), int(round((start_s + gap_s) * sr))
    out = np.asarray(y, dtype=np.float32).copy()
    n = b - a
    if kind == "silence":
        filler = np.zeros(n, np.float32)
    else:
        before = out[max(0, a - int(2 * sr)):a]
        filler = shaped_noise(before, n, rng_for(clip_id, gap_s, kind))
    x = int(round(XFADE_S * sr))
    w = 0.5 - 0.5 * np.cos(np.pi * np.arange(x) / x)                # 0 -> 1
    orig = y[a:b].astype(np.float32)
    seg = filler.copy()
    seg[:x] = orig[:x] * (1 - w) + filler[:x] * w                    # music -> filler
    seg[n - x:] = filler[n - x:] * (1 - w) + orig[n - x:] * w       # filler -> music
    out[a:b] = seg
    return out


def onset_ok(features_gapped, features_original, start_s, gap_s, rate=100.0, col=40):
    """(ok, gap onset mean, 5 % of the clip's median onset strength)."""
    lo, hi = int(round((start_s + EDGE_GUARD_S) * rate)), int(round((start_s + gap_s - EDGE_GUARD_S) * rate))
    inside = float(features_gapped[lo:hi, col].mean())
    limit = ONSET_FRACTION * float(np.median(features_original[:, col]))
    return inside < limit, inside, limit
