# Builder prompt: work order 26B, the Stage 3 trainer, then one timed round (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. A second builder (work order 26A, branch `body-s3d`) produces the
slow-stream lanes, the tempo/RMS table, the energy/jerk thresholds and the bar evaluation at the same time; you read its files through the
fixed interface below. **The full Stage 3 run is NOT part of this work order:** you build, test, then run ONE timed round only when the
overseer says "timed round", report the projection, and stop. One arm only (permanent rule): never add multiple arms, ensembles or
formations.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo26b-<fresh-name> -p MemoryMax=14G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll).
  - **Tests and builds: cores 12-17** (26A uses 6-11 for its long runs). **The timed round and the later Stage 3 run: exactly 6 threads,
    `taskset -c 6-11`, stated in the log** (BRAIN_SPEC 7.38.4: results depend on thread count).
- **Push** within 30 minutes, before every long run, and after every phase. Log: `docs/NIGHT_LOG_body-s3t.md` (new; WO26B section,
  MORNING SUMMARY on top). Run each test module in its own process.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s3t origin/body`, then push `body-s3t`.
- **Environment:** `/secondary/hyst-env/body`. **Data:** `/secondary/hyst-data/body/s3/` (shared with 26A; you write only under
  `/secondary/hyst-data/body/s3/train*/`).

## Read first

- `docs/BRAIN_SPEC.md` **§7.39 and §7.40** (binding: the Stage 3 design and the rulings on every open detail), then 7.34-7.38
  (the Stage 1 toy and its results), 7.27-7.33 (pass2).
- `docs/STAGE1_RULES.md` sections 3-5, 12 (the toy's target, InfoNCE with matched negatives, the 1-Lipschitz observer, hinges with dual
  multipliers, the D hinge) and `docs/PLANNER_BRIEF_WO25_STAGE3_GAPS.md`.
- Code: `scripts/body/s1_toy.py` (the reference implementation of the ingredients at toy scale), `k5p2_train.py` (pass2 trainer:
  `K5P2Run`, `CFG`, `OPTS`, data windows, resume, compute box, mains), `k5_train.py`, `m3f.py` (`make_fns` loss, `Trainer`), `m3f_jax.py`
  (per-block outputs: energy, jerk, hand_v, jolt, acc, floor, lim, tv), `m3e.py` (observers, scoring). Data:
  `/secondary/hyst-data/body/k5/` (splits, windows, lanes).

## The design you implement (BRAIN_SPEC 7.39.4 + 7.40; anything not covered: log FOR USER, take the nearest default, tell the overseer)

- **Body:** the pass2 body and options exactly (`k5p2_train.CFG`: v2f, raised plane 0.053, contact tc 0.006, end stops, smooth-u
  c = 0.5, hard clip); generator caps at defaults; basal ganglia as built, program switch cost W_SWITCH 0.01 kept.
- **Brain (B7 epoch 6, frozen), two state streams:** fast = arousal, surprisal, l3_cos, l3_sin from `k5/lanes` `y[:, :4]`, causal 30 s
  z-score (as the toy's arm-i definition, sd floored at 0.1 x corpus sd); slow = the 13 columns of 26A's `slow` lanes (already
  corpus-normalised). Decide and document how the policy reads them (default: the same input path pass2 uses for `y`, extended by the slow
  columns) and what the observers decode (both streams).
- **Objective:**
  - decoding of both streams by an external and an internal observer, both Lipschitz by spectral norm (exact SVD per step; units
    stated: external = metres of hand/joint position, internal = its descriptor units);
  - InfoNCE music<->motion (temperature 0.1, weight 0.5, symmetric), 4 s motion windows of hand positions vs the matched brain-state
    windows, batch = an anchor song + its 7 nearest train songs by sqrt((dBPM/10)^2 + (dlogRMS/0.3)^2) from 26A's `tempo_rms.json`;
    gradient through the motion encoder;
  - **D hinge per stream** (two multipliers, rising, `mu <- max(0, mu + 0.16 max(0, 0.7 - D_est))` once per round), D_est on a fixed set
    of 16 **validation** windows (never trained on, never the 357 held-out), the toy's shifted-gap definition; decoding loss of each
    stream scaled by (1 + mu_stream);
  - limits as hinge constraints with dual multipliers (start 1, step 0.02 per batch, rising only), free interiors: jerk and energy
    (thresholds from 26A's `thresholds.json`), hand speed 1.2 m/s, hand jolt 9 m/s^2 (the change rate of the 50 Hz hand speed), hand acceleration 4.8 m/s^2, floor margin and limit
    proximity (pass2's definitions in `m3f_jax`). These replace pass2's LAM-weighted soft costs in the Stage 3 path only.
- **Data and compute:** the K5 splits, 60 s windows, resumable (`k5_train.K5Run` machinery), compute box 30 h, validation and best.pkl as
  pass2 (state what "best" uses; default: pass2's ext a).

## Steps

1. **Write `docs/STAGE3_RULES_TRAIN.md` FIRST** (commit and push before the timed round): every definition above made exact (shapes,
   windows, where each term is computed, the multiplier update points, the policy inputs, the observers' targets), so a reader can
   recompute it. Amendments later only as dated entries at the end.
2. **Code**, additive only: `scripts/body/s3_train.py` (+ helpers in new `s3_*.py` files). Existing modules imported, never edited; if a
   small hook in an existing module is unavoidable, it is default-off and pass2's path stays bit-identical (test: one pass2 round from
   `k5p2_train` gives the same loss as origin/body).
   Until 26A's files exist, test with a small stub written by your tests under a temp dir (never under `/secondary/hyst-data/body/s3/`).
3. **Tests:** spectral-norm Lipschitz bound measured on random inputs; InfoNCE batch construction (anchor + 7 nearest, no duplicates);
   D_est on a hand-made case; multiplier updates (rising only); limit hinges zero inside the envelope; resume gives the same state as an
   uninterrupted run for 2 rounds on a tiny window set; end-to-end smoke (a few windows, a few rounds) without NaN.
4. **Report to the overseer** (push, night log): the design file, tests, smoke numbers, one-round time on cores 12-17 (informational).
   Then **wait**. The overseer merges 26A's deliverables and says "timed round".
5. **Timed round** (on the overseer's word only): one detached unit, 6 threads, cores 6-11, real data, the full round as the run would do
   it (including one validation and the per-round D_est). Report: seconds per round, rounds in the run, projected compute hours vs the
   30 h box (BRAIN_SPEC 7.39.4: if it projects past 30 h, the overseer asks). **Do not launch the Stage 3 run.**

## Done when

`body-s3t` pushed with the rules file (committed before the timed round), code + tests, night log, smoke results; after the overseer's
word, the timed round's projection reported.
