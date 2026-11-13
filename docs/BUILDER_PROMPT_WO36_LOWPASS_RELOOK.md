# Builder prompt: work order 36, joint-space low-pass to the human's smoothness, then clips for the blind re-look (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.55** (Kosta's ruling on `docs/PLANNER_BRIEF_V3.md`) with the overseer notes 7.55.7. Then §7.51-7.54.
**No verdict. You do not run the blind session yourself:** the overseer builds and serves it.

**Header rules:**
- In your current worktree: `git fetch origin && git checkout -b body-lowpass origin/body`. Absolute paths; no new worktrees.
- Cores 6-11. Jobs longer than 2 minutes run as detached, memory-capped units (`hyst-wo36-<fresh-name>`, `MemoryMax=8G`,
  `MemorySwapMax=0`).
- Run on battery; never wait for mains.
- Commit and push the code before every run; push at least every 30 minutes.
- Plain commit messages with **no co-author or attribution lines**.
- No installs, downloads, uploads or SMPL model files.
- Round-1 files unchanged. The shown look-test clips and `retarget_look/clips/` are untouched. New output goes to
  `/secondary/hyst-data/body/retarget_look/lowpass/`.

## Read first

- `docs/BRAIN_SPEC.md` §7.53-7.55.
- `docs/RETARGET_RULES.md` (a)-(m), `docs/JITTER_DIAGNOSIS.md`, `docs/V3_REPORT.md` (Step A, column (0r)).
- `scripts/body/retarget.py`, `retarget_run.py`, `retarget_limiter.py`, `jitter_diag.py` (`run_variant`, measures), `v3_lib.py` (human FK,
  end-point measures), `retarget_render.sh`, `dialstudy_session.py`.

## The work

1. **Rules note "(n) low-pass to the human's smoothness"** in `docs/RETARGET_RULES.md`, pushed **before any render**. The overseer reviews
   it. It fixes, per 7.55.7:
   - **Filter:** 2nd-order Butterworth, `filtfilt`, at 30 fps, on the stage-1 angles. Base yaw and wrist roll are unwrapped. The filter runs
     over the whole sequence before windowing.
   - **Cutoff rule:** the **highest** cutoff in 0.5-14.5 Hz (0.25 Hz steps) at which the median over the variant's 10 look-test windows of
     the lamp path's speed power share above 3 Hz (lamp by arm FK of the filtered stage-1 angles, the Step A measure) is <= the median of the
     human end point's (0r: right wrist relative to the right shoulder for V1, head relative to the pelvis for V2). Computed per variant.
   - The note states the chosen cutoffs, the curve (cutoff vs median power, as a table) and the two human medians.
   - Pipeline: filtered stage-1 angles -> cubic spline to 100 Hz -> guard -> round-1 `motornet.spinal` (H1) -> fixed limiter (k) -> servo
     -> v2p body -> gates at 1.25 (l).
2. **Measure:** on the 20 look-test windows (V1 and V2), the jitter measures per stage as in `JITTER_DIAGNOSIS.md`:
   - stages: stage 1 filtered, spline, spinal, limiter, realised;
   - also the lamp-path power above 3 Hz at each stage;
   - the 7.52 gate pass/fail and the shoulder numbers of 7.52.5;
   - the medians side by side with the V1/V2 baseline, + H1, and the S03 references.

   Write `docs/LOWPASS_REPORT.md` and `lowpass/numbers.json`, and save the realised CSVs in `lowpass/work/`.
3. **Re-look clips (7.55.7):**
   - C04_V2 and C10_V1, plus 4 more by seeded pick (`numpy.random.default_rng(32071)`, a permutation of the other 18 shown clip ids, taken
     in order).
   - A clip whose fixed version fails the 1.25 gate is skipped, and the next in the permutation is taken. Log every skip. If C04_V2 or
     C10_V1 fails, write "HOLD <clip> <failed parts>", push and stop.
   - Render the 6 fixed clips exactly as the look-test clips were rendered (same camera, lamp head, v2p column, 20 s, FineDance music,
     1280x720 h264 + aac) to `lowpass/clips/<id>_LP.mp4`. Look at 3 frames per clip, never to select or reshape.
   - Write `lowpass/clips/manifest.json` in the look-test manifest format with 6 `kind: "pair"` items, each with `files: [old, fixed]` or
     `[fixed, old]`. "Old" = the shown look-test mp4, by absolute path (`/secondary/hyst-data/body/retarget_look/clips/<id>.mp4`). The fixed
     version comes first in exactly 3 of 6, set by `default_rng(32081)`. Use `variants` labels `["old", "LP"]` in the shown order.
4. **Tool change (small):** in `dialstudy_session.py` look-test mode, the pair answers are **"first / second / same"**. "neither" stays in
   every other mode. Add a test. Build and run a throwaway test session on your manifest to confirm 6 pair items with the fixed order kept,
   then delete it.
5. **Done when:** "CLIPS READY <commit>" in `docs/NIGHT_LOG_body-lowpass.md` with a short MORNING SUMMARY (cutoffs, gate counts, the picks
   and skips, the pair order), pushed. Then **STOP**. The overseer checks, then builds and serves the session.

**Out of scope (stop and ask; log FOR USER):** any other filter, cutoff rule or retarget variant; training; music conditioning; gain
modulation; limiter redesign; hardware; uploads; serving the session.
