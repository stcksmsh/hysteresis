# Night log, builder (body-s3t), work order 26B, the Stage 3 trainer (2026-11-09)

## MORNING SUMMARY (WO26B)

Build and tests done; **the timed round has NOT been run** (waits for the overseer's word "timed round"; the Stage 3 run is never launched by this work order).

- Rules: `docs/STAGE3_RULES_TRAIN.md` (committed before any code; dated entry of 2026-11-09 for the overseer's ruling: the external observer reads a causal 1.5 s window of FK positions in metres, elbow/wrist/hand, 135 inputs, G = 4 Lipschitz).
- Code (new files only, no existing module edited, so the pass2 path is unchanged by construction; `git diff origin/body -- scripts` lists only the new files): `scripts/body/s3_data.py`, `s3_obs.py`, `s3_loss.py`, `s3_train.py`, `s3t_smoke.sh`, tests `test_s3_train.py`.
- Tests (cores 12-17):
  - 8 fast tests OK (Lipschitz bound measured on random inputs for both observer sizes with and without the normalisation; chunk window equals whole-episode window; D on hand-made cases; rising-only D multiplier; limit hinges zero inside the envelope and counted only on scored blocks; policy equals pass2 at init with 13 zero rows; fast-z sd floor; anchor + 7 nearest, no duplicates, deterministic).
  - Smoke/resume test `test_s3_train.Run` OK (detached unit `hyst-wo26b-smoke`, MemoryMax 14G, cores 12-17, 927 s in total): 2 rounds straight == 1 round + resume + 1 round, bit-identical (policy, encoders, observers, multipliers, key); no NaN in parameters or in the logged losses/D; limit multipliers >= 1 and non-decreasing, D multipliers non-decreasing; a validation ran and wrote `best.pkl` (policy first weights 54 rows = 16 + 13 + 25, `s3.slow_inputs` true).
  - Seconds per round (4 windows = batches of 2, NOT the real round of 16; cores 12-17; the machine was loaded by 26A's runs at the same time, load average about 17): round 0 **352 s** (includes the one-time JIT compile of the gradient through the body), round 1 **95 s**. Informational only: the real round is 16 windows (batches of 8), the timed round on cores 6-11 gives the number that counts.
- Stub for 26A's files: written to a temp dir by the test (train windows and all 217 validation songs); nothing under `/secondary/hyst-data/body/s3/` except `train_tests/` (logs).
- The trainer refuses to start without `tempo_rms.json`, `thresholds.json` and `slow/norm.json` under `--s3` (explicit message).

## FOR USER (information for the planner)

1. Anchors: each round has 2 anchor windows from the pass2 seeded order plus 14 matched-neighbour windows (a batch must be one anchor plus its 7 nearest songs), so a pass sees 1,954 anchors and 13,664 neighbour windows; a window can repeat. Pass2 saw each window once.
2. External observer: metres window of FK positions (overseer ruling), internal: descriptor units.
3. Hinge multipliers step per optimiser step (one per 4 s chunk, 30 per round, shared by both groups), the choice for "step 0.02 per batch"; D multipliers once per round (ruled).
4. The D estimate uses the group-A and group-B external observers (fitted on training rollouts only) on 16 fixed validation windows and averages their D.
5. Cached compiled functions: `s3_loss.make_fns` is cached per cfg within a process (C is the fixed cerebellum file).

## Next

On the overseer's word: `s3_train.py --out /secondary/hyst-data/body/s3/train_timed --timed` as one detached unit (MemoryMax 14G, `taskset -c 6-11`, mains), after 26A's files exist; report seconds per round, rounds in the run, projected hours against the 30 h box.
