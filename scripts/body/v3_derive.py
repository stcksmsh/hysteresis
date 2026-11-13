"""WO35: derive the IK numbers of rules note (m) from their stated rules (probe on synthetic targets only; no V3 clip is run). Run (body env): python -u v3_derive.py
Rules:
  d_total = sigma_c^2 / 9: sigma_c = the smallest singular value of the 3 x 5 position Jacobian at the workspace-centre pose, so a 1 cm target step moves the joints by >= 90 % of the exact
            (undamped) solution in the weakest direction there: sigma^2 / (sigma^2 + d) >= 0.9.
  lam    = 1 % of the arm's reach (0.0069), the DLS damping that keeps the solve stable near singular poses; lam^2 = (0.01 * 0.69)^2.
  mu     = d_total - lam^2 (the per-frame joint-change penalty takes the rest of d_total, so a stationary target, whose previous solution is already the minimiser, gives zero motion).
  step cap = 2 x (1 cm / sigma_c) rad per iteration = 0.35 rad (a trust region that never binds on a 1 cm step in the weakest direction, where the exact joint move is 1 cm / sigma_c = 0.18 rad).
  w_o    = 0.05 m/rad: a 1 rad orientation error costs as much as a 5 cm position error (position first).   w_c = 1: a column violation of d metres costs as a d metre position error.
  N      = the smallest iteration count for which, on 1,000 random target steps of 1 cm and of 5 cm (5 cm = the largest per-frame end-point step expected: a hand at 5 m/s at 100 Hz; only the steps whose target lies inside the arm's reach, 0.66 m from the shoulder, since beyond it the optimum is a singular full extension where convergence is slow by nature) from the centre pose
           (warm start = centre pose), the end point after N iterations is within 1 mm of the end point after 50 iterations. (The 1 cm probe alone gave N = 1; the 5 cm probe was added before any clip was run.)
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v3_ik as K  # noqa: E402


def pos_jacobian(q):
    h = 1e-4
    Qp = np.vstack([q] + [q + np.degrees(h) * np.eye(5)[j] for j in range(5)])
    pts, _ = K.fk_batch(Qp)
    return (pts[1:, 5] - pts[0, 5]).T / h


def derive():
    q0 = K.CENTRE_POSE
    sig = np.linalg.svd(pos_jacobian(q0), compute_uv=False)
    sigma_c = float(sig.min())
    d_total = sigma_c ** 2 / 9
    lam2 = (0.01 * K.REACH_M) ** 2
    mu = d_total - lam2
    assert mu > 0
    cap = 2 * 0.01 / sigma_c
    prm = dict(K.PARAMS, lam2=lam2, mu=mu, step_cap_rad=cap)
    rng = np.random.default_rng(35001)
    p0 = K.fk_batch(q0[None])[0][0, 5]
    R0 = K.fk_batch(q0[None])[1][0]
    dirs = rng.normal(size=(1000, 3))
    dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
    frac = []
    diffs = {n: [] for n in range(1, 11)}
    diffs5 = {n: [] for n in range(1, 11)}
    n5 = 0
    for d in dirs:
        pt = p0 + 0.01 * d
        ref = K.solve_frame(q0, pt, R0, 50, prm)
        pr = K.fk_batch(ref[None])[0][0, 5]
        for n in range(1, 11):
            qn = K.solve_frame(q0, pt, R0, n, prm)
            diffs[n].append(np.linalg.norm(K.fk_batch(qn[None])[0][0, 5] - pr))
        pt5 = p0 + 0.05 * d
        if np.linalg.norm(pt5 - np.array([0, 0, 0.08])) > 0.66:                                    # only targets inside the arm's reach (0.69 m from the shoulder, with a 3 cm margin)
            continue
        n5 += 1
        pr5 = K.fk_batch(K.solve_frame(q0, pt5, R0, 50, prm)[None])[0][0, 5]
        for n in range(1, 11):
            diffs5[n].append(np.linalg.norm(K.fk_batch(K.solve_frame(q0, pt5, R0, n, prm)[None])[0][0, 5] - pr5))
        # response of one iteration along the step: fraction of the exact (min-norm, undamped) position move
        J = pos_jacobian(q0)
        dq_exact = np.linalg.pinv(J) @ (0.01 * d)
        q1 = K.solve_frame(q0, pt, R0, 1, dict(prm, w_o=0.0, w_c=0.0))
        frac.append(float(np.linalg.norm(np.radians(q1 - q0)) / np.linalg.norm(dq_exact)))
    maxdiff = {n: float(np.max(v)) for n, v in diffs.items()}
    maxdiff5 = {n: float(np.max(v)) for n, v in diffs5.items()}
    N = next(n for n in range(1, 11) if maxdiff[n] < 1e-3 and maxdiff5[n] < 1e-3)
    out = dict(sigma_singular_values_centre_pose=sig.tolist(), sigma_c=sigma_c, d_total=d_total, lam=0.01 * K.REACH_M, lam2=lam2, mu=mu, w_o=0.05, w_c=1.0, step_cap_rad=cap, iters=N, reach_m=K.REACH_M, probes_5cm_reachable=n5,
               probe_max_endpoint_diff_to_50_iterations_m_1cm=maxdiff, probe_max_endpoint_diff_to_50_iterations_m_5cm=maxdiff5, one_iteration_response_fraction_min_median=[float(np.min(frac)), float(np.median(frac))])
    return out


if __name__ == "__main__":
    o = derive()
    print(json.dumps(o, indent=1))
    Path("/secondary/hyst-data/body/retarget_look/v3/ik_params.json").write_text(json.dumps(o, indent=1))
