"""WO49: docs/A2_REPORT.md = training + checks of the retrained A (grammar2, seeds 49101-49103), side by side with A1 (WO45B fix 1, grammar/, seeds 45101-45103). Brain env.   grammar_report2.py"""
import json
import re
from pathlib import Path

import numpy as np

import grammar_report as GR

HERE = Path(__file__).resolve().parent
G1, G2 = GR.G, Path("/secondary/hyst-data/body/grammar2")
S1, S2 = (45101, 45102, 45103), (49101, 49102, 49103)
MEAS = ["vigour", "height", "sharp", "pause", "dirz", "acccom", "dirchg", "basespeed"]
DIAG = dict(vigour="vigour", height="height", accent="acccom", sharp="sharp", direction="dirz", pause="pause")


def load(g, seeds):
    return {s: json.loads((g / "checks" / f"seed{s}.json").read_text()) for s in seeds if (g / "checks" / f"seed{s}.json").exists()}


def m(vals):
    return "n/a" if not vals else f"{np.mean(vals):.3f}"


def side(R1, R2):
    L = ["## 3. Side by side: A1 (WO45B fix 1, seeds 45101-3) vs A2 (this run, seeds 49101-3), mean over seeds (each seed's own song-bootstrap interval is in section 2)", "",
         "A1 numbers are those of `grammar/checks/seed451*.json` after addendum 2 (pause 0 / 1.0). The first-run table of `A_REPORT.md` at commit 1250e2c used pause = p10 / p90 (both 0), so its pause effect was exactly 0.", ""]
    for g, s in ((G1, S1), (G2, S2)):
        lg = {x: json.loads((g / "runs" / f"seed{x}" / "log.json").read_text()) for x in s}
        L.append(f"- {'A1' if g == G1 else 'A2'}: epochs " + ", ".join(str(len(v)) for v in lg.values()) + "; best validation total " + ", ".join(f"{min(e['val']['total'] for e in v):.3f}" for v in lg.values()))
    L += ["", "### 3.1 Intervention diagonal (effect of varying a control on its own measure, sd units; expected positive)", "", "| control | A1 | A2 |", "|---|---|---|"]
    for c, k in DIAG.items():
        L.append(f"| {c} | " + " | ".join(m([r["intervention"][c]["effect"][k][0] for r in R.values()]) for R in (R1, R2)) + " |")
    L.append("| pause (high = train p99) | " + " | ".join(m([r["intervention"]["pause_high_p99"]["effect"]["pause"][0] for r in R.values() if "pause_high_p99" in r["intervention"]]) for R in (R1, R2)) + " |")
    L += ["", "Largest absolute off-diagonal effect per varied control (cross-talk, report only):", "", "| control | A1 (measure: effect) | A2 (measure: effect) |", "|---|---|---|"]
    for c, k in DIAG.items():
        cells = []
        for R in (R1, R2):
            best = max(((mm, np.mean([r["intervention"][c]["effect"][mm][0] for r in R.values()])) for mm in MEAS if mm != k), key=lambda x: abs(x[1]), default=("n/a", float("nan")))
            cells.append(f"{best[0]}: {best[1]:.2f}")
        L.append(f"| {c} | " + " | ".join(cells) + " |")
    L += ["", "### 3.2 Substitution (std abs error of the request against the realised output of the same sequence; lower is closer)", "", "| request / output | A1 | A2 |", "|---|---|---|"]
    for k in ("own", "other", "shuffled", "constant"):
        L.append(f"| request {k}, output own | " + " | ".join(m([r["substitution"][f"request_{k}__output_own"]["std_abs_err"][0] for r in R.values()]) for R in (R1, R2)) + " |")
    L.append("| Pearson, output own vs request own | " + " | ".join(m([r["substitution"]["request_own__pearson_with_own_request"][0] for r in R.values()]) for R in (R1, R2)) + " |")
    L += ["", "### 3.3 Jitter, frozen share, split (A / HJ ratio of p_gt3; frozen windows share)", "", "| condition | ratio A1 | ratio A2 | frozen windows A1 | frozen windows A2 |", "|---|---|---|---|---|"]
    for k in ("A", "HJ", "A_posture_human_gesture", "human_posture_A_gesture"):
        L.append(f"| {k} | " + " | ".join(m([r["jitter_frozen"][k]["ratio_to_HJ"][0] for r in R.values()]) for R in (R1, R2)) + " | "
                 + " | ".join(m([r["jitter_frozen"][k]["frozen_any_share"][0] for r in R.values()]) for R in (R1, R2)) + " |")
    L += ["", "### 3.4 Coherence ratio A / human (ratio of means over songs)", "", "| measure | A1 | A2 |", "|---|---|---|"]
    for k in ("ctl_cos_L4", "ctl_cos_L8", "family_same_L4", "family_same_L8"):
        L.append(f"| {k} | " + " | ".join(m([r["coherence"]["A"][k]["ratio_to_human"][0] for r in R.values()]) for R in (R1, R2)) + " |")
    return L


def main():
    GR.G, GR.SEEDS = G2, S2
    R1, R2 = load(G1, S1), load(G2, S2)
    t = GR.training()
    t[2] = "All three seeds stopped early (patience 5 on the validation total) before the 100-epoch cap; `best.pt` = the epoch with the lowest validation total. Pause up-weighting as A_RULES addendum 3 (f = 1.471 / 1.268 / 1.000 / 1.935)."
    L = ["# A2 report: A retrained to convergence with pause up-weighting (WO49)", "",
         "Binding: `docs/A_RULES.md` with addenda 1-3. Numbers only, no verdict. Seeds 49101-49103; checks as WO45B (200 held-out starts, 2 samples each, nucleus 0.9, song bootstrap 95 %, same starts and check seeds). Per-start values: `grammar2/checks/seed<S>_values.npz`.", ""]
    L += [re.sub(r"`grammar/runs", "`grammar2/runs", x) for x in t]
    L += [x for x in GR.checks()]
    L += side(R1, R2)
    refs = G2 / "look" / "excerpts.json"
    if refs.exists():
        L += ["", "## 4. S-B clip candidates (not served)", "", "Manifest `grammar2/look/manifest.json`; room left for the motor-clock pairs of 7.78 Q7. Excerpts:", ""]
        for e in json.loads(refs.read_text()):
            v = e["v1_v2_matching"]
            L.append(f"- E{e['excerpt']:02d} {e['song']} window {e['window']} token {e['token_start']} t = {e['song_time_s']:.1f} s; V1/V2 realised sharpness {v['P']:.4f} vs {v['Q']:.4f} (|diff| {v['abs_diff']:.4f}); requested {v['requested_sharp_own_controls']}")
    (HERE.parents[1] / "docs" / "A2_REPORT.md").write_text("\n".join(L) + "\n")
    print("A2 report written")


if __name__ == "__main__":
    main()
