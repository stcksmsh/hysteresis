"""WO37 tests of t0_lib (body env): python -m pytest scripts/body/test_t0_lib.py"""
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation as Rot

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t0_lib as T  # noqa: E402


def rand_rot(n=40, seed=1):
    r = np.random.default_rng(seed)
    out = {j: Rot.from_rotvec(r.normal(0, .5, (n, 3))).as_matrix() for j in T.ROT_JOINTS}
    return out, r.normal(size=(n, 3))


def test_mirror_twice_identity():
    rot, tr = rand_rot()
    r2, t2 = T.mirror(*T.mirror(rot, tr))
    assert max(np.abs(r2[j] - rot[j]).max() for j in rot) < 1e-12 and np.abs(t2 - tr).max() == 0


def test_mirrored_wrists_are_reflected():
    rot, tr = rand_rot()
    mr, _ = T.mirror(rot, tr)
    R0, L0 = T.fk_synthetic(rot)
    R1, L1 = T.fk_synthetic(mr)
    assert np.abs(L1 - R0 * [-1, 1, 1]).max() < 1e-12 and np.abs(R1 - L0 * [-1, 1, 1]).max() < 1e-12


def test_split_grouping_and_seed():
    units = [dict(key=f"s{i}", name=f"Song {i // 2}", hash=f"h{i}") for i in range(40)] + [dict(key="x", name="other", hash="h3")]
    g = T.make_groups(units)
    assert any({"s2", "s3", "x"} <= set(a) for a in g) and len(g) == 20        # name pairs merged, x joins through the hash
    sp = T.split_groups(g)
    assert sp == T.split_groups(g) and sorted(set(sp.values())) == ["test", "train", "validation"]
    assert sum(v == "test" for v in sp.values()) == round(.15 * 20) and sum(v == "validation" for v in sp.values()) == 2
    assert len(sp) == len(g)


def test_weights():
    w = T.hours_of_dancers([("a", 2.0), ("b", 1.0)])
    assert abs(w["a"] * 2.0 + w["b"] * 1.0 - 2.0) < 1e-12                       # the group's total weight = its longest dancer
    assert T.hours_of_dancers([("a", 1.0)]) == {"a": 1.0} and T.hours_of_dancers([("a", 1.0), ("b", 0.0)]) == {"a": 1.0, "b": 1.0}


def test_windows():
    assert T.n_windows(601) == 1 and T.n_windows(600) == 0 and T.n_windows(1801) == 3 and T.n_windows(1800) == 2
    assert T.n_tokens(30) == 2 and T.t100(31) == 101


def test_posture_gesture_sum_and_lowpass():
    t = np.arange(6000) / 100.0
    x = np.stack([np.sin(2 * np.pi * .05 * t) + np.sin(2 * np.pi * 3 * t)] * 5, 1)
    p, g = T.posture_gesture(x)
    assert np.abs(p + g - x).max() < 1e-12 and np.abs(p[500:-500, 0] - np.sin(2 * np.pi * .05 * t[500:-500])).max() < .05


def test_token_pooling_synthetic():
    n_tok, n10 = 4, 20
    ear = np.tile(np.arange(n_tok * 50)[:, None] / 50.0, (1, 44))
    h = np.tile(np.arange(n10)[:, None].astype(float), (1, 32))
    sur = np.tile(np.arange(n10)[:, None].astype(float), (1, 4))
    sur[:7] = np.nan                                                    # token 0 has no surprisal stamp, token 1 has stamps 7, 8, 9
    y = np.zeros((n_tok, 8))
    y[:, 2] = np.arange(n_tok)
    tok, m = T.pool_tokens(ear, h, sur, np.arange(n10, dtype=float), np.ones(n10), y, n_tok)
    assert tok.shape == (n_tok, 86) and len(T.TOKEN_COLS) == 86
    assert m.tolist() == [1, 0, 0, 0] and np.isnan(tok[0, 76]) and T.standardise_tokens(tok, dict(mean=[0.0] * 86, sd=[1.0] * 86))[0, 76] == 0.0
    assert abs(tok[1, 76] - np.mean([7, 8, 9])) < 1e-6 and abs(tok[2, 44] - 12) < 1e-6      # token 2 holds stamps 10..14
    assert abs(tok[1, 0] - (50 + 99) / 2 / 50) < 1e-6
    assert abs(tok[2, 84] - 2.0) < 1e-6 and abs(tok[2, 82] - 1.5) < 1e-6                     # mid 1.25 s = block 2's stamp; start 1.0 s halfway between blocks 1 and 2


def test_norm_roundtrip():
    r = np.random.default_rng(0)
    tm = [(r.normal(3, 2, (50, 86)).astype(np.float32), np.zeros(50, np.uint8))]
    nm = T.fit_token_norm(tm)
    z = T.standardise_tokens(tm[0][0], nm)
    assert np.abs(z[:, 50].mean()) < 1e-5 and z.max() <= 3.0
