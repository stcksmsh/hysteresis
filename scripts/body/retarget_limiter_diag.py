"""WO32D step A: where does the command limiter's own shoulder output exceed the acceleration limit? Report only (no fix here).

For the 145 candidates x 2 variants of the v2p stream: the limiter output (motornet.limiter_out, 100 Hz, guarded command) measured exactly as the gate measures realised acceleration
(rows at 50 Hz, second difference x 50^2 / limit), per joint; the worst case is dissected frame by frame. Run (body env): python -u retarget_limiter_diag.py
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retarget_limiter as FX  # noqa: E402
import retarget_run as RR  # noqa: E402


def gate_acc(rows50, LIM_A):
    return np.abs(rows50[2:] - 2 * rows50[1:-1] + rows50[:-2]).max(0) * 50 * 50 / LIM_A


def main():
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    D, M = RR.patch_gates()
    cat = RR.catalogue()
    order = [str(g) for g in np.random.default_rng(RR.SEED).permutation(sorted({v[0] for v in cat.values()}))]
    nw = round(RR.PRE_S * 100)
    res = []
    for k in range(145):
        c = RR.pick(k, order, cat)
        for var in ("V1", "V2"):
            v = RR.human(c["seq"])[0 if var == "V1" else 1]
            G0 = RT.to_100hz(RT.to_commands(RT.referenced(v, round(c["start_s"] * RT.FPS)), var), c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
            G, _ = P.guard(G0)
            L = M.limiter_out(G)
            a = gate_acc(L[nw::2], D.LIM_A)
            a_fix = gate_acc(FX.limiter_out(G)[nw::2], D.LIM_A)
            res.append((float(a[1]), k, var, a.tolist(), float(a_fix[1]), a_fix.tolist()))
    over = [r for r in res if r[0] > 1.0]
    print("limiter-output shoulder accel (gate measure) > 1.0 x limit:", len(over), "of", len(res), "; > 1.05:", sum(1 for r in res if r[0] > 1.05),
          "by variant", {v: sum(1 for r in res if r[2] == v and r[0] > 1.05) for v in ("V1", "V2")})
    print("other joints > 1.05:", {j: sum(1 for r in res if r[3][i] > 1.05) for i, j in enumerate(RR.JN)})
    print("AFTER the fix (retarget_limiter): shoulder > 1.0:", sum(1 for r in res if r[4] > 1.0 + 1e-6), "; any joint > 1.0:", sum(1 for r in res if max(r[5]) > 1.0 + 1e-6),
          "; max over all joints and candidates", max(max(r[5]) for r in res))
    worst = max(res, key=lambda r: r[0])
    print("worst before", worst[0], "after (same candidate)", worst[4], "cand", worst[1], worst[2])
    _, k, var = worst[:3]
    c = RR.pick(k, order, cat)
    v = RR.human(c["seq"])[0 if var == "V1" else 1]
    G0 = RT.to_100hz(RT.to_commands(RT.referenced(v, round(c["start_s"] * RT.FPS)), var), c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
    G, _ = P.guard(G0)
    L = M.limiter_out(G)
    L50 = L[nw::2]
    acc = (L50[2:, 1] - 2 * L50[1:-1, 1] + L50[:-2, 1]) * 2500 / D.LIM_A[1]
    i = int(np.abs(acc).argmax())
    j = nw + 2 * (i + 1)                                               # 100 Hz row index of the middle sample
    lo_t, hi_t = D.LO[1] + D.CLIP_MARGIN, D.HI[1] - D.CLIP_MARGIN
    print("range clip", lo_t, hi_t, "worst frame 100 Hz row", j, "gate accel", acc[i])
    for r in range(j - 6, j + 7):
        print(r, "goal %.2f clipped %.2f out %.3f  step %.4f deg/frame  accel100 %.2fx" % (G[r, 1], np.clip(G[r, 1], lo_t, hi_t), L[r, 1], L[r, 1] - L[r - 1, 1],
              (L[r, 1] - 2 * L[r - 1, 1] + L[r - 2, 1]) * 1e4 / D.LIM_A[1]))
    json.dump(dict(over_1_0=len(over), over_1_05=sum(1 for r in res if r[0] > 1.05), worst=dict(ratio=worst[0], cand=k, variant=var), all=[(r[0], r[1], r[2], r[4]) for r in res]),
              open("/secondary/hyst-data/body/retarget_look/limiter_diag.json", "w"))


if __name__ == "__main__":
    main()
