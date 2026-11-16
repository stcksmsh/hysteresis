"""WO41: assemble docs/T1B_REPORT.md from the saved results (training logs, T2 summary, tables). Brain env. Narrative text is in this file; every number comes from the data or the generated tables."""
import json
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path("/secondary/hyst-data/body/t1b")
SEEDS = (41101, 41102, 41103)
HEADS = ("code1", "code2", "vigour", "posture1", "posture2")
CHANCE = dict(code1=np.log(1024), code2=np.log(1024), vigour=np.log(32), posture1=np.log(256), posture2=np.log(256))


def curves():
    L = []
    for s in SEEDS:
        log = json.loads((OUT / "e1" / f"seed{s}" / "log.json").read_text())
        best = min(range(len(log)), key=lambda i: sum(log[i]["val"].values()))
        L += [f"### Seed {s} (best epoch {best}, {len(log)} epochs, {np.mean([r['secs'] for r in log]) / 60:.1f} min per epoch)", "",
              "| epoch | val total | train-subset total | gap | " + " | ".join(f"val {h}" for h in HEADS) + " | " + " | ".join(f"train {h}" for h in HEADS) + " | lr |", "|" + "---|" * (5 + 2 * len(HEADS) + 1)]
        for r in log:
            L.append(f"| {r['epoch']}{' *' if r['epoch'] == best else ''} | {sum(r['val'].values()):.3f} | {sum(r['train_eval'].values()):.3f} | {r['gap']:.3f} | " + " | ".join(f"{r['val'][h]:.3f}" for h in HEADS)
                     + " | " + " | ".join(f"{r['train_eval'][h]:.3f}" for h in HEADS) + f" | {r['lr']:g} |")
        L.append("")
    return "\n".join(L)


def genres():
    sp = {}
    for g in json.loads((Path("/secondary/hyst-data/body/t0/split.json")).read_text())["groups"]:
        if "finedance" in g["dataset"]:
            for m in g["members"]:
                sp[m] = g["split"]
    rows = []
    for k, s in sp.items():
        if s != "train":
            continue
        n = len(np.load(OUT / "tokens" / f"{k}__V1.npz")["code1"])
        if n == 0:
            continue
        j = json.loads((Path("/secondary/hyst-data/datasets/finedance/data/finedance/label_json") / f"{k.split('_')[1]}.json").read_text())
        rows.append(j["style1"])
    return dict(Counter(rows)), len(rows)


def main():
    summ = json.loads((OUT / "t2" / "summary.json").read_text())
    tables = (ROOT / "docs" / "T1B_T2_TABLES.md").read_text()
    g, n = genres()
    swap = {s: json.loads((OUT / "e1" / f"seed{s}" / "t2" / "swap.json").read_text()) for s in SEEDS}
    div = {s: json.loads((OUT / "e1" / f"seed{s}" / "t2" / "diversity.json").read_text()) for s in SEEDS}
    st = summ["stops"]
    stop_names = {s: [c for c, v in st[str(s)].items() if v["stop"]] for s in SEEDS}
    txt = f"""# T1b E1 report (work order 41; BRAIN_SPEC 7.63-7.71)

No verdict (Kosta decides). One arm. FineDance only (4 copies), pooled V1/V2/mirrored, ear + cortex listener (rhythm 192 / affect 64), planner over the frozen 2 x 1024 vocabulary with a residual 2 x 256 posture head (7.70).
Rules: `docs/T1B_RULES.md`. Causality: `docs/T1B_CAUSAL.md`. Facts: `docs/T1B_FACTS.md`. All T2 numbers: `docs/T1B_T2_TABLES.md` (generated; copied below). Per-song values: `t1b/e1/seed*/t2/measures.json`, `swap.json`, `diversity.json`.
Seeds 41101, 41102, 41103; every T2 number is the mean over held-out songs, with the seed mean and the min / max over seeds. STOP = a stop rule of the spec; reported as is, nothing was tuned after seeing it.

## 1. STOP checks (value and threshold, per seed)

{tables.split('## Measures')[0].split('## STOP checks (per seed)')[1].strip()}

Reading (numbers only):
- **Swapped music** (7.64.6 / 7.68.5, 3 tempo-matched partners from the validation pool, 14 of 17 songs had at least one partner, 3 had none, none needed half / double tempo): the mean log-likelihood gap is
  {', '.join(f"{swap[s]['mean_gap_nats']:+.3f} nats (95 % interval {swap[s]['ci95'][0]:+.2f} to {swap[s]['ci95'][1]:+.2f})" for s in SEEDS)} for the three seeds; every interval includes 0 -> STOP on all three seeds.
- Stops that fired: {json.dumps({str(k): v for k, v in stop_names.items()})}.
- Training validation per head (section 2) shows the cause that the data supports: the two gesture-code heads barely beat, and for code 2 fall below, a uniform guess on validation, while vigour and posture heads learned; the model overfits the code stages (train-subset code losses 5.8-6.3 vs validation 6.7-7.1).

## 2. Training (E1)

Early stopping on validation total cross-entropy (patience 5, lr halved after 2 stale epochs, cap 60); train-subset = fixed 16 train songs in evaluation mode. Chance per head (uniform): code1 {CHANCE['code1']:.3f}, code2 {CHANCE['code2']:.3f}, vigour {CHANCE['vigour']:.3f}, posture1 {CHANCE['posture1']:.3f}, posture2 {CHANCE['posture2']:.3f}.
Train sequences per FineDance genre (style1; {n} train sequences after dropping fd_192, 17 s, no 20 s window): {json.dumps(g)}.
Parameters: 1,926,944 (listener 0.37 M, planner 1.56 M; `docs/T1B_FACTS.md` section c).

{curves()}

## 3. T2 measures (copied from `T1B_T2_TABLES.md`)

{tables.split('## Measures')[1].strip() if False else '## Measures' + tables.split('## Measures')[1]}

## 4. Reports named in the work order

- **Diversity (7.63.8, 8 samples per song):** mean pairwise sample distance {', '.join(f"{div[s]['mean_pairwise_samples']:.1f}" for s in SEEDS)} (seeds) vs {div[SEEDS[0]]['mean_pairwise_human']:.1f} between the 4 human copies of the same song (RMS in scaled units over the 60 s). Nearest-human-copy share of samples (V1 / V2 / V1m / V2m), seed 41101: {', '.join(f"{c} {div[SEEDS[0]]['nearest_share'][c]:.2f}" for c in ('V1', 'V2', 'V1m', 'V2m'))}; the other seeds are in `diversity.json`.
- **2 s history truncation (7.64.6):** mean change of the per-token cross-entropy when the listener hears only the last 2 s: {', '.join(f"{swap[s]['mean_trunc_minus_true']:+.3f} nats" for s in SEEDS)} (negative = the truncated listener fits slightly better).
- **Event response, emotion-channel correlations, self-similarity at 2 / 8 / 30 s, beat alignment, endpoint jerk and direction changes, approximate repetition, commanded vs realised, gate shares, controls:** in the measures table (rows `event_*`, `vigour_energy_corr`, `posture_height_energy_corr`, `selfsim_*tok`, `beat_alignment`, `hand_jerk`, `hand_dir_changes_per_s`, `approx_repeat`, `cmd_vs_real_rms`, `gate_share`); columns human / retrieval / random / model.
  Self-similarity windows 4, 16, 60 tokens = 2, 8, 30 s. Gate share = share of the three 20 s windows of each dance that pass the 1.25 gates through the full body pipeline; guard_share, limit_hit_share and speed_sat_share are the guard, joint-limit and limiter-saturation shares.
- **Held-out set:** {len(json.loads((OUT / 'e1' / 'seed41101' / 't2' / 'measures.json').read_text()))} of the 23 FineDance test songs (60 s dance from 10 s needs 70 s of audio and tokens; the others are shorter).

## 5. What was not done, and deviations (flagged)

- **AIOZ held-out (report-only, 7.63.3) and the AIOZ-only code share (7.66.3) were NOT run:** the cortex states for the 41 AIOZ test groups and the token encoding of AIOZ dancers were not built (extra scope; not needed for the FineDance result). Say if you want them.
- **Music-label probes** dropped by 7.71; replaced by the two report-only correlations (vigour vs ear energy, posture height vs ear energy: rows in the table).
- **Audio shorter than motion** (fd_043, fd_059) and the zero-token song fd_192: tokens past the audio end dropped; fd_192 skipped (`T1B_FACTS.md`, night log).
- **Jitter STOP baseline:** the rule says "the training data's"; the human copies of the same held-out windows, realised through the same simulation, were used (the T1a2 realised numbers cover other windows). The model's power above 3 Hz is higher than human on several joints; acceleration sign changes are close to human.
- **Human reference** keeps all rows regardless of the T0 gate (most human windows fail some gate: human gate share in the table); the likelihood tests are masked by the T0 `ok` flag.
- **Controls** (retrieval, random chunks) are single runs (seeded), identical across the model seeds. They concatenate raw training chunks (no decoder), so token-code measures are empty for them.
- **Posture** is integrated from sampled posture-change entries with no feedback to the human posture; ranges grow beyond the human's in 2 of 3 seeds (section 3 rows `posture_range`), and `limit_hit_share` / `guard_share` show how often the commanded rows reach the joint limits / the guard.
- **Event detection** (report-only): onsets = ear column 40 above its song 95th percentile, local maxima within +-0.1 s, ties and neighbours closer than 0.1 s counted once; energy jumps = the 3 s trailing mean of the standardised RMS column rises by more than 1.0 (corpus sd) over the previous 3 s; slow changes = cosine distance of layer-4 mean states over 1 s blocks above the song 95th percentile. Counts per dance are in `n_events`; energy jumps are rare (0.35 per dance), so `event_energy` is poorly determined.
- Numbers are not comparable to AIOZ; no viewing, no clips of generated dance, no T3.
"""
    (ROOT / "docs" / "T1B_REPORT.md").write_text(txt)
    print("written", len(txt))


main()
