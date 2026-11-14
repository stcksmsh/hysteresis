"""WO37 T0 chain (body env): one dancer's rotations -> 4 copies -> whole-sequence targets, posture/gesture, per-window gates. Rules: docs/T0_RULES.md sections 3, 4, 6."""
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lowpass_cutoff as LC  # noqa: E402
import make_arm_v2p as P  # noqa: E402
import motornet as M  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_limiter as FX  # noqa: E402
import retarget_run as RR  # noqa: E402
import t0_lib as T  # noqa: E402

CUT = {"V1": 2.50, "V2": 5.75}                                           # lowpass/cutoffs.json, reused not recomputed
COPIES = ("V1", "V2", "V1m", "V2m")
MARGIN = 60                                                               # spline margin (frames) around a window


def stage1(rot, copy):
    """-> (yraw, yf): command rows at 30 fps referenced at frame 0, and the zero-phase low-passed rows"""
    var = copy[:2]
    y = RT.to_commands(RT.referenced(T.angles_of(rot, var), 0), var)
    return y, LC.lowpass(y, CUT[var])


def target(yf):
    """whole sequence: cubic to 100 Hz on [0, (T30 - 1) / 30], guard -> (target (T100, 5), guard share)"""
    tt = np.arange(T.t100(len(yf))) / 100.0
    return P.guard(CubicSpline(np.arange(len(yf)) / T.FPS, yf, axis=0)(tt))


def window_rows(yraw, yf, start_s):
    """pre-H1 rows of one window incl. the 1.5 s pre-roll: shift yaw and roll to the window start (rules 6), margin slice, spline -> G0 (pre-guard), (nw + 2001, 5)"""
    i0 = round(start_s * T.FPS)
    sh = np.zeros(5)
    sh[[0, 4]] = (yraw[i0] - yraw[0])[[0, 4]]
    lo, hi = i0 - int(T.PRE_S * T.FPS) - MARGIN, i0 + int(T.WIN_S * T.FPS) + MARGIN
    seg = yf[max(lo, 0):hi + 1] - sh
    if lo < 0:
        seg = np.concatenate([np.repeat(seg[:1], -lo, 0), seg])
    return RT.to_100hz(seg, start_s - T.PRE_S - lo / T.FPS, T.WIN_S + T.PRE_S)


def gate_window(yraw, yf, start_s):
    """the full chain of lowpass_run.run_clip: guard, spinal (H1), limiter, servo, v2p, gates at 1.25 -> dict(passed, parts, guard_share, G (pre-H1 rows after pre-roll), q50)"""
    RR.patch_gates()
    G, gshare = P.guard(window_rows(yraw, yf, start_s))
    q50, contacts = FX.simulate_goals(M.spinal(G))
    g = RR.gates_v2p(q50, contacts, gshare)
    return dict(passed=g["passed"], parts=g["parts"], guard_share=gshare, G=G[round(T.PRE_S * 100):], q50=q50)


PARTS = None


def process(rot, trans, copy, fps_ok=True, gate=True):
    """-> dict of arrays for one copy of one dancer (targets, posture, gesture, window table). rot: dict of 30 fps rotations (mirrored already for m copies)"""
    global PARTS
    yraw, yf = stage1(rot, copy)
    tg, gs = target(yf)
    p, g = T.posture_gesture(tg)
    nw = T.n_windows(len(yf))
    res = dict(targets=tg.astype(np.float32), posture=p.astype(np.float32), gesture=g.astype(np.float32), guard_share_seq=gs, n_win=nw)
    rows, ok, parts = [], [], None
    for i in range(nw if gate else 0):
        w = gate_window(yraw, yf, i * T.WIN_S)
        parts = list(w["parts"])
        ok.append(w["passed"])
        rows.append([bool(w["parts"][k]) for k in parts])
    res.update(win_pass=np.array(ok, bool), win_part_names=np.array(parts or [], str), win_parts=np.array(rows, bool).reshape(len(ok), len(parts or [])))
    return res
