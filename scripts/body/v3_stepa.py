"""WO35 Step A (report only, BRAIN_SPEC 7.54.4 and 7.54.8): end-point smoothness for the 20 look-test clips.
(0w) human end point in world space (right wrist, joint 21, for V1 clips; head, joint 15, for V2 clips; root translation included);
(0r) the same relative to its origin (right shoulder 17 for V1; pelvis 0 for V2);
(1)  the stage-1 joint angles (jitter/numbers.json);
(1e) the robot lamp position (arm FK, point p5) of the stage-1 angles.
All at the dataset's 30 fps over the shown 20 s (frames k/30 inside the window, as jitter_diag). Positions: per axis acceleration sign changes per second (deadband 0.01 m/s^2), their mean over axes, share of speed-vector power above 3 / 6 Hz.
Run (body env): python -u v3_stepa.py  -> /secondary/hyst-data/body/retarget_look/v3/numbers.json (key stepA) and docs/V3_REPORT.md section A
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import m3f_report as R  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402
import v3_lib as L  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")
V3 = OUT / "v3"
END = {"V1": (21, 17), "V2": (15, 0)}          # (end point, origin) joint indices


def med(v):
    return float(np.median(v))


def main():
    V3.mkdir(exist_ok=True)
    picks = json.loads((OUT / "work" / "picks.json").read_text())["picks"]
    jn = json.loads((OUT / "jitter" / "numbers.json").read_text())["variants"]["baseline"]
    per = {}
    for c in picks:
        for var in ("V1", "V2"):
            cid = f"{c['clip']}_{var}"
            k0, k1 = int(np.ceil(c["start_s"] * 30 - 1e-9)), int(np.floor((c["start_s"] + RR.SHOW_S) * 30 + 1e-9))
            P, _ = L.fk(c["seq"], k0, k1)
            e, o = END[var]
            v = RR.human(c["seq"])[0 if var == "V1" else 1]
            y = RT.to_commands(RT.referenced(v, round(c["start_s"] * RT.FPS)), var)[k0:k1 + 1]
            lamp = R.fk_points(y)[:, 5]
            s1 = jn[cid]["stages"]["s1"]["own"]
            per[cid] = {"end_joint": e, "origin_joint": o, "frames": int(k1 - k0 + 1),
                        "0w": L.pos_measures(P[:, e], 30.0), "0r": L.pos_measures(P[:, e] - P[:, o], 30.0), "1e": L.pos_measures(lamp, 30.0),
                        "1": {j: s1[j] for j in RR.JN}}
    nums = json.loads((V3 / "numbers.json").read_text()) if (V3 / "numbers.json").exists() else {}
    nums["stepA"] = per
    (V3 / "numbers.json").write_text(json.dumps(nums, indent=1))
    write_md(per, Path(__file__).resolve().parents[2] / "docs" / "V3_REPORT.md")
    print("done")


def row(vals, sig):
    return med(vals)


def write_md(per, path):
    sel = lambda var: {k: v for k, v in per.items() if k.endswith(var)}
    lines = ["# V3 report (work order 35, BRAIN_SPEC 7.54; report only)", "",
             "No verdict, no video, no blind session. Code: `scripts/body/v3_lib.py`, `v3_stepa.py` (+ tests). Per-clip numbers: `/secondary/hyst-data/body/retarget_look/v3/numbers.json`.", "",
             "## A. End-point smoothness (Step A)", "",
             "Same 20 clips and windows as the look test, dataset frames k/30 s inside the shown 20 s. Signals: **(0w)** the human end point in world space (right wrist, joint 21, for V1 clips; head, joint 15, for V2 clips; root translation included); "
             "**(0r)** the same end point relative to its origin (right shoulder, joint 17, for V1; pelvis, joint 0, for V2), the signal V3 follows; **(1)** the stage-1 joint angles (the V1/V2 retargeted command at 30 fps); "
             "**(1e)** the robot lamp position by arm FK (point p5) of the stage-1 angles. Human FK uses the canonical T-pose offsets of the WO34 viewing figure (no SMPL model file; scale cancels in the reach normalisation).", "",
             "Measures: acceleration sign changes per second (second difference at 30 fps; angles: accelerations below 1 deg/s^2 count as zero, positions: below 0.01 m/s^2, the same deadband in the sense that 1 deg/s^2 at a 0.57 m radius is 0.01 m/s^2 (FOR USER: default)); "
             "for positions per axis (x left, y up, z forward for the human; robot X forward, Y left, Z up for the lamp) and the mean over axes; share of speed power above 3 and 6 Hz (Welch, Hann, 5 s segments, mean removed; for positions the power of the speed vector = the three axes summed). Medians over the clips.", ""]
    for title, S in (("All 20 clips", per), ("V1 clips (10): end point = right wrist, origin = right shoulder", sel("V1")), ("V2 clips (10): end point = head, origin = pelvis", sel("V2"))):
        lines += [f"### {title}", "", "| signal | sign changes /s x | y | z | mean over axes | power > 3 Hz | power > 6 Hz |", "|---|---|---|---|---|---|---|"]
        for key, name in (("0w", "(0w) human end point, world"), ("0r", "(0r) human end point relative to origin"), ("1e", "(1e) robot lamp position, FK of stage-1 angles")):
            v = [d[key] for d in S.values()]
            lines.append("| %s | %.2f | %.2f | %.2f | %.2f | %.3f | %.3f |" % (name, med([x["flips_per_s"]["x"] for x in v]), med([x["flips_per_s"]["y"] for x in v]), med([x["flips_per_s"]["z"] for x in v]),
                                                                              med([x["flips_mean"] for x in v]), med([x["p_gt3"] for x in v]), med([x["p_gt6"] for x in v])))
        lines += ["", "(1) stage-1 joint angles (per joint; jerk and power as `JITTER_DIAGNOSIS.md`):", "", "| joint | sign changes /s | power > 3 Hz | power > 6 Hz |", "|---|---|---|---|"]
        for j in RR.JN:
            v = [d["1"][j] for d in S.values()]
            lines.append("| %s | %.2f | %.3f | %.3f |" % (j, med([x["acc_sign_changes_per_s"] for x in v]), med([x["p_gt3"] for x in v]), med([x["p_gt6"] for x in v])))
        lines += ["| mean over the 5 joints | %.2f | %.3f | %.3f |" % tuple(np.mean([[med([d["1"][j][k] for d in S.values()]) for j in RR.JN] for k in ("acc_sign_changes_per_s", "p_gt3", "p_gt6")], axis=1)), ""]
    lines += ["### Per clip (sign changes mean over axes / power > 3 Hz)", "", "| clip | (0w) | (0r) | (1e) | (1) mean over joints |", "|---|---|---|---|---|"]
    for cid, d in per.items():
        m1 = np.mean([d["1"][j]["acc_sign_changes_per_s"] for j in RR.JN]), np.mean([d["1"][j]["p_gt3"] for j in RR.JN])
        lines.append("| %s | %.2f / %.3f | %.2f / %.3f | %.2f / %.3f | %.2f / %.3f |" % (cid, d["0w"]["flips_mean"], d["0w"]["p_gt3"], d["0r"]["flips_mean"], d["0r"]["p_gt3"], d["1e"]["flips_mean"], d["1e"]["p_gt3"], m1[0], m1[1]))
    Path(path).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
