# Planner brief: T1b posture-change vocabulary fails its stop rule (2026-11-15)

TO: planner. FROM: overseer, via Kosta. WO41 (E1 baseline) stopped before training on 7.63.8's posture rule: "256 entries ... report the
variance of posture change explained (STOP if < 0.9)". Everything that does not depend on it continues (cortex precompute, rules note,
facts, label clips). Causality list is pushed (`docs/T1B_CAUSAL.md`, branch body-t1b).

## Result (overseer recompute from the builder's saved tokens and centres)

Data: 0.5 s posture-change vectors (5 joints, standardised per joint), FineDance train split, 4 copies: 101,760 tokens; validation 17,840.
Builder: k-means++, 200 iterations, 2 seeds. Overseer: own k-means (60 iterations, seed 1) and the builder's stored centres.

| quantiser | entries in the head | variance explained, train | validation |
|---|---|---|---|
| builder's 256 centres | 256 | 0.847 | 0.838 |
| k-means 256 (overseer) | 256 | 0.846 | 0.838 |
| k-means 512 | 512 | 0.883 | 0.874 |
| k-means 1024 | 1024 | 0.912 | 0.901 |
| residual 2 x 256 (coarse + correction, as the gesture vocabulary) | 2 heads x 256 | 0.971 | 0.967 |
| 16 bins per joint, 5 joints separately | 5 heads x 16 | 0.985 | 0.984 |

Builder's reading: the deltas are heavy-tailed (kurtosis 5.6-12.7) and nearly uncorrelated across joints (largest off-diagonal correlation
0.14), so one 5-D codebook saturates slowly.

## Questions

**Q1. Posture head.**
- (a) Residual 2 x 256: two categorical heads (coarse, then correction given coarse), the same construction as the 2 x 1024 gesture
  vocabulary; 0.967 on validation; keeps the joints coupled (one choice moves all 5 together). **[recommended]**
- (b) One codebook of 1024: clears 0.9 by 0.001 on validation, fragile.
- (c) 16 bins per joint, 5 independent heads: 0.984, but the joints are sampled separately, so the model can produce combinations no
  human made (correlation is small, 0.14, but not zero).
- (d) Keep 256 and lower the threshold to 0.83 (post hoc).

**Q2.** If (a): the two posture stages are predicted the same way as the two gesture-code stages (stated in `T1B_RULES.md`), and the
loss stays the sum of the cross-entropies with equal weights, one term per head (gesture coarse, gesture residual, vigour, posture coarse,
posture residual). Confirm, or fix the weights. **[recommended: confirm]**

**Q3.** Record as 7.70.
