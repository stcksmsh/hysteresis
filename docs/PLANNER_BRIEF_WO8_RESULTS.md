# Planner brief: work order 8 results (2026-11-05, afternoon)

Answers `docs/BRAIN_SPEC.md` §7.19 parts A and B. Numbers marked (R) were recomputed or re-read by the overseer from the saved files. Both
orders are done and merged into `body`. One arm; ARGMAX mode for every pass/fail (§7.19 A2).

## 1. M3e toy rerun: try 1 passes the toy bar in argmax, and beats all three WO7 controls (R)

Branch `body-m3e` 2884e74. New files only (`m3e*.py`); M3d's code is untouched. Changes as §7.19 B: closed loop (proprioception quantised,
delayed 10 ms, roll included; the frozen K1 round-2 cerebellum's predicted pose and error, ported to JAX, parity max abs 1.7e-4 against a 2e-4
tolerance; new input weights zero-initialised); dopamine (critic of the next 2 s of legibility, |δ| scales the selection-path learning rate);
causal 30 s normalisation; self-observer on proprioception. Loss = external + internal decoding − λ·energy.

Grid (tune episodes, 12 epochs, argmax; external (a) / internal (a) / (b) °/s), rule "largest external (a) among (b) passes", fixed before:
**λ 0.03: 1.001 / 0.957 / 44.8 (chosen)**; λ 0.3: 0.850 / 0.696 / 47.4; λ 3: 0.874 / 0.931 / 36.5.

Try 1 (λ 0.03, lr 1e-3, 40 epochs), 16 held-out episodes, the WO7 observer procedure for each decoder:

| Policy | Mode | external (a) [95 %] | internal (a) [95 %] | (b) °/s | (c) p |
|---|---|---|---|---|---|
| trained | **argmax** | 0.991 [0.871, 1.120] | 0.951 [0.859, 1.038] | 48.8 | 0.001 (MI 0.152, null 0.032) |
| trained | sampled | 0.846 | 0.839 | 47.9 | 0.001 (MI 0.073) |
| (i) untrained | argmax | 0.436 [0.326, 0.553] | 0.307 [0.185, 0.436] | 45.1 | 0.001 |
| (i) untrained | sampled | −0.050 | −0.071 | | 0.183 |
| (ii) trained, kappa 0 | argmax | 0.803 [0.685, 0.927] | 0.757 [0.628, 0.890] | 53.2 | 0.001 |
| (iii) untrained, trained kappa | argmax | 0.464 [0.321, 0.619] | 0.328 [0.189, 0.477] | 41.9 | 0.001 |

Paired (a)_trained − (a)_control, mean [95 %], 16 episodes (R, recomputed from the per-episode values), external | internal:

| Control | argmax | sampled |
|---|---|---|
| (i) untrained | 0.555 [0.394, 0.721] \| 0.644 [0.507, 0.763] | 0.896 \| 0.909 |
| (ii) kappa 0 | 0.188 [0.083, 0.297] \| 0.193 [0.054, 0.342] | 0.234 \| 0.223 |
| (iii) untrained + trained kappa | 0.527 [0.325, 0.731] \| 0.622 [0.489, 0.763] | 0.884 \| 0.872 |

- Every interval is above 0, including against kappa = 0 in argmax for both decodings (the §7.19 A1 wording condition, on the toy).
- Compared with M3d (WO7 controls, same observer procedure): trained argmax external (a) 0.688 → 0.991; margin over the untrained cortex
  0.272 → 0.555; the margin over kappa = 0 went from 0.019 (interval spanning 0) to 0.188.
- Dopamine (kept, built cleanly): builder's training summary mean |δ| 0.651, σ_δ 1.854, 1.6 % of blocks at the multiplier cap, 81.6 % below
  0.5 σ, training-mean multiplier about 1.0. The saved held-out lane (16 × 117 blocks) gives mean |δ| 0.629, SD 0.967 (R); the training figures
  were not recomputed.
- Learned norms of the new input weights (state inputs 8.00 for scale): proprioception 1.04, cerebellum pose 0.77, cerebellum error 1.11.
- Per-joint kappa 0.39 / 0.31 / 2.88 / 0.27 / 0.83 (elbow strongest).
- Tests: test_m3e 12 OK and test_m3d 13 OK, rerun by the overseer at 2884e74.
- Wall time 1 h 36 min for grid, try 1, controls and tests. Try 2 not run.

Builder's caveats, not tested:
- the loop closes at block rate (the cortex decides once per 0.5 s);
- the cerebellum's continuous run was checked on 12 s, the episodes are 60 s;
- the internal and external observers read the same joint positions (quantised, roll added), so the two decodings are not independent evidence;
- no ablation of the closed-loop inputs or of dopamine was asked or run, so the toy does not say which new mechanism produced the gain.

## 2. K5 data: done (R)

Branch `body-k5data` 9c9e139. Splits recomputed from `splits.json`, zero artist and song overlap:

| Split | Songs | Artists | Hours |
|---|---|---|---|
| K5 train | 2,602 | 650 | 162.0 |
| validation (tuning only) | 217 | 72 | 12.7 |
| check (held-out) | 357 | 73 | 20.1 |

B7 epoch-6 lanes for 3,176 songs (17.4 s per audio hour), stored un-normalised, 311 MB. Windows: 15,624 training (60 s, stride 30 s), 1,071
check (25 / 50 / 75 %; 362 moved back to fit the song end). Tests 7 OK.

**Projection.** M3d: 2.17 s per training window. M3e's epochs take about 75 s against M3d's 34.8 s on the same toy (R, from the logs), so
about 2.2× the cost: one pass over the 15,624 training windows ≈ 20 h on the laptop, 0.4 of a pass in the 8 h box. The check costs about
1 h more per scored policy and mode, and the controls repeat it three times.

## Questions

1. **K5 compute.** One pass is about 20 h on the laptop.
   - (a) Kaggle via run_job (free tier; no spending), as §7.19 A3 allows. Needs a JAX/MJX Kaggle image check first.
   - (b) Laptop, 8 h box: train on a fixed subset (e.g. 0.4 pass = one window per song from about 2,600 songs, ≈ 3.5 h, plus a second window
     each if time allows), stated before training.
   - (c) Laptop over several nights, resuming from checkpoints, with the 8 h box counted as compute actually spent per try (like 7.17 point 2).
   - Recommendation: (b) for try 1, which is fully on the laptop and inside the rules, with (a) prepared in parallel for try 2 if needed.
2. **Ablations.** The toy does not say which new mechanism produced the gain.
   - (a) None before K5.
   - (b) Report-only toy ablations before K5 (no retraining of the main policy; retrain small copies with one mechanism off each: closed-loop
     inputs off, dopamine off, internal observer off), so the monitor and story name only mechanisms that matter.
   - Recommendation: (b), on the laptop while K5's data and Kaggle path are prepared; they decide wording, not the K5 pass.
3. **Internal decoding.** Both observers read the same positions. Is the internal decoding still required for the "both it and you can read"
   wording (§7.19 C), or should the internal observer get a genuinely different input (e.g. the cerebellum's error and motor commands, not
   positions)? Recommendation: keep as fixed for K5; state the shared input in any claim.
