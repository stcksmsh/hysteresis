"""WO37: reproduce one look-test window's V2 target stage before H1 (WO36 lowpass chain) with the T0 chain; also the gate verdict and the realised rows vs the stored csv.
Body env: python -u t0_repro_lookwindow.py [CLIP VARIANT] -> prints max abs differences (deg)."""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jitter_diag as J  # noqa: E402
import lowpass_cutoff as LC  # noqa: E402
import make_arm_v2p as P  # noqa: E402
import retarget as RT  # noqa: E402
import retarget_run as RR  # noqa: E402
import t0_chain as C  # noqa: E402
import t0_lib as T  # noqa: E402

OUT = Path("/secondary/hyst-data/body/retarget_look")


def main(clip="C04", var="V2"):
    c = next(p for p in json.loads((OUT / "work" / "picks.json").read_text())["picks"] if p["clip"] == clip)
    fc = json.loads((OUT / "lowpass" / "cutoffs.json").read_text())[var]["cutoff_hz"]
    G_old, _ = P.guard(RT.to_100hz(LC.lowpass(LC.stage1(c, var), fc), c["start_s"] - RR.PRE_S, RR.SHOW_S + RR.PRE_S))
    rot, _ = T.load_rot(RR.FD / "motion" / f"{c['seq']}.npy")
    yraw, yf = C.stage1(rot, var)
    w = C.gate_window(yraw, yf, c["start_s"])
    d_pre = float(np.abs(w["G"] - G_old[round(RR.PRE_S * 100):]).max())
    stored = json.loads((OUT / "lowpass" / "work" / f"{clip}_{var}.json").read_text())["gates"]
    q_old = J.read_csv(OUT / "lowpass" / "work" / f"{clip}_{var}.csv")
    d_q = float(np.abs(np.asarray(w["q50"]) - np.asarray(q_old)).max()) if len(q_old) == len(w["q50"]) else None
    print(json.dumps(dict(clip=clip, variant=var, start_s=c["start_s"], max_abs_diff_deg_pre_H1_target=d_pre, gate_passed_new=bool(w["passed"]), gate_passed_stored=stored["passed"],
                          parts_equal=w["parts"] == stored["parts"], max_abs_diff_deg_realised_vs_csv=d_q)))


if __name__ == "__main__":
    main(*sys.argv[1:3])
