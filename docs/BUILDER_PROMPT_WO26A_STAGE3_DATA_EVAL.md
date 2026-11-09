# Builder prompt: work order 26A, Stage 3 data, limit thresholds and the bar evaluation (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. A second builder (work order 26B, branch `body-s3t`) builds the Stage 3
trainer at the same time and reads the files you produce; the interface in "Deliverables" is fixed, do not change it without logging
FOR USER. **No training run in this work order.** One arm only (permanent rule): never add multiple arms, ensembles or formations.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo26a-<fresh-name> -p MemoryMax=12G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll).
  - **6 threads, `taskset -c 6-11`, for every run, stated in the log.** Work order 26B uses cores 12-17 for its tests.
- **Push** within 30 minutes, before every long run, and after every phase. Log: `docs/NIGHT_LOG_body-s3.md` (new; WO26A section,
  MORNING SUMMARY on top). Run each test module in its own process.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s3d origin/body`, then push `body-s3d`.
- **Environments:** brain `/secondary/hyst-env/brain` (torch, B7, librosa as used by `scripts/body/s0_tempo.py`), body
  `/secondary/hyst-env/body` (JAX, MuJoCo). **Data:** `/secondary/hyst-data/body/s3/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.39 and §7.40** (binding: the Stage 3 design, bars (a)-(f), and the rulings on thresholds and defaults), then
  7.34-7.36 (Stage 0: the measures and the interleaved 2AFC ruling 7.36.3), 7.27-7.33 (pass2: check-csv, (e'1)/(e'2)).
- `docs/PLANNER_BRIEF_WO25_STAGE3_GAPS.md` section 2 (what exists).
- Code: `scripts/body/k5_data.py` (`song_lanes`: the B7 epoch-6 pass; L4 = `out[3]["h"]`, complex), `s0_tempo.py`, `s0_measure.py`,
  `s0_roll.py`, `k5p2_eval.py`, `k5p2_train.py`, `m3f.py`, `m3f_jax.py` (energy, jerk outputs), `build_v47.py`, `hf_share.py`,
  `m3f_report.py`. Data: `/secondary/hyst-data/body/k5/` (splits, windows, lanes), `/secondary/hyst-data/body/s0/` (pass2 rollouts of
  the 357 held-out songs, tempo.json), `/secondary/hyst-data/body/k5p2/run/best.pkl` (pass2, r600).

## Steps

1. **Write `docs/STAGE3_RULES_DATA_EVAL.md` FIRST** (commit and push before any long run): every definition below, in enough detail that
   a reader can recompute each number. Amendments later only as dated entries at the end.
2. **Slow-stream lanes** (new B7 pass, brain env, resume-safe, one detached unit; the first lane pass took 57 min for 3,176 songs):
   for every song in train, val and check, the block mean (0.5 s blocks, the same block indexing as `k5/lanes`) of the L4 state's real
   and imaginary parts. PCA fitted on **train songs only**; keep the top 8 components (report explained variance). Then per block:
   `slow` = [8 L4 PCs, 8 s surprisal integral (causal sum of total surprisal over the last 8 s, from `s10[:, 4]`, NaN as 0),
   logpow_L1..L4 (from `k5/lanes` `y[:, 4:8]`)] = 13 columns, each z-scored by the **train-corpus** mean and sd (one fixed affine map,
   no within-song normalisation). Test: block count equals `k5/lanes` for 10 songs; the PCA projection reproduces on a reload.
3. **Tempo and RMS for every song** (train, val, check): librosa BPM exactly as `s0_tempo.librosa_bpm`, and log RMS of the whole song's
   audio (mono, 22,050 Hz, `log(sqrt(mean(y^2)))`). Reuse `s0/tempo.json` for the 357 check songs if it is the same computation (check
   5 songs). Parallel processes allowed within the 6 cores.
4. **Energy and jerk thresholds (BRAIN_SPEC 7.40.2):** replay the v47 reference joint trajectories (the danced-song exports used by
   `build_v47.py` / `hf_share.py`; reference data only) as servo targets on the **v2f** body with the pass2 configuration
   (`k5p2_train.CFG`), in 0.5 s blocks; energy per block and jerk per block exactly as `m3f_jax` computes them for the policy.
   Energy threshold = v47's mean block energy; jerk threshold = 1.25 x v47's mean block jerk. If v47 cannot be replayed on v2f: log FOR
   USER with the reason, and use pass2's realised values (best.pkl, mean over its training windows) x 1.5. Write `thresholds.json` and a
   dated note in the rules file before 26B's timed round.
5. **Bar evaluation `scripts/body/s3_eval.py`** (new file; imports, never edits, existing modules): given a policy pickle (pass2 format
   or 26B's), roll out the 357 held-out songs (argmax; or reuse given rollouts) and compute, per BRAIN_SPEC 7.39.4:
   (a) K5 external (a) > 0 and paired vs untrained > 0 (as `k5p2_eval`);
   (b) machine 2AFC on tempo-matched pairs (|dBPM| <= 5, different artists; `s0_measure.tempo_pairs`), interleaved 30 s clips, odd
       clips train, even clips test, a 30 s gap between clips (7.36.3), the `s0_measure.pair_2afc` classifier otherwise;
   (c) between-song JS / within-song JS, within = odd vs even clips of the same song (5 cm cells, `s0_measure.js_dist`);
   (d) occupied cells per song at equal duration (median), vs pass2's;
   (e) share of songs with shoulder sd >= 8 deg;
   (f) check-csv on the three danced songs, (e'1)/(e'2) vs `docs/hf_v47_eprime_reference.json` (<= 1.25x), and the per-joint limit
       report (BRAIN_SPEC 7.39.3: p99 and max of realised speed and acceleration, central differences, single-sample max = flag).
   Reported only: decoding D per stream (fast, slow), kappa-0 control, program usage, the Burger contrasts (shoulder amplitude vs pulse
   clarity, wrist bend vs low-band flux; state your definitions in the rules file). Output one JSON with every bar's value and pass/fail.
6. **Reference run of `s3_eval.py` on pass2 best.pkl** (one detached unit). Expected (sanity, from 7.39.4): 2AFC about 49 %, JS ratio
   about 0.69, shoulder sd about 3-4 deg. Its occupied-cells median is the pass2 reference for bar (d). If a number is far from the
   expectation, find out why and report; do not tune to it.
7. **Report:** push; night log; tell the overseer: paths, the PCA variance, the thresholds and how they were obtained, the pass2
   reference bars, test results, any FOR USER.

## Deliverables (fixed interface for 26B)

- `/secondary/hyst-data/body/s3/slow/{train,val,check}/<id>.npz` with `slow` (nb, 13) float32 (column order as step 2) and
  `/secondary/hyst-data/body/s3/slow/norm.json` (PCA components, means, sds, explained variance, column names).
- `/secondary/hyst-data/body/s3/tempo_rms.json`: `{song_id: {"bpm": float, "log_rms": float}}` for every song.
- `/secondary/hyst-data/body/s3/thresholds.json`: `{"energy": float, "jerk": float, "method": "v47-v2f" | "pass2x1.5", ...}` in the units
  of `m3f_jax`'s per-block `energy` and `jerk` outputs.
- `scripts/body/s3_eval.py` + tests; `/secondary/hyst-data/body/s3/eval_pass2/bars.json`.

## Done when

`body-s3d` pushed with the rules file (committed before the long runs), code + tests, night log; the deliverables above exist; pass2
reference bars reported.
