# Builder prompt: work order 34, one jitter viewing video for Kosta, report only (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting.

**Source:** a direct request from Kosta (2026-11-13), before the Q1 re-look session of `docs/PLANNER_BRIEF_JITTER.md`.
- This video is **for viewing only**. It is not part of any blind test and is never shown in a session.
- It must not change the Q1 session design, the seeded picks, or any shown clip.
- Report only; no verdict.

**Header rules:**
- In your current worktree: `git fetch origin && git checkout -b body-viewing origin/body`. Absolute paths; no new worktrees.
- Cores 6-11. Jobs longer than 2 minutes run as detached, memory-capped units (`hyst-wo34-<fresh-name>`, `MemoryMax=8G`).
- Run on battery.
- Commit and push the code before every run.
- Plain commit messages with **no co-author or attribution lines**.
- No installs, downloads or uploads. No SMPL model files (7.50.8). Round-1 files unchanged.

## Read first

- `docs/JITTER_DIAGNOSIS.md` and `scripts/body/jitter_diag.py` (stages, `run_variant`, the sign-change measure).
- `scripts/body/retarget.py`, `retarget_run.py`, `retarget_render.sh`, `retarget_page.py` (how the look-test clips are rendered: camera,
  lamp head, v2p column).
- `/secondary/hyst-data/body/retarget_look/manifest.json` and `jitter/numbers.json`.

## Fixed choices (the overseer picked by measure; do not re-pick)

- **Clips:**
  - **C05_V1** (miao, seq 136): the highest realised (stage 4, baseline) wrist-bend acceleration sign-change rate among the 20, 8.39 per
    second (next is C10_V2, 7.74);
  - **C04_V2** (dunhuang, seq 021) for contrast, 5.59 per second.

  State both numbers in the log, read from `jitter/numbers.json`.
- **The 6 s slice:** the 6 s window inside the shown 20 s with the most realised (stage 4, baseline) wrist-bend acceleration sign changes.
  Use the same counting rule as `jitter_diag.py`. Windows start every 0.1 s; on a tie take the earliest. Log the start time per clip.
- **The four panels, same 6 s, labelled with the stage name and the clip id:**
  1. **"human (FineDance), stick figure"**: the dancer's body joints from the canonical T-pose skeleton with the sequence's local
     rotations and root translation, the same way `retarget.py` reads them (no SMPL mesh, no model files). It is framed to fit its panel,
     seen from the same direction as the robot camera.
  2. **"stage 1: raw retargeted command (kinematic, no limiter, no servo)"**: the 30 fps command rows drawn directly on the robot. Range
     limits and the column are not enforced; say so in the label.
  3. **"stage 4: as shown in the look test"**: the realised rows of the shown clip (`work/<id>.csv`).
  4. **"H1: spinal layer before the limiter (realised)"**: stage 4 of `jitter_diag.run_variant(..., "H1")`.

  Panels 2-4 use the look-test camera, lamp head and v2p column, unchanged. Layout 2 x 2 at 1920 x 1080 (960 x 540 per panel).
- **Timing:** the 6 s at normal speed **with the clip's FineDance music** (the same audio slice), then the same 6 s at 0.5x **without
  music** (12 s). Put a 1 s title card per clip ("<clip id>, seconds a-b, normal speed" / "0.5x"). Both clips go into **one mp4**: C05_V1
  first, then C04_V2. h264 + aac, 30 fps.
- **Tools:** reuse the existing look-test renderer for the robot panels. Draw the stick figure with anything already installed (e.g. SVG or
  canvas frames rasterised by the system Chrome, as the jitter plots were) and compose with ffmpeg.
- **Output:** `/secondary/hyst-data/body/retarget_look/jitter/viewing/jitter_viewing.mp4`, plus `viewing.json` (clips, slice starts, the
  four sources per panel, frame counts) and a 4-frame contact sheet PNG. Nothing goes in git except code and the night log.

## Done when

"VIEWING READY <commit>" in `docs/NIGHT_LOG_body-viewing.md` with the path, pushed. Then STOP.

**Out of scope:** any change to the Q1 session, its clip choice or seeds; any fix adopted; training; hardware; uploads.
