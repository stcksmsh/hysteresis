"""WO21: where does pass2's identical 0.741 m/s peak hand speed come from? Diagnostic only; body env (jax). Imports k5p2_eval / m3f_jax / cpg; edits none, changes no default.

    s0_ceiling.py roll    --out DIR [--songs a,b,...|--n N] [--variant base|amp|c|freq]
    s0_ceiling.py analytic --out DIR            (no jax needed beyond import of make_arm/m3f_report; brain env also works)

roll: the pass2 policy (k5p2 best.pkl), the same continuous argmax rollout as s0_roll.py but with cfg["diag"] on (same physics, adds the generator state per 10 ms step: centre, amp, freq, phase, the oscillator
target and the held target). For each song, at the step of the 50 Hz central-difference peak hand speed (the Stage 0 definition), per joint: the generator centre / amplitude / slewed frequency against their bounds,
the frequency actually used after the generator's own speed and acceleration caps (cpg.py), which of F_MAX / speed cap / acceleration cap binds, the joint speed against the speed limit, and each joint's
contribution to the hand velocity. Over the whole song: the share of steps at each bound. Variants (diagnostic only; module constants patched in this process before the functions are traced):
  base: as trained;  amp: AMP_CAP_CONTINUOUS x 1.5 (base yaw and roll amplitude cap 180 -> 270 deg);  c: smooth-u scale c 0.5 -> 0.35;  freq: F_MAX x 1.5 (4 -> 6 Hz).
analytic: the largest hand speed the arm can reach with the joint speeds at a given fraction of the speed limits (LIMITS), over all poses and all sign choices (vertices of the joint-velocity box).
"""
import argparse
import itertools
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

import cpg
import make_arm as MA
import m3f_report as R

HZ = 50
V = np.array([v for v, _ in MA.LIMITS])
A = np.array([a for _, a in MA.LIMITS])
JN = ("base_yaw", "shoulder", "elbow", "wrist_bend", "wrist_roll")
W = 2 * math.pi * (1 + cpg.COUPLING)


def hand_pos(q):
    return R.fk_points(np.asarray(q, float))[:, 5]


def jacobian(q, h=1e-3):
    """q (N, 5) deg -> (N, 3, 5) m per deg... returned in m per rad."""
    q = np.asarray(q, float)
    out = np.zeros((len(q), 3, 5))
    for j in range(5):
        dq = np.zeros(5)
        dq[j] = h
        out[:, :, j] = (hand_pos(q + dq) - hand_pos(q - dq)) / (2 * math.radians(h))
    return out


def peak(rows50):
    h = hand_pos(rows50)
    v = np.linalg.norm(np.gradient(h, axis=0) * HZ, axis=1)
    return int(v.argmax()), float(v.max())


def f_caps(amp):
    """The generator's frequency caps for amplitudes amp (5,) deg (cpg.py / m3d_jax.cpg_step): speed cap and acceleration cap, Hz."""
    am = np.maximum(amp, 1e-9)
    return cpg.SPEED_SHARE * V / am / W, np.sqrt(cpg.ACC_SHARE * A / am) / W


def at_peak(g, k):
    """g: dict of per-step arrays (T100, 5) (centre, amp_raw, freq, tgt_held, tgt_osc, qdeg); k: the 100 Hz step of the peak -> per joint record."""
    centre, amp_raw, freq = g["centre"][k], g["amp"][k], g["freq"][k]
    a_max = np.where(cpg.BEND, cpg.HI - np.abs(centre), cpg.AMP_CAP_CONTINUOUS)
    amp = np.maximum(np.where(cpg.BEND, np.minimum(amp_raw, a_max), amp_raw), 0.0)
    fs, fa = f_caps(amp)
    f_used = np.minimum(freq, np.minimum(fs, fa))
    bind = ["F_MAX" if freq[j] >= 0.999 * cpg.F_MAX and freq[j] <= min(fs[j], fa[j]) else ("slewed_freq" if freq[j] <= min(fs[j], fa[j]) else ("speed_cap" if fs[j] <= fa[j] else "acc_cap")) for j in range(5)]
    osc_speed = amp * 2 * math.pi * f_used                                        # deg/s, the oscillation alone (no coupling)
    qd = (g["q"][min(k + 1, len(g["q"]) - 1)] - g["q"][max(k - 1, 0)]) * 50.0   # deg/s central difference of the realised joints
    tv = (g["tgt"][min(k + 1, len(g["tgt"]) - 1)] - g["tgt"][max(k - 1, 0)]) * 50.0
    J = jacobian(g["q"][k:k + 1])[0]
    contrib = J * np.radians(qd)[None]                                           # (3, 5) m/s per joint
    return {j: {"centre_deg": float(centre[i]), "amp_deg": float(amp[i]), "amp_bound_deg": float(a_max[i]), "amp_share_of_bound": float(amp[i] / a_max[i]),
                "freq_slewed_hz": float(freq[i]), "freq_used_hz": float(f_used[i]), "f_max_hz": cpg.F_MAX, "cap_speed_hz": float(fs[i]), "cap_acc_hz": float(fa[i]), "binding": bind[i],
                "osc_speed_deg_s": float(osc_speed[i]), "speed_limit_deg_s": float(V[i]), "osc_speed_share_of_limit": float(osc_speed[i] / V[i]),
                "joint_speed_deg_s": float(abs(qd[i])), "joint_speed_share_of_limit": float(abs(qd[i]) / V[i]), "held_target_speed_deg_s": float(abs(tv[i])),
                "hand_velocity_contribution_m_s": float(np.linalg.norm(contrib[:, i]))} for i, j in enumerate(JN)}


def shares(g):
    """Whole-song share of steps (per joint) with the used frequency at F_MAX / on the speed cap / on the acceleration cap, amplitude at >= 98 % of its bound, centre within 2 % of the smooth-u limits."""
    centre, amp_raw, freq = g["centre"], g["amp"], g["freq"]
    a_max = np.where(cpg.BEND, cpg.HI - np.abs(centre), cpg.AMP_CAP_CONTINUOUS)
    amp = np.maximum(np.where(cpg.BEND, np.minimum(amp_raw, a_max), amp_raw), 0.0)
    am = np.maximum(amp, 1e-9)
    fs, fa = cpg.SPEED_SHARE * V / am / W, np.sqrt(cpg.ACC_SHARE * A / am) / W
    f_used = np.minimum(freq, np.minimum(fs, fa))
    on_s, on_a = (fs <= fa) & (fs < freq), (fa < fs) & (fa < freq)
    return {j: {"speed_cap": float(on_s[:, i].mean()), "acc_cap": float(on_a[:, i].mean()), "freq_at_fmax": float((freq[:, i] >= 0.98 * cpg.F_MAX).mean()),
                "amp_at_bound": float((amp[:, i] >= 0.98 * a_max[:, i]).mean()), "mean_amp_share": float((amp[:, i] / a_max[:, i]).mean()), "mean_freq_used_hz": float(f_used[:, i].mean()),
                "centre_min": float(centre[:, i].min()), "centre_max": float(centre[:, i].max())} for i, j in enumerate(JN)}


# ---------------------------------------------------------------------------------------------------------------- analytic
SIGNS = np.array(list(itertools.product((-1.0, 1.0), repeat=5)))


def speed_at(q, frac):
    """q (N, 5) deg -> (N,) the largest hand speed with every |qdot_j| = frac_j * V_j (any signs): max over the 32 vertices."""
    J = jacobian(q)                                                              # (N, 3, 5), m/rad
    vd = np.radians(V * frac)[None, :] * SIGNS                                   # (32, 5) rad/s
    v = np.einsum("nij,sj->nsi", J, vd)
    return np.linalg.norm(v, axis=2).max(1)


def box_max(frac, lo, hi, n=60000, seed=0, refine=40):
    """Largest hand speed over poses in the box [lo, hi] (deg, per joint) at joint speeds frac * V: random search then a local refinement of the best poses."""
    rng = np.random.default_rng(seed)
    q = rng.uniform(lo, hi, (n, 5))
    s = speed_at(q, frac)
    top = q[np.argsort(-s)[:refine]]
    best, bq = s.max(), q[s.argmax()]
    for sc in (10.0, 3.0, 1.0, 0.3):
        for _ in range(8):
            c = np.clip(np.repeat(top, 8, 0) + rng.normal(0, sc, (len(top) * 8, 5)), lo, hi)
            sc_ = speed_at(c, frac)
            i = sc_.argmax()
            if sc_[i] > best:
                best, bq = sc_[i], c[i]
            top = c[np.argsort(-sc_)[:refine]]
    return float(best), bq.tolist()


def run_analytic(a):
    out = {}
    full_lo = np.array([-180.0, -110, -110, -110, -180.0])
    full_hi = -full_lo
    # the box of poses the pass2 policy actually visits: 0.5 / 99.5 percentiles of every joint over the saved Stage 0 rollouts
    qs = []
    for f in sorted(Path("/secondary/hyst-data/body/s0/pass2").glob("*.npz"))[:120]:
        qs.append(np.load(f)["rows50"][::10])
    qs = np.concatenate(qs)
    vis_lo, vis_hi = np.percentile(qs, 0.5, 0), np.percentile(qs, 99.5, 0)
    out["visited_box_deg"] = {"lo": vis_lo.tolist(), "hi": vis_hi.tolist()}
    for frac_name, frac in (("0.64 V (oscillation alone, no coupling)", 0.64), ("0.80 V (oscillation with coupling at its maximum)", 0.8), ("1.00 V (the target limiter, LIM_V)", 1.0)):
        r = {}
        for bx_name, lo, hi in (("all poses in the joint ranges", full_lo, full_hi), ("poses pass2 visits (0.5-99.5 %)", vis_lo, vis_hi)):
            best, bq = box_max(np.full(5, frac), lo, hi)
            r[bx_name] = {"max_hand_speed_m_s": best, "pose_deg": bq}
        out[frac_name] = r
    # single-joint reading: hand speed from base yaw alone at its limit, for the largest horizontal radius
    out["base_yaw_alone"] = {}
    for frac in (0.64, 0.8, 1.0):
        qs_ = np.random.default_rng(1).uniform(full_lo, full_hi, (40000, 5))
        r_h = np.linalg.norm(hand_pos(qs_)[:, :2], axis=1)
        out["base_yaw_alone"][str(frac)] = {"max_horizontal_radius_m": float(r_h.max()), "max_speed_m_s": float(r_h.max() * math.radians(V[0] * frac))}
    Path(a.out, "analytic.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: (v if k.startswith("base") else {b: c["max_hand_speed_m_s"] for b, c in v.items()}) for k, v in out.items() if k != "visited_box_deg"}, indent=1))


# ---------------------------------------------------------------------------------------------------------------- rolling
def smooth_u_c(c):
    import jax.numpy as jnp
    return lambda s: 0.5 + 0.5 * jnp.tanh((s - 0.5) / c)


def run_roll(a):
    import jax
    import jax.numpy as jnp
    import k5p2_eval as EV
    import k5_video_roll as VR
    import m3d
    import m3f_jax as F
    import s0_roll
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    keep_old = (F.smooth_u, cpg.AMP_CAP_CONTINUOUS, cpg.F_MAX)
    if a.variant == "amp":
        cpg.AMP_CAP_CONTINUOUS = 1.5 * cpg.AMP_CAP_CONTINUOUS
    elif a.variant == "c":
        F.smooth_u = smooth_u_c(0.35)
    elif a.variant == "freq":
        cpg.F_MAX = 1.5 * cpg.F_MAX
    songs = a.songs.split(",") if a.songs else s0_roll.check_songs()[::max(1, len(s0_roll.check_songs()) // a.n)][:a.n]
    C = EV.M.load_cb()
    P, stats, cfg = EV.load_policy(a.policy)
    cfg = {**cfg, "diag": True}
    fns = EV.make_fns(C, cfg)
    res = {}
    for name in songs:
        f = out / f"{a.variant}_{name}.json"
        if f.exists():
            res[name] = json.loads(f.read_text())
            continue
        t0 = time.time()
        z = np.load(Path(a.lanes) / f"{name}.npz")
        inps, _ = EV.episode_inputs(z["y"], z["phi_end"], z["omega"])
        padded, nb = EV.pad_chunks(inps, VR.CB)
        q0 = m3d.start_poses(1, VR.START_SEED)
        carry = jax.vmap(lambda q: F.init_carry(cfg, q, C))(jnp.asarray(q0))
        keep = ("q", "dg_centre", "dg_amp", "dg_freq", "dg_tgt", "pi")
        outs = []
        for c0 in range(0, padded["x"].shape[1], VR.CB):
            carry, o = fns["hard"]["argmax"](P, carry, m3d.take(padded, c0, c0 + VR.CB))
            outs.append({k: np.asarray(o[k])[0] for k in keep})
        r = {k: np.concatenate([o[k] for o in outs], 0)[:nb] for k in keep}
        g = {"q": r["q"].reshape(-1, 5), "centre": r["dg_centre"].reshape(-1, 5), "amp": r["dg_amp"].reshape(-1, 5), "freq": r["dg_freq"].reshape(-1, 5), "tgt": r["dg_tgt"].reshape(-1, 5)}
        rows = VR.csv_rows(r["q"], q0[0])
        i, v = peak(rows)
        k = min(2 * i - 1, len(g["q"]) - 1) if i > 0 else 0
        res[name] = {"variant": a.variant, "peak_hand_speed_m_s": v, "peak_row50": i, "peak_time_s": i / HZ, "at_peak": at_peak(g, k), "shares": shares(g), "seconds": nb / 2}
        f.write_text(json.dumps(res[name]))
        print(f"{a.variant} {name}: peak {v:.4f} m/s at {i / HZ:.1f} s ({time.time() - t0:.0f} s)", flush=True)
    F.smooth_u, cpg.AMP_CAP_CONTINUOUS, cpg.F_MAX = keep_old
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=("roll", "analytic"))
    ap.add_argument("--out", default="/secondary/hyst-data/body/s0/ceiling")
    ap.add_argument("--policy", default="/secondary/hyst-data/body/k5p2/run/best.pkl")
    ap.add_argument("--lanes", default="/secondary/hyst-data/body/k5/lanes/check")
    ap.add_argument("--songs")
    ap.add_argument("--n", type=int, default=24)
    ap.add_argument("--variant", default="base", choices=("base", "amp", "c", "freq"))
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    {"roll": run_roll, "analytic": run_analytic}[a.what](a)


if __name__ == "__main__":
    main()
