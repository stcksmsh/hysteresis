"""WO35: V3 inverse kinematics known-behaviour tests. Run: python -m unittest test_v3_ik (body env)."""
import unittest

import numpy as np

import v3_ik as K

Q0 = K.CENTRE_POSE


def tool_of(q):
    pts, B = K.fk_batch(q[None])
    return pts[0, 5], B[0]


class IK(unittest.TestCase):
    def test_fk_matches_the_rig_points(self):
        import m3f_report as R
        q = np.array([[30.0, -50.0, 40.0, -20.0, 10.0]])
        self.assertTrue(np.allclose(K.fk_batch(q)[0], R.fk_points(q), atol=1e-12))

    def test_stationary_target_gives_zero_motion(self):
        p, Rt = tool_of(Q0)
        q = Q0.copy()
        for _ in range(20):
            q2 = K.solve_frame(q, p, Rt, K.PARAMS["iters"])
            self.assertLess(np.abs(q2 - q).max(), 1e-6)
            q = q2

    def test_one_centimetre_step_moves_the_joints_at_least_90_percent_of_the_exact_solution(self):
        p, Rt = tool_of(Q0)
        h = 1e-4
        Qp = np.vstack([Q0] + [Q0 + np.degrees(h) * np.eye(5)[j] for j in range(5)])
        J = (K.fk_batch(Qp)[0][1:, 5] - K.fk_batch(Qp)[0][0, 5]).T / h
        rng = np.random.default_rng(3)
        for _ in range(50):
            d = rng.normal(size=3)
            d /= np.linalg.norm(d)
            exact = np.linalg.pinv(J) @ (0.01 * d)
            q1 = K.solve_frame(Q0, p + 0.01 * d, Rt, 1, dict(K.PARAMS, w_o=0.0, w_c=0.0))
            self.assertGreaterEqual(np.linalg.norm(np.radians(q1 - Q0)) / np.linalg.norm(exact), 0.9 - 1e-6)

    def test_reachable_target_converges(self):
        q_true = np.array([20.0, -50.0, 50.0, 10.0, 0.0])
        p, Rt = tool_of(q_true)
        q = K.solve_frame(Q0, p, Rt, 60)
        self.assertLess(np.linalg.norm(tool_of(q)[0] - p), 0.002)

    def test_joint_limits_hold(self):
        p = np.array([0.0, 0.0, -0.5])                                                            # far below: the arm tries to fold into the column
        q = K.solve_frame(Q0, p, np.eye(3), 30)
        self.assertTrue((np.abs(q[1:4]) <= 109.5 + 1e-9).all())

    def test_unreachable_target_gives_bounded_motion_and_finite_error(self):
        p = np.array([2.0, 0.0, 0.5])
        q = K.solve_frame(Q0, p, np.eye(3), 3)
        self.assertTrue(np.isfinite(q).all())
        self.assertLess(np.linalg.norm(np.radians(q - Q0)), 3 * K.PARAMS['step_cap_rad'] + 1e-9)                # the trust region bounds the step

    def test_projection_clears_small_column_violations(self):
        import make_arm_v2p as P
        rng = np.random.default_rng(7)
        Q = np.concatenate([rng.uniform(-100, 100, (4000, 1)) * 0, rng.uniform(-100, 100, (4000, 3)), np.zeros((4000, 1))], 1)
        m = K.col_margin(Q)
        bad = Q[(m < 0) & (m > -0.04)][:200]
        self.assertGreater(len(bad), 50)
        ok = 0
        for q in bad:
            q2 = K.project_column(q.copy(), 10)
            self.assertGreaterEqual(float(K.col_margin(q2[None])[0]), float(K.col_margin(q[None])[0]) - 1e-9)          # never worse
            ok += int(float(K.col_margin(q2[None])[0]) >= -1e-3 and float(P.margins(q2[None])[0]) >= -1e-3)
        self.assertGreaterEqual(ok / len(bad), 0.85)                                                            # best effort; what it cannot clear is the guard's (7.51) job


if __name__ == "__main__":
    unittest.main()
