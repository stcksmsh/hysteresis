"""WO45B: docs/A_REPORT.md from the training logs and the check JSONs. Brain env.   grammar_report.py"""
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
G = Path("/secondary/hyst-data/body/grammar")
SEEDS = (45101, 45102, 45103)
HEADS = ("code1", "code2", "vigour", "posture1", "posture2")


def f(x, d=3):
    return "n/a" if x is None else f"{x:.{d}f}"


def ci(v, d=3):
    return "n/a" if v is None or v[0] is None else f"{v[0]:.{d}f} [{v[1]:.{d}f}, {v[2]:.{d}f}]"


def training():
    L = ["## 1. Training", "", "All three seeds ran to the 40-epoch cap and were still improving at the cap (validation total fell in the last epochs; see the last-5-epoch column); the cap is the rules' (A_RULES section 4), not an early stop. `best.pt` = the epoch with the lowest validation total (here the last or next-to-last epoch).", "",
         "| seed | best epoch | val total | train eval-subset total | gap (val - train) | val no-controls total | aux train noisy | aux val | val total, last 5 epochs |", "|---|---|---|---|---|---|---|---|---|"]
    logs = {}
    for s in SEEDS:
        lg = json.loads((G / "runs" / f"seed{s}" / "log.json").read_text())
        logs[s] = lg
        b = int(np.argmin([e["val"]["total"] for e in lg]))
        e = lg[b]
        L.append(f"| {s} | {b + 1} | {e['val']['total']:.3f} | {e['train_eval_subset']['total']:.3f} | {e['gap']['total']:.3f} | {e['val_no_controls']['total']:.3f} | {e['train_noisy']['aux']:.3f} | {e['val']['aux']:.3f} | "
                 + ", ".join(f"{x['val']['total']:.3f}" for x in lg[-5:]) + " |")
    L += ["", "Per head at the best epoch (validation / train eval-subset / gap), seed mean:", "", "| head | validation | train subset | gap | validation without controls |", "|---|---|---|---|---|"]
    for h in HEADS:
        v, t, n = [], [], []
        for s, lg in logs.items():
            e = lg[int(np.argmin([x["val"]["total"] for x in lg]))]
            v.append(e["val"][h]), t.append(e["train_eval_subset"][h]), n.append(e["val_no_controls"][h])
        L.append(f"| {h} | {np.mean(v):.3f} | {np.mean(t):.3f} | {np.mean(v) - np.mean(t):.3f} | {np.mean(n):.3f} |")
    L += ["", "Per-epoch table (seed 45101; validation per head, no-controls total, aux), every 5th epoch:", "", "| epoch | train noisy total | train subset total | val total | no controls | aux val | " + " | ".join(HEADS) + " |", "|---|---|---|---|---|---|" + "---|" * 5]
    for e in logs[SEEDS[0]]:
        if e["epoch"] % 5 == 0 or e["epoch"] == 1:
            L.append(f"| {e['epoch']} | {sum(e['train_noisy'][h] for h in HEADS):.3f} | {e['train_eval_subset']['total']:.3f} | {e['val']['total']:.3f} | {e['val_no_controls']['total']:.3f} | {e['val']['aux']:.3f} | "
                     + " | ".join(f"{e['val'][h]:.2f}" for h in HEADS) + " |")
    L += ["", "The controls help: validation total without controls is higher by " + ", ".join(f"{logs[s][-1]['val_no_controls']['total'] - logs[s][-1]['val']['total']:.2f}" for s in SEEDS) + " nats (seeds, last epoch). Full per-epoch logs: `grammar/runs/seed*/log.json`.", ""]
    return L


def checks():
    R = {s: json.loads((G / "checks" / f"seed{s}.json").read_text()) for s in SEEDS if (G / "checks" / f"seed{s}.json").exists()}
    L = ["## 2. A checks (200 held-out starts, 2 samples each, song bootstrap 95 % intervals, seeds shown separately)", ""]
    L += ["### 2.1 Residual-code utilisation", "", "| seed | stage-2 codes used | perplexity | H(c2) | H(c2 given c1) | mutual information | model entropy of the code-2 head | decoded stage-2 effect (RMS ratio, median [quartiles]) |", "|---|---|---|---|---|---|---|---|"]
    for s, r in R.items():
        x = r["residual"]
        L.append(f"| {s} | {x['stage2_codes_used_share']:.3f} | {x['stage2_perplexity']:.0f} | {x['H_c2_nats']:.2f} | {x['H_c2_given_c1_nats']:.2f} | {x['mutual_information_nats']:.2f} | {x['model_mean_entropy_c2_head_nats']:.2f} | "
                 f"{x['decoded_stage2_rms_ratio_median']:.3f} {x['decoded_stage2_rms_ratio_quartiles']} |")
    meas = ["vigour", "height", "sharp", "pause", "dirz", "acccom", "dirchg", "basespeed"]
    L += ["", "### 2.2 Intervention matrix (effect = mean over starts of output(high) - output(low), in sd of the human starts' own window means; expected sign positive; accent = back-loaded minus front-loaded centre of mass)", ""]
    for s, r in R.items():
        L += [f"**seed {s}**", "", "| varied control | " + " | ".join(meas) + " |", "|---|" + "---|" * len(meas)]
        for c, v in r["intervention"].items():
            L.append(f"| {c} | " + " | ".join(ci(v["effect"][m], 2) for m in meas) + " |")
        L.append("")
    L += ["Held-out combinations (effect of the first control at the other's low / high level, and of the second at the first's low / high):", ""]
    for s, r in R.items():
        L += [f"**seed {s}**", "", "| pair | effect | value |", "|---|---|---|"]
        for p, d in r["combinations"].items():
            for k, v in d.items():
                L.append(f"| {p} | {k} | {ci(v, 2)} |")
        L.append("")
    L += ["### 2.3 Control substitution (std abs error between request and realised output, lower = closer; Pearson of the realised output with the request)", ""]
    for s, r in R.items():
        L += [f"**seed {s}**", "", "| request \\ output of | own | other | shuffled | constant |", "|---|---|---|---|---|"]
        for k in ("own", "other", "shuffled", "constant"):
            L.append(f"| {k} | " + " | ".join(ci(r["substitution"][f"request_{k}__output_{o}"]["std_abs_err"], 2) for o in ("own", "other", "shuffled", "constant")) + " |")
        L.append("")
        L.append("Pearson of output with its own request: " + "; ".join(f"{k}: {ci(r['substitution'][f'request_{k}__pearson_with_own_request'], 2)}" for k in ("own", "other", "shuffled")) + "")
        L.append("")
    L += ["### 2.4 Jitter and frozen share against re-joined human A1 (HJ), and the posture/gesture split (7.74 Q4, DIAG method)", "",
          "A = A's posture + A's gestures; A_posture_human_gesture = A's posture knots with the human's gesture codes; human_posture_A_gesture = the reverse; HJ = the human window re-decoded by A1. p_gt3 = share of lamp speed power above 3 Hz.", ""]
    for s, r in R.items():
        L += [f"**seed {s}**", "", "| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |", "|---|---|---|---|---|---|"]
        for k, v in r["jitter_frozen"].items():
            L.append(f"| {k} | {ci(v['p_gt3_mean'], 4)} | {ci(v['ratio_to_HJ'], 2)} | {ci(v['frozen_any_share'], 3)} | {ci(v['frozen_frame_share'], 4)} | {ci(v['dirchg'], 2)} |")
        L.append("")
    L += ["### 2.5 Coherence over 2 s (L = 4 tokens) and 4 s (L = 8)", "", "Control cosine = mean cosine between the standardised (vigour, height, sharpness, pause) vectors of tokens k and k + L; family repeat = share of tokens whose gesture family (code 1 in 32 k-means families) equals that L tokens earlier.", ""]
    for s, r in R.items():
        c = r["coherence"]
        L += [f"**seed {s}**", "", "| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |", "|---|---|---|---|---|"]
        for name in ("human", "A", "A_motif_ablated"):
            L.append(f"| {name} | " + " | ".join(ci(c[name][k]["value"], 3) for k in ("ctl_cos_L4", "ctl_cos_L8", "family_same_L4", "family_same_L8")) + " |")
        L.append("| ratio A / human | " + " | ".join(ci(c["A"][k]["ratio_to_human"], 2) for k in ("ctl_cos_L4", "ctl_cos_L8", "family_same_L4", "family_same_L8")) + " |")
        L.append("| ratio ablated / human | " + " | ".join(ci(c["A_motif_ablated"][k]["ratio_to_human"], 2) for k in ("ctl_cos_L4", "ctl_cos_L8", "family_same_L4", "family_same_L8")) + " |")
        L.append("")
    return L


def main():
    L = ["# A report: motor grammar conditioned on controls (WO45 / WO45B)", "",
         "Binding: `docs/A_RULES.md` with addendum 1. Numbers only, no verdict. Seeds 45101-45103; checks on 200 held-out starts (FineDance 100, AIOZ 50, PhantomDance 25, Motorica 25; validation + test; at most 2 per song), 2 samples each, nucleus 0.9, first 4 tokens teacher forced, style triple pinned to the window's own. Realised stage throughout (guard, spinal, limiter, servo, v2p). Control refinements: `docs/CONTROLS_REFINE_REPORT.md`.", ""]
    L += training() + checks()
    refs = G / "look" / "excerpts.json"
    if refs.exists():
        L += ["## 3. S-B clip candidates", "", "Manifest `grammar/look/manifest.json` (not served). Excerpts (song, token start, song time, V1/V2 sharpness match):", ""]
        for m in json.loads(refs.read_text()):
            v = m["v1_v2_matching"]
            L.append(f"- E{m['excerpt']:02d} {m['song']} window {m['window']} token {m['token_start']} t = {m['song_time_s']:.1f} s; V1 vs V2 matched on {v.get('matched_on', 'requested controls')}: chosen pair realised sharpness {v['P']:.5f} vs {v['Q']:.5f} "
                     f"(|diff| {v['abs_diff']:.5f}, best of {v.get('n_pairs_searched', 64)} pairs); the 8 V1 samples span {min(v['pool_realised_sharp_v1']):.3f}-{max(v['pool_realised_sharp_v1']):.3f} (mean {v['pool_mean_v1']:.3f}), the 8 V2 samples "
                     f"{min(v['pool_realised_sharp_v2']):.3f}-{max(v['pool_realised_sharp_v2']):.3f} (mean {v['pool_mean_v2']:.3f}); requested-control sharpness {v['requested_sharp_own_controls']}; gesture code-1 tokens differing between a V1 and a V2 sample: {v['code1_tokens_differ_share_v1_vs_v2_sample0']:.2f}"
                     if "pool_mean_v1" in v else f"- E{m['excerpt']:02d} {m['song']} (old match fields)")
        L += ["", "A |diff| that rounds to 0.000 at three decimals is the minimum over 64 pairs of continuous values (about 1e-3 expected), so it is small by construction; the realised-sharpness spread of the candidates (above) shows the match is on motion produced, not on requested controls."]
    (HERE.parents[1] / "docs" / "A_REPORT.md").write_text("\n".join(L) + "\n")
    print("report written")


if __name__ == "__main__":
    main()
