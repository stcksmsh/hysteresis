"""WO29A re-run steps (i)-(iv) of BRAIN_SPEC 7.45.10, gain 1 silent only. Writes motornet_fit.json; no setting is sampled or viewed here."""
import json

import numpy as np

import dialstudy as D
import motornet as M

NW, NS = round(M.WARM_S / M.DT), round(M.SHOW_S / M.DT)
OUT = "/secondary/hyst-data/body/motornet_toy/motornet_fit.json"


def drives():
    """mean-over-units std over the shown 12 s of Win u and of W r, gain 1 silent (same stepping as run_net)"""
    c = np.ones(M.NCTRL)
    g = M.gains(c)
    x = np.zeros(M.N)
    W, Win = M.NET["W"], M.NET["Win"] * M.INPUT_S
    IN, REC = [], []
    for i in range(NW + NS + 1):
        r = np.tanh(g * x)
        u = Win @ M.silent_input(i * M.DT)
        IN.append(u), REC.append(W @ r)
        for _ in range(2):
            x = x + M.DT_NET / M.TAU * (-x + W @ np.tanh(g * x) + u)
    IN, REC = np.array(IN)[NW:], np.array(REC)[NW:]
    return float(IN.std(0).mean()), float(REC.std(0).mean())


def p595(a):
    return np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)


def shares():
    Y, _ = M.run_net(np.ones(M.NCTRL), M.silent_input, NW + NS)
    G = M.to_targets(Y)
    S = M.spinal(G)
    L = M.limiter_out(S)
    t, s, l = p595(G[NW:]), p595(S[NW:]), p595(L[NW:])
    return dict(target=t.tolist(), spinal=s.tolist(), limiter_out=l.tolist(), share=(l / t).tolist())


def extent():
    q, r, g = M.run_setting(np.ones(M.NCTRL))
    import m3f_report as R
    h = R.fk_points(q)[:, 5]
    return float(p595(h).max()), p595(q).tolist()


def recal(cal, f):
    M.CAL_FRAC, M.SPINAL_F, M._CAL = cal, f, None


res = {}
# (i) input scale
s, hist = 1.0, []
for it in range(30):
    M.INPUT_S = s
    i, r = drives()
    hist.append(dict(s=s, input=i, recurrent=r, ratio=i / r))
    if abs(i / r - 0.25) <= 0.005:        # tighter than the 2 % allowed
        break
    s *= 0.25 * r / i
res["input_scale"] = dict(s=s, history=hist)
# (ii) calibrate at +-60 %, spinal 3 Hz
recal(0.6, 3.0)
res["step_iii_spinal3"] = shares()
low = [j for j in (0, 1) if res["step_iii_spinal3"]["share"][j] < 0.5]
res["spinal_1p5_needed"] = bool(low)
if low:
    recal(0.6, 1.5)
    res["step_iii_spinal1p5"] = shares()
res["spinal_f"] = M.SPINAL_F
# (iv) extent at +-60 %
ext, rng = extent()
res["extent_at_0p6"] = dict(extent_m=ext, realised_p5p95=rng)
if ext >= 0.10:
    res["cal_frac"], res["min_extent_m"] = 0.6, 0.10
else:
    recal(1.0, M.SPINAL_F)
    ext1, rng1 = extent()
    res["extent_at_1p0"] = dict(extent_m=ext1, realised_p5p95=rng1)
    res["cal_frac"], res["min_extent_m"] = 1.0, 0.05
res["calibration_mean_sd"] = [a.tolist() for a in M.calibration()]
res["drives_final"] = dict(zip(("input", "recurrent"), drives()))
res["shares_final"] = shares()
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "input_scale"}, indent=1))
print("s", s, "iterations", len(hist), "ratio", hist[-1]["ratio"])
