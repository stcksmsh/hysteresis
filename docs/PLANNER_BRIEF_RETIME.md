# Planner brief: re-timed lamp analyses and token-level effect (BRAIN_SPEC 7.87 Q3 step 1 and Q4), 2026-11-19

TO: planner. FROM: overseer (via Kosta). Reports `docs/RETIME_REPORT_A.md`, tables `docs/RETIME_TABLES_A.md`, rules `docs/RETIME_RULES.md`; data
`/secondary/hyst-data/body/retime/a/`. Merged in `body` (75a0c50). Report only. Original results untouched. L(V1) = 0.35 s, L(V2) = 0.28 s: every
lamp-derived array is read L later, i.e. shifted earlier (the last L seconds of a window are dropped). Overseer recomputed the headline cells
below from `retime/a/tables.md`; they match the builder's report. Reproduction with L = 0 is exact (0.0 difference on 4,594 BAS
sequences, 0 of 310,065 rhythm rows).

## Result 1: do the lamp results change after re-timing? Little, and not toward coupling.

| analysis | what moved | numbers |
|---|---|---|
| WO47 lamp BAS (excess over chance, sigma 0.1 s) | 15 of 64 cells outside the original 95 % interval, largest change 0.017 | FineDance and PhantomDance stay within +-0.005, intervals include 0. Motorica V2 librosa excess -0.008 [-0.014, -0.003] -> +0.011 [+0.005, +0.017]; AIOZ V1 project grid -0.005 -> +0.005 |
| WO47 V3 offsets (FineDance) | per-file best offset moves by exactly +0.36 s (V1) / +0.28 s (V2); medians V1 -0.10 -> -0.04 s, V2 -0.14 -> -0.06 s (inside the original intervals) | offsets still spread over +-1 s; max correlation unchanged (median 0.035-0.042) |
| WO52 event locks (hold / change / burst vs onset, dropout, novelty, cortex) | 25 of 360 cells outside, largest 0.032; pooled 4 of 72 | **change** responses shrink and lose significance: all, change x cortex_total +0.180 @ -0.65 s (p 0.005) -> +0.077 @ +0.95 s (p 0.045); change x dropout_end +0.157 (p 0.005) -> +0.068 (p 0.144). **hold and burst keep their size; their peak lags move by -0.1 to -0.5 s, mostly -0.3** |
| WO53 B lamp rhythm column | 0 of 60 cells outside, every cell within 0.008 | pooled cluster share 0.398 vs 0.400; excess vs similar-tempo chance +0.019 vs +0.020 (period ratio is shift-invariant, as stated in the rules) |

Notes: the re-timed change-response peaks sit at the +0.95 s edge of the +-1 s window, so their lag is not meaningful; the original peak at
-0.65 s did not simply move by L. Per-dataset, AIOZ change x cortex_total goes +0.383 (p 0.005) -> +0.138 (p 0.010).
BAS and V3 do not become clearly coupled after re-timing (largest BAS excess +0.011, still within what the raw-joint chance model gives for
the other cells); the weak-coupling reading of the lamp stands, with two cells (Motorica V2, AIOZ V1 project) now slightly positive.

## Result 2: token-level effect (7.87 Q4)

- A's tokens are 0.5 s. L is 0.70 token (V1) and 0.56 token (V2); rounding to whole tokens would shift by 1 token, i.e. 0.15 s (V1) /
  0.22 s (V2) off L.
- Event-locked controls (vigour, height, sharpness, pause onset x 6 WO52 events) at lag 0: 3 of 120 cells change, largest 0.002.
- Control-vs-music correlations are small in both alignments: vigour x low-band r 0.11, vigour x onset 0.04, all others |r| <= 0.03
  (within-sequence, lags -1..+1 s). Peaks move by +0.2 to +0.8 s (vigour +0.4 and +0.3 against L 0.28-0.35); this is the expected
  bookkeeping of a shift, not a new effect.
- Nothing was rebuilt or trained.

## Round 2 of the mismatch test is built (WO55 B, body dd36b7b), not yet viewed

Re-timed by L, arm only (hint and trail removed at render time), shifts 4.0-6.0 s, all 10 different-song foils from another dataset (9 AIOZ,
1 PhantomDance), 0 songs shared with round 1, intro page, 20 pairs + 5 repeats, 25/25 checks pass. Kosta views it next; the 7.84 rule is unchanged;
this is the second and last round.

## Questions

**Q1. Reading of Result 1.** Record "re-timing does not move the lamp's weak coupling: BAS excess <= +0.011, V3 spread unchanged, rhythm
unchanged; hold and burst event responses keep their size with lags about -0.3 s; change responses weaken." Then lamp results stand on the
re-timed arrays from now on. **[recommended]** Alternatives: (b) leave the original arrays as the reference and report both; (c) rerun
WO52's change definition first (the change responses depended on the unshifted alignment).

**Q2. A3 data rebuild (Q4).** Align controls to music by exactly L, not by whole tokens.
- (a) Re-cut the controls and tokens at the re-timed times (shift the 50 Hz q50 rows by L, rebuild windows and tokens on the 0.5 s grid
  from there; drop the last L seconds of each window). **[recommended]** Cost: a data rebuild, no re-simulation.
- (b) Shift by one whole token (0.5 s), accepting 0.15-0.22 s error. (c) Keep the unshifted alignment and give B the lag as an input.
Given the small control-vs-music correlations (|r| <= 0.11), the alignment may change little in A; the rebuild is for correctness.

**Q3. Order.** Kosta views mismatch round 2 now; the combined "A3 controls and B senses" ruling follows after the result and the 7.83
positive control. Still open on the overseer's side: the 7.82 and 7.83 texts (Jyväskylä data check), and the A2 and CORTEX_EVENTS briefs not
yet at the planner. **[recommended: yes, in that order]**
