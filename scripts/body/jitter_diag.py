"""WO33 jitter diagnosis on the 20 retarget look-test clips (C01-C10 x V1, V2), REPORT ONLY (BRAIN_SPEC 7.53). Adopts nothing, renders no video.

Stages: 1 retargeted command at 30 fps; 2 after the 30 -> 100 Hz resampling (+ guard); [2s round-1 spinal layer, H1 only]; 3 limiter output (the fixed limiter of rules (k)); 4 realised (servo/body, 50 Hz).
Per stage and joint: acceleration sign changes per second, jerk RMS (deg/s^3), share of joint-speed power above 3 and above 6 Hz (mean removed, Welch, Hann, 0.2 Hz resolution),
at the stage's own rate and (stages 2-4) at the 30 fps instants of the dataset frames (linear interpolation of the stage's rows). Everything over the shown 20 s.
Variants: baseline (cubic spline, no spinal), H1 (spinal 3 Hz zeta 0.7 before the limiter), H3_linear (linear interpolation instead of the spline), H1_linear (H1 with linear).
Run (body env): python -u jitter_diag.py        -> /secondary/hyst-data/body/retarget_look/jitter/numbers.json, SVG plots, docs/JITTER_DIAGNOSIS.md
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import welch

sys.path.insert(0, str(Path(__file__).resolve().parent))

FS30 = 30.0
EPS_ACC = 1.0                                        # deg/s^2: accelerations below this count as zero for sign changes (as the gate's 1 deg/s speed deadband)
OUT = Path("/secondary/hyst-data/body/retarget_look")
JIT = OUT / "jitter"


# ------------------------------------------------------------------------------------------------ measures
def measures(x, fs):
    """x (n,) deg at rate fs -> dict: acc_sign_changes_per_s, jerk_rms (deg/s^3), p_gt3, p_gt6 (share of speed power above 3 / 6 Hz, mean removed, 0.2 Hz bins)"""
    x = np.asarray(x, float)
    a = (x[2:] - 2 * x[1:-1] + x[:-2]) * fs * fs
    s = np.sign(a[np.abs(a) >= EPS_ACC])
    flips = float((np.diff(s) != 0).sum()) / (len(x) / fs)
    jerk = np.diff(a) * fs
    v = np.diff(x) * fs
    f, P = welch(v - v.mean(), fs, window="hann", nperseg=min(len(v), round(5 * fs)), detrend=False)
    tot = P[f > 0].sum()
    return dict(acc_sign_changes_per_s=flips, jerk_rms=float(np.sqrt((jerk ** 2).mean())),
                p_gt3=float(P[f > 3].sum() / tot) if tot > 0 else 0.0, p_gt6=float(P[f > 6].sum() / tot) if tot > 0 else 0.0)


def all_joints(X, fs, names):
    return {j: measures(X[:, i], fs) for i, j in enumerate(names)}


def h2(L100, lim_a, nw):
    """H2 on limiter output rows L100 (n, 5) at 100 Hz (pre-roll nw rows included): per joint the share of frames with |acceleration| >= 0.98 x limit on the 100 Hz frames and on the
    gate's 50 Hz measure, and the sign flips per second of the 100 Hz acceleration"""
    S = L100[nw:]
    a100 = (S[2:] - 2 * S[1:-1] + S[:-2]) * 1e4
    S5 = S[::2]
    a50 = (S5[2:] - 2 * S5[1:-1] + S5[:-2]) * 2500
    out = {}
    for i in range(S.shape[1]):
        s = np.sign(a100[np.abs(a100[:, i]) >= EPS_ACC, i])
        out[i] = dict(share_ge_0p98_100hz=float((np.abs(a100[:, i]) >= 0.98 * lim_a[i]).mean()), share_ge_0p98_gate50hz=float((np.abs(a50[:, i]) >= 0.98 * lim_a[i]).mean()),
                      acc_sign_flips_per_s=float((np.diff(s) != 0).sum() / (len(S) / 100.0)))
    return out


# ------------------------------------------------------------------------------------------------ pipeline
def read_csv(path):
    rows = [[float(c) for c in ln.split(",")] for ln in Path(path).read_text().splitlines() if ln and not ln.startswith("#") and not ln.startswith("time_s")]
    return np.array(rows)[:, 1:6]


def to_100hz_linear(y, t0_s, dur_s):
    t = np.arange(len(y)) / 30.0
    tt = t0_s + np.arange(round(dur_s * 100) + 1) / 100.0
    return np.stack([np.interp(tt, t, y[:, j]) for j in range(5)], 1)


def run_variant(c, var, variant):
    """pick c, 'V1'|'V2', variant name -> dict of stage arrays, gate verdict, guard share"""
    import dialstudy as D
    import make_arm_v2p as P
    import motornet as M
    import retarget as RT
    import retarget_limiter as FX
    import retarget_run as RR
    RR.patch_gates()
    v = RR.human(c["seq"])[0 if var == "V1" else 1]
    i0 = round(c["start_s"] * RT.FPS)
    y = RT.to_commands(RT.referenced(v, i0), var)                                   # stage 1, whole sequence, 30 fps
    linear = variant in ("H3_linear", "H1_linear")
    spinal = variant in ("H1", "H1_linear")
    G0 = to_100hz_linear(y, c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S) if linear else RT.to_100hz(y, c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
    G, gshare = P.guard(G0)                                                          # stage 2
    Gin = M.spinal(G) if spinal else G
    nw = round(RR.PRE_S * 100)
    L = FX.limiter_out(Gin)                                                          # stage 3 (100 Hz, pre-roll included)
    q50, contacts = FX.simulate_goals(Gin)                                           # stage 4
    gate = RR.gates_v2p(q50, contacts, gshare)
    k0, k1 = int(np.ceil(c["start_s"] * 30 - 1e-9)), int(np.floor((c["start_s"] + RR.SHOW_S) * 30 + 1e-9))
    tk = np.arange(k0, k1 + 1) / 30.0
    return dict(s1=y[k0:k1 + 1], t30=tk, s2=G[nw:], s2_pre_guard=G0[nw:], s2s=Gin[nw:] if spinal else None, s3=L[nw:], s4=q50, L100=L, nw=nw,
                gate=dict(passed=gate["passed"], parts=gate["parts"], speed_ratio=gate["values"]["speed_ratio"], accel_ratio=gate["values"]["accel_ratio"]), guard_share=gshare,
                guard_changed_max=float(np.abs(G - G0).max()), start=c["start_s"], D=D)


def at30(rows, rate, start, tk):
    t = start + np.arange(len(rows)) / rate
    return np.stack([np.interp(tk, t, rows[:, j]) for j in range(rows.shape[1])], 1)


def clip_numbers(r, names, lim_a):
    st = {}
    tk, start = r["t30"], r["start"]
    st["s1"] = dict(own=all_joints(r["s1"], FS30, names))
    for key, rate in (("s2", 100.0), ("s2s", 100.0), ("s3", 100.0), ("s4", 50.0)):
        if r[key] is None:
            continue
        st[key] = dict(own=all_joints(r[key], rate, names), at30=all_joints(at30(r[key], rate, start, tk), FS30, names))
    out = dict(stages=st, gate=r["gate"], guard_share=r["guard_share"], guard_changed_max_deg=r["guard_changed_max"], h2=h2(r["L100"], lim_a, r["nw"]))
    out["h2"] = {names[i]: v for i, v in out["h2"].items()}
    return out


# ------------------------------------------------------------------------------------------------ plots (SVG, rasterised with the system Chrome)
def plot_svg(path, r, title, t_lo=8.0, t_hi=12.0):
    W, H, ML, MT = 1000, 640, 70, 40
    ph = (H - 2 * MT - 40) / 2
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" font-family="sans-serif" font-size="13"><rect width="100%" height="100%" fill="white"/>',
             f'<text x="{ML}" y="22" font-size="15">{title}  (shoulder and wrist bend, seconds {t_lo:g}-{t_hi:g} of the clip; dots = stage 1 at 30 fps, thin = limiter output, thick = realised)</text>']
    for p, (j, name) in enumerate(((1, "shoulder"), (3, "wrist bend"))):
        top = MT + p * (ph + 40)
        segs = {"s1": (r["s1"][:, j], r["t30"] - r["start"]), "s3": (r["s3"][:, j], np.arange(len(r["s3"])) / 100.0), "s4": (r["s4"][:, j], np.arange(len(r["s4"])) / 50.0)}
        vals = np.concatenate([a[(t >= t_lo) & (t <= t_hi)] for a, t in segs.values()])
        lo, hi = vals.min() - 2, vals.max() + 2
        X = lambda t: ML + (t - t_lo) / (t_hi - t_lo) * (W - ML - 20)
        Y = lambda a: top + ph - (a - lo) / (hi - lo) * ph
        parts.append(f'<rect x="{ML}" y="{top}" width="{W - ML - 20}" height="{ph}" fill="none" stroke="#999"/><text x="8" y="{top + ph / 2}" transform="rotate(-90 12 {top + ph / 2})" text-anchor="middle">{name} (deg)</text>')
        for tick in np.linspace(lo, hi, 5):
            parts.append(f'<text x="{ML - 6}" y="{Y(tick) + 4}" text-anchor="end">{tick:.0f}</text><line x1="{ML}" x2="{W - 20}" y1="{Y(tick)}" y2="{Y(tick)}" stroke="#eee"/>')
        for k, (a, t) in segs.items():
            m = (t >= t_lo) & (t <= t_hi)
            pts = " ".join(f"{X(tt):.1f},{Y(aa):.1f}" for tt, aa in zip(t[m], a[m]))
            if k == "s1":
                parts += [f'<circle cx="{X(tt):.1f}" cy="{Y(aa):.1f}" r="3" fill="#d62728"/>' for tt, aa in zip(t[m], a[m])]
            else:
                parts.append(f'<polyline points="{pts}" fill="none" stroke="{"#1f77b4" if k == "s3" else "#000"}" stroke-width="{1 if k == "s3" else 2}"/>')
    parts.append("</svg>")
    Path(path).write_text("\n".join(parts))


def rasterise(svgs):
    import subprocess
    for s in svgs:
        subprocess.run(["/usr/bin/google-chrome", "--headless", "--no-sandbox", "--disable-gpu", f"--screenshot={s.with_suffix('.png')}", "--window-size=1000,640", f"file://{s}"],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=120)


# ------------------------------------------------------------------------------------------------ report
STAGE_NAMES = {"s1": "1 retargeted command, 30 fps", "s2": "2 resampled to 100 Hz (+guard)", "s2s": "2s spinal layer output (H1)", "s3": "3 limiter output", "s4": "4 realised (50 Hz)"}
VARIANTS = ("baseline", "H1", "H3_linear", "H1_linear")


def med(vals):
    return float(np.median(vals))


def table(num, variant, joints, rate_key):
    lines = ["| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |", "|---|---|---|---|---|---|"]
    clips = num[variant]
    for st in ("s1", "s2", "s2s", "s3", "s4"):
        if st not in next(iter(clips.values()))["stages"]:
            continue
        if rate_key == "at30" and st == "s1":
            continue
        for j in joints:
            vs = [c["stages"][st][rate_key if st != "s1" else "own"][j] for c in clips.values()]
            lines.append("| %s | %s | %.2f | %.0f | %.3f | %.3f |" % (STAGE_NAMES[st], j, med([v["acc_sign_changes_per_s"] for v in vs]), med([v["jerk_rms"] for v in vs]),
                                                                       med([v["p_gt3"] for v in vs]), med([v["p_gt6"] for v in vs])))
    return "\n".join(lines)


def write_md(num, ctl, base_check, joints, md_path):
    L = ["# Jitter diagnosis on the 20 retarget look-test clips (work order 33, BRAIN_SPEC 7.53; report only)", "",
         "No verdict, nothing adopted, no video rendered. Code: `scripts/body/jitter_diag.py` (+ `test_jitter_diag.py`). Data: `/secondary/hyst-data/body/retarget_look/jitter/numbers.json`, plots there (not in git).", "",
         "## Method", "",
         "- Clips: C01-C10 x V1, V2, the windows of `manifest.json`, rebuilt from FineDance exactly as `retarget_run.py` builds them (v2p body, guard, fixed limiter of rules (k)). Everything is measured over the shown 20 s.",
         "- Stages: **1** the retargeted command at the dataset's 30 fps; **2** after the 30 -> 100 Hz resampling (`retarget.to_100hz`, a cubic spline) and the guard; **3** the limiter output (100 Hz); **4** the realised joint angles (servo/body, 50 Hz). Variant H1 has a stage **2s**, the round-1 spinal layer output.",
         "- Measures per stage and joint: acceleration sign changes per second (second difference at the stage's rate; accelerations below 1 deg/s^2 count as zero); jerk RMS in deg/s^3 (difference of the acceleration); share of joint-speed power above 3 Hz and above 6 Hz (mean removed, Welch, Hann window, 5 s segments = 0.2 Hz bins).",
         "- Each is computed at the stage's own rate (\"own\") and, for stages 2-4, at the 30 fps instants of the dataset frames (\"at 30 fps\": the stage's rows linearly interpolated to the instants k/30 s, so stage 1 compares like for like). Tables give the **median over the 20 clips**; per-clip numbers are in `numbers.json` and the appendix.",
         "- Variants: **baseline** (as shown); **H1** the round-1 `motornet.spinal` (3 Hz, zeta 0.7, unchanged) applied to the 100 Hz command before the fixed limiter, stages 3-4 re-run; **H3 linear** linear interpolation instead of the cubic spline (control showing the size of the effect H3 describes; the shown clips already use the cubic spline); **H1 + H3 combined** = H1 with the cubic spline as used (the H1 tables); `H1_linear` (H1 with linear interpolation) is added as an extra control.",
         "- 7.52 gate (speed and acceleration at 1.25, every other gate as run) pass/fail per variant run is reported, not used to select anything.", "",
         "## Baseline reproduction (stage 4 vs `work/<id>.csv`)", "",
         "Maximum absolute difference between the rebuilt stage-4 rows and the CSV of the shown clip, over the 20 clips: **%.4f deg** (worst clip %s; the CSV is written with fixed decimals)." % (base_check["max"], base_check["worst"]), ""]
    L += ["## Gate verdicts (7.52, 1.25) per variant, 20 clips", "", "| variant | passes | failing clips (failed parts) |", "|---|---|---|"]
    for v in VARIANTS:
        fails = [(cid, [p for p, ok in c["gate"]["parts"].items() if not ok]) for cid, c in num[v].items() if not c["gate"]["passed"]]
        L.append("| %s | %d / 20 | %s |" % (v, 20 - len(fails), "; ".join(f"{cid} ({', '.join(p)})" for cid, p in fails) or "-"))
    L += ["", "Guard: baseline guard share median %.4f, max %.4f; the guard changed the command by at most %.3f deg on any clip." % (
        med([c["guard_share"] for c in num["baseline"].values()]), max(c["guard_share"] for c in num["baseline"].values()), max(c["guard_changed_max_deg"] for c in num["baseline"].values())), ""]
    for v, title in (("baseline", "Baseline (as shown)"), ("H1", "H1: spinal layer (3 Hz, zeta 0.7) before the limiter = H1 + H3 combined (cubic spline as used)"),
                     ("H3_linear", "H3: linear interpolation instead of the cubic spline (control)"), ("H1_linear", "Extra control: H1 with linear interpolation")):
        L += [f"## {title}", "", "### Own rate (median over 20 clips)", "", table(num, v, joints, "own"), "", "### Stages 2-4 at the 30 fps instants (median over 20 clips)", "", table(num, v, joints, "at30"), ""]
    L += ["## H2: limiter output at the acceleration limit (baseline, median over 20 clips)", "",
          "Share of frames where |limiter output acceleration| >= 0.98 x the limit (100 Hz frames, and the gate's 50 Hz measure) and sign flips per second of the 100 Hz limiter output acceleration.", "",
          "| joint | share >= 0.98 limit, 100 Hz | share >= 0.98 limit, gate 50 Hz | acceleration sign flips /s |", "|---|---|---|---|"]
    for j in joints:
        hs = [c["h2"][j] for c in num["baseline"].values()]
        L.append("| %s | %.3f | %.3f | %.2f |" % (j, med([h["share_ge_0p98_100hz"] for h in hs]), med([h["share_ge_0p98_gate50hz"] for h in hs]), med([h["acc_sign_flips_per_s"] for h in hs])))
    L += ["", "Same measures with H1 (median over 20 clips):", "", "| joint | share >= 0.98 limit, 100 Hz | share >= 0.98 limit, gate 50 Hz | acceleration sign flips /s |", "|---|---|---|---|"]
    for j in joints:
        hs = [c["h2"][j] for c in num["H1"].values()]
        L.append("| %s | %.3f | %.3f | %.2f |" % (j, med([h["share_ge_0p98_100hz"] for h in hs]), med([h["share_ge_0p98_gate50hz"] for h in hs]), med([h["acc_sign_flips_per_s"] for h in hs])))
    L += ["", "## Control: round-1 S03 reference clips at stage 4 as they are", "", "| clip | joint | acc sign changes /s | jerk RMS deg/s^3 | power > 3 Hz | power > 6 Hz |", "|---|---|---|---|---|---|"]
    for cid, d in ctl.items():
        for j in joints:
            v = d[j]
            L.append("| %s | %s | %.2f | %.0f | %.3f | %.3f |" % (cid, j, v["acc_sign_changes_per_s"], v["jerk_rms"], v["p_gt3"], v["p_gt6"]))
    L += ["", "## Appendix: per clip, baseline, shoulder and wrist bend (own rate)", "", "| clip | stage | shoulder sign/s | shoulder jerk RMS | shoulder >3 Hz | wrist bend sign/s | wrist bend jerk RMS | wrist bend >3 Hz |", "|---|---|---|---|---|---|---|---|"]
    for cid, c in num["baseline"].items():
        for st in ("s1", "s2", "s3", "s4"):
            s, w = c["stages"][st]["own"]["shoulder"], c["stages"][st]["own"]["wrist_bend"]
            L.append("| %s | %s | %.2f | %.0f | %.3f | %.2f | %.0f | %.3f |" % (cid, st, s["acc_sign_changes_per_s"], s["jerk_rms"], s["p_gt3"], w["acc_sign_changes_per_s"], w["jerk_rms"], w["p_gt3"]))
    Path(md_path).write_text("\n".join(L) + "\n")


def main():
    import retarget_run as RR
    import dialstudy as D
    JIT.mkdir(parents=True, exist_ok=True)
    names = RR.JN
    picks = json.loads((OUT / "work" / "picks.json").read_text())["picks"]
    num = {v: {} for v in VARIANTS}
    worst, dmax = None, 0.0
    plots = []
    for c in picks:
        for var in ("V1", "V2"):
            cid = f"{c['clip']}_{var}"
            for variant in VARIANTS:
                r = run_variant(c, var, variant)
                if variant == "baseline":
                    csv = read_csv(OUT / "work" / f"{cid}.csv")
                    d = float(np.abs(csv - r["s4"]).max())
                    if d > dmax:
                        dmax, worst = d, cid
                num[variant][cid] = clip_numbers(r, names, D.LIM_A)
                if cid in ("C04_V2", "C10_V1") and variant in ("baseline", "H1", "H3_linear"):
                    p = JIT / f"{cid}_{variant}.svg"
                    plot_svg(p, r, f"{cid} {variant}")
                    plots.append(p)
                print(cid, variant, "gate", r["gate"]["passed"], flush=True)
    ctl = {}
    for cid in ("C01_R1S03", "C09_R1S03"):
        q = read_csv(OUT / "work" / f"{cid}.csv")
        ctl[cid] = all_joints(q, 50.0, names)
    base_check = dict(max=dmax, worst=worst)
    (JIT / "numbers.json").write_text(json.dumps(dict(base_check=base_check, variants=num, control_stage4=ctl, eps_acc_deg_s2=EPS_ACC), indent=1))
    write_md(num, ctl, base_check, names, Path(__file__).resolve().parents[2] / "docs" / "JITTER_DIAGNOSIS.md")
    rasterise(plots)
    print("done; baseline max abs diff vs CSV", dmax, worst)


if __name__ == "__main__":
    main()
