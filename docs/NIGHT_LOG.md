# NIGHT LOG: B7, overnight order of 2026-11-02

## MORNING SUMMARY (updated after every phase)

- Phase: 0 (setup) done. Path through the decision tree: not started.
- Toys: not run yet. Leak: not looked at yet. Smoke: not run yet. Training: not launched.
- FOR USER: (none yet)
- Commits: see the log below.

## LOG

- 2026-11-02 00:30 Setup: order read; rulings R1 to R7 added to BRAIN_SPEC.md as 7.10 (before any code). Branch b7 at 1e95c5b.
- 2026-11-02 00:40 Phase 1a done in code (not yet committed): R1/R2 implemented in scripts/brain/core_b7.py (pointer replay, centred keys, 17 s eligibility, 2 s blocks, two-level per-row scan in core.py), toy_b7.py rewritten (designs A/B/C, T1a/T1b split, oracle, aux option, T2 with tapped skip option). 27 unit tests pass (replay equals the true targets on an exact repeat to 1e-5; untrained retrieval finds an exact repeat in 100 % of repeat blocks; identity float64 < 1e-9).
- 2026-11-02 00:35 Toys launched in parallel (4 threads, 6 GB scope each): t1A, t1B, t1C, t1A oracle, t2 (2000 steps). Logs in /secondary/hyst-data/brain/b7/toys/.
- 2026-11-02 01:00 TOYS round 1 (reduced-width model, ~190 steps each = 20 min deadline; the ratio is repeat / first over L1+L2+L3, needs <= 0.5):
  | run | T1a (source share in first S / recog median vs p95) | ratio |
  |---|---|---|
  | A iid, trained | 0.90 / 0.573 vs 0.578 FAIL (untrained: 0.98 / 0.73 vs 0.38 pass) | 0.609 |
  | B levels+clock, trained | 0.99 / 0.669 vs 0.584 pass | 0.745 |
  | C smooth AR, trained | 0.97 / 0.592 vs 0.502 pass | 0.712 |
  | A iid, ORACLE pointer | (forced) | 0.348 PASS |
  The ratio code had a bug (summed a NaN L4 entry); the numbers above were recomputed from the logged per-layer MSEs (L1, L2, L3). Fixed in toy_b7.py.
  Reading: retrieval finds the source (T1a ok except A after training), the oracle passes T1b, trained runs are at 0.61 to 0.75 and still improving at the deadline. Decision tree: T1a passes, T1b fails, oracle passes -> TRY 2, auxiliary loss weight 0.1. Launched 3 runs (A, B, C with --aux 0.1, deadline 20 min). T2 (2000 steps) still running.
- 2026-11-02 01:55 TOYS round 2 (try 2, aux loss 0.1, ~150 steps in the 20 min because the aux term and 4 parallel runs slow each step): ratios A 0.737, B 0.808, C 0.804 (retrieval off: 1.00). T1a: A fail (recognition median 0.44 vs p95 0.59), B pass, C pass. No better than round 1 per wall time (fewer steps). The oracle passes (0.348), so the relay can use the replay; learning is slow in steps. Not a tree exit yet: toy budget (3.5 h, until ~04:00) is not spent. ROUND 3: aux 0.1 plus new-parameter learning rate x10 (the debug item from the oracle branch), 3 runs, 20 min each. T2 first run was OOM-killed in its ridge fit (200 sequences x 704 features); fixed (120 sequences, every 5th frame, lr 1e-3, no flat-loss stop) and relaunched as t2b.
- 2026-11-02 10:52 RESUME after power loss (01:44). Round 3 (aux 0.1 + new-parameter lr x10; t1Aaux10/Baux10/Caux10) and T2b relaunched from scratch under fresh scope names (hyst-b7-toyr-*). About 2 h of the 3.5 h toy budget remain at this point (the clock above is wall time; the toy budget counts run time).
- 2026-11-02 11:25 TOYS round 3 (aux 0.1 + new-parameter lr x10, ~330 steps in 20 min): ratio A 0.958 (T1a fail: recognition 0.547 vs p95 0.566), B 0.773 (T1a pass), C 0.790 (T1a pass); retrieval off 1.00. T1b fails on all three designs; the oracle (true pointer) passes at 0.348.
  TOY TABLE (ratio repeat/first, needs <= 0.5; design A iid | B levels+clock | C smooth): try 1 trained 0.609 | 0.745 | 0.712; oracle A 0.348; try 2 aux 0.1: 0.737 | 0.808 | 0.804; try 2 + lr x10: 0.958 | 0.773 | 0.790. T1a (retrieval finds the source) passes on B and C in every run, fails on A after training.
  DECISION (tree 1c: still failing after try 2): DROP THE HIPPOCAMPUS from B7. Implemented as `hippocampus=False` (checkpoint buffer hippo_flag = 0): no buffer, keys or read; relay (features + grid phase), head skip and modulation stay. train_b7.py trains with it dropped by default. Consequences: C1, C2 and C3 cannot pass (no recognition; novelty is constant 1); the words "recognises, stores, habituates, novelty signal" are not claimable from B7. FOR USER: the hippocampus code stays in the repo (core_b7.py, 28 tests); retrieval itself works (T1a, exact replay, oracle passes); what failed is the relay learning to use the replay within the toy budget. Default taken: drop, as ordered.
