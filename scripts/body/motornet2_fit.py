"""WO30B silent fit of the two-population network (rules: docs/MOTORNET2_RULES.md), gain 1 silent only; no setting is sampled or viewed here.
Steps as BRAIN_SPEC 7.45.10 / 7.47.6: input scale per population (fixed-point), calibrate at +-60 %, limiter shares at spinal 3 Hz (1.5 Hz rule), extent.
Writes motornet_toy2/motornet2_fit.json."""
import json

import numpy as np

import dialstudy as D
import motornet as M
import motornet2 as M2

NW, NS = round(M2.WARM_S / M2.DT), round(M2.SHOW_S / M2.DT)
OUT = "/secondary/hyst-data/body/motornet_toy2/motornet2_fit.json"


def drives():
    """per population: mean-over-units std over the shown part of Win u and of W r, gain 1 silent"""
    g = M2.gains(np.ones(M2.NCTRL))
    x = np.zeros(M2.N)
    W, Win = M2.NET["W"], M2.win_scaled()
    k = M2.DT_NET / M2.TAU
    IN, REC = [], []
    for i in range(NW + NS + 1):
        r = np.tanh(g * x)
        u = Win @ M2.silent_input(i * M2.DT)
        IN.append(u), REC.append(W @ r)
        for _ in range(2):
            x = x + k * (-x + W @ np.tanh(g * x) + u)
    IN, REC = np.array(IN)[NW:], np.array(REC)[NW:]
    return [(float(IN[:, p].std(0).mean()), float(REC[:, p].std(0).mean())) for p in (M2.SLOW, M2.FAST)]


def shares():
    Y, _ = M2.run_net(np.ones(M2.NCTRL), M2.silent_input, NW + NS)
    G = M2.to_targets(Y)
    S = M.spinal(G)
    L = M.limiter_out(S)
    t, s, l = M2.p595(G[NW:]), M2.p595(S[NW:]), M2.p595(L[NW:])
    return dict(target=t.tolist(), spinal=s.tolist(), limiter_out=l.tolist(), share=(l / t).tolist())


def recal(cal, f):
    M2.CAL_FRAC, M.SPINAL_F, M2._CAL = cal, f, None


res = dict(block_rho_raw=M2.NET["block_rho_raw"], full_matrix_radius=M2.NET["full_rho"],
           subsets_per_population=[[int(M2.NET["mask"][k, M2.SLOW].sum()), int(M2.NET["mask"][k, M2.FAST].sum())] for k in range(M2.NCTRL)])
s, hist = np.array([1.0, 1.0]), []
for it in range(30):
    M2.INPUT_S = s.copy()
    d = drives()
    ratio = [i / r for i, r in d]
    hist.append(dict(s=s.tolist(), input=[x[0] for x in d], recurrent=[x[1] for x in d], ratio=ratio))
    if all(abs(x - 0.25) <= 0.005 for x in ratio):       # tighter than the 2 % allowed
        break
    s = s * 0.25 / np.array(ratio)
res["input_scale"] = dict(s_slow=float(s[0]), s_fast=float(s[1]), iterations=len(hist), history=hist)
recal(M2.CAL_FRAC, 3.0)
res["limiter_spinal3"] = shares()
low = [j for j in (0, 1) if res["limiter_spinal3"]["share"][j] < 0.5]
res["spinal_1p5_needed"] = bool(low)
if low:
    recal(0.6, 1.5)
    res["limiter_spinal1p5"] = shares()
res["spinal_f"] = M.SPINAL_F
q, r, g = M2.run_setting(np.ones(M2.NCTRL))
import m3f_report as R
h = R.fk_points(q)[:, 5]
res["extent_gain1_m"] = float(M2.p595(h).max())
res["realised_p5p95_deg"] = M2.p595(q).tolist()
res["gain1_gates"] = g
res["gain1_pr"] = M2.pr_per_population(r)
res["calibration_mean_sd"] = [a.tolist() for a in M2.calibration()]
res["drives_final"] = [dict(input=a, recurrent=b) for a, b in drives()]
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "input_scale"}, indent=1))
print("s", s, "iterations", len(hist), "ratio", hist[-1]["ratio"])
