import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import syncaudit_b as S  # noqa: E402


def _env(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    x = np.convolve(rng.normal(size=n), np.ones(5) / 5, "same")
    return S.demean(x)


def test_known_lag_recovered_both_signs():
    env = _env()
    for lag_s in (0.3, -0.46, 0.0):
        k = round(lag_s * S.FS)
        m = np.roll(env, k)                       # m(t) = e(t - lag): motion LATER than music for lag > 0
        c = S.curve(m, env, base=0, lo=500, hi=2000)
        l, h = S.peak(c)
        assert abs(l - lag_s) <= 0.02 and h > 0.95, (lag_s, l, h)


def test_subsample_parabola():
    env = _env(seed=1)
    m = 0.5 * (np.roll(env, 10) + np.roll(env, 11))   # lag 10.5 samples = 0.21 s
    l, _ = S.peak(S.curve(m, env, lo=500, hi=2000))
    assert abs(l - 0.21) <= 0.01


def test_demean_does_not_move_peak():
    env = _env(seed=2)
    drift = np.linspace(0, 5, len(env))
    m = np.roll(env, 15) + drift
    l, _ = S.peak(S.curve(S.demean(m), env, lo=500, hi=2000))
    assert abs(l - 0.30) <= 0.02


def test_chance_shift_changes_lag_not_sign_convention():
    env = _env(seed=3)
    m = np.roll(env, 25)                                       # +0.5 s
    shifted = np.roll(env, 4 * S.FS)                           # own music circularly shifted 4 s
    l, h = S.peak(S.curve(m, shifted, lo=500, hi=2000))
    assert h < 0.5 or abs(l - 0.5) > 0.2                       # the true lag does not survive the shift


def test_foil_offset_convention():
    # foil music = real music at t + offset  <=>  c_real at L = -offset equals c_foil at 0 (correction to the rules note)
    env = _env(n=4000, seed=5)
    m = env[1000:1500].copy()
    off = int(round(3.4 * S.FS))
    cr = S.curve(m, env, base=1000, lo=0, hi=500, kmax=300)
    cf = S.curve(m, env, base=1000 + off, lo=0, hi=500, kmax=0)[0]
    assert abs(cr[300 - off] - cf) < 1e-12
    assert abs(S.peak(cr, 75, 300)[0]) < 1e-3


def test_out_of_range_and_constant_are_nan():
    env = _env(n=400)
    assert np.isnan(S.curve(np.ones(400), env, lo=0, hi=300)).all()
    assert np.isnan(S.curve(env, env, base=0, lo=0, hi=400)).all()
    assert np.isnan(S.peak(np.full(2 * S.KMAX + 1, np.nan))[0])
