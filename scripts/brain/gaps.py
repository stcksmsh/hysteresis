"""Gate 2 gaps (docs/BRAIN_SPEC.md 2.2): synthetic gaps of 2, 4 and 8 s cut into a clip after at least 10 s of music,
two kinds. The gap replaces audio; the beat annotations are left alone and continue through it.

  silence  digital zeros
  noise    noise shaped to the average magnitude spectrum of the 2 s before the gap (STFT 2048, hop 512, Hann),
           random phase, RMS equal to that of those 2 s (an onset-free filler; a low-pass would keep the kick)
Each gap has 50 ms raised-cosine crossfades at both ends (music to filler over the first 50 ms of the gap, filler to
music over the last 50 ms). Verification (BRAIN_SPEC 2.2 correction, replacing the 5 % onset rule): `gap_valid` tests the bank's
input over the gap for rhythm against a permutation null; a clip that fails is reported and left out of gate 2.
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
PERMUTATIONS = 1000
LAG_MIN_S, LAG_MAX_S = 0.25, 2.0
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


def lag_statistic(x, lo, hi):
    """Maximum of the mean-removed normalised autocorrelation of each row of x over lags lo..hi (frames)."""
    x = np.atleast_2d(np.asarray(x, dtype=np.float64))
    x = x - x.mean(axis=1, keepdims=True)
    n = x.shape[1]
    power = np.fft.rfft(x, 2 * n, axis=1)
    ac = np.fft.irfft(power * np.conj(power), 2 * n, axis=1)[:, :n]
    var = ac[:, 0]
    r = ac[:, lo:hi + 1] / np.where(var > 0, var, 1.0)[:, None]
    return r.max(axis=1)


def gap_valid(x, start_s, gap_s, clip_id, kind, rate=100.0, detrend=False):
    """Gap verification (BRAIN_SPEC 2.2 correction): is there rhythm in what the bank was fed over the gap?
    x = the bank's actual input series (summed standardised onset and low-band flux, as `grfnn.pulse(...)["input"]`).
    Statistic: max of the mean-removed normalised autocorrelation of the gap's frames over lags 0.25 s .. min(2 s, gap / 2).
    Null: PERMUTATIONS random permutations of the gap's frames (seed from SEED, the clip id, the gap and the kind).
    Valid if the statistic <= the 95th percentile of the permuted statistics; a zero-variance gap is valid.
    detrend=True (round 2, reported only): the gap's linear trend is removed first; the gated test never uses it.
    Returns (valid, statistic, threshold)."""
    a, b = int(round(start_s * rate)), int(round((start_s + gap_s) * rate))
    g = np.asarray(x[a:b], dtype=np.float64)
    if detrend:
        g = g - np.polyval(np.polyfit(np.arange(len(g)), g, 1), np.arange(len(g)))
        if not np.ptp(g) > 1e-9:
            return True, 0.0, 0.0
    lo, hi = int(round(LAG_MIN_S * rate)), int(round(min(LAG_MAX_S, gap_s / 2.0) * rate))
    if not np.ptp(g) > 0.0:
        return True, 0.0, 0.0
    stat = float(lag_statistic(g, lo, hi)[0])
    rng = np.random.default_rng([SEED, zlib.crc32(clip_id.encode()), int(round(gap_s * 10)), KINDS.index(kind), 7])
    perms = np.stack([rng.permutation(g) for _ in range(PERMUTATIONS)])
    thr = float(np.percentile(lag_statistic(perms, lo, hi), 95))
    return stat <= thr, stat, thr
