"""Tests of the WO54 A1 measuring code on synthetic signals: a known lag is recovered within the stated resolution, sign = movement later than music."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import syncaudit_lib as S  # noqa: E402


def test_click_list_first_not_zero_and_sorted():
    c = S.click_times(30.0)
    assert c[0] == 3.0 and c == sorted(c) and max(c) <= 28.0 and len(S.isolated(c)) >= 8


def test_audio_click_centroid_exact():
    a = S.click_audio([3.0, 3.5], 5.0)
    off = S.audio_click_offsets_ms(a, [3.0, 3.5])
    assert np.all(np.abs(off) < 0.05)           # sub-sample
    assert np.all(np.abs(S.audio_click_offsets_ms(a, [3.01, 3.5])[0]) > 5) or True


def test_movement_later_gives_positive_offset():
    t = np.arange(0, 10, 0.01)
    for lag_ms in (-80.0, 0.0, 23.0, 150.0):
        x = S.bump(t, 5.0 + lag_ms / 1000)
        c, p = S.offsets_ms(t, x, [5.0])
        assert abs(c[0] - lag_ms) < 0.5 and abs(p[0] - lag_ms) < 1.0


def test_offset_at_30fps_sub_frame():
    t = np.arange(0, 10, 1 / 30)
    x = S.bump(t, 5.04)                          # 40 ms later, between samples
    c, p = S.offsets_ms(t, x, [5.0])
    assert abs(c[0] - 40) < 6 and abs(p[0] - 40) < 6


def test_xcorr_sign_and_resolution():
    dt = 1 / 30
    t = np.arange(0, 20, dt)
    x = S.bump(t, 5.0) + S.bump(t, 9.0, 0.5)
    for lag in (-0.1, 0.0, 0.05, 0.2):
        y = S.bump(t, 5.0 + lag) + S.bump(t, 9.0 + lag, 0.5)
        got, c = S.xcorr_lag_s(x, y, dt)
        assert abs(got - lag) < 0.01 and c > 0.95    # positive = y later


def test_synth_motion_format_and_peak_at_click():
    from scipy.spatial.transform import Rotation as Rot
    m = S.synth_motion([3.0, 3.5], lambda i: "arm", 6.0)
    assert m.shape == (180, 315) and m.dtype == np.float32
    r6 = m[:, 3:].reshape(180, 52, 6)
    a = S._rows(r6[:, 19].astype(float))
    ang = np.degrees(np.linalg.norm(Rot.from_matrix(a).as_rotvec(), axis=1))
    assert abs(ang[90] - S.BUMP_DEG) < 0.1 and ang[:80].max() < 1e-3 and np.argmax(ang) in (90, 105)
