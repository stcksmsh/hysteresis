"""WO43 control representation (BRAIN_SPEC 7.73 Step 0a). Rules: docs/CONTROLS_RULES.md. numpy + scipy only; lamp positions come from the caller (no data access, no mujoco).

    raw_window(q50, lamp)         -> raw per-token measures of one 20 s window (40 tokens, 25 samples each at 50 Hz)
    fit_norm(raws)                -> constants fitted on FineDance train tokens
    finalise(raw, norm)           -> the six controls per token
"""
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, filtfilt

FS, TOK, NTOK, NSLOT = 50, 25, 40, 8
EPS_V = 0.01                      # log offset, deg/s for joints and m/s for the lamp
Z_LO, Z_HI = 0.11, 0.77           # usable workspace height (m): floor clearance gate, straight-up reach
SHARP_HZ, ACC_FLOOR = 3.0, 0.05   # sharpness cutoff (Hz), minimum lamp acceleration RMS (m/s^2)
PAUSE_V, PAUSE_RUN = 0.05, 13     # pause: lamp speed < 0.05 m/s for >= 13 samples (> 0.25 s)
DIR_MIN = 0.02                    # m/s, below it the direction is the zero vector
SMOOTH = 5                        # accent smoothing box, samples
PROX, DIST = (0, 1), (3, 4)       # movement lead: base yaw, shoulder | wrist bend, wrist roll
ONSET_FRAC, REST_FRAC, REST_N, PAIR_N = 0.25, 0.125, 10, 25


def _grad(x):
    return np.gradient(x, axis=0) * FS


def slots(x):
    """(25,) samples of a token -> (8,) area-weighted means over 62.5 ms (3.125 samples) sub-slots"""
    cs = np.concatenate([[0.0], np.cumsum(x)])
    f = np.interp(np.arange(NSLOT + 1) * TOK / NSLOT, np.arange(TOK + 1), cs)
    return np.diff(f) / (TOK / NSLOT)


def pause_mask(speed):
    """True inside runs of >= PAUSE_RUN consecutive samples with speed < PAUSE_V"""
    low = np.concatenate([[0], (speed < PAUSE_V).astype(np.int8), [0]])
    d = np.diff(low)
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    m = np.zeros(len(speed), bool)
    for a, b in zip(st, en):
        if b - a >= PAUSE_RUN:
            m[a:b] = True
    return m


def onsets(x, p90):
    """sample indices where |w| crosses 0.25 p90 upward after >= REST_N samples below 0.125 p90"""
    th, lo = ONSET_FRAC * p90, REST_FRAC * p90
    out = []
    for i in range(REST_N, len(x)):
        if x[i - 1] < th <= x[i] and (x[i - REST_N:i] < lo).all():
            out.append(i)
    return np.array(out, int)


def lead(w, p90):
    """w (N, 5) deg/s -> (NTOK,) mean distal-minus-proximal onset lead (s) of the pairs whose proximal onset is in the token, NaN if none"""
    ons = {j: onsets(np.abs(w[:, j]), p90[j]) for j in range(5)}
    prox = np.sort(np.concatenate([ons[j] for j in PROX]))
    dist = np.concatenate([ons[j] for j in DIST])
    acc = [[] for _ in range(NTOK)]
    if len(prox):
        for d in dist:
            i = int(np.argmin(np.abs(prox - d)))
            if abs(int(prox[i]) - int(d)) <= PAIR_N and prox[i] // TOK < NTOK:
                acc[prox[i] // TOK].append((d - prox[i]) / FS)
    return np.array([np.mean(a) if a else np.nan for a in acc])


def raw_window(q50, lamp, p90=None):
    """q50 (1001, 5) deg, lamp (1001, 3) m -> dict of raw per-token arrays (no constants applied except p90 for the optional lead)"""
    n = NTOK * TOK
    w, v = _grad(q50), _grad(lamp)
    a = _grad(v)
    j = _grad(a)
    speed = np.linalg.norm(v, axis=1)
    amag, jmag = np.linalg.norm(a, axis=1), np.linalg.norm(j, axis=1)
    sa = uniform_filter1d(amag, SMOOTH, mode="reflect")
    sj = uniform_filter1d(jmag, SMOOTH, mode="reflect")
    b, c = butter(2, SHARP_HZ / (FS / 2), "high")
    ahp = filtfilt(b, c, a, axis=0)
    pm = pause_mask(speed)
    r = dict(vj=np.zeros(NTOK), vl=np.zeros(NTOK), vjoint=np.zeros((NTOK, 5)), z_mean=np.zeros(NTOK), a_slots=np.zeros((NTOK, NSLOT)), j_slots=np.zeros((NTOK, NSLOT)),
             sharp=np.full(NTOK, np.nan), acc_rms=np.zeros(NTOK), dir=np.zeros((NTOK, 3)), dir_ok=np.zeros(NTOK, np.int8), pause_prob=np.zeros(NTOK), activity=np.zeros(NTOK))
    for k in range(NTOK):
        s = slice(k * TOK, (k + 1) * TOK)
        r["vj"][k] = np.sqrt((w[s] ** 2).mean())
        r["vl"][k] = np.sqrt((speed[s] ** 2).mean())
        r["vjoint"][k] = np.sqrt((w[s] ** 2).mean(0))
        r["z_mean"][k] = lamp[s, 2].mean()
        r["a_slots"][k], r["j_slots"][k] = slots(sa[s]), slots(sj[s])
        e_tot = (a[s] ** 2).sum()
        r["acc_rms"][k] = np.sqrt(e_tot / TOK)
        if r["acc_rms"][k] >= ACC_FLOOR:
            r["sharp"][k] = (ahp[s] ** 2).sum() / e_tot
        d = v[s].mean(0)
        nd = np.linalg.norm(d)
        if nd >= DIR_MIN:
            r["dir"][k], r["dir_ok"][k] = d / nd, 1
        r["pause_prob"][k] = pm[s].mean()
        r["activity"][k] = (speed[s] >= PAUSE_V).mean()
    r["lead"] = lead(w, p90) if p90 is not None else np.full(NTOK, np.nan)
    r["_samples"] = dict(amag=amag[:n], jmag=jmag[:n], absw=np.abs(w[:n]))
    return r


def fit_norm(raws):
    """FineDance train raws (list of raw_window dicts) -> constants (json-able dict). p90 per joint is for the movement lead only."""
    cat = lambda k: np.concatenate([r[k] for r in raws])
    out = {}
    z = []
    for name, eps in (("vj", EPS_V), ("vl", EPS_V)):
        l = np.log(cat(name) + eps)
        med = float(np.median(l))
        mad = float(1.4826 * np.median(np.abs(l - med)))
        out[name] = dict(median=med, mad=mad)
        z.append((l - med) / mad)
    cov = np.cov(np.stack(z))
    ev, evec = np.linalg.eigh(cov)
    pc = evec[:, -1] * (1 if evec[:, -1].sum() > 0 else -1)
    out["vigour"] = dict(loadings=pc.tolist(), sd=float(np.sqrt(ev[-1])), eigenvalues=ev.tolist())
    am = np.concatenate([r["_samples"]["amag"] for r in raws])
    jm = np.concatenate([r["_samples"]["jmag"] for r in raws])
    out["accent"] = dict(A=float(np.percentile(am, 95)), J=float(np.percentile(jm, 95)))
    out["p90_abs_w"] = np.percentile(np.concatenate([r["_samples"]["absw"] for r in raws]), 90, axis=0).tolist()
    return out


def finalise(r, norm):
    """raw_window dict + constants -> the controls per token (arrays with leading NTOK axis)"""
    zs = [(np.log(r[k] + EPS_V) - norm[k]["median"]) / norm[k]["mad"] for k in ("vj", "vl")]
    vig = (zs[0] * norm["vigour"]["loadings"][0] + zs[1] * norm["vigour"]["loadings"][1]) / norm["vigour"]["sd"]
    u = r["a_slots"] / norm["accent"]["A"] + r["j_slots"] / norm["accent"]["J"]
    mean_u = u.mean(1)
    return dict(vigour=vig, vj_z=zs[0], vl_z=zs[1], vj=r["vj"], vl=r["vl"], vjoint=r["vjoint"],
                height=np.clip((r["z_mean"] - Z_LO) / (Z_HI - Z_LO), 0, 1), z_mean=r["z_mean"],
                accent_slots=u, accent_mean=mean_u, accent_peak=np.where(mean_u > 0, u.max(1) / np.maximum(mean_u, 1e-12), np.nan),
                sharp=r["sharp"], dir=r["dir"], dir_ok=r["dir_ok"], pause_prob=r["pause_prob"], activity=r["activity"], lead=r["lead"], acc_rms=r["acc_rms"])
