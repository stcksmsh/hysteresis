"""B1 pulse: a Hopf (GrFNN canonical-model) oscillator bank and its beat readout (BRAIN_SPEC 2.1).

Model (values and sources in GRFNN_PARAMS.md; nothing here is tuned on a test set):
    dz/dt = z (alpha + i w + beta1 |z|^2 + eps beta2 |z|^4 / (1 - eps |z|^2))  +  c P(eps, x) A(eps, conj z)
    P(eps, x) = x / (1 - sqrt(eps) x),   A(eps, conj z) = 1 / (1 - sqrt(eps) conj z),   w = 2 pi f
One sensory network of N_PER_OCTAVE-per-octave oscillators, F_MIN..F_MAX Hz log-spaced, critical regime.
Integration: RK4 at 5 ms (two sub-steps per 10 ms frame), the input held over the frame.
"""
import numpy as np
from numba import njit

F_MIN, F_MAX, N_PER_OCTAVE = 0.25, 8.0, 48
ALPHA, BETA1, BETA2, EPS = 0.0, -1.0, -0.25, 1.0
# Not in the cited papers (see GRFNN_PARAMS.md): input gain, input cap, input standardisation time constant,
# the initial state, the clip of |z| that keeps 1 - sqrt(eps)|z| away from zero.
C_IN = 0.05
X_MAX = 0.5
STD_TAU_S = 10.0
Z0 = 1e-3
R_MAX = 0.95
FRAME_HZ = 100.0
SUBSTEPS = 2
BEAT_BAND = (0.5, 4.0)
SWITCH_RATIO = 1.2
SWITCH_SECONDS = 2.0


def frequencies():
    n = int(round(np.log2(F_MAX / F_MIN) * N_PER_OCTAVE)) + 1
    return F_MIN * 2.0 ** (np.arange(n) / N_PER_OCTAVE)


@njit(cache=True)
def _deriv(zr, zi, w, x, alpha, b1, b2, eps, c, dr, di):
    s = np.sqrt(eps)
    p = x / (1.0 - s * x)
    for k in range(zr.shape[0]):
        r2 = zr[k] * zr[k] + zi[k] * zi[k]
        nl = alpha + b1 * r2 + eps * b2 * r2 * r2 / (1.0 - eps * r2)
        ar = 1.0 - s * zr[k]
        ai = s * zi[k]
        den = ar * ar + ai * ai
        # 1 / (ar + i ai)
        qr = ar / den
        qi = -ai / den
        dr[k] = zr[k] * nl - zi[k] * w[k] + c * p * qr
        di[k] = zi[k] * nl + zr[k] * w[k] + c * p * qi


@njit(cache=True)
def _run(x, w, alpha, b1, b2, eps, c, dt, sub, z0, rmax):
    n = w.shape[0]
    T = x.shape[0]
    out_r = np.empty((T, n))
    out_i = np.empty((T, n))
    zr = np.full(n, z0)
    zi = np.zeros(n)
    k1r = np.empty(n); k1i = np.empty(n); k2r = np.empty(n); k2i = np.empty(n)
    k3r = np.empty(n); k3i = np.empty(n); k4r = np.empty(n); k4i = np.empty(n)
    for t in range(T):
        for _ in range(sub):
            _deriv(zr, zi, w, x[t], alpha, b1, b2, eps, c, k1r, k1i)
            _deriv(zr + 0.5 * dt * k1r, zi + 0.5 * dt * k1i, w, x[t], alpha, b1, b2, eps, c, k2r, k2i)
            _deriv(zr + 0.5 * dt * k2r, zi + 0.5 * dt * k2i, w, x[t], alpha, b1, b2, eps, c, k3r, k3i)
            _deriv(zr + dt * k3r, zi + dt * k3i, w, x[t], alpha, b1, b2, eps, c, k4r, k4i)
            zr += dt / 6.0 * (k1r + 2 * k2r + 2 * k3r + k4r)
            zi += dt / 6.0 * (k1i + 2 * k2i + 2 * k3i + k4i)
            for k in range(n):
                r = np.sqrt(zr[k] * zr[k] + zi[k] * zi[k])
                if r > rmax:
                    zr[k] *= rmax / r
                    zi[k] *= rmax / r
        out_r[t] = zr
        out_i[t] = zi
    return out_r, out_i


def standardise_causal(x, tau_s=STD_TAU_S, rate=FRAME_HZ):
    """Running z-score with exponential statistics (prior mean 0, variance 1); uses no future samples."""
    a = 1.0 / (tau_s * rate)
    m, v = 0.0, 1.0
    out = np.empty(len(x), dtype=np.float64)
    for i, s in enumerate(np.asarray(x, dtype=np.float64)):
        out[i] = (s - m) / np.sqrt(v + 1e-12)
        m += a * (s - m)
        v += a * ((s - m) ** 2 - v)
    return out


def bank_input(flux_low, onset):
    """The bank's input: low-band flux (< 200 Hz) and onset strength, each standardised, summed with equal
    weight; half-wave rectified, scaled by C_IN and capped at X_MAX so that 1 - sqrt(eps) x stays positive."""
    u = standardise_causal(flux_low) + standardise_causal(onset)
    return np.minimum(C_IN * np.maximum(u, 0.0), X_MAX)


def run_bank(x):
    """Drive the bank with the input series x (one value per 10 ms frame). Returns (freqs, amplitude, phase)
    with amplitude and phase of shape (frames, oscillators)."""
    f = frequencies()
    zr, zi = _run(np.ascontiguousarray(x, dtype=np.float64), 2 * np.pi * f, ALPHA, BETA1, BETA2, EPS, 1.0,
                  1.0 / (FRAME_HZ * SUBSTEPS), SUBSTEPS, Z0, R_MAX)
    return f, np.hypot(zr, zi), np.arctan2(zi, zr)


def readout(freqs, amp, phase):
    """Beat readout: the strongest oscillator in 0.5-4 Hz, switching to another only when some oscillator's
    amplitude exceeds the current one's by 20 % on 2 s of consecutive frames. Beats are the upward phase-zero
    crossings of the selected oscillator. Returns beat times (s), the selected index per frame, its amplitude,
    and its frequency."""
    band = np.flatnonzero((freqs >= BEAT_BAND[0]) & (freqs <= BEAT_BAND[1]))
    T = amp.shape[0]
    need = int(round(SWITCH_SECONDS * FRAME_HZ))
    cur, run = None, 0
    chosen = np.zeros(T, dtype=np.int64)
    beats = []
    prev_phase = None
    for t in range(T):
        a = amp[t, band]
        best = band[int(np.argmax(a))]
        if cur is None:
            cur = best
            prev_phase = phase[t, cur]
        else:
            if amp[t, best] > SWITCH_RATIO * amp[t, cur]:
                run += 1
            else:
                run = 0
            if run >= need:
                cur, run = best, 0
                prev_phase = phase[t, cur]
                chosen[t] = cur
                continue
        p = phase[t, cur]
        if prev_phase < 0.0 <= p and p - prev_phase < np.pi:   # upward crossing of phase 0 (not the +-pi wrap)
            frac = -prev_phase / (p - prev_phase)
            beats.append((t - 1 + frac) / FRAME_HZ)
        prev_phase = p
        chosen[t] = cur
    chosen_amp = amp[np.arange(T), chosen]
    return np.array(beats), chosen, chosen_amp, freqs[chosen]


def pulse(flux_low, onset):
    """Features of one clip -> {beats, amp (readout amplitude), freq (readout frequency), bank amplitude}."""
    f, amp, phase = run_bank(bank_input(flux_low, onset))
    beats, chosen, chosen_amp, chosen_freq = readout(f, amp, phase)
    return {"beats": beats, "readout_amp": chosen_amp, "readout_freq": chosen_freq, "freqs": f, "amp": amp.astype(np.float32)}
