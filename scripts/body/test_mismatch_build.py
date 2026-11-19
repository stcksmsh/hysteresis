"""Tests of the pure pair-building logic (docs/MISMATCH_RULES.md). No audio, no renderer."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mismatch_build as M  # noqa: E402


def test_tempo_within_5_percent():
    assert M.tempo_ok(100, 105) and M.tempo_ok(100, 95) and not M.tempo_ok(100, 105.1) and not M.tempo_ok(100, 94.9)


def test_excerpt_rule():
    assert M.excerpt_ok(0.2, 0.2, 10.0, 60.0) and not M.excerpt_ok(0.19, 0.2, 10.0, 60.0)
    assert not M.excerpt_ok(0.5, 0.2, 9.9, 60.0) and not M.excerpt_ok(0.5, 0.2, 40.1, 60.0) and M.excerpt_ok(0.5, 0.2, 40.0, 60.0)


def test_shift_range_and_fit():
    for seed in range(300):
        r = M.shift_foil(random.Random(seed), 30.0, 100.0)
        o, flag = r
        assert 2.0 <= abs(o) <= 6.0 and not flag and 10 <= 30 + o and 30 + o + 10 <= 90
    # near the Q3 edge the sign is flipped to stay inside
    for seed in range(100):
        o, flag = M.shift_foil(random.Random(seed), 11.0, 100.0)
        assert o > 0 and not flag
    # no fit inside the Q3 window but inside the song: flagged
    o, flag = M.shift_foil(random.Random(1), 5.0, 25.0)
    assert flag and 0 <= 5 + o and 5 + o + 10 <= 25
    assert M.shift_foil(random.Random(1), 0.0, 10.0) is None


def test_assign_totals_for_many_seeds():
    for seed in range(50):
        a = M.assign(random.Random(seed))
        flat = [x for v in a.values() for x in v]
        assert len(flat) == 20 and sum(v == "V1" for v, _ in flat) == 10 and sum(k == "shifted" for _, k in flat) == 10
        for ds, n in M.QUOTA.items():
            assert len(a[ds]) == n and 3 <= sum(k == "shifted" for _, k in a[ds]) <= 4 and 3 <= sum(v == "V1" for v, _ in a[ds]) <= 4


def test_order_balance_and_repeats():
    for seed in range(100):
        rng = random.Random(seed)
        kinds = ["shifted"] * 10 + ["different_song"] * 10
        rng.shuffle(kinds)
        side, rep = M.draw_sides_and_repeats(rng, kinds)
        assert side.count("first") == 10 and side.count("second") == 10
        for k in ("shifted", "different_song"):
            ss = [s for s, x in zip(side, kinds) if x == k]
            assert ss.count("first") == 5 and ss.count("second") == 5
        assert len(rep) == 5 and len(set(rep)) == 5
        assert sum(kinds[i] == "shifted" for i in rep) >= 2 and sum(kinds[i] == "different_song" for i in rep) >= 2


def test_gap_geometry():
    assert M.GAP_START == 441000 and M.SECOND_START == 507150 and M.TOTAL == 948150 and abs(M.TOTAL / M.SR_OUT - 21.5) < 1e-9
