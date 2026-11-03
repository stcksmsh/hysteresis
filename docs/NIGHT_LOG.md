# NIGHT LOG: H1, hippocampus toy (order of 2026-11-03)

## H1 MORNING SUMMARY (filled at the end)

- Try 1, A and B only: both fail T1a and T1b (A ratio 1.084, B 0.790). C, oracle reference and try 2 not run (usage limit). Hippocampus stays off.

## H1 LOG

- 2026-11-03 Setup. Worktree `.claude/worktrees/body-h1`, branch `body-h1` from origin/body (ded76a9). Read: BODY_BRAIN_PLAN 1, 5, 12; BRAIN_SPEC 7.1, 7.3, 7.10, 7.11; core_b7.py, toy_b7.py, test_core_b7.py, B7_NOTES.md, the B7 log below.
  Mechanisms, all behind default-off attributes of `Core7` (flags off = module unchanged; every older test passes unmodified except that `read` returns a 6th value, `hind`):
  - (a) `hind` (hindsight loss). Per read (one per 2 s block), per row: for every eligible entry (>= 17 s old) the squared error between its replay and the block's true targets,
    on every 20th frame of the block (10 offsets) and on each of the four horizons whose target window lies inside the chunk, computed under no_grad; the target is the entry with the lowest
    summed error (argmin, no gate, no margin). Loss = cross-entropy of softmax(cos / tau) over the eligible entries toward that entry, averaged over rows and blocks, weight 0.1 added to the beta-NLL loss. Gradient reaches the query, the keys of the chunk and log_tau.
  - (b) `oracle_p` (scheduled sampling). Per row and per read, with probability p the oracle pointer (weight 1 on the true source, as the oracle of try 0) replaces the retrieved sources; recognition stays the retrieved cosine. p = 1 - step / (0.5 steps), so p = 0 from half-way on. Rows where the oracle says "no source" use retrieval. The oracle is training-only; evaluation is pure retrieval.
  - Novelty lane (`novelty_lane`). At every tick (0.5 s), 1 - max cosine of the tick's own key (centred by the running key mean at that tick) against the eligible entries (>= 17 s old), no gradient, computed after the block, independent of the 2 s read; 1 if nothing is eligible. Reported on the toy: repeat ticks (from the 2nd second of the repeat on) against all other ticks from 17 s on. No pass rule.
  Toy otherwise as toy_b7.py (reduced width, random init seed 0, lr 3e-3, 20 warm-up steps, 8 sequences per step, 4 threads per run, eval 32 draws seed 991). Bar fixed: T1a and T1b of 7.10 R3. Oracle reference: the same code, pure oracle training (`--oracle`), design A.
- 2026-11-03 TRY 1 (1500 steps planned, lr 3e-3, hind 0.1, sched 0.5, seed 0; designs A and B only, C and the oracle reference NOT run). Both runs hit the existing flat-loss stop at step ~800-875 (after the handover, which ended at step 750).
  A iid: ratio 1.084 (T1b fail); T1a fail (source share 0.263, recognition median 0.282 vs p95 0.518); retrieval off 1.000. Novelty lane: repeat mean 0.478, outside mean 0.686.
  B levels+clock: ratio 0.790 (T1b fail); T1a fail (share 0.902, recognition median 0.580 vs p95 0.635); retrieval off 1.000. Novelty lane: repeat mean 0.458, outside mean 0.689.
  Logs: /secondary/hyst-data/brain/h1/try1_{A,B}.log. Unit tests: pass (OK). Try 2 and design C not started: usage limit reached.

---

# NIGHT LOG: B7, overnight order of 2026-11-02

## MORNING SUMMARY (updated 2026-11-02 12:35)

- **Path through the tree:** R1/R2 built (pointer replay, centred keys, 2 s blocks). T1a (retrieval finds the source) passes on designs B and C in every run, A fails after training; the oracle (true pointer) passes T1b (ratio 0.348); trained T1b fails in tries 1, 2 and 2 + lr x10 (best 0.61). **Hippocampus DROPPED** (flag `hippo_flag` = 0). B7 = relay (features + grid phase) + head skip with a 10-frame tapped delay + acting modulation (2 s blocks). C1 to C3 and the words "recognises, stores, habituates, novelty signal" are not claimable.
- **T2:** 2000 steps, 1 tap: 1.069 x ridge AR (fail); R4 fallback 10 taps: **1.017 (pass)**, relay off 1.515.
- **Toy table** (ratio repeat/first, <= 0.5 needed; A iid | B levels+clock | C smooth): try 1 0.609 | 0.745 | 0.712; oracle A 0.348; aux 0.1: 0.737 | 0.808 | 0.804; aux + lr x10: 0.958 | 0.773 | 0.790.
- **Identity:** float64 4.6e-14 (<= 1e-9 PASS), float32 1.2e-4 on 10 held-out songs.
- **Smoke** (8 streams x 180 s): no checkpointing 13.3 s/step, 20.5 GB peak (> 18); **checkpointing 14.5 s/step, 8.4 GB**, epoch 2.34 h, 8 epochs 18.7 h (fits the 24 h stop). Leak: not found (jump 15 -> 20.5 GB between steps 1 and 2 without checkpointing; detach verified in code and tests). Dry run C1-C5 on 5 songs: clean, per-cut z saved.
- **Training:** RUNNING since 2026-11-02 12:29. Service `hyst-b7-train.service` (MainPID 158213, MemoryMax 20G), log `/secondary/hyst-data/brain/b7/train.log`, checkpoints `/secondary/hyst-data/brain/b7/ckpt/phase/` (epoch_NNN.pt, best.pt, last.pt; resume = rerun the same command). Warm start B3 round 2 epoch 12, 8 epochs max, patience 2, hard stop 24 h (ends by 2026-11-03 12:29), batch 8, gradient checkpointing, 10-tap skip. Validation beta-NLL per epoch: see the log (JSON line per epoch). Stop: `systemctl --user stop hyst-b7-train`. Do NOT run C1-C5 until the user is awake.
- **FOR USER:** (1) hippocampus dropped (default of the order); code and tests kept, retrieval works, the relay did not learn to use it in the toy budget. (2) memory leak not found; checkpointing used. (3) novelty lane would have updated only every 2 s (block read), so C3 as written could not see a cut within its 1 s window even with a working hippocampus. (4) training uses `--taps 10` (R4 fallback), not part of the first spec text. (5) float32 identity is 1.2e-4, float64 passes.
- **Commits:** see `git log` on b7 (BRAIN_SPEC 7.10 c81ad68; core fc1fa6f; later commits below).

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
- 2026-11-02 11:50 SMOKE (8 streams x 180 s, 2 s blocks, hippocampus dropped, relay + skip + modulation; machine shared with a toy run). Without checkpointing: step 13.3 s, epoch 2.18 h, 8 epochs 17.5 h, but peak RSS 15.1 GB at step 1 then 20.5 to 20.7 GB from step 2 (> 18 GB). With gradient checkpointing: step 14.5 s, epoch 2.34 h (567 train + 47 validation steps), 8 epochs 18.7 h, peak RSS 8.4 GB (scope peak 8.76 GB, anon 8.0 GB), 4 steps flat after a small rise. B3 smoke for reference: 14.5 s/step, 14.2 GB. No B3-calibration scaling applied (B3's real run was 1.46 h/epoch against 2.35 h in smoke; B7 is expected to be faster than projected). Slowdown of B7 over B3 per step: 1.0x without checkpointing, 1.0x with it (the hippocampus was the cost; 2 s blocks and the two-level scan removed the rest).
  LEAK (phase 2): not found. Carried state and store entries are detached at the chunk edge (code read: Core7.detach_state cuts lv, qs, ksum, kr, and the B3 state; tests check kr/ksum.requires_grad and that chunk-2 backward does not free chunk-1's graph). The 15 -> 20.5 GB jump at step 2 reproduces with the hippocampus dropped and plateaus. Default taken: gradient checkpointing at 8 streams (8.4 GB). FOR USER: leak not found (jump 15 -> 20.5 GB between steps 1 and 2 without checkpointing).
  IDENTITY on 10 held-out songs (B3 round 2 epoch 12): float64 max abs diff 4.6e-14 (criterion <= 1e-9: PASS); float32 1.2e-4 (logged).
- 2026-11-02 12:00 DRY RUN of C1 to C5 on 5 held-out songs with step-0 B7 (hippocampus dropped), 12 training songs for the baselines: runs end to end, writes results.json with per-cut z values (C3 per_cut_z, C1 per_song, per_song_scores, C4 rel_per_song). Numbers not looked at or acted on.
- 2026-11-02 12:00 T2 (2000 steps, reduced width, lr 1e-3): model MSE 0.006262, ridge AR 0.005859, ratio 1.069 (needs <= 1.05; relay off ratio 5.42). Still > 1.05 -> R4: tapped delay of 10 frames in each head skip, rerun once (t2tap, 2000 steps, running). Training launch waits for this one result (it decides whether the run uses --taps 10).
- 2026-11-02 12:28 T2 with the 10-frame tapped skip (R4): model MSE 0.005960, ridge AR 0.005859, ratio 1.017 PASS (relay off 1.515). Final module set fixed: relay + 10-tap skip + modulation, no hippocampus.
- 2026-11-02 12:29 TRAINING LAUNCHED: hyst-b7-train.service (a systemd user service, MemoryMax=20G, detached from this session), MainPID 158213, batch 8, grad checkpointing, taps 10, warm start B3 round 2 epoch 12, 1,415,789 parameters, 2602 fit / 217 validation tracks, cap 24 h.
