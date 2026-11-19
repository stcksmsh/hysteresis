"""WO35 Step B (report only): V3a and V3b on the 10 seeded windows C01-C10 through IK -> guard -> round-1 spinal (H1) -> fixed limiter -> servo -> v2p -> gates at 1.25. No video.
Rules: docs/RETARGET_RULES.md (m). Run (body env): python -u v3_run.py -> /secondary/hyst-data/body/retarget_look/v3/{numbers.json (key stepB), work/*.csv}, docs/V3_REPORT.md section B (appended)
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arm_sim  # noqa: E402
import jitter_diag as J  # noqa: E402
import make_arm_v2p as P  # noqa: E402
import motornet as M  # noqa: E402
import retarget_limiter as FX  # noqa: E402
import retarget_run as RR  # noqa: E402
import v3_ik as K  # noqa: E402
import v3_lib as L  # noqa: E402
import v3_targets as TG  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")
V3 = OUT / "v3"
DOCS = Path(__file__).resolve().parents[2] / "docs"
RESID = 0.02                                                       # m: frames with a residual end-point error above this are counted


def lamp(Q):
    return K.fk_batch(Q)[0][:, 5]


def shoulder_numbers(Gcmd, Lin, Lout, q50, nw):
    """7.52.5 for V3: commanded shoulder acceleration (the IK output after the guard, 50 Hz rows, second difference x 2500 / limit) and realised, as p50 / p95 / max in multiples of the limit;
    the limiter's share (100 Hz frames where its output differs from its input, the spinal output, by > 1e-6 deg) and the shoulder RMS of (limiter input - limiter output) in deg"""
    import dialstudy as D
    acc = lambda r: np.abs(r[2:, 1] - 2 * r[1:-1, 1] + r[:-2, 1]) * 2500 / D.LIM_A[1]
    st = lambda a: dict(p50=float(np.percentile(a, 50)), p95=float(np.percentile(a, 95)), max=float(a.max()))
    d = Lin[nw:, 1] - Lout[nw:, 1]
    return dict(commanded_accel_x_limit=st(acc(Gcmd[nw::2])), realised_accel_x_limit=st(acc(q50)), limiter_share=float((np.abs(d) > 1e-6).mean()), rms_limiter_input_minus_output_deg=float(np.sqrt((d ** 2).mean())))


def run_clip(c, var):
    RR.patch_gates()
    import dialstudy as D
    nw = round(RR.PRE_S * 100)
    pos, rot, aux = TG.build_targets(c["seq"], var, c["start_s"], RR.PRE_S, RR.SHOW_S)
    Q, err = K.run_path(pos, rot)
    G, gshare = P.guard(Q)
    Gin = M.spinal(G)
    Lout = FX.limiter_out(Gin)
    q50, contacts = FX.simulate_goals(Gin)
    gate = RR.gates_v2p(q50, contacts, gshare)
    k0, k1 = int(np.ceil(c["start_s"] * 30 - 1e-9)), int(np.floor((c["start_s"] + RR.SHOW_S) * 30 + 1e-9))
    tk = np.arange(k0, k1 + 1) / 30.0
    p30 = np.stack([np.interp(tk, aux["t30"], aux["p30"][:, i]) for i in range(3)], 1)
    names = RR.JN
    stages = {"ik": (Q[nw:], 100.0), "spinal": (Gin[nw:], 100.0), "limiter": (Lout[nw:], 100.0), "realised": (q50, 50.0)}
    start = c["start_s"]
    out = dict(gate=dict(passed=gate["passed"], parts=gate["parts"], speed_ratio=gate["values"]["speed_ratio"], accel_ratio=gate["values"]["accel_ratio"]), guard_share=gshare,
               ik=dict(frames_err_gt_2cm_shown=int((err[nw:] > RESID).sum()), frames_shown=int(len(err[nw:])), frames_err_gt_2cm_all=int((err > RESID).sum()), frames_all=int(len(err)),
                       err_median_m=float(np.median(err[nw:])), err_p95_m=float(np.percentile(err[nw:], 95)), err_max_m=float(err[nw:].max()),
                       max_joint_step_deg_per_frame=float(np.abs(np.diff(Q, axis=0)).max())),
               shoulder=shoulder_numbers(G, Gin, Lout, q50, nw),
               endpoint=dict(target_30fps=L.pos_measures(p30, 30.0), ik_lamp_100hz=L.pos_measures(lamp(Q[nw:]), 100.0), realised_lamp_50hz=L.pos_measures(lamp(q50), 50.0)),
               stages={})
    for key, (rows, rate) in stages.items():
        out["stages"][key] = dict(own=J.all_joints(rows, rate, names), at30=J.all_joints(J.at30(rows, rate, start, tk), 30.0, names))
    (V3 / "work").mkdir(exist_ok=True)
    return out, q50, Q


def main():
    V3.mkdir(exist_ok=True)
    picks = json.loads((OUT / "work" / "picks.json").read_text())["picks"]
    res = {}
    for c in picks:
        for var in ("V3a", "V3b"):
            cid = f"{c['clip']}_{var}"
            o, q50, Q = run_clip(c, var)
            res[cid] = o
            (V3 / "work" / f"{cid}.csv").write_text(arm_sim.csv_text(q50, 50, name=cid))
            np.save(V3 / "work" / f"{cid}_ik.npy", Q)
            print(cid, "gate", o["gate"]["passed"], [p for p, ok in o["gate"]["parts"].items() if not ok], "ik>2cm shown", o["ik"]["frames_err_gt_2cm_shown"], "/", o["ik"]["frames_shown"], flush=True)
    nums = json.loads((V3 / "numbers.json").read_text()) if (V3 / "numbers.json").exists() else {}
    nums["stepB"] = res
    (V3 / "numbers.json").write_text(json.dumps(nums, indent=1))
    write_report(res)
    print("done")


def med(v):
    return float(np.median(v))


def write_report(res):
    jn = json.loads((OUT / "jitter" / "numbers.json").read_text())
    base, h1, ctl = jn["variants"]["baseline"], jn["variants"]["H1"], jn["control_stage4"]
    names = RR.JN
    L_ = ["", "## B. V3 space retarget (Step B)", "",
          "Rules: `RETARGET_RULES.md` (m). V3a = lamp follows the right wrist relative to the right shoulder, V3b = the head relative to the pelvis; IK on the v2p arm; then guard, round-1 spinal layer (H1), fixed limiter, servo, v2p body; gates at 1.25 (l). "
          "The same 10 seeded windows C01-C10 as the look test, nothing re-picked, no video. Medians are over the 10 clips of the variant. The baseline columns are the look-test V1 (for V3a) and V2 (for V3b) clips of the same windows, `JITTER_DIAGNOSIS.md` baseline and H1 runs.", "",
          "### B1. Gate (1.25) and IK residual, per clip", "", "| clip | gate | failed parts | speed x | accel x | guard share | IK frames > 2 cm (shown 20 s) | IK frames > 2 cm (all 21.5 s) | IK error median / p95 / max (cm) |", "|---|---|---|---|---|---|---|---|---|"]
    for cid, o in res.items():
        k = o["ik"]
        L_.append("| %s | %s | %s | %.2f | %.2f | %.4f | %d / %d | %d / %d | %.1f / %.1f / %.1f |" % (cid, "pass" if o["gate"]["passed"] else "FAIL", ", ".join(p for p, ok in o["gate"]["parts"].items() if not ok) or "-", o["gate"]["speed_ratio"], o["gate"]["accel_ratio"],
                                                                                                    o["guard_share"], k["frames_err_gt_2cm_shown"], k["frames_shown"], k["frames_err_gt_2cm_all"], k["frames_all"], 100 * k["err_median_m"], 100 * k["err_p95_m"], 100 * k["err_max_m"]))
    for var, bv in (("V3a", "V1"), ("V3b", "V2")):
        sel = {k: v for k, v in res.items() if k.endswith(var)}
        npass = sum(1 for v in sel.values() if v["gate"]["passed"])
        L_ += ["", f"### B2. {var}: jitter measures per stage (median over the {len(sel)} clips; own rate)", "",
               f"Gate passes: **{npass} / {len(sel)}**; IK frames > 2 cm (shown 20 s): median {med([v['ik']['frames_err_gt_2cm_shown'] for v in sel.values()]):.0f} of {next(iter(sel.values()))['ik']['frames_shown']}.", "",
               "| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |", "|---|---|---|---|---|---|"]
        for st, title in (("ik", "IK output"), ("spinal", "spinal layer output"), ("limiter", "limiter output"), ("realised", "realised")):
            for j in names:
                vs = [v["stages"][st]["own"][j] for v in sel.values()]
                L_.append("| %s | %s | %.2f | %.0f | %.3f | %.3f |" % (title, j, med([x["acc_sign_changes_per_s"] for x in vs]), med([x["jerk_rms"] for x in vs]), med([x["p_gt3"] for x in vs]), med([x["p_gt6"] for x in vs])))
        L_ += ["", f"End point (lamp position, per axis mean; medians over the clips): target path at 30 fps / IK output at 100 Hz / realised at 50 Hz", "", "| signal | sign changes /s (mean over axes) | power > 3 Hz | power > 6 Hz |", "|---|---|---|---|"]
        for key, title in (("target_30fps", "target path (30 fps)"), ("ik_lamp_100hz", "lamp FK of the IK output (100 Hz)"), ("realised_lamp_50hz", "lamp FK of the realised angles (50 Hz)")):
            vs = [v["endpoint"][key] for v in sel.values()]
            L_.append("| %s | %.2f | %.3f | %.3f |" % (title, med([x["flips_mean"] for x in vs]), med([x["p_gt3"] for x in vs]), med([x["p_gt6"] for x in vs])))
        L_ += ["", f"### B3. {var} next to {bv} (baseline), {bv} + H1 and the S03 references (stage 4 realised, median over clips; own rate)", "",
               "| joint | metric | " + f"{var} | {bv} baseline | {bv} + H1 | S03 refs (2 clips) |", "|---|---|---|---|---|---|"]
        for j in names:
            for metric, fmt, title in (("acc_sign_changes_per_s", "%.2f", "acc sign changes /s"), ("jerk_rms", "%.0f", "jerk RMS"), ("p_gt3", "%.3f", "power > 3 Hz")):
                a = med([v["stages"]["realised"]["own"][j][metric] for v in sel.values()])
                b = med([base[f"{k.split('_')[0]}_{bv}"]["stages"]["s4"]["own"][j][metric] for k in sel])
                h = med([h1[f"{k.split('_')[0]}_{bv}"]["stages"]["s4"]["own"][j][metric] for k in sel])
                s = med([ctl[c][j][metric] for c in ctl])
                L_.append(f"| {j} | {title} | {fmt} | {fmt} | {fmt} | {fmt} |".replace("%", "%") % (a, b, h, s))
        L_ += ["", f"### B4. {var} shoulder numbers (7.52.5): acceleration as multiples of the limit (p50 / p95 / max), limiter share, RMS (limiter input - output)", "",
               "| clip | commanded (IK output) | realised | limiter share | RMS deg |", "|---|---|---|---|---|"]
        for cid, v in sel.items():
            s_ = v["shoulder"]
            c_, r_ = s_["commanded_accel_x_limit"], s_["realised_accel_x_limit"]
            L_.append("| %s | %.2f / %.2f / %.1f | %.2f / %.2f / %.2f | %.0f %% | %.1f |" % (cid, c_["p50"], c_["p95"], c_["max"], r_["p50"], r_["p95"], r_["max"], 100 * s_["limiter_share"], s_["rms_limiter_input_minus_output_deg"]))
    p = DOCS / "V3_REPORT.md"
    txt = p.read_text()
    if "## B. V3 space retarget" in txt:
        txt = txt[:txt.index("\n## B. V3 space retarget")]
    p.write_text(txt.rstrip("\n") + "\n" + "\n".join(L_) + "\n")


if __name__ == "__main__":
    main()
