"""WO28A hand-set dial study: underlying movement, five dials, plain-MuJoCo v2f stepping, glitch gates. Rules: docs/DIALSTUDY_RULES.md.

    python -I dialstudy.py gen OUTDIR        # all Set A + B clips: CSV + dials json + gate values (no video)
"""
import json
import math
import sys
from pathlib import Path

import mujoco
import numpy as np
from scipy.signal import welch

import make_arm as MA
import make_arm_v2 as V2
import m3f_report as R

SEED, NPOSE, BPM = 28011, 12, 100
BEAT = 60.0 / BPM
INTERVAL = 2 * BEAT                      # one move per two beats
CLIP_S, PRE_S, HZ = 12.0, 1.5, 50
CLIP_MARGIN, CTC = 0.5, 0.006
AMP = np.array([30.0, 12.0, 16.0, 16.0, 45.0])
POST = {-1: np.array([0, -45, 60, -70, 0.]), 0: np.array([0, -60, 30, -15, 0.]), 1: np.array([0, -80, 10, -20, 0.])}
LAGMAX = np.array([0, 0.10, 0.35, 0.55, 0.70])      # beats
Z = np.random.default_rng(SEED).uniform(-1, 1, (NPOSE, 5))
LO = np.array([-np.inf if r is None else r[0] for r in MA.RANGE_DEG])
HI = np.array([np.inf if r is None else r[1] for r in MA.RANGE_DEG])
LIM_V = np.array([v for v, _ in MA.LIMITS])
LIM_A = np.array([a for _, a in MA.LIMITS])
NEUTRAL = dict(vigour=0.0, stiffness=0.0, roundness=0.0, lag=0.0, posture=0.0)


def pw(d, a, b, c):
    """piecewise linear through (-1, a), (0, b), (1, c)"""
    return b + (b - a) * d if d < 0 else b + (c - b) * d


def params(dials, hold=1.0, zeta=None):
    """dials (five values in [-1, 1]) -> physical parameters."""
    d = {**NEUTRAL, **dials}
    return dict(scale=pw(d["vigour"], 0.35, 1.0, 1.7), share=pw(d["vigour"], 0.95, 0.70, 0.45) * hold,
                kp_scale=0.45 ** (-d["stiffness"]) if d["stiffness"] < 0 else 1.0 * 2.5 ** d["stiffness"],
                zeta=zeta if zeta is not None else pw(d["stiffness"], 0.3, 1.5, 1.0),
                rho=(d["roundness"] + 1) / 2, lag01=(d["lag"] + 1) / 2,
                centre=POST[0] + (POST[1] - POST[0]) * d["posture"] if d["posture"] >= 0 else POST[0] + (POST[0] - POST[-1]) * d["posture"])


def poses(p):
    return p["centre"] + Z * AMP * p["scale"]


def _ease(u, k):
    """trapezoid position profile with ease fraction k at each end, u in [0, 1]"""
    u = np.clip(u, 0, 1)
    v = 1.0 / (1.0 - k)                                  # cruise speed so the integral is 1
    return np.where(u < k, v * u * u / (2 * k), np.where(u < 1 - k, v * (u - k / 2), 1 - v * (1 - u) ** 2 / (2 * k)))


def target_fn(p):
    """-> f(t) giving the 5 joint targets (deg) at time t (scalar), t = 0 is the clip start; before 0 holds pose 0."""
    P = poses(p)
    k = np.arange(NPOSE)
    t_arr = (k - 1) * INTERVAL + p["share"] * INTERVAL                         # arrival of pose k; move k (pose k-1 -> k) leaves at (k-1)*INTERVAL, move 1 at t = 0
    off = p["lag01"] * LAGMAX * BEAT

    def spline_val(tj, j):
        """C1 Catmull-Rom through (t_arr, P[:, j]) (non-uniform tangents)"""
        i = np.clip(np.searchsorted(t_arr, tj, side="right") - 1, 0, NPOSE - 2)
        t0, t1 = t_arr[i], t_arr[i + 1]
        m = lambda a: (P[min(a + 1, NPOSE - 1), j] - P[max(a - 1, 0), j]) / (t_arr[min(a + 1, NPOSE - 1)] - t_arr[max(a - 1, 0)])
        h = t1 - t0
        s = (np.clip(tj, t0, t1) - t0) / h
        h00, h10, h01, h11 = 2 * s ** 3 - 3 * s ** 2 + 1, s ** 3 - 2 * s ** 2 + s, -2 * s ** 3 + 3 * s ** 2, s ** 3 - s ** 2
        return h00 * P[i, j] + h10 * h * m(i) + h01 * P[i + 1, j] + h11 * h * m(i + 1)

    def ang_val(tj, j):
        n = int(np.clip(np.floor(tj / INTERVAL) + 1, 1, NPOSE - 1))
        u = (tj - (n - 1) * INTERVAL) / (p["share"] * INTERVAL)
        return P[n - 1, j] + (P[n, j] - P[n - 1, j]) * float(_ease(np.array(u), 0.15))

    def f(t):
        out = np.empty(5)
        for j in range(5):
            tj = t - off[j]
            a = ang_val(tj, j) if tj > 0 else P[0, j]
            tj = max(tj, t_arr[0])
            if p["rho"] > 0:
                tj2 = min(max(tj, 0.0), t_arr[-1])
                a = (1 - p["rho"]) * a + p["rho"] * spline_val(tj2, j)
            out[j] = a
        return out
    return f


# ---------------------------------------------------------------------------------------------------------------- simulation
_KV_I = None


def _inertia():
    global _KV_I
    if _KV_I is None:
        m = mujoco.MjModel.from_xml_string(MA.build_xml())
        d = mujoco.MjData(m)
        mujoco.mj_forward(m, d)
        M = np.zeros((m.nv, m.nv))
        mujoco.mj_fullM(m, d, M)
        _KV_I = np.diag(M).copy()
    return _KV_I


def make_model(kp_scale, zeta):
    kp = MA.KP * kp_scale
    kv = 2 * zeta * np.sqrt(kp * _inertia())
    m = mujoco.MjModel.from_xml_string(V2.xml_v2(kv=list(kv), condim=1, table_z=V2.RAISED_PLANE_Z))
    m.geom_solref[:] = [CTC, 1.0]
    m.actuator_gainprm[:, 0] = kp
    m.actuator_biasprm[:, 1] = -kp
    m.actuator_biasprm[:, 2] = -kv
    return m


def simulate(f, kp_scale, zeta):
    """-> q50 (601, 5) deg realised at 50 Hz from the clip start; contacts (count of substeps with any contact, pre-roll included)."""
    m = make_model(kp_scale, zeta)
    d = mujoco.MjData(m)
    q0 = f(0.0)
    d.qpos[:] = np.radians(q0)
    d.ctrl[:] = np.radians(q0)
    mujoco.mj_forward(m, d)
    tgt, tv = q0.copy(), np.zeros(5)
    lo_t, hi_t = LO + CLIP_MARGIN, HI - CLIP_MARGIN
    lo_r, hi_r = np.radians(LO), np.radians(HI)
    dt, sub = 0.01, 5
    n_pre, n_clip = round(PRE_S / dt), round(CLIP_S / dt)
    rows, contacts = [], 0
    for i in range(-n_pre, n_clip + 1):
        goal = np.clip(f(max(i * dt, 0.0)), lo_t, hi_t)
        e = goal - tgt
        v_des = np.sign(e) * np.minimum(LIM_V, np.sqrt(2 * LIM_A * np.abs(e) + 1e-12))
        v_des = np.where(np.abs(v_des) * dt > np.abs(e), e / dt, v_des)
        tv = np.clip(tv + np.clip(v_des - tv, -LIM_A * dt, LIM_A * dt), -LIM_V, LIM_V)
        tgt = np.clip(tgt + tv * dt, lo_t, hi_t)
        d.ctrl[:] = np.radians(tgt)
        for _ in range(sub):
            mujoco.mj_step(m, d)
            qc = np.clip(d.qpos, lo_r, hi_r)
            d.qvel[:] = np.where(qc != d.qpos, 0.0, d.qvel)
            d.qpos[:] = qc
            contacts += int(d.ncon > 0)
        if i >= 0 and i % 2 == 0:
            rows.append(np.degrees(d.qpos))
    return np.array(rows), contacts


# ---------------------------------------------------------------------------------------------------------------- gates
def gate_values(q50, contacts):
    P = R.fk_points(q50)
    floor = float(np.minimum((P[:, 1:5, 2] - R.FLOOR_M).min(1), P[:, 5, 2] - R.FLOOR_M - R.DISC_M).min())
    near = np.zeros(len(q50), bool)
    stop = 0
    for j in (1, 2, 3):
        n = (q50[:, j] < MA.RANGE_DEG[j][0] + 3) | (q50[:, j] > MA.RANGE_DEG[j][1] - 3)
        run = best = 0
        for x in n:
            run = run + 1 if x else 0
            best = max(best, run)
        stop = max(stop, best)
    v = np.diff(q50, axis=0) * HZ
    hf = R.hf_share_q50(q50, f_cut=8.0)
    rev = []
    for j in range(5):
        s = np.where(np.abs(v[:, j]) > 1.0, np.sign(v[:, j]), 0)
        s = s[s != 0]
        rev.append(float((np.diff(s) != 0).sum() / CLIP_S))
    sp = np.abs(v) / LIM_V
    ac = np.abs(q50[2:] - 2 * q50[1:-1] + q50[:-2]) * HZ * HZ / LIM_A
    return dict(floor_m=floor, contact_substeps=int(contacts), endstop_samples=int(stop), hf_share=float(hf), reversals_max=max(rev),
                speed_ratio=float(sp.max()), accel_ratio=float(ac.max()), finite=bool(np.isfinite(q50).all()))


def judge(g, thr):
    ok = dict(clearance=g["floor_m"] >= 0, contact=g["contact_substeps"] == 0, endstop=g["endstop_samples"] < 6,
              hf=g["hf_share"] <= thr["hf_share"], reversals=g["reversals_max"] <= thr["reversals_max"],
              limits=g["speed_ratio"] <= 1.05 and g["accel_ratio"] <= 1.05 and g["finite"])
    return all(ok.values()), ok


def thresholds(g_neutral):
    return dict(hf_share=max(3 * g_neutral["hf_share"], 0.01), reversals_max=max(3 * g_neutral["reversals_max"], 6.0))


# ---------------------------------------------------------------------------------------------------------------- clip definitions
def clip_defs():
    L = lambda d, lv: dict(zip(("vigour", "stiffness", "roundness", "lag", "posture"), (0,) * 5)) | {d: lv}
    defs = [dict(id="A_neutral", set="A", intent=dict(kind="neutral"), dials={})]
    for dial in ("vigour", "stiffness", "roundness", "lag", "posture"):
        for lv, name in ((-1, "low"), (1, "high")):
            defs.append(dict(id=f"A_{dial}_{name}", set="A", intent=dict(kind="dial", dial=dial, level=name), dials={dial: lv}))
    pre = {"heavy": dict(vigour=-1, stiffness=1, roundness=1, lag=1, posture=-1),
           "angry": dict(vigour=1, stiffness=1, roundness=-1, lag=-1, posture=1),
           "tense": dict(vigour=-0.6, stiffness=1, roundness=-1, lag=-1, posture=1, hold=0.55),
           "calm": dict(vigour=-1, stiffness=-1, roundness=1, lag=0.5, posture=0),
           "light": dict(vigour=0.6, stiffness=-1, roundness=1, lag=0, posture=1, zeta=0.2)}
    for name, dv in pre.items():
        defs.append(dict(id=f"B_{name}", set="B", intent=dict(kind="preset", preset=name), dials=dv))
    return defs


def run_clip(c, overrides=None):
    """-> (q50, gates, effective dials). `overrides`: feasibility adjustments {key: value} merged over the clip's dials (logged by the caller)."""
    dv = {**c["dials"], **(overrides or {})}
    hold, zeta = dv.pop("hold", 1.0), dv.pop("zeta", None)
    p = params({k: v for k, v in dv.items()}, hold=hold, zeta=zeta)
    q50, contacts = simulate(target_fn(p), p["kp_scale"], p["zeta"])
    return q50, gate_values(q50, contacts), dict(**{k: dv.get(k, 0.0) for k in NEUTRAL}, hold=hold, zeta=p["zeta"], kp_scale=p["kp_scale"],
                                                  scale=p["scale"], share=p["share"], centre=[float(x) for x in p["centre"]])


def gen(out, overrides=None):
    """Run every Set A/B clip: write <id>.csv, <id>.json (dials, gates). overrides: {clip id: {key: value}} (feasibility adjustments, logged by caller)."""
    import arm_sim
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    overrides = overrides or {}
    defs = clip_defs()
    res = {}
    for c in defs:
        q, g, eff = run_clip(c, overrides.get(c["id"]))
        res[c["id"]] = (c, q, g, eff)
    thr = thresholds(res["A_neutral"][2])
    for cid, (c, q, g, eff) in res.items():
        ok, parts = judge(g, thr)
        (out / f"{cid}.csv").write_text(arm_sim.csv_text(q, HZ, name=cid))
        (out / f"{cid}.json").write_text(json.dumps(dict(id=cid, set=c["set"], intent=c["intent"], dials=eff, gates=dict(passed=ok, parts=parts, values=g, thresholds=thr),
                                                         overrides=(overrides or {}).get(cid, {})), indent=1))
        print(f"{cid:22s} {'PASS' if ok else 'FAIL'} floor {g['floor_m']:+.3f} stop {g['endstop_samples']:3d} hf {g['hf_share']:.4f} rev {g['reversals_max']:.1f} "
              f"v {g['speed_ratio']:.2f} a {g['accel_ratio']:.2f} con {g['contact_substeps']}  {[k for k, v in parts.items() if not v]}")
    return thr


if __name__ == "__main__":
    gen(sys.argv[2], json.loads(sys.argv[3]) if len(sys.argv) > 3 else None)
