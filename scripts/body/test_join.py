"""WO44 tests (docs/JOIN_RULES.md section 6). Brain env: python -m pytest scripts/body/test_join.py"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.signal import welch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import join_lib as J  # noqa: E402

RUNB = Path("/secondary/hyst-data/body/t1a2/runB/best.pt")
needs_vq = pytest.mark.skipif(not RUNB.exists(), reason="frozen decoder weights absent")


def test_cut_and_rejoin_raw_identical():
    rng = np.random.default_rng(0)
    rows = np.cumsum(rng.normal(size=(51 * 10, 5)), 0)
    ch = np.stack([rows[50 * i:50 * i + 51] for i in range(10)])                 # chunks of one unbroken sequence (row 50 = next chunk's row 0)
    ref = rows[:500]
    assert np.allclose(J.concat_raw(ch)[:-1], ref, atol=1e-4)
    assert np.allclose(J.concat_ramp(ch)[:-1], ref, atol=1e-4)                   # zero jump -> ramp adds nothing


def test_ramp_removes_jump():
    a = np.zeros((2, 51, 5))
    a[1] += 7.0                                                                   # chunk 1 starts 7 deg off chunk 0's continuation
    r = J.concat_ramp(a)
    assert np.allclose(r[50], 0, atol=1e-5)                                       # chunk 1 row 0 now equals the continuation
    assert np.allclose(r[99], 7.0, atol=0.01) and np.all(np.diff(r[50:100, 0]) >= 0)


@pytest.fixture(scope="module")
def ctx():
    import t1a2_train as TR2
    import torch
    import t1b_t2 as T2
    torch.set_num_threads(1)
    vq = TR2.make("B")
    vq.load_state_dict(torch.load(RUNB))
    vq.eval()
    sd = np.asarray(json.loads(Path("/secondary/hyst-data/body/t1a/scale.json").read_text())["sd"], np.float32)
    return T2, vq, sd, T2.vocab()


def _tok(T2, n=120, seed=0):
    rng = np.random.default_rng(seed)
    return dict(c1=rng.integers(0, 1024, n), c2=rng.integers(0, 1024, n), v=rng.integers(0, 32, n), p=rng.integers(0, 256, (n, 2)))


@needs_vq
def test_blocks_equals_e1(ctx):
    T2, vq, sd, voc = ctx
    t = _tok(T2)
    e1, _ = T2.decode_rows(t, np.zeros(5), voc, vq, sd)
    assert np.array_equal(J.build_rows(t, np.zeros(5), voc, vq, sd, "blocks"), e1)


@needs_vq
def test_overlap_matches_blocks_away_from_borders(ctx):
    T2, vq, sd, voc = ctx
    t = _tok(T2)
    gb, go = (J.decode_gesture(t, voc, vq, sd, m) for m in ("blocks", "overlap"))
    ok = np.ones(len(gb), bool)
    for b in range(0, 6001, 1000):                                                 # block borders (2000, 4000) and overlap window edges (every 1000 rows); decoder reach is 24 rows
        ok[max(0, b - 60):b + 60] = False
    assert np.abs(gb[ok] - go[ok]).max() < 0.05


def _hf(g, fs=100.0):
    v = np.diff(g, axis=0) * fs
    tot = hi = 0.0
    for i in range(g.shape[1]):
        f, P = welch(v[:, i] - v[:, i].mean(), fs, window="hann", nperseg=500, detrend=False)
        tot += P[f > 0].sum()
        hi += P[f > 3].sum()
    return hi / tot


@needs_vq
def test_constant_tokens_overlap_adds_no_hf(ctx):
    T2, vq, sd, voc = ctx
    t = dict(c1=np.full(120, 7), c2=np.full(120, 3), v=np.full(120, 10), p=np.zeros((120, 2), int))
    a, b = (J.decode_gesture(t, voc, vq, sd, m) for m in ("blocks", "overlap"))
    ha, hb = _hf(a), _hf(b)
    assert hb <= ha * 1.01 + 1e-12, (ha, hb)
