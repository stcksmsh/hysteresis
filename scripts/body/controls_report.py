"""WO43 report: docs/CONTROLS_REPORT.md from controls/{norm,counts}.json, stats/*.json, look/selection.json. Aggregates only for Motorica (no per-file numbers). Brain env."""
import json
from pathlib import Path

import numpy as np

OUT = Path("/secondary/hyst-data/body/controls")
DOC = Path(__file__).resolve().parents[2] / "docs" / "CONTROLS_REPORT.md"
DS = ("finedance", "aioz", "phantom", "motorica")
TITLE = {"finedance": "FineDance", "aioz": "AIOZ-GDANCE (calibrated keep list)", "phantom": "PhantomDance (look check pending)", "motorica": "Motorica (look check pending)"}
CAP = {"finedance": "", "aioz": "", "phantom": " Marked: look check pending.", "motorica": " Marked: look check pending."}
f2 = lambda x: "nan" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}" if abs(x) < 100 else f"{x:.1f}"
ci = lambda v: f"{f2(v[0])} [{f2(v[1])}, {f2(v[2])}]"


def main():
    nm = json.loads((OUT / "norm.json").read_text())
    cnt = json.loads((OUT / "counts.json").read_text())
    L = ["# Controls report (work order 43, BRAIN_SPEC 7.73 Steps 0a, 0b, 0c, clip candidates for 0b')", "",
         "Numbers only, no verdict. Rules: `CONTROLS_RULES.md` (pushed before any control value was computed). Source trajectory: realised `q50` (50 Hz) of every kept window of every copy. Intervals: 95 % percentile, bootstrap by song (200 resamples, seed 4301). "
         "Motorica: aggregates only; nothing per file. PhantomDance and Motorica: look check pending.", "", "## 1. What was computed", "",
         "| dataset | files (dancer x copy) | kept windows | tokens |", "|---|---|---|---|"]
    for ds in DS:
        c = cnt[ds]
        L.append(f"| {TITLE[ds]} | {c['files']} | {c['windows']} | {c['tokens']} |")
    L += ["", "Realised-stage agreement: share of windows whose re-simulated gate verdict equals the stored one: " + "; ".join(f"{ds} {json.loads((OUT / 'stats' / 'gate_agree.json').read_text())[ds]:.4f}" for ds in DS) if (OUT / "stats" / "gate_agree.json").exists() else "", ""]
    L += ["Constants fitted on FineDance train (kept windows, four copies; `controls/norm.json`):", "",
          f"- vigour: log(vj + 0.01) median {nm['vj']['median']:.3f}, MAD x 1.4826 {nm['vj']['mad']:.3f}; log(vl + 0.01) median {nm['vl']['median']:.3f}, {nm['vl']['mad']:.3f}; PC1 loadings {nm['vigour']['loadings'][0]:.3f}, {nm['vigour']['loadings'][1]:.3f}, PC1 sd {nm['vigour']['sd']:.3f}, eigenvalues {nm['vigour']['eigenvalues'][0]:.3f} / {nm['vigour']['eigenvalues'][1]:.3f} (PC1 share {nm['vigour']['eigenvalues'][1] / sum(nm['vigour']['eigenvalues']):.3f}).",
          f"- accent: A (p95 |a|) {nm['accent']['A']:.3f} m/s^2, J (p95 |jerk|) {nm['accent']['J']:.2f} m/s^3.", f"- lead: p90 of |w| per joint {[round(x, 1) for x in nm['p90_abs_w']]} deg/s.", f"- tokens used: {nm['n_tokens']} ({nm['n_windows']} windows).", ""]
    # ----------------------------------------------------------------------------------- 0b
    L += ["## 1b. Headline numbers (all taken from the tables below)", ""]
    for ds in DS:
        b = json.loads((OUT / "stats" / f"b_{ds}.json").read_text())
        c = json.loads((OUT / "stats" / f"c_{ds}.json").read_text())
        s = json.loads((OUT / "stats" / f"s_{ds}.json").read_text())["tokens"]
        top = sorted(((abs(v["spearman"][0]), k, v["spearman"][0]) for k, v in c["within"].items() if k.endswith("|0")), reverse=True)[:3]
        L.append(f"- {TITLE[ds]}: redundant pairs (|r| > 0.7 Pearson or Spearman) = {', '.join(k.replace('|', ' x ') for k in b['redundant'])}. Sharpness undefined in {b['nan_share']['sharp']:.3f} of tokens, pause_prob is 0 in "
                 f"{(np.array(b['dist']['pause_prob']['hist'])[0] / sum(b['dist']['pause_prob']['hist'])):.3f} of tokens (first histogram bin). Strongest within-song lag-0 Spearman: " + "; ".join(f"{k.split('|')[0]} x {k.split('|')[1]} {v:.3f}" for _, k, v in top)
                 + f". Motion boundaries within +-1 token of a music boundary: {s['hit_rate']:.3f} against {s['chance_rate']:.3f} by chance.")
    L.append("")
    L += ["## 2. Step 0b: numeric validation", ""]
    for ds in DS:
        b = json.loads((OUT / "stats" / f"b_{ds}.json").read_text())
        L += [f"### {TITLE[ds]}", f"{b['n_tokens']} tokens, {b['n_groups']} songs.{CAP[ds]} Tokens by split {b['tokens_by_split']}; share by copy {', '.join(f'{k} {v:.3f}' for k, v in b['token_share_by_copy'].items())}.", "",
              "| control | NaN share | median [CI] | q1 | q5 | q25 | q75 | q95 | q99 | between-song share [CI] |", "|---|---|---|---|---|---|---|---|---|---|"]
        for k in b["sc"] + b["extra"]:
            q = b["dist"][k]["q"]
            L.append(f"| {k} | {b['nan_share'][k]:.3f} | {ci(b['dist'][k]['median_ci'])} | " + " | ".join(f2(q[i]) for i in (0, 1, 2, 4, 5, 6)) + f" | {ci(b['varshare'][k])} |")
        L += ["", "20-bin histograms (counts; range = FineDance train p0.5 .. p99.5, values clipped into it):", ""]
        for k in b["sc"] + b["extra"]:
            h = b["dist"][k]["hist"]
            L.append(f"- {k} [{f2(b['dist'][k]['hist_range'][0])}, {f2(b['dist'][k]['hist_range'][1])}]: {h}")
        L += ["", "Pairwise correlations (Pearson | Spearman, bootstrap interval of each; **bold** = |r| > 0.7 in either):", "", "| pair | n | Pearson [CI] | Spearman [CI] |", "|---|---|---|---|"]
        for k, v in b["corr"]["pearson"].items():
            s = b["corr"]["spearman"][k]
            flag = k in b["redundant"]
            w = (lambda x: f"**{x}**") if flag else (lambda x: x)
            L.append(f"| {w(k.replace('|', ' x '))} | {v[3]} | {w(ci(v[:3]))} | {w(ci(s[:3]))} |")
        L += ["", "Redundant (|r| > 0.7): " + (", ".join(k.replace("|", " x ") for k in b["redundant"]) or "none"), ""]
        if "corr_by_split" in b:
            L += ["FineDance Pearson by split (point estimates) for the flagged pairs: " + "; ".join(f"{k.replace('|', ' x ')}: " + ", ".join(f"{s} {b['corr_by_split'][s][k]:.2f}" for s in b["corr_by_split"]) for k in b["redundant"]), ""]
    # ----------------------------------------------------------------------------------- 0c
    L += ["## 3. Step 0c: controls against acoustic measures (report only)", "",
          "Spearman rank correlation, lag 0 (control of token k, measure of token k). Global and within-song (song mean removed), intervals by bootstrap over songs; per-song = median [quartiles] over songs with >= 60 tokens and share of songs positive. Beat strength: FineDance only.", ""]
    for ds in DS:
        c = json.loads((OUT / "stats" / f"c_{ds}.json").read_text())
        L += [f"### {TITLE[ds]}", "", "| control | measure | global Spearman [CI] | within-song Spearman [CI] | per song median [q25, q75], share > 0 (n) |", "|---|---|---|---|---|"]
        for ctl in c["controls"]:
            for ms in c["measures"]:
                k = f"{ctl}|{ms}|0"
                if k not in c["global_"]:
                    continue
                ps = c["per_song"].get(k)
                L.append(f"| {ctl} | {ms} | {ci(c['global_'][k]['spearman'][:3])} | {ci(c['within'][k]['spearman'][:3])} | " + (f"{f2(ps['median'])} [{f2(ps['q25'])}, {f2(ps['q75'])}], {ps['share_positive']:.2f} ({ps['n']})" if ps else "") + " |")
        L += ["", "Within-song Spearman over lags -2..+2 tokens (-1 s .. +1 s; L > 0: the measure comes after the control's token), strongest |value| per control-measure pair marked with `*`:", "", "| control | measure | -2 | -1 | 0 | +1 | +2 |", "|---|---|---|---|---|---|---|"]
        for ctl in c["controls"]:
            for ms in c["measures"]:
                vals = [c["within"].get(f"{ctl}|{ms}|{lag}", {}).get("spearman", [np.nan])[0] for lag in c["lags"]]
                if np.isnan(vals).all():
                    continue
                a = int(np.nanargmax(np.abs(vals)))
                L.append(f"| {ctl} | {ms} | " + " | ".join(f"{f2(v)}{'*' if i == a else ''}" for i, v in enumerate(vals)) + " |")
        L.append("")
    # ----------------------------------------------------------------------------------- structure
    L += ["## 4. Structure layer (report only)", "", "Motion side: per window novelty / boundaries / repetition of the control vector (rules 4). Music side: the same routine on the token music features (44 ear + 32 mode columns) and, for FineDance, the frozen cortex. "
          "Alignment = share of motion boundaries with a music boundary within +-1 token, against 20 circular shifts per song.", "",
          "| dataset | features | motion boundaries / window | music boundaries / min | motion repetition (mean) | music repetition (mean) | hit rate | chance | hit - chance [CI] | novelty Spearman (motion vs music, n) |", "|---|---|---|---|---|---|---|---|---|---|"]
    for ds in DS:
        s = json.loads((OUT / "stats" / f"s_{ds}.json").read_text())
        for v in ("tokens", "cortex"):
            if v in s:
                r = s[v]
                L.append(f"| {ds} | {v} | {r['motion_boundaries_per_window']:.2f} | {r['music_boundaries_per_min']:.2f} | {r['motion_repetition_mean']:.3f} | {r['music_repetition_mean']:.3f} | {r['hit_rate']:.3f} | {r['chance_rate']:.3f} | {r['hit_minus_chance']:.3f} [{r['hit_minus_chance_ci'][0]:.3f}, {r['hit_minus_chance_ci'][1]:.3f}] | {r['novelty_spearman']:.3f} ({r['n_novelty_pairs']}) |")
    L.append("")
    # ----------------------------------------------------------------------------------- clips
    sp = OUT / "look" / "selection.json"
    if sp.exists():
        sel = json.loads(sp.read_text())
        C = ("vigour", "height", "sharp", "pause_prob", "accent_mean")
        L += ["## 5. Clip candidates for Step 0b' (FineDance validation + test, V1/V2, 8 s)", "",
              f"Pool {sel['pool']} candidate clips; p10 / p90 per control: " + "; ".join(f"{c} {f2(sel['p10'][c])} / {f2(sel['p90'][c])}" for c in C) + f"; pool sd {', '.join(f'{c} {f2(sel['sd'][c])}' for c in C)}. Matching rule: rules section 8 (shortlist {sel['pairs'][0]['shortlist']}, residual = sum of |difference| / pool sd over the other four controls).", "",
              "| pair | control | clip (low) | clip (high) | variant | residual | low values (" + ", ".join(C) + ") | high values | other-control differences (sd units) |", "|---|---|---|---|---|---|---|---|---|"]
        for n, p in enumerate(sel["pairs"]):
            lo, hi = p["low"], p["high"]
            cl = lambda d: f"{d['lane']} w{d['win']} t{d['start']}"
            L.append(f"| P{n + 1:02d} | {p['name']} | {cl(lo)} (C{2 * n + 1:02d}) | {cl(hi)} (C{2 * n + 2:02d}) | {('V1', 'V2')[lo['copy']]} | {p['residual']:.2f} | " + ", ".join(f2(lo['values'][c]) for c in C) + " | " + ", ".join(f2(hi['values'][c]) for c in C) + " | " + ", ".join(f"{k} {v:.2f}" for k, v in p["residual_sd_units"].items()) + " |")
        L.append("")
    DOC.write_text("\n".join(L) + "\n")
    print("report written", DOC)


if __name__ == "__main__":
    main()
