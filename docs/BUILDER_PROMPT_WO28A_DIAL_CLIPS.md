# Builder prompt: work order 28A, hand-set dial study: dials, simulation and clips (2026-11-12)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing from it ships:
- no learning or training of any kind;
- no numeric pass bars;
- no verdict from you. Kosta (the user) judges the clips by eye, blind.

One arm only (permanent rule). A second builder (work order 28B) builds the blind labelling tool and two new end-effector shapes in
parallel. Its interface with you is the manifest in section 4.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing. No network downloads.
  - v47 must not seed anything: no v47 poses, scores or CSVs as input. Its exports stay byte-identical in Off.
  - Data and videos stay outside git.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-dial origin/body`, then push `body-dial`.
- **Jobs:**
  - Detached and memory-capped:
    `systemd-run --user --unit=hyst-wo28a-<fresh-name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - `python -u`. Cores **6-11** (`taskset -c 6-11`), 6 threads; state the thread count in the report.
  - Mains only: the script polls `/sys/class/power_supply/ADP1/online` and waits while it reads 0.
  - Nothing else of Hysteresis is running. Agent 2 uses cores 12-17.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-dial.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (MuJoCo, JAX), brain `/secondary/hyst-env/brain`.
  **Output root:** `/secondary/hyst-data/body/dialstudy/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.43** (binding: the piece, the study, its out-of-scope list) and §7.42 (why: no proxy objectives).
- Body code in `scripts/body/`:
  - `m3f_jax.py`: `_model_v2` / `body_model` for the v2f model (`condim=1`, raised plane `V2.RAISED_PLANE_Z`, contact tc 0.006, end
    stops), `arm_step` (the target limiter), `smooth_command`;
  - `make_arm.py`: `KP`, `tune_kv`, `ZETA`, `LIMITS`, `RANGE_DEG`, ball mass;
  - `arm_sim.py`: plain-MuJoCo stepping and `csv_text`, the 50 Hz joint CSV format;
  - `k5p2_train.py` line 33: the v2f CFG pass2 used;
  - `m3f_report.py`: `fk_points` and the check-csv thresholds.
- Render path: `scripts/body/k5p2_render.sh` (`ensemble_preview --joint-csv` page + `scripts/author/record_ensemble.cjs` + `mp4_720`) and
  its one-arm camera.

## The work

### 1. Rules file first

Write `docs/DIALSTUDY_RULES.md` and push it **before any clip is rendered**. It holds:
- (a) the body and stepping you use (plain MuJoCo CPU on the v2f model; threads);
- (b) the underlying movement;
- (c) each dial's implementation and numeric range;
- (d) the glitch gates (section 3).

The overseer reviews it within 30 min. Continue meanwhile. If the overseer asks for a change, redo only what it touches.

### 2. Underlying movement and dials

- **Underlying movement:** one fixed, seeded random sequence of feasible poses (seed recorded). Moves are timed to a beat grid: 100 BPM for
  Sets A-C, one move per beat or per two beats (your choice, the same for all). It is the SAME sequence for every clip, so clips differ only
  by dial settings.
  - Poses are random within the joint ranges and clear of the plane and base by the check-csv margins at every dial setting.
  - **Not v47.**
- **Five dials**, each with a low and a high extreme and a neutral middle. The implementation is yours. The default ideas:
  1. **Vigour:** scale of each move's excursion about the posture centre, and its time share of the beat (small and slow <-> large and
     fast). Peak speed and acceleration stay inside `make_arm.LIMITS`.
  2. **Stiffness:** servo `kp`, and `kv` via `ZETA` in the sim (loose: low kp, low damping, overshoots and settles <-> rigid: high kp,
     near-critical damping, stops dead).
     Report whether this range is plausible for a position servo like the Feetech STS3215 (12 V). Give a best estimate, marked **unverified**.
  3. **Roundness:** end-effector path between poses (straight Cartesian or joint-linear segments with corners <-> curved arcs, e.g. a
     spline through intermediate via points).
  4. **Lead/lag:** per-joint time offsets (all together <-> base and shoulder lead, elbow and wrist follow late, as a fraction of a beat).
  5. **Posture:** the centre pose that the random sequence is drawn around (drooped, low, folded <-> lifted, tall, open).
- **Report in two lines per dial:** how it was done, and the numeric range used. These go into `docs/DIALSTUDY_DIALS.md`.
- **Preset words that are not dials (overseer default, 7.43.6; Kosta may amend):**
  - tense "long holds" = vigour's move-time share very short, so each move finishes early in its beat and holds to the next;
  - light "bouncy" = low stiffness overshoot and settle.
  Neither may change the pose sequence.

### 3. Glitch gates (clip rejection, not pass bars)

No clip Kosta sees may show:
- jitter;
- penetration of the plane or base;
- dwelling at an end stop.

Define the gates numerically in the rules file. Defaults:
- floor and base clearance by the check-csv margins (`m3f_report` FLOOR_M / DISC_M, all FK points, every 50 Hz sample) and no contact;
- end stops: no joint within 3 deg of a `RANGE_DEG` limit for more than 0.1 s;
- jitter: a high-frequency check on joint velocity, e.g. the share of velocity power above 8 Hz, or velocity sign reversals per second.
  Threshold set from the all-neutral clip and stated. Low-stiffness overshoot is allowed; buzzing is not.

Also look at 3 frames per clip, and a fast-forward contact sheet. A clip that fails a gate is regenerated within its dial or preset intent:
adjust the range for feasibility only, and log what changed. **Never show a failing clip.**

### 4. Clips and manifest

12 s each, 1280x720 h264, fixed three-quarter camera (the existing one-arm camera, unless the table/pillar is not visible). The same framing
for all. Sets A-C are **silent**; render with a silent audio track if the recorder needs one.

- **Set A** (11): each dial low and high, others neutral (10), plus 1 all-neutral.
- **Set B** (5): presets with the starting recipes of 7.43.4. Adjust them by eye for feasibility only, and report the final values:
  - heavy: low vigour, high stiffness, large lag, drooped, round;
  - angry: high vigour, high stiffness, angular, together, lifted;
  - tense: small moves, high stiffness, angular, long holds, lifted;
  - calm: low vigour, low stiffness, round, flowing lag, neutral;
  - light: medium-high vigour, low stiffness, round, bouncy, lifted.
- **Set C** (6): heavy, angry and light with the lamp-like head and with the hand/gripper. The sim keeps the ball's mass and inertia;
  shapes are visual only.
  - Render Set C **only after the overseer tells you** that work order 28B's end-effector option is merged into `body`. Until then, do
    A and B.
- **Set D:** the audio folder `/secondary/hyst-data/audio/checkset/` does not exist (overseer, 2026-11-12). **Skip Set D** unless the
  overseer tells you the files are there.

Files go in `/secondary/hyst-data/body/dialstudy/clips/`, with plain descriptive names (e.g. `A_vigour_high.mp4`). Next to each video,
save its 50 Hz joint CSV and its dial values. `manifest.json` lists every clip:
`{id, set, file, csv, effector, intent: {kind: "dial"|"preset"|"neutral", dial?, level?, preset?}, dials: {vigour, stiffness, roundness,
lag, posture}, gates: {passed, values}}`.
Work order 28B reads only this manifest: it codes the names and hides the intent from Kosta.

### 5. Done when

- Sets A and B are rendered, gated and in the manifest; Set C follows once the effector option is merged.
- `docs/DIALSTUDY_DIALS.md` (two lines per dial, ranges, final preset values, the STS3215 plausibility estimate) is pushed.
- MORNING SUMMARY: what was rendered, what was regenerated and why, thread count, total compute.
- Give no reading of the clips. Do not show clips to the user yourself: the overseer checks them first.

**Out of scope (stop and ask; log FOR USER):**
- training of any kind; DEAM; limbic readout; exploration archive / pyribs; brain monitor; any cortex change; hardware;
- new dials or feelings;
- audio of any kind beyond silence.
