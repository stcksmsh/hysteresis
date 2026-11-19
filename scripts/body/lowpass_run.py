"""WO36: the low-passed V1/V2 on the 20 look-test windows, then the re-look picks and manifest. Rules: docs/RETARGET_RULES.md (n).

    lowpass_run.py run        20 windows: filter (cutoffs.json) -> spline -> guard -> spinal (H1) -> fixed limiter -> servo -> v2p -> gates at 1.25; numbers, CSVs, docs/LOWPASS_REPORT.md
    lowpass_run.py pick       the 6 re-look clips (default_rng(32071) permutation of the other 18, skipping gate failures) -> lowpass/picks.json (HOLD if C04_V2 or C10_V1 fails)
    lowpass_run.py manifest   lowpass/clips/manifest.json (6 pairs old vs LP; LP first in exactly 3, default_rng(32081)), after the render
Body env. Data and clips stay outside git.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import arm_sim  # noqa: E402
import jitter_diag as J  # noqa: E402
import lowpass_cutoff as LC  # noqa: E402
import make_arm_v2p as P  # noqa: E402
import motornet as M  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_limiter as FX  # noqa: E402
import retarget_run as RR  # noqa: E402
import v3_lib as L  # noqa: E402
import v3_run as V3  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")
LP = OUT / "lowpass"
DOCS = Path(__file__).resolve().parents[2] / "docs"
MUST = ("C04_V2", "C10_V1")


def lamp_p3(rows, rate):
    import m3f_report as R
    return L.pos_measures(R.fk_points(rows)[:, 5], rate)["p_gt3"]


def run_clip(c, var, fc):
    RR.patch_gates()
    nw = round(RR.PRE_S * 100)
    y = LC.stage1(c, var)
    yf = LC.lowpass(y, fc)
    k0, k1 = LC.window_frames(c)
    G0 = RT.to_100hz(yf, c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S)
    G, gshare = P.guard(G0)
    Gin = M.spinal(G)
    Lout = FX.limiter_out(Gin)
    q50, contacts = FX.simulate_goals(Gin)
    gate = RR.gates_v2p(q50, contacts, gshare)
    tk = np.arange(k0, k1 + 1) / 30.0
    st = {"s1": (yf[k0:k1 + 1], 30.0), "s2": (G[nw:], 100.0), "spinal": (Gin[nw:], 100.0), "limiter": (Lout[nw:], 100.0), "realised": (q50, 50.0)}
    out = dict(gate=dict(passed=gate["passed"], parts=gate["parts"], speed_ratio=gate["values"]["speed_ratio"], accel_ratio=gate["values"]["accel_ratio"]), guard_share=gshare, cutoff_hz=fc,
               shoulder=V3.shoulder_numbers(G, Gin, Lout, q50, nw), stages={}, lamp_p_gt3={})
    for key, (rows, rate) in st.items():
        out["stages"][key] = dict(own=J.all_joints(rows, rate, RR.JN))
        if key != "s1":
            out["stages"][key]["at30"] = J.all_joints(J.at30(rows, rate, c["start_s"], tk), 30.0, RR.JN)
        out["lamp_p_gt3"][key] = lamp_p3(rows, rate)
    return out, q50


def cmd_run():
    (LP / "work").mkdir(exist_ok=True)
    cut = json.loads((LP / "cutoffs.json").read_text())
    picks = json.loads((OUT / "work" / "picks.json").read_text())["picks"]
    base = json.loads((OUT / "jitter" / "numbers.json").read_text())
    res, comp = {}, {}
    for c in picks:
        for var in ("V1", "V2"):
            cid = f"{c['clip']}_{var}"
            o, q50 = run_clip(c, var, cut[var]["cutoff_hz"])
            res[cid] = o
            (LP / "work" / f"{cid}.csv").write_text(arm_sim.csv_text(q50, 50, name=cid))
            (LP / "work" / f"{cid}.json").write_text(json.dumps(dict(id=cid, gates=dict(passed=o["gate"]["passed"], parts=o["gate"]["parts"]), cutoff_hz=o["cutoff_hz"])))
            h1 = J.run_variant(c, var, "H1")["s4"]
            comp[cid] = dict(baseline_lamp_p_gt3_realised=lamp_p3(J.read_csv(OUT / "work" / f"{cid}.csv"), 50.0), h1_lamp_p_gt3_realised=lamp_p3(h1, 50.0))
            print(cid, "gate", o["gate"]["passed"], [p for p, ok in o["gate"]["parts"].items() if not ok], flush=True)
    ctl = {cid: lamp_p3(J.read_csv(OUT / "work" / f"{cid}.csv"), 50.0) for cid in ("C01_R1S03", "C09_R1S03")}
    (LP / "numbers.json").write_text(json.dumps(dict(cutoffs={v: cut[v]["cutoff_hz"] for v in cut}, windows=res, comparison=comp, s03_lamp_p_gt3_realised=ctl), indent=1))
    write_report(res, comp, ctl, cut, base)
    print("done")


def med(v):
    return float(np.median(v))


def write_report(res, comp, ctl, cut, base):
    names = RR.JN
    b, h1, s03 = base["variants"]["baseline"], base["variants"]["H1"], base["control_stage4"]
    L_ = ["# Low-pass to the human's smoothness: report (work order 36, BRAIN_SPEC 7.55; no verdict)", "",
          f"Rules `RETARGET_RULES.md` (n). 2nd-order Butterworth, zero phase, 30 fps, on the whole-sequence stage-1 angles; cutoffs **V1 {cut['V1']['cutoff_hz']:.2f} Hz, V2 {cut['V2']['cutoff_hz']:.2f} Hz** "
          f"(highest cutoff at which the median lamp-path power above 3 Hz of the 10 windows is <= the human end point's: V1 {cut['V1']['human_0r_median_p_gt3']:.4f}, V2 {cut['V2']['human_0r_median_p_gt3']:.4f}). "
          "Then cubic spline to 100 Hz, guard, round-1 spinal layer (H1), fixed limiter (k), servo, v2p body, gates at 1.25 (l). The same 20 windows as the look test. Medians over the 10 clips of the variant; own rate unless stated. Data: `lowpass/numbers.json`.", "",
          "## 1. Gate (1.25) per clip and shoulder numbers (7.52.5)", "",
          "| clip | gate | failed parts | speed x | accel x | guard share | shoulder commanded p50 / p95 / max (x limit) | shoulder realised p50 / p95 / max | limiter share | RMS limiter in - out (deg) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for cid, o in res.items():
        s, c_, r_ = o["shoulder"], o["shoulder"]["commanded_accel_x_limit"], o["shoulder"]["realised_accel_x_limit"]
        L_.append("| %s | %s | %s | %.2f | %.2f | %.4f | %.2f / %.2f / %.1f | %.2f / %.2f / %.2f | %.0f %% | %.1f |" % (cid, "pass" if o["gate"]["passed"] else "FAIL", ", ".join(p for p, ok in o["gate"]["parts"].items() if not ok) or "-", o["gate"]["speed_ratio"], o["gate"]["accel_ratio"],
                                                                                                              o["guard_share"], c_["p50"], c_["p95"], c_["max"], r_["p50"], r_["p95"], r_["max"], 100 * s["limiter_share"], s["rms_limiter_input_minus_output_deg"]))
    for var, bv in (("V1", "V1"), ("V2", "V2")):
        sel = {k: v for k, v in res.items() if k.endswith(var)}
        L_ += ["", f"## 2. {var} (cutoff {cut[var]['cutoff_hz']:.2f} Hz): jitter measures per stage (median over the {len(sel)} clips; gate passes {sum(1 for v in sel.values() if v['gate']['passed'])} / {len(sel)})", "",
               "| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | power > 3 Hz | power > 6 Hz |", "|---|---|---|---|---|---|"]
        for st, title in (("s1", "1 filtered stage-1 angles (30 fps)"), ("s2", "2 spline (100 Hz, guard)"), ("spinal", "spinal layer"), ("limiter", "limiter output"), ("realised", "realised (50 Hz)")):
            for j in names:
                vs = [v["stages"][st]["own"][j] for v in sel.values()]
                L_.append("| %s | %s | %.2f | %.0f | %.3f | %.3f |" % (title, j, med([x["acc_sign_changes_per_s"] for x in vs]), med([x["jerk_rms"] for x in vs]), med([x["p_gt3"] for x in vs]), med([x["p_gt6"] for x in vs])))
        L_ += ["", f"Lamp-path speed power above 3 Hz at each stage ({var}, median): " + ", ".join(f"{t} {med([v['lamp_p_gt3'][k] for v in sel.values()]):.4f}" for k, t in (("s1", "filtered stage 1"), ("s2", "spline"), ("spinal", "spinal"), ("limiter", "limiter"), ("realised", "realised"))) + ".", "",
               f"### 3. {var}: realised stage next to the look-test baseline, baseline + H1 and the S03 references (median over the clips)", "",
               "| joint | metric | low-pass + H1 | look-test baseline | baseline + H1 | S03 refs (2) |", "|---|---|---|---|---|---|"]
        for j in names:
            for metric, fmt, title in (("acc_sign_changes_per_s", "%.2f", "acc sign changes /s"), ("jerk_rms", "%.0f", "jerk RMS"), ("p_gt3", "%.3f", "power > 3 Hz")):
                a = med([v["stages"]["realised"]["own"][j][metric] for v in sel.values()])
                bb = med([b[k]["stages"]["s4"]["own"][j][metric] for k in sel])
                hh = med([h1[k]["stages"]["s4"]["own"][j][metric] for k in sel])
                ss = med([s03[c][j][metric] for c in s03])
                L_.append(f"| {j} | {title} | {fmt} | {fmt} | {fmt} | {fmt} |" % (a, bb, hh, ss))
        L_.append("| lamp path | power > 3 Hz (FK of realised angles) | %.4f | %.4f | %.4f | %.4f |" % (med([v["lamp_p_gt3"]["realised"] for v in sel.values()]), med([comp[k]["baseline_lamp_p_gt3_realised"] for k in sel]),
                                                                                                      med([comp[k]["h1_lamp_p_gt3_realised"] for k in sel]), med(list(ctl.values()))))
    (DOCS / "LOWPASS_REPORT.md").write_text("\n".join(L_) + "\n")


def cmd_pick():
    res = json.loads((LP / "numbers.json").read_text())["windows"]
    ids = sorted(res)
    others = [i for i in ids if i not in MUST]
    perm = [others[k] for k in np.random.default_rng(32071).permutation(len(others))]
    log = dict(permutation=perm, skipped=[])
    for m in MUST:
        if not res[m]["gate"]["passed"]:
            bad = [p for p, ok in res[m]["gate"]["parts"].items() if not ok]
            (LP / "picks.json").write_text(json.dumps(dict(log, hold=m, failed=bad)))
            print("HOLD", m, bad)
            sys.exit(3)
    chosen = list(MUST)
    for i in perm:
        if len(chosen) == 6:
            break
        if res[i]["gate"]["passed"]:
            chosen.append(i)
        else:
            log["skipped"].append(dict(clip=i, failed=[p for p, ok in res[i]["gate"]["parts"].items() if not ok]))
    log["chosen"] = chosen
    (LP / "picks.json").write_text(json.dumps(log, indent=1))
    print(json.dumps(log))


def cmd_manifest():
    pk = json.loads((LP / "picks.json").read_text())["chosen"]
    genre = {p["clip"]: p["genre"] for p in json.loads((OUT / "work" / "picks.json").read_text())["picks"]}
    lp_first = {int(i) for i in np.random.default_rng(32081).choice(6, 3, replace=False)}
    items = []
    for n, cid in enumerate(pk):
        old, new = str(OUT / "clips" / f"{cid}.mp4"), str(LP / "clips" / f"{cid}_LP.mp4")
        assert Path(old).exists() and Path(new).exists(), cid
        files, variants = ([new, old], ["LP", "old"]) if n in lp_first else ([old, new], ["old", "LP"])
        items.append(dict(id=f"PAIR_{cid}", kind="pair", files=files, variants=variants, clip=cid.split("_")[0], genre=genre[cid.split("_")[0]]))
    (LP / "clips" / "manifest.json").write_text(json.dumps(items, indent=1))
    print("manifest", [(i["id"], i["variants"]) for i in items], "LP first in", sorted(lp_first))


if __name__ == "__main__":
    {"run": cmd_run, "pick": cmd_pick, "manifest": cmd_manifest}[sys.argv[1]]()
