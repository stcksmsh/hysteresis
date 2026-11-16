"""WO43 tests: controls on synthetic trajectories with known answers. Run: /secondary/hyst-env/brain/bin/python -m pytest scripts/body/test_controls.py -q"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import controls_lib as C

N = C.NTOK * C.TOK + 1
T = np.arange(N) / C.FS
NORM = dict(vj=dict(median=0.0, mad=1.0), vl=dict(median=0.0, mad=1.0), vigour=dict(loadings=[0.7071, 0.7071], sd=1.0), accent=dict(A=1.0, J=1.0))


def lamp_line(vel, z0=0.4):
    """straight constant-velocity lamp path"""
    p = np.zeros((N, 3))
    p[:, 2] = z0
    return p + T[:, None] * np.asarray(vel, float)[None]


def raw(lamp, q=None):
    return C.raw_window(np.zeros((N, 5)) if q is None else q, lamp)


def test_constant_speed_vigour():
    r = raw(lamp_line([0.3, 0.0, 0.0]), q=np.stack([T * 20.0, np.zeros(N), np.zeros(N), np.zeros(N), np.zeros(N)], 1))
    assert np.allclose(r["vl"], 0.3, atol=1e-9)
    assert np.allclose(r["vj"], np.sqrt(20.0 ** 2 / 5), atol=1e-9)      # one joint at 20 deg/s, RMS over the five
    assert np.allclose(r["vjoint"][:, 0], 20.0)


def test_height_workspace_bounds():
    c = C.finalise(raw(lamp_line([0, 0, 0], z0=-0.569)), NORM)
    assert np.allclose(c["height"], 0.0)
    c = C.finalise(raw(lamp_line([0, 0, 0], z0=0.77)), NORM)
    assert np.allclose(c["height"], 1.0)
    c = C.finalise(raw(lamp_line([0, 0, 0], z0=0.1005)), NORM)
    assert np.allclose(c["height"], 0.5)
    c = C.finalise(raw(lamp_line([0, 0, 0], z0=-0.2)), NORM)               # below the old 0.11 m bound, clear of the v2p floor
    assert np.all((c["height"] > 0) & (c["height"] < 1))


def test_direction_known_line():
    d = np.array([1.0, 2.0, 2.0]) / 3.0
    r = raw(lamp_line(0.5 * d))
    assert np.allclose(r["dir"][5], d, atol=1e-9) and r["dir_ok"][5] == 1
    r = raw(lamp_line([0.001, 0, 0]))                                      # below 0.02 m/s: zero vector
    assert r["dir_ok"][5] == 0 and not r["dir"][5].any()


def tone(f, amp=0.05):
    p = np.zeros((N, 3))
    p[:, 0] = amp * np.sin(2 * np.pi * f * T)
    p[:, 2] = 0.4
    return p


def test_sharpness_tones_and_scale_invariance():
    lo, hi = raw(tone(1.0))["sharp"], raw(tone(10.0))["sharp"]
    assert np.nanmedian(lo[5:-5]) < 0.05 and np.nanmedian(hi[5:-5]) > 0.95
    a, b = raw(tone(7.0, 0.02))["sharp"], raw(tone(7.0, 0.06))["sharp"]    # x3 amplitude, same shape
    assert np.allclose(a[3:-3], b[3:-3], atol=1e-9)
    m = tone(5.0) + 0.0
    m2 = m.copy()
    m2[:, 2] = 0.4 + 3 * (m[:, 2] - 0.4)
    m2[:, 0] *= 3
    assert np.allclose(raw(m)["sharp"][3:-3], raw(m2)["sharp"][3:-3], atol=1e-9)
    still = raw(lamp_line([0, 0, 0]))["sharp"]
    assert np.isnan(still).all()                                           # acceleration below the floor: undefined


def test_pause_runs_exact():
    for length, n_expect in ((12, 0), (13, 13), (30, 30)):
        sp = np.full(100, 0.3)
        sp[20:20 + length] = 0.0
        assert C.pause_mask(sp).sum() == n_expect
    p = lamp_line([0.3, 0, 0])
    v = np.full(N, 0.3)
    v[100:200] = 0.0                                                       # 2 s standstill = tokens 4..7 entirely
    p[:, 0] = np.concatenate([[0], np.cumsum(v[1:]) / C.FS])
    r = raw(p)
    assert np.allclose(r["pause_prob"][5:7], 1.0) and np.allclose(r["activity"][5:7], 0.0)
    assert r["pause_prob"][12] == 0.0 and r["activity"][12] == 1.0
    assert raw(lamp_line([0, 0, 0]))["pause_prob"].min() == 1.0 and raw(lamp_line([0.3, 0, 0]))["activity"].min() == 1.0


def test_slots_ramp_exact():
    x = np.arange(C.TOK, dtype=float)
    s = C.slots(x)
    assert len(s) == 8 and abs(s.mean() - x.mean()) < 1e-12
    assert np.all(np.diff(s) > 0)
    assert np.allclose(C.slots(np.ones(C.TOK)), 1.0)


def test_token_locality_of_controls():
    p = tone(2.0)
    base = C.finalise(raw(p), NORM)
    p2 = p.copy()
    p2[1000, 0] += 0.5                                                     # last sample, 20 s: far from token 5 and its support
    other = C.finalise(raw(p2), NORM)
    for key in ("vigour", "height", "accent_mean", "pause_prob", "activity"):
        assert np.array_equal(base[key][:30], other[key][:30]), key


def test_lead_order():
    w = np.zeros((N, 5))
    for j, t0 in ((1, 100), (3, 106)):                                     # shoulder starts, wrist bend follows 6 samples (0.12 s) later
        w[t0:t0 + 30, j] = 50.0
    p90 = np.full(5, 40.0)
    ld = C.lead(w, p90)
    assert abs(np.nanmean(ld) - 0.12) < 1e-9
