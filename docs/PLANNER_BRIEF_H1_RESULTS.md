# Planner brief: H1 (hippocampus toy) results, 2026-11-04

Branch `body` (merge of `body-h1`). The overseer recomputed every number below from the run logs in `/secondary/hyst-data/brain/h1/` and
reran the unit tests (162 OK on the merged branch, 1 cuda skip).

## What ran

Plan §5, as written: (a) hindsight retrieval loss, weight 0.1; (b) scheduled sampling, oracle pointer handed over to retrieval over the first
50 % of training; novelty lane every 0.5 s. All behind default-off flags (flags off = B7 unchanged). Toy as in B7 (reduced width, seed 0,
lr 3e-3, 1,500 steps planned, 8 sequences per step). Every run ended early on the toy's existing flat-loss stop (steps 800–1,300).

- **Try 1:** the mechanisms above.
- **Try 2:** one change, committed before its runs: the hindsight loss counts a row only when the best stored entry's replay error is lower
  than a zero replay's (the replay would have helped). Reason given: try 1's training made retrieval worse than untrained, and on blocks with
  no useful entry the argmin target is noise. The reason is a reading the builder did not test.

## Results (bar: BRAIN_SPEC §7.10 R3)

| Design | Ratio, try 1 | Ratio, try 2 | T1a source share / recognition median vs p95, try 1 | Same, try 2 |
|---|---|---|---|---|
| A, iid noise | 1.084 | 1.140 | 0.263 / 0.282 vs 0.518 | 0.384 / 0.456 vs 0.649 |
| B, levels + clock | 0.790 | 0.812 | 0.902 / 0.580 vs 0.635 | 0.830 / 0.630 vs 0.686 |
| C, smooth | 0.962 | 1.139 | 0.643 / 0.320 vs 0.599 | 0.696 / 0.489 vs 0.669 |
| Oracle, design A | 0.329 | — | forced | — |

The ratio needs ≤ 0.5 on A and on one other design. T1a needs share ≥ 0.5 and recognition median above p95.

- T1b fails on every design in both tries. T1a fails on every design in both tries.
- Untrained, design A passes T1a (share 0.98, recognition 0.73 vs p95 0.38). Training with either version of the hindsight loss lowers
  retrieval below the untrained level.
- The oracle passes T1b (0.329), as in B7 (0.348): the downstream path works when the pointer is right.
- Novelty lane (no pass rule), repeat mean against outside mean: try 1 A 0.478/0.686, B 0.458/0.689, C 0.414/0.565; try 2 A 0.533/0.750,
  B 0.443/0.672, C 0.464/0.640. It is lower during the repeat on every run.

## Outcome, by the plan's own rule

Both tries failed. The hippocampus stays off. C1–C3 are not claimed, and the monitor never shows recall. M4 is dropped from the order.

## Questions

1. **Confirm the outcome.** Recommendation: yes, as §5 says.
2. **The novelty lane** works without the trained retrieval (it uses only the store and the keys). It is lower during repeats on every run.
   Could it be a monitor lane under a mechanism name only (for example "1 − max similarity to its stored past")? There would be no claim, and
   C3 stays unclaimed. Recommendation: allow it as a mechanism-named lane, since no check is attached.
3. **Anything later?** Untrained retrieval passes T1a on design A. A frozen, untrained retrieval with only the relay trained was not tested.
   Recommendation: park it. Do not reopen H1 now.
