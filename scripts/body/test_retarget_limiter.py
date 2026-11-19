"""WO32D step A: the limiter's output acceleration, measured as the gate measures realised acceleration (50 Hz rows, second difference x 2500 / limit), must stay within the limit.
The round-1 limiter fails this near the range edge (the test documents it); the fixed one must not. Run: python -m unittest test_retarget_limiter (body env)."""
import unittest

import numpy as np

import dialstudy as D
import motornet as M
import retarget_limiter as L


TOL = 1.0 + 1e-6                       # the gate's own measure of the limiter output must not exceed the limit


def gate_acc(rows100):
    r = rows100[::2]
    return np.abs(r[2:] - 2 * r[1:-1] + r[:-2]).max(0) * 2500 / D.LIM_A


def reversal_goals(speed=120.0, edge=-108.0, dwell=0.2):
    """the shoulder goal runs toward the lower range edge at `speed` deg/s, waits, then turns round at the same speed while the held target is still moving (what a retargeted
    dancer does); the other joints stay still"""
    n = 1200
    G = np.tile(np.array([0.0, -60.0, 30.0, -15.0, 0.0]), (n, 1))
    t = np.arange(n) / 100.0
    t1 = (edge + 60) / -speed
    G[:, 1] = np.where(t < t1, -60 - speed * t, np.where(t < t1 + dwell, edge, edge + speed * (t - t1 - dwell)))
    return G


class Limiter(unittest.TestCase):
    def test_round1_limiter_breaks_the_acceleration_limit_at_the_range_edge(self):
        a = gate_acc(M.limiter_out(reversal_goals()))
        assert a[1] > 2.0, a


    def test_fixed_limiter_holds_the_acceleration_limit_at_the_range_edge(self):
        a = gate_acc(L.limiter_out(reversal_goals()))
        assert (a <= TOL).all(), a


    def test_fixed_limiter_random_goals_stay_within_limits_and_range(self):
        rng = np.random.default_rng(1)
        for _ in range(20):
            G = np.cumsum(rng.normal(0, 14, (800, 5)), 0) * np.array([1, 0.5, 0.5, 0.5, 1]) + np.array([0, -60, 30, -15, 0])
            out = L.limiter_out(G)
            a = gate_acc(out)
            assert (a <= TOL).all(), a
            v = np.abs(np.diff(out, axis=0)).max(0) * 100 / D.LIM_V
            assert (v <= 1.0 + 1e-6).all(), v
            assert (out[:, 1:4] <= D.HI[1:4] - D.CLIP_MARGIN + 1e-9).all() and (out[:, 1:4] >= D.LO[1:4] + D.CLIP_MARGIN - 1e-9).all()


    def test_fixed_limiter_equals_round1_away_from_the_range(self):
        G = reversal_goals()
        G[:, 1] = np.clip(G[:, 1], -80, 80)                                    # never near the edge: the two limiters must agree
        assert np.allclose(L.limiter_out(G), M.limiter_out(G), atol=1e-9)


if __name__ == "__main__":
    unittest.main()
