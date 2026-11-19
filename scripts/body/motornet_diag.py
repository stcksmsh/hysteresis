"""WO29A diagnosis for the overseer (read-only: changes nothing in the network, settings or clips). Output: JSON on stdout.
(1) input drive Win u vs recurrent drive W r (per-unit std over the shown 12 s, mean over units): gain 1 and S01-S10;
(2) per joint p5-p95 range of the calibrated target, spring-damper output, realised angle: gain 1 and S01-S10;
(3) PR and per-joint peak frequency: S11, S12, gain 1 with zero input from a small random start (seed 29099, x0 = 0.01 N(0,1)).
"""
import json

import numpy as np

import dialstudy as D
import motornet as M

NW, NS = round(M.WARM_S / M.DT), round(M.SHOW_S / M.DT)


def run(c, u_fn, x0=None):
    g = M.gains(c)
    x = np.zeros(M.N) if x0 is None else x0.copy()
    W, Win, Wout = M.NET["W"], M.NET["Win"], M.NET["Wout"]
    Y, Rt, IN, REC = [], [], [], []
    for i in range(NW + NS + 1):
        r = np.tanh(g * x)
        u = Win @ u_fn(i * M.DT)
        Y.append(Wout @ r), Rt.append(r), IN.append(u), REC.append(W @ r)
        for _ in range(2):
            x = x + M.DT_NET / M.TAU * (-x + W @ np.tanh(g * x) + u)
    return [np.array(a) for a in (Y, Rt, IN, REC)]


def rng595(a):
    return (np.percentile(a, 95, axis=0) - np.percentile(a, 5, axis=0)).round(2).tolist()


def pr(r):
    lam = np.clip(np.linalg.eigvalsh(np.cov(r.T)), 0, None)
    return float(lam.sum() ** 2 / (lam ** 2).sum())


def peak_hz(a, hz):
    X = a - a.mean(0)
    P = np.abs(np.fft.rfft(X * np.hanning(len(X))[:, None], axis=0)) ** 2
    f = np.fft.rfftfreq(len(X), 1 / hz)
    return [round(float(f[np.argmax(np.where(f > 0.1, P[:, j], 0))]), 3) for j in range(a.shape[1])]


def one(c, u_fn, x0=None):
    Y, Rt, IN, REC = run(c, u_fn, x0)
    s = slice(NW, None)
    G = M.to_targets(Y)
    S = M.spinal(G)
    q50, _ = M.simulate_goals(S)
    shown = lambda a: a[NW:]
    out = dict(
        input_drive_std=float(IN[s].std(0).mean()), recurrent_drive_std=float(REC[s].std(0).mean()),
        target_p5p95=rng595(shown(G)), spinal_p5p95=rng595(shown(S)), realised_p5p95=rng595(q50),
        pr=pr(shown(Rt)[::2]), peak_hz_target=peak_hz(shown(G)[::2], 50), peak_hz_realised=peak_hz(q50, 50))
    return out


if __name__ == "__main__":
    st = json.loads(open("/secondary/hyst-data/body/motornet_toy/settings.json").read())
    res = {"gain1": one(np.ones(M.NCTRL), M.silent_input)}
    for s in st["settings"]:
        if s["id"] in [f"S{k:02d}" for k in range(1, 11)]:
            res[s["id"]] = one(np.array(s["values"]), M.silent_input)
    for sid, v in (("S11", M.C_LO), ("S12", M.C_HI)):
        res[sid] = one(np.full(M.NCTRL, v), M.silent_input)
    x0 = 0.01 * np.random.default_rng(29099).standard_normal(M.N)
    res["gain1_zero_input"] = one(np.ones(M.NCTRL), lambda t: np.zeros(3), x0)
    print(json.dumps(res, indent=1))
