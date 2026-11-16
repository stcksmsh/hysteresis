# Planner brief: posture-vs-gesture diagnostic (7.74 Q4) and the GO for A (2026-11-16)

TO: planner. FROM: overseer (via Kosta). Answers please together with the open `docs/PLANNER_BRIEF_VIEWINGS.md` (7.75), as 7.77 if 7.75
is answered separately.

## What ran

WO46 part 1, branch `body-diag`, merged into `body` (0761c93).
- Rules `docs/DIAG_RULES.md` pushed before the run.
- Material as WO44: 37 FineDance validation + test songs, 60 s, decoder A1, realised stage.
- Swaps, aligned token slot by token slot:
  - (i) the control's or model's gesture codes with HUMAN posture knots;
  - (ii) HUMAN gesture codes with the control's or model's posture knots.
- Posture here = the change-based posture entries that E1 used (quantised deltas from a fixed start).
- Report `docs/DIAG_REPORT.md`.

## Results (overseer recomputed from the per-song values; all match; tests 4/4)

Lamp power above 3 Hz, ratio to continuous human, mean of per-song (median); frozen share (human 0.095):

| material | as decoded | own gesture + human posture | human gesture + own posture |
|---|---|---|---|
| retrieval (37 songs) | 3.65 (1.71), frozen 0.254 | 1.46 (1.06), frozen 0.064 | 2.52 (1.75), frozen 0.161 |
| random chunks (37) | 4.47 (3.69), frozen 0.224 | 1.99 (1.51), frozen 0.033 | 2.93 (2.49), frozen 0.164 |
| E1 model seed 41101 (17 test songs) | 4.43 (2.47), frozen 0.166 | 1.71 (1.38), frozen 0.030 | 2.35 (1.61), frozen 0.149 |

Reference: human chunks re-joined with A1 = 0.88 (0.82), frozen 0.100.

- **Most of the excess sits in the posture-knot sequence.**
  - Human posture brings the model from 4.43 to 1.71, and its frozen share from 0.166 to 0.030.
  - Human gestures with the model's posture stay at 2.35, frozen 0.149.
- The gesture codes carry a smaller part. Random chunks with human posture still sit at 1.99 [1.54, 2.49].
- Each swap lands between the two ends, so part of the excess comes from the two streams interacting; the split is not decomposed
  further.
- A few songs carry a large excess: means are well above medians.
- This agrees with 7.74 Q6: change-based posture was a spec error (drift). WO45's A already uses ABSOLUTE posture (7.73).

## Questions

**Q1. GO for A's training (WO45, waiting at its timing estimate).**
- (a) GO once 7.75 is ruled. Add to A's checks: lamp power above 3 Hz and frozen share of A's realised output against re-joined human A1,
  reported for the posture stream alone (A's posture + human gestures) and the gesture stream alone (A's gestures + human posture), as in
  this diagnostic. **[rec]**
- (b) GO now, without that split.
- (c) Hold A until an absolute-posture version of this diagnostic is run on the controls (retrieval / random with absolute posture).

**Q2.** Record as 7.77, or inside 7.75 if answered together.
