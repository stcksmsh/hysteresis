import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t1b_t2_lib as L


def test_ident_repeat():
    assert L.ident_repeat_share([1, 2, 1, 1], [5, 5, 5, 6]) == 0.25
    assert L.ident_repeat_share([1, 1, 1], [2, 2, 2]) == 2 / 3


def test_triples():
    assert L.triples_per_min([1, 1, 2], [1, 1, 1], [0, 0, 0], [[3], [3], [3]], 0.5) == 4.0


def test_approx_repeat_zero_for_repeated_chunks():
    g = np.tile(np.random.default_rng(0).normal(size=(1, 50, 5)), (6, 1, 1))
    assert L.approx_repeat(g) == 0.0


def test_selfsim_corr_identical_is_one_and_independent_is_low():
    r = np.random.default_rng(1)
    x = np.repeat(r.normal(size=(10, 6)), 6, 0) + 0.01 * r.normal(size=(60, 6))
    assert L.selfsim_corr(x, x, 4) > 0.999
    y = r.normal(size=(60, 6))
    assert abs(L.selfsim_corr(x, y, 4)) < 0.3


def test_beat_alignment_perfect_and_off():
    hz = 50
    t = np.arange(0, 20, 1 / hz)
    sp = 1 + np.cos(2 * np.pi * 2 * t)                      # minima every 0.5 s at 0.25, 0.75, ...
    beats = np.arange(0.25, 20, 0.5)
    assert L.beat_alignment(sp, hz, beats) > 0.95
    assert L.beat_alignment(sp, hz, beats + 0.25) < 0.2


def test_frozen_and_flips():
    sp = np.r_[np.ones(100), np.zeros(200), np.ones(50)]
    assert L.frozen_longest_s(sp, 50, 0.05) == 4.0
    t = np.arange(0, 10, 0.02)
    h = np.stack([np.sin(2 * np.pi * t), 0 * t, 0 * t], 1)
    j, d = L.endpoint_jerk_dirchanges(h, 50)
    assert 1.0 < d < 3.0 and j > 0


def test_bootstrap_includes_zero_for_noise_and_not_for_shift():
    r = np.random.default_rng(2)
    m, lo, hi = L.bootstrap_mean_ci(r.normal(size=40))
    assert lo < 0 < hi
    m, lo, hi = L.bootstrap_mean_ci(r.normal(size=40) + 2)
    assert lo > 0


def test_viterbi_prefers_smooth_path():
    unary = np.zeros((4, 2))
    pos = np.array([[0.0, 10.0]] * 4)
    trans = lambda i: np.abs(pos[i][:, None] - pos[i + 1][None])
    assert L.viterbi(unary, trans) in ([0, 0, 0, 0], [1, 1, 1, 1])


def test_events_and_response():
    r = np.random.default_rng(3)
    ear = r.normal(size=(3000, 44))
    ear[1000, 40] = 50
    on, up = L.detect_events(ear)
    assert 1000 in on
    sp = np.r_[np.zeros(100), np.ones(100)]
    assert L.event_response(sp, 100, [10000 / 100], 1.0, 1.0) == 1.0
