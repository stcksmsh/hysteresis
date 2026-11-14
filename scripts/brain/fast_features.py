"""Fast features (docs/BRAIN_SPEC.md 1.1): 44 columns at 100 Hz from the full mix.

Fixed here, before any check runs (BRAIN_SPEC section 8, "the feature code"):
  audio      mono, SR = 44100 Hz (soxr HQ resample when the file differs)
  STFT       Hann window, N_FFT = 2048 (46.4 ms), HOP = 441 (10 ms = 100 Hz), centred (reflect padding),
             so frame t is centred on t / 100 s and a clip of n samples has 1 + n // 441 frames
  power      P = |X|^2; dB(x) = 10 log10(x + 1e-8)  (floor -80 dB)
  columns    0..31   log-mel: 32 mel bands (librosa Slaney mel, triangular, 30..16000 Hz) of P, in dB
             32..39  8-band flux: for each of 8 frequency groups (GROUP_EDGES_HZ), the mean over the group's
                     STFT bins of the half-wave rectified one-frame rise of dB(P); column 32 (30-200 Hz) is
                     the "low-band flux below 200 Hz" the pulse bank uses as a kick proxy
             40      onset strength: mean over the 32 log-mel bands of the half-wave rectified one-frame rise
                     (the librosa onset_strength definition, with lag 1 and no extra smoothing)
             41      RMS of the 2048-sample frame (rectangular), linear amplitude
             42      spectral centroid of |X|, in units of the Nyquist frequency (0..1)
             43      spectral flatness of P: geometric mean / arithmetic mean (0..1)
  first frame: every rise (flux, onset) is 0.
Standardisation statistics come later from the B3 corpus; `standardise` is the hook.
"""
import numpy as np
import librosa
import soundfile as sf
import soxr

SR = 44100
N_FFT = 2048
HOP = 441
FRAME_RATE = SR / HOP  # 100 Hz
N_MEL = 32
FMIN, FMAX = 30.0, 16000.0
GROUP_EDGES_HZ = (30.0, 200.0, 400.0, 800.0, 1600.0, 3200.0, 6400.0, 12800.0, 16000.0)
FLOOR = 1e-8
COLUMNS = ([f"logmel{i}" for i in range(N_MEL)] + [f"flux{i}" for i in range(8)]
           + ["onset", "rms", "centroid", "flatness"])
N_COLUMNS = len(COLUMNS)  # 44
COL_FLUX_LOW = COLUMNS.index("flux0")
COL_ONSET = COLUMNS.index("onset")

_MEL = librosa.filters.mel(sr=SR, n_fft=N_FFT, n_mels=N_MEL, fmin=FMIN, fmax=FMAX).astype(np.float32)
_FREQ = np.linspace(0.0, SR / 2, N_FFT // 2 + 1, dtype=np.float32)
_GROUP = [np.flatnonzero((_FREQ >= lo) & (_FREQ < hi)) for lo, hi in zip(GROUP_EDGES_HZ[:-1], GROUP_EDGES_HZ[1:])]


def load_mono(path, sr=SR):
    """Audio file -> float32 mono at `sr`."""
    y, native = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if native != sr:
        y = soxr.resample(y, native, sr, quality="HQ")
    return np.ascontiguousarray(y, dtype=np.float32)


def _rise(x):
    """Half-wave rectified one-frame rise along the last axis (0 at the first frame)."""
    d = np.zeros_like(x)
    d[..., 1:] = np.maximum(x[..., 1:] - x[..., :-1], 0.0)
    return d


def fast_features(y):
    """Mono float audio at SR -> (frames, 44) float32 at 100 Hz."""
    y = np.asarray(y, dtype=np.float32)
    S = librosa.stft(y, n_fft=N_FFT, hop_length=HOP, window="hann", center=True, pad_mode="reflect")
    mag = np.abs(S).astype(np.float32)               # (1025, T)
    P = mag ** 2
    logmel = 10.0 * np.log10(_MEL @ P + FLOOR)       # (32, T)
    logp = 10.0 * np.log10(P + FLOOR)
    flux = np.stack([_rise(logp[g]).mean(axis=0) for g in _GROUP])      # (8, T)
    onset = _rise(logmel).mean(axis=0)
    rms = librosa.feature.rms(y=y, frame_length=N_FFT, hop_length=HOP, center=True, pad_mode="reflect")[0]
    centroid = (_FREQ[:, None] * mag).sum(axis=0) / (mag.sum(axis=0) + 1e-12) / (SR / 2)
    flatness = np.exp(np.log(P + 1e-12).mean(axis=0)) / (P.mean(axis=0) + 1e-12)
    out = np.concatenate([logmel, flux, onset[None], rms[None], centroid[None], flatness[None]], axis=0).T
    return np.ascontiguousarray(out, dtype=np.float32)


def standardise(features, mean, std):
    """Hook: (features - mean) / std with statistics from the B3 training corpus."""
    return (features - mean) / np.maximum(std, 1e-8)
