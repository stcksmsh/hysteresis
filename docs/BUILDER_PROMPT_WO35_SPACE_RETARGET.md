# Builder prompt: work order 35, end-point smoothness (Step A) and space retarget V3 (Step B), report only (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.54** (Kosta + planner; Kosta judged by eye that the jitter is created by the retargeting), with the
overseer notes 7.54.8. Then §7.51-7.53. **Report only: no verdict, no video, no blind session.** Step C (the blind look) waits for Kosta's
"go".

**Header rules:**
- In your current worktree: `git fetch origin && git checkout -b body-v3 origin/body`. Absolute paths; no new worktrees.
- Cores 6-11. Jobs longer than 2 minutes run as detached, memory-capped units (`hyst-wo35-<fresh-name>`, `MemoryMax=8G`,
  `MemorySwapMax=0`).
- Run on battery; never wait for mains.
- Commit and push the code before every run; push at least every 30 minutes.
- Plain commit messages with **no co-author or attribution lines**.
- No installs, downloads, uploads or SMPL model files. Round-1 files (`motornet.py`, `dialstudy.py`, `arm_sim.py`) and the V1/V2 code paths
  unchanged; the shown clips untouched.

## Read first

- `docs/BRAIN_SPEC.md` §7.51-7.54.
- `docs/RETARGET_RULES.md` (a)-(l), `docs/RETARGET_SCALE.json`, `docs/JITTER_DIAGNOSIS.md`.
- `scripts/body/retarget.py`, `retarget_run.py`, `retarget_limiter.py`, `make_arm.py` / `make_arm_v2p.py` (FK, column, guard),
  `jitter_diag.py` (measures, `run_variant`).
- The WO34 viewing code (branch body-viewing, merged in body): the FineDance stick-figure FK with canonical T-pose offsets.

## The work

1. **STEP A, report-only (do first, push "STEP A READY <commit>").** For the 20 look-test clips, compute direction changes per second (the
   jitter_diag counting rule) and the share of speed power above 3 Hz and above 6 Hz for:
   - (0w) the human end point in world space: right wrist (joint 21) for V1 clips, head (joint 15) for V2 clips;
   - (0r) the same end point relative to its origin (right shoulder, joint 17, for V1; pelvis, joint 0, for V2);
   - (1) the stage-1 joint angles (from `jitter/numbers.json`);
   - (1e) the robot lamp position by arm FK of the stage-1 angles.

   For positions, report per axis and the mean over axes. Write `docs/V3_REPORT.md` section A with medians over the 20 clips, plus per-clip
   numbers in `/secondary/hyst-data/body/retarget_look/v3/numbers.json`.
2. **Q2, report-only:** why the C04_V2 realised shoulder sits about 10 deg above the command in seconds 8-12. Check gravity sag in the
   servo model, the limiter, the guard, the end stops and the column contact. Write it in V3_REPORT.md section Q2.
3. **Rules note "(m) space retarget V3"** in `docs/RETARGET_RULES.md`, **pushed before any V3 run**. The overseer reviews it. It fixes
   (7.54.5, 7.54.8):
   - V3a: the lamp follows the right wrist relative to the right shoulder. V3b: the lamp follows the head relative to the pelvis.
   - **Scale:** uniform; the pooled p98 reach over the 4,603 eligible windows maps to 80 % of the arm's reach (p1 to the lamp centre at
     full extension). New keys in `RETARGET_SCALE.json`; old keys unchanged.
   - **Offset:** the workspace centre is the lamp position at round 1's centre pose. The human forward axis maps to the robot's base-0
     forward.
   - **Orientation:** the hand (V3a) or head (V3b) orientation is mapped onto the wrist's two axes (bend, roll). State the projection.
   - **IK:** damped least squares on the v2p arm at 100 Hz, on the cubic-spline-resampled end-point path, warm-started from the previous
     frame.
     - Fix lambda, the per-frame joint-change penalty, the orientation weight (position first) and the iteration count as numbers, each
       from a rule stated in the note. Default for the change penalty: a stationary target gives zero motion, and a 1 cm target step moves
       the joints by at least 90 % of the exact solution within one frame.
     - Never tune any of them by eye or on the gate outcome.
     - Joint limits by clamping in the solve; column clearance by a penalty plus projection; the 7.51 guard as backstop.
     - Count the frames whose residual error is > 2 cm.
   - **Then the existing pipeline:** round-1 `motornet.spinal` (H1) before the fixed limiter (k), servo, v2p body, gates at 1.25 (l).
4. **STEP B run:** the same 10 seeded windows (C01-C10), V3a and V3b each. No re-pick.
   - Report the 7.52 gate pass/fail and failed parts per clip.
   - Report the jitter measures per stage, as in `docs/JITTER_DIAGNOSIS.md`: end point, IK output, spinal, limiter, realised.
   - Report the IK residual (> 2 cm frame count) and the shoulder numbers of 7.52.5.
   - Put the medians side by side with V1/V2 baseline and H1 from the diagnosis, and the S03 reference.
   - Write `docs/V3_REPORT.md` section B and `v3/numbers.json`, and save the realised CSVs in `v3/work/`. **Render no video.**
5. **Done when:** "V3 READY <commit>" in `docs/NIGHT_LOG_body-v3.md` with a short MORNING SUMMARY, pushed. Then **STOP**. The overseer
   checks; Kosta sees the numbers and decides on Step C.

**Out of scope (stop and ask; log FOR USER):** Step C, any render, training, music conditioning, gain modulation, limiter redesign, changes
to V1/V2 or the shown clips, hardware, uploads.
