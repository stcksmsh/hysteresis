# Builder prompt: work order 32B, retarget look test: human dance on the arm (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**Purpose (BRAIN_SPEC 7.49.5):** before any training, find out whether human dance mapped onto this arm looks like dancing to Kosta (the user).
If it does not, imitation cannot work and the line stops. No training of any kind, no hand-picking of clips, no shaping by eye, no verdict.
Kosta judges blind. One arm only (permanent rule). A second builder (32A) downloads the datasets and builds the session tool in parallel.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing. No downloads (32A does them).
  - The cortex (B7 epoch 6) is frozen. v47 seeds nothing.
  - Data, audio, video stay outside git. Never upload or redistribute any dataset content (BRAIN_SPEC 7.50.3).
  - Do not use SMPL / SMPL-H body model files (they need a registration): see 7.50.8.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-retarget origin/body`, then push `body-retarget`.
- **Jobs:** detached and memory-capped:
  `systemd-run --user --unit=hyst-wo32b-<fresh-name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  `python -u`. Cores **6-11** (`taskset -c 6-11`), never 12-17 (32A's). Mains only: poll `/sys/class/power_supply/ADP1/online`, wait while 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-retarget.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (MuJoCo, numpy, scipy), brain `/secondary/hyst-env/brain` (torch, for cortex lanes).
  **Output root:** `/secondary/hyst-data/body/retarget_look/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.50** (binding, incl. the overseer notes 7.50.8) and **§7.49.5** (the look test as ordered).
- Round-1 body and render path: `docs/MOTORNET_RULES.md`, `docs/MOTORNET_PARAMS.md`; `scripts/body/motornet.py` (limiter, servo, sim, gates),
  `motornet_render.sh`, `motornet_part3.py` / `motornet_part3_render.sh` (music clips, audio mux), `scripts/body/make_arm.py` (`RANGE_DEG`,
  `LIMITS`; base yaw and wrist roll are continuous, the three bend joints +-110 deg), `scripts/body/m3f_report.py` (`fk_points`).
- Round-1 S03 and its network: `/secondary/hyst-data/body/motornet_toy/clips/settings.json`; cortex lanes: `scripts/body/k5_video_lanes.py`,
  `scripts/body/motornet_music.py`.

## The work

1. **Rules file first:** `docs/RETARGET_RULES.md`, pushed before any clip is rendered or viewed, and reviewed by the overseer. You may write
   it while waiting for the data, and fill in the data-dependent numbers once FineDance is in. It fixes:
   - **Source:** FineDance public part (`/secondary/hyst-data/datasets/finedance/`, after "FINEDANCE READY <commit>" appears in
     `docs/NIGHT_LOG_body-data.md` on `origin/body-data`). If "FINEDANCE BLOCKED" appears instead, use Motorica Dance
     (`/secondary/hyst-data/datasets/motorica/`, BVH, after "MOTORICA READY"), report the switch in the night log and the rules file, and do not
     wait.
   - **Angles from local joint rotations only,** with canonical T-pose bone directions (arms along +-x, spine, neck and head along +y). No SMPL
     model file. If a variant cannot be built that way, STOP and log FOR USER.
   - **V1 "arm as arm":** the human's right arm drives the robot: shoulder elevation -> shoulder, elbow flexion -> elbow, wrist flexion -> wrist
     bend; torso (pelvis + spine) yaw -> base yaw; forearm/hand twist -> wrist roll. State the exact axis and projection for each (e.g. the
     upper-arm direction in the torso frame, its elevation angle).
   - **V2 "arm as whole body"** (PROPOSAL in 7.49): hip/torso yaw -> base yaw; torso lean forward/back -> shoulder; upper-body bend / neck ->
     elbow; head nod -> wrist bend; head tilt -> wrist roll. State the exact angle per joint.
   - **Scaling, one rule per variant:** each human angle is mapped linearly so that its pooled p2-p98 over all sequences of the source fills a
     stated share of the robot joint's range around round 1's calibration centre (`MOTORNET_PARAMS`). For the continuous base yaw and wrist roll,
     state the target span. Sign conventions stated. Numbers computed once, written down, never tuned after viewing.
   - **Body path (7.50.8):** commands at 100 Hz (cubic interpolation from the dataset frame rate) -> the existing command limiter -> servo ->
     v2f sim, as round 1, **without the spinal spring-damper**. Lamp head, round 1's camera and framing. Report per joint the share of the
     command the limiter cut (as round 1's limiter shares).
   - **Clips:** 10 clips of 20 s; seeded pick (seed 32011): one sequence per genre in a seeded genre order, until 10; the window start seeded
     inside each sequence after its first 5 s. Gates as 7.44 (floor and base clearance, contact, end-stop dwell, >8 Hz share, speed and
     acceleration limits, minimum motion). A clip failing a gate in either variant is replaced by the next seeded pick; every failure logged.
   - **Music:** FineDance's own music, locally, muxed into every clip (7.50 allows local use). Credit lines for any shown music recorded in
     the manifest.
   - **Reference:** round-1 S03 (round-1 network, inputs and calibration unchanged) on 2 of the 10 clips' music (seed 32021), same 20 s window,
     cortex lanes computed from that audio as round 1's music path does.
   - **Pairs:** 5 of the 10 clips (seed 32031) are also shown as V1-vs-V2 pairs; V1 plays first in exactly 2 or 3 of them, chosen by seed 32041.
   - **Manifest format** (32A's tool reads it): singles `{id, kind: "single", file, variant: "V1"|"V2"|"R1_S03", clip, genre, source_seq,
     window_start_s, csv, music_credit}`; pairs `{id, kind: "pair", files: [first, second], variants: [..], clip, genre}`.
2. **Render:** 20 singles (10 clips x V1, V2) + 2 references, 1280x720 h264 + aac, 20 s. Pairs reuse the same files. CSVs (realised angles,
   50 Hz) as round 1. `numbers.json`: per clip and variant: limiter cut per joint, every gate value, joint p5-p95 ranges, mean hand speed.
3. **Done when:** rules file pushed and reviewed; all clips gated and in the manifest; you have looked at 3 frames per clip (never to select or
   reshape); night log with MORNING SUMMARY pushed, **"CLIPS READY <commit>"**. Then stop. Do not show clips to the user; the overseer checks
   them first.

**Out of scope (stop and ask; log FOR USER):** any training or learning; SMPL model files; downloads; changing a mapping or scale after the
rules file is pushed; choosing clips by looking; the gain-modulation module; cortex changes; hardware; uploads.
