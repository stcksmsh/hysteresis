# Planner brief: Stage 3 build done, timed round, run launched (2026-11-09) — information, one optional question

From the Hysteresis overseer. ONE arm (permanent). Rules of record: `docs/BRAIN_SPEC.md` 7.39, 7.40. Build rules:
`docs/STAGE3_RULES_DATA_EVAL.md` (WO26A), `docs/STAGE3_RULES_TRAIN.md` (WO26B), both committed before their long runs. Code of record:
branch `body` a9fd858. All numbers below were checked or recomputed by the overseer unless marked.

## 1. What ran

- **WO26A (data, thresholds, bar evaluation):** new B7 epoch-6 pass storing the L4 state (3,176 songs, ~1 h). PCA on train songs only:
  top-8 explained variance 0.375, 0.111, 0.090, 0.068, 0.039, 0.032, 0.029, 0.023 (cumulative 0.767). Slow stream = 13 columns (8 L4 PCs,
  8 s surprisal integral, logpow L1-L4), train-corpus z-scored (overseer spot check on 300 train songs: means -0.10..0.04, sds 0.93-1.07;
  block counts match the K5 lanes). librosa tempo + log RMS for all 3,176 songs (held-out tempi identical to Stage 0's).
- **Thresholds (7.40.2), v47 replayed on v2f** (arm 0 of the three danced songs, 1,784 blocks, pass2 body config; no fallback needed):
  energy 0.3747 J/block; jerk 1.25 x 3.799e6 = 4.748e6 deg^2/s^6 (overseer recomputed the block-weighted means). Per-song v47 jerk varies:
  Instant Crush 7.1e6, Five Years 1.3e6, Presence 2.2e6.
- **WO26B (trainer):** as 7.39.4/7.40; tests pass (overseer reran 8 unit tests; smoke run: resume bit-identical, no NaN, rising-only
  multipliers, validation writes best.pkl).
- **Timed round** (6 threads, cores 6-11): 73.4 s per round after compile (one round measured), validation 200 s; 977 rounds + 5
  validations = **20.2 h**, within the 30 h box. **The Stage 3 run was launched without asking (7.39.4).**

## 2. Pass2 reference on the Stage 3 bars (357 held-out songs; `s3/eval_pass2/bars.json`)

| bar | pass2 | Stage 3 needs |
|---|---|---|
| (a) K5 external (a) / vs untrained | 0.943 [0.911, 0.977] / +0.922 | > 0 / > 0 |
| (b) machine 2AFC, interleaved | 0.468 [0.407, 0.528], 54 pairs; shuffled 0.491 | >= 0.75 |
| (c) between / within JS | 0.321 / 0.663 = 0.48 | >= 2 |
| (d) median occupied cells, 120 s | 385 (285 songs) | >= 577.5 |
| (e) songs with shoulder sd >= 8 deg | 0 % (median 3.76 deg) | >= 70 % |
| (f) check-csv, (e'1), (e'2) on 3 danced songs | all pass | pass |

(d) and (e) recomputed by the overseer from the Stage 0 pass2 rollouts (match). Pass2 used one program for all 144,095 blocks.

## 3. Facts you should know (no action unless you choose)

1. **Bar (c) on pass2 is 0.48, not "about 0.69".** 0.69 was Stage 0's half-vs-half within-song JS; the interleaved odd/even clips
   (7.36.3) give a larger within-song JS (0.663), so the ratio is lower. The bar (>= 2) is measured on the interleaved definition.
2. **Bar (b) uses 54 pairs, not Stage 0's 128:** the interleaved layout (30 s clips, 30 s gaps, >= 2 train and >= 2 test clips per song)
   needs songs >= 210 s; 125 held-out songs qualify, 54 tempo-matched pairs. CI half-width about 0.06.
3. **Energy budget:** trained pass2 used 0.363 J/block, the new energy threshold is 0.375. Stage 3 has about pass2's energy budget;
   v47 moves widely (shoulder sd 14-17 deg) at that energy, so bar (e) is not ruled out by it.
4. **Start-of-run constraint scale:** the starting policy's jerk is ~90x the threshold (pass2 untrained 4.56e8; trained pass2 5.8e5, 1/8
   of the threshold), so the jerk multiplier rose to 108 after one round and, being rising-only, stays high. Energy starts 2.5x over.
5. **Training design detail (builder, documented):** an InfoNCE batch is one anchor window + windows of its 7 nearest train songs, so a
   round of 16 windows has 2 anchors: 1,954 anchors over the run; neighbour windows can repeat.
6. **8 train songs have librosa tempo < 40 BPM (six are 0, librosa found no beat);** left as is (none in val or held-out).
7. **Correction of the overseer's own error:** the WO25 gaps brief (Q4) said pass2's external observer "reads hand and joint positions".
   It read joint-angle descriptors. The build follows 7.39.4 literally: the external observer reads a causal 1.5 s window of elbow, wrist
   and hand positions in metres (10 Hz, 135 inputs) and is 4-Lipschitz in metres; the internal observer stays in descriptor units.
8. Report-only Burger contrasts on pass2: shoulder sd vs B7 pulse proxy rho -0.03; wrist sd vs audio 50-200 Hz flux rho 0.07.

## 4. Optional question

**Q1. Energy threshold.** Keep 0.375 (v47-derived, as ruled) for this run (recommended: it is running; the threshold is reachable and
v47 shows wide motion within it), or rule a change for a round 2 only if bar (e) fails.
