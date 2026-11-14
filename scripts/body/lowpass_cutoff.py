"""WO36: the cutoff of the zero-phase low-pass on the stage-1 angles, by the rule of BRAIN_SPEC 7.55.7: per variant (V1, V2), the HIGHEST cutoff (least smoothing) on the grid 0.5-14.5 Hz in 0.25 Hz steps at which the
median over the variant's 10 look-test windows of the lamp path's speed power share above 3 Hz (lamp = arm FK, point p5, of the filtered stage-1 angles; the Step A measure) is <= the median of the human end point's (0r:
right wrist relative to the right shoulder for V1, head relative to the pelvis for V2; `v3/numbers.json` stepA). Filter: 2nd-order Butterworth, scipy filtfilt (zero phase), 30 fps, on the whole sequence's stage-1 angles
(base yaw and wrist roll unwrapped, as `retarget.human_angles` makes them) before windowing. No clip is simulated or rendered here.
Run (body env): python -u lowpass_cutoff.py -> /secondary/hyst-data/body/retarget_look/lowpass/cutoffs.json
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m3f_report as R  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402
import v3_lib as L  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")
LP = OUT / "lowpass"
GRID = np.arange(0.5, 14.5 + 1e-9, 0.25)
FS = 30.0


def lowpass(y, fc):
    b, a = butter(2, fc / (FS / 2))
    return filtfilt(b, a, y, axis=0)


def stage1(c, var):
    v = RR.human(c["seq"])[0 if var == "V1" else 1]
    return RT.to_commands(RT.referenced(v, round(c["start_s"] * RT.FPS)), var)            # whole sequence, 30 fps


def window_frames(c):
    return int(np.ceil(c["start_s"] * 30 - 1e-9)), int(np.floor((c["start_s"] + RR.SHOW_S) * 30 + 1e-9))


def lamp_power(yf, c):
    k0, k1 = window_frames(c)
    return L.pos_measures(R.fk_points(yf[k0:k1 + 1])[:, 5], FS)["p_gt3"]


def main():
    LP.mkdir(exist_ok=True)
    picks = json.loads((OUT / "work" / "picks.json").read_text())["picks"]
    stepA = json.loads((OUT / "v3" / "numbers.json").read_text())["stepA"]
    res = {}
    for var in ("V1", "V2"):
        ys = {c["clip"]: stage1(c, var) for c in picks}
        human = float(np.median([stepA[f"{c['clip']}_{var}"]["0r"]["p_gt3"] for c in picks]))
        unfiltered = float(np.median([lamp_power(ys[c["clip"]], c) for c in picks]))
        curve = []
        for fc in GRID:
            curve.append((float(fc), float(np.median([lamp_power(lowpass(ys[c["clip"]], fc), c) for c in picks]))))
        ok = [fc for fc, p in curve if p <= human]
        res[var] = dict(human_0r_median_p_gt3=human, lamp_unfiltered_median_p_gt3=unfiltered, curve=curve, cutoff_hz=max(ok) if ok else None, grid_points_meeting_rule=len(ok),
                        monotone=bool(all(curve[i][1] <= curve[i + 1][1] + 1e-12 for i in range(len(curve) - 1))))
    (LP / "cutoffs.json").write_text(json.dumps(res, indent=1))
    for v, r in res.items():
        print(v, "human", round(r["human_0r_median_p_gt3"], 4), "unfiltered lamp", round(r["lamp_unfiltered_median_p_gt3"], 4), "cutoff", r["cutoff_hz"], "meeting", r["grid_points_meeting_rule"], "monotone", r["monotone"])


if __name__ == "__main__":
    main()
