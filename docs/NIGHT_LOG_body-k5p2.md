# Night log: body-k5p2 (work order 14B, K5-pass2)

## MORNING SUMMARY

Pass2 RUNNING as unit hyst-wo14-a2 since 2026-11-08 (projection 16.2 h training plus validations). Eval script, check and videos not yet built.

## Phase 1: trainer

`K5P2Run` subclasses `k5_train.K5Run` (same order, seed, early stopping, checkpoints, pause/stop/mains) and drives `m3f.Trainer` with cfg body v2f + movement changes 1-4, jerk 0.03, switch 0.01. Windows carry the R input. The 14A hinges and hard clip go in `CFG`/`OPTS` of `k5p2_train.py` after the merge. Box is 30 h.

## Phase 2: pass2 body wired (2026-11-07)

Merged origin/body and origin/body-m3f (c0dc439). `k5p2_train.py` CFG = body v2f, obs_lp, phase_lp, xfade, ctc 0.006, plane `make_arm_v2.RAISED_PLANE_Z` (0.053), clip; OPTS pen2 on; W_FLOOR 1.0 (BRAIN_SPEC 7.30.8; values taken from agent 2's code, not reimplemented). 6 tests OK (trainer resume bit-identity, R input, end-stop report; `/secondary/hyst-data/body/k5p2/unittest2.log`, 915 s). LAUNCH HELD by the overseer (7.30.8): the user wants to see clips first. Not timed, not launched. `k5p2_eval.py`, timing, check and videos not started.

## Phase 3: launch (2026-11-08)

Tests 6 OK (680 s). Unit `hyst-wo14-a1` failed at once (relative script path, no working directory); fixed in `k5p2_run.sh` (93e18bb). Launched `hyst-wo14-a2` (`scripts/body/k5p2_run.sh a2`), 10 GB cap, cores 6-11, 6 threads, log and checkpoint in `/secondary/hyst-data/body/k5p2/run/`. Options: body v2f, hard clip, floor/acc hinges, contact-tc 0.006, raised plane 0.053, w-floor 1.0, smooth-u, jerk 0.03, switch 0.01.
Timing: round 0 189.5 s (compile), rounds 1-3 59.65 / 59.52 / 59.39 s. Projection 977 x 59.5 s = 16.2 h plus 5 validations and the check (validation cost not yet measured); under the 30 h box. Memory 4.2 GB.
Pause `systemctl --user freeze hyst-wo14-a2`; stop `systemctl --user stop hyst-wo14-a2`; resume `scripts/body/k5p2_run.sh <new suffix>`.
