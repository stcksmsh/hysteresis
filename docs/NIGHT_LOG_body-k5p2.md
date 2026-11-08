# Night log: body-k5p2 (work order 14B, K5-pass2)

## MORNING SUMMARY

Pass2 RUNNING as unit hyst-wo14-a2 (validations so far: round 200 ext (a) 0.862, 400 0.895, 600 0.913). WO18 check and video scripts built and tested; real check and videos run when training ends.

## Phase 1: trainer

`K5P2Run` subclasses `k5_train.K5Run` (same order, seed, early stopping, checkpoints, pause/stop/mains) and drives `m3f.Trainer` with cfg body v2f + movement changes 1-4, jerk 0.03, switch 0.01. Windows carry the R input. The 14A hinges and hard clip go in `CFG`/`OPTS` of `k5p2_train.py` after the merge. Box is 30 h.

## Phase 2: pass2 body wired (2026-11-07)

Merged origin/body and origin/body-m3f (c0dc439). `k5p2_train.py` CFG = body v2f, obs_lp, phase_lp, xfade, ctc 0.006, plane `make_arm_v2.RAISED_PLANE_Z` (0.053), clip; OPTS pen2 on; W_FLOOR 1.0 (BRAIN_SPEC 7.30.8; values taken from agent 2's code, not reimplemented). 6 tests OK (trainer resume bit-identity, R input, end-stop report; `/secondary/hyst-data/body/k5p2/unittest2.log`, 915 s). LAUNCH HELD by the overseer (7.30.8): the user wants to see clips first. Not timed, not launched. `k5p2_eval.py`, timing, check and videos not started.

## Phase 3: launch (2026-11-08)

Tests 6 OK (680 s). Unit `hyst-wo14-a1` failed at once (relative script path, no working directory); fixed in `k5p2_run.sh` (93e18bb). Launched `hyst-wo14-a2` (`scripts/body/k5p2_run.sh a2`), 10 GB cap, cores 6-11, 6 threads, log and checkpoint in `/secondary/hyst-data/body/k5p2/run/`. Options: body v2f, hard clip, floor/acc hinges, contact-tc 0.006, raised plane 0.053, w-floor 1.0, smooth-u, jerk 0.03, switch 0.01.
Timing: round 0 189.5 s (compile), rounds 1-3 59.65 / 59.52 / 59.39 s. Projection 977 x 59.5 s = 16.2 h plus 5 validations and the check (validation cost not yet measured); under the 30 h box. Memory 4.2 GB.
Pause `systemctl --user freeze hyst-wo14-a2`; stop `systemctl --user stop hyst-wo14-a2`; resume `scripts/body/k5p2_run.sh <new suffix>`.

## Work order 18: check and video scripts (2026-11-08)

Built and tested while `hyst-wo14-a2` trains (untouched; validations at round 200 / 400 / 600: ext (a) 0.862 / 0.895 / 0.913).
- `scripts/body/k5p2_eval.py`: `check` (K5 check on the 1,071 held-out windows, trained / untrained / kappa 0, per-song bootstrap, paired; ARGMAX decides, sampled reported; report-only lines on the held-out rollouts), `songs` (the three danced songs as one continuous episode each on the pass2 body: joint CSV, `hyst check-csv`, (e'1)/(e'2) vs `hf_v47_eprime_reference.json`, (e), contact time, within 2 deg / on a stop per joint, longest stop-hold, longest any-pose hold, clip-boundary holds, end stops at 50 and 100 Hz pooled and per episode via `m3f_endstop.analyse` (whole song, and its full 60 s segments), shoulder-at-limit, programs, readability per 60 s), `summary` (bar components, pass2 bar, trained - kappa0). cfg is read from best.pkl.
- `scripts/body/k5p2_render.sh`: 1080p + 720p per song, v47 arm 0 | fallback | K5-pass2 three-panel 720p (< 30 MiB each); the page label "K5 policy" is replaced by "K5-pass2 policy" in the generated html (no Rust change).
- Tests (`test_k5p2_eval.py`, 3 threads): synthetic report lines, chunk padding, continuous first 120 blocks bit-identical to the windowed rollout (same start seed 4242, chunk 8), and an end-to-end run (6 windows, 24 blocks, resume, summary) on the round-600 best.pkl: all OK. A 6 s render test (old K5 CSV as stand-in) produced a 1280x720 clip whose frame shows the "K5-pass2 policy" label.
- Not yet: the real check and videos (wait for `hyst-wo14-a2` to finish; check as a detached unit, 6 threads, 14 GB).
