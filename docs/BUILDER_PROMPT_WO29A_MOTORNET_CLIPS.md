# Builder prompt: work order 29A, motor-network toy test: network, body, gates, clips (2026-11-12)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing from it ships:
- no reward or label-driven learning, no training of any weights;
- no hand-tuning of movement by eye, no picking of settings by looking at them;
- no pass bars beyond the safety gates;
- no verdict from you. Kosta (the user) judges the clips by eye, blind.

One arm only (permanent rule). A second builder (work order 29B) adapts the blind labelling tool, writes the measurement script and the
report script in parallel. Its interface with you is the manifest and the per-clip files of section 6.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing. No network downloads.
  - The cortex (B7 epoch 6) is frozen: read its lanes, never change or retrain it.
  - v47 must not seed anything. Its exports stay byte-identical in Off.
  - Data, audio and videos stay outside git. Copyrighted audio is never committed or uploaded anywhere.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-mnet origin/body`, then push `body-mnet`.
- **Jobs:**
  - Detached and memory-capped:
    `systemd-run --user --unit=hyst-wo29a-<fresh-name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - `python -u`. Cores **6-11** (`taskset -c 6-11`), 6 threads; state the thread count in the report.
  - Mains only: the script polls `/sys/class/power_supply/ADP1/online` and waits while it reads 0.
  - Agent 2 (29B) uses cores 12-17.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnet.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body` (MuJoCo, JAX), brain `/secondary/hyst-env/brain` (torch, for the cortex lanes).
  **Output root:** `/secondary/hyst-data/body/motornet_toy/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.44** (binding: the toy test, its gates, out-of-scope list, overseer defaults 7.44.5), §7.43 (the piece) and
  §7.42 (why: no proxy objectives).
- Round 1 (the hand-set dial study), whose body, camera and gates you reuse:
  - `docs/DIALSTUDY_RULES.md` (body, stepping, gates (d)), `docs/DIALSTUDY_DIALS.md`, `docs/DIALSTUDY_REPORT.md`;
  - `scripts/body/dialstudy.py`, `dialstudy_render.sh`, `dialstudy_manifest.py`, `dialstudy_straight.py`, `dialstudy_sheets.sh`;
  - round-1 clips and manifest: `/secondary/hyst-data/body/dialstudy/clips/manifest.json` (22 clips; Set C has the lamp head).
- Body code in `scripts/body/`: `make_arm.py` (`KP`, `tune_kv`, `ZETA`, `LIMITS`, `RANGE_DEG`), `make_arm_v2.py`, `arm_sim.py`
  (`limit_target`, `csv_text`), `m3f_report.py` (`fk_points`, FLOOR_M / DISC_M).
- Cortex lanes (only for Part 3): `scripts/body/k5_data.py` (`song_lanes`: `l3_cos`, `l3_sin` = beat-band phase, `arousal_b7`) and
  `scripts/body/k5_video_lanes.py` (lanes of a song outside the corpus, same model, same format).
- The paper the study is built on (no download; from memory is fine): Stroud, Hennequin, Porter & Vogels, Nature Neuroscience 2018,
  "Motor primitives in space and time via targeted gain modulation in cortical networks".

## The work

### 1. Rules file first

Write `docs/MOTORNET_RULES.md` and push it **before any clip is rendered**. It holds:
- (a) the network: unit count, time constant, nonlinearity, recurrent weight distribution and spectral radius, inputs, control units
  (count, subset size and overlap, how a unit scales gains, the range of each unit's value, the optional global gain), readout, seeds;
- (b) the one calibration (section 2);
- (c) the spinal spring-damper and the body/stepping path (section 3);
- (d) the gates, including the minimum-motion gate (section 4);
- (e) the sampling rule (section 5);
- (f) the definitions of every measurement (section 7), so 29B's script and yours agree.

The overseer reviews it within 30 min. Continue meanwhile. If the overseer asks for a change, redo only what it touches.

### 2. Motor network (7.44.3.1)

- One recurrent rate network, about **200 units**; unit time constant one value in **50-100 ms** (state it); smooth saturating
  nonlinearity (default `tanh`, gain applied as `r_i = tanh(g_i x_i)` or the paper's form; state it).
- Recurrent weights random (Gaussian, seeded), **fixed for the whole study**, scaled so the network sits near the edge between decaying
  and self-sustained activity at gain 1 (default spectral radius 1.0-1.1 of the effective linearised matrix; state the value and how you
  checked it, e.g. activity with zero input decays slowly or persists).
- Inputs: `cos` and `sin` of the beat-band phase (silent clips: a fixed 100 BPM phase; music clips: the song's cortex `l3_cos`, `l3_sin`),
  plus the cortex arousal signal when music is present (silent: 0). Input weights random, seeded, fixed.
- About **4 modulatory control units**. Each scales the gains of a random subset of neurons (subsets overlap; state the subset size and the
  combination rule, e.g. `g_i = g_global * prod_k c_k^{m_ki}`). A gain setting = the values of these units (+ optional global gain).
- Readout: **5 linear outputs** -> joint targets (base yaw, shoulder, elbow, wrist bend, wrist roll). Readout weights random, seeded, fixed.
- **One allowed calibration:** a single overall scale and offset per joint, fitted once at gain 1 on a silent run, so the outputs use a
  sensible part of each joint's range (default: the gain-1 output mean maps to round 1's neutral centre pose, and +-2 sd maps to +-60 % of
  round 1's neutral amplitudes; state the numbers). Fixed afterwards for every clip. **No other fitting.**
- Integrate the network at the control rate (100 Hz) or finer (state it).

### 3. Body below the network (7.44.3.2)

- Spinal layer: each joint target passes through a per-joint spring-damper (muscle-like, second order), stiffness and damping **fixed at
  mid values for the whole study** (default: natural frequency about 3 Hz, damping ratio about 0.7; state them). No per-clip changes.
- Then the same body and stepping as round 1 (`docs/DIALSTUDY_RULES.md` (a)): v2f model, plain MuJoCo on CPU, 100 Hz control with 5
  substeps of 2 ms, `arm_sim.ArmSim.limit_target` limiter, hard end stops, servo gains at round 1's neutral stiffness (state kp and kv).
- End effector: the **lamp head** (default, round 1 Set C geometry, `ensemble_preview --implement lamp`); the ball only for Part 2. The
  sim keeps the ball's mass and inertia for both.
- **Warm-up** (overseer default 7.44.5a): every clip runs network and sim for 10 s before the 12 s shown. For music, the 10 s of the song
  before the excerpt drive the warm-up.

### 4. Gates (7.44.3.4; clip rejection, not pass bars)

Round 1's gates (d), unchanged: clearance (check-csv FLOOR_M / DISC_M), no contact at any substep, end stops (no ranged joint within 3 deg
of a limit for more than 0.1 s; target: dwell 0), jitter (share of joint-velocity power above 8 Hz; threshold as round 1 or stricter),
realised speed and acceleration within `make_arm.LIMITS` (p99 and max, central differences). **Plus:** the arm must actually move.
Default: hand-point p5-p95 extent at least 0.10 m on at least one axis over the 12 s, and no 3 s stretch with mean hand speed below
0.01 m/s; state the values in the rules file.
A setting that fails is discarded and replaced by the next sampled one (section 5). Report how many were discarded and by which gate.
Look at 3 frames per clip and a contact sheet; **never show a failing clip.** Do not discard for any reason other than a gate.

### 5. Sampling the gain settings (7.44.3.3)

- Draw seeded random settings of the control units, uniform (or log-uniform; state it) across their full range, one seed for the whole
  draw (record it). Simulate each silent; discard only those that fail a gate; take **the first 10 that pass**, in draw order.
- Add 2 settings: all control units at their **low** extreme, and all at their **high** extreme (global gain, if used, at 1). If one fails a
  gate, it is not shown and not replaced; report it (overseer default 7.44.5d).
- You must not look at clips or measurements before the 12 settings are fixed. Settings are numbered S01-S12 in draw order (S11 low, S12 high).

### 6. Clips, files and manifest

12 s each, 1280x720 h264, the round-1 one-arm camera and framing. Files in `/secondary/hyst-data/body/motornet_toy/clips/`.

- **Part 1, silent:** S01-S12 with the lamp. 12 clips. Silent audio track if the recorder needs one.
- **Part 2, ball:** S01 and S02 with the ball. 2 clips.
- **Part 3, with music: HELD.** The audio folder `/secondary/hyst-data/audio/checkset/` does not exist (overseer, 2026-11-12), and the
  excerpt times are not chosen. Build the music path (cortex lanes for a song via `k5_video_lanes.py`, excerpt + preceding 10 s, audio muxed
  into the clip) and test it on a **synthetic click track** you generate (not copyrighted). Do not render Part 3 until the overseer says
  the files and excerpt times are there. Then: per song, two settings drawn with a recorded seed from S01-S12 (two different settings).
  Never pick an excerpt or setting yourself.
- **Part 4, consistency:** 4 round-1 clips drawn with a recorded seed from round 1's manifest; reference the existing files, do not
  re-render.

Next to each rendered video save: its 50 Hz joint CSV (`arm_sim.csv_text`), the network activity `r(t)` at 50 Hz for the 12 s as
`<id>.activity.npy` (float32, shape T x N), the hand FK path is derivable from the CSV. Settings in `settings.json` (S01-S12, values, draw
index, discards with gate names). `manifest.json` lists every item:
`{id, part, file | files, csv, activity, effector, setting, setting_values, song?, excerpt?, round1_id?, gates: {passed, values}}`.
Part 3 items use `files: [a, b]` (the two renders, setting ids in `setting: [..]`); Part 4 items carry `round1_id` and the round-1 file
path. Work order 29B reads only this manifest and these files.

### 7. Measurements (7.44.3.5)

29B writes `scripts/body/motornet_measure.py`, computing per setting from your files: participation ratio of `r(t)`; regime (decays /
cycles / wanders); dominant movement frequency; mean hand speed; mean hand height; hand-path straightness (chord/arc per stroke). You
define each in the rules file (f) first (defaults: PR = (sum lambda)^2 / sum lambda^2 of the covariance of `r` over the 12 s; regime from the
silent run with input: "decays" if the std of `r` in the last 4 s is < 0.1x that of the first 4 s, "cycles" if the top PC's
autocorrelation has a peak > 0.5 at a lag of 0.3-5 s, else "wanders"; frequency = peak of the hand-speed power spectrum; stroke = hand path
between hand-speed minima, as `dialstudy_straight.py`). Run 29B's script on your files once it is pushed and check the numbers against
your own spot-check of two settings.

### 8. Done when

- Parts 1, 2 and 4 are rendered (or referenced), gated, in the manifest; the Part 3 path is tested on a synthetic click track.
- `docs/MOTORNET_RULES.md` and `docs/MOTORNET_PARAMS.md` (every parameter actually used: network, calibration, spring-damper, servo gains,
  seeds, threads, total compute) are pushed.
- MORNING SUMMARY: what was rendered, discards per gate, thread count, total compute.
- Write "CLIPS READY <commit>" in the night log. Give no reading of the clips. Do not show clips to the user yourself: the overseer checks
  them first.

**Out of scope (stop and ask; log FOR USER):** reward or label-driven learning; training of network weights or readout beyond the one
calibration; limbic part; DEAM; exploration archive / pyribs; brain monitor; any cortex change; hardware; hand-picking or hand-shaping of
movements; any audio file other than the synthetic test click track.
