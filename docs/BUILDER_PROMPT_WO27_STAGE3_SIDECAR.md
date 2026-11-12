# Builder prompt: work order 27, Stage 3 side-car reports (hinge activity at each validation, round-400 clip) (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **The Stage 3 run is running and must stay untouched** (BRAIN_SPEC 7.41.4):
never write into its folder, never signal its unit, never use its cores. Report only. One arm only (permanent rule).

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **The run:** unit `hyst-wo26b-run-r3` (amended 2026-11-12: r1 was stopped by a power-off at round 54; the overseer resumed it from
  its checkpoint as r3 on 2026-11-12 09:28; a further resume would get a new unit name `hyst-wo26b-run-r<N>`, so treat the run as alive
  while any unit matching `hyst-wo26b-run-*` is active), code = branch `body` a9fd858 (`scripts/body/s3_train.py`,
  `s3_data.py`, `s3_obs.py`, `s3_loss.py`; rules `docs/STAGE3_RULES_TRAIN.md`), output `/secondary/hyst-data/body/s3/run/` (`train.log`,
  `ckpt.pkl` every round, `best.pkl` at validations, `progress.json`). It uses cores 6-11. Validations at rounds 200, 400, 600, 800 and
  the end (977). At ~82 s per round, round 200 is expected around 12:50 on 2026-11-12 and round 400 around 17:30. Arm the watcher
  before round 200; if it is armed late, report the missed round as missed (do not reconstruct it from a later checkpoint).
- **Other load:** sessions of another project (Kabl) also run on this machine. Check `top`/`htop` before your test rollouts; if cores
  12-17 are busy, still use only 12-17 and note the timing in the night log.
- **Your jobs:** detached and memory-capped:
  `systemd-run --user --unit=hyst-wo27-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, **cores 12-17 only (`taskset -c 12-17`), never 6-11**, mains only (armed poll on `/sys/class/power_supply/ADP1/online`).
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-s3r.md` (new; MORNING SUMMARY on top). Run each test module
  in its own process.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s3r origin/body`, then push `body-s3r`.
- **Environments:** body `/secondary/hyst-env/body`, brain `/secondary/hyst-env/brain`. **Output:** `/secondary/hyst-data/body/s3/run_report/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.41** (binding: this work order), 7.39.4, 7.40, 7.39.3 (limit reporting).
- `docs/STAGE3_RULES_TRAIN.md` (section 2 point 4: the seven limit hinges and their thresholds; point 3: the 16 fixed validation windows
  of the D estimate) and `docs/STAGE3_RULES_DATA_EVAL.md` (section 4: occupied cells, shoulder sd).
- Code: `s3_train.py` (checkpoint contents, `update_D` rollout of the 16 validation windows), `m3f_jax.py` (`penalties`, per-block
  `energy`, thresholds `HAND_MPS`, `JOLT_MPS2`, `ACC_MPS2`, `LIM_DEG`, `FLOOR_M`, `DISC_M`), `s3_eval.py` (song rollouts), `s0_measure.py`
  (cells, shoulder sd), `k5p2_render.sh` (one-arm camera render of a joint CSV), `hf_share.py` (CSV format).

## Steps

1. **Rules first:** `docs/STAGE3_SIDECAR_RULES.md` with the exact definitions below; commit and push before any long job.
2. **Hinge activity at each validation** (`scripts/body/s3_sidecar.py`, new): a watcher that polls `train.log` every 60 s. When a new
   "validation at round R" line appears, it copies `ckpt.pkl` (copy to `run_report/R/` first; read only the copy; if the copy fails to load,
   retry after 30 s) and:
   - reads the current multipliers of the seven limit hinges and the two D multipliers from the checkpoint;
   - rolls out, with the checkpoint's policy, the same 16 fixed validation windows the trainer uses for D_est (argmax, start poses seed
     4242, the trainer's own data path) and computes, **per limit hinge, the share of steps with the constraint active (on or over its
     threshold)**: hand speed, jolt and hand acceleration on their 50 Hz hand samples (>= 1.2 m/s, >= 9 m/s^2, >= 4.8 m/s^2); floor on control
     steps with check-csv floor margin <= 0; limit proximity on control steps x the three bends with |q| >= 100 deg; energy and jerk per
     block (block energy >= 0.3747, block jerk >= 4.748e6, from `thresholds.json`), reported as the share of blocks;
   - writes `run_report/R/hinges.json` (shares, multipliers, D_fast/D_slow from the log line of that round, the validation numbers from
     the log) and appends one line per validation to `run_report/summary.txt`.
   Test on the timed-round output `/secondary/hyst-data/body/s3/train_timed/` (its validation at round 2) before arming the watcher.
   Arm the watcher as one detached unit; it exits after the final validation or when the run unit is no longer active.
3. **Round-400 clip** (same watcher, at the round-400 validation only): roll out `best.pkl` as of that validation (copy it first) on
   **Instant Crush** (the whole song, as `s3_eval.py` rolls out a held-out song, argmax), write the joint CSV, render **60 s, from 60 s to
   120 s of the song**, with the one-arm camera of `k5p2_render.sh` (720p < 30 MiB, the song's audio for that window), to
   `run_report/400/instant-crush-r400-60s.mp4`. Report for that 60 s clip: shoulder sd (deg, joint column 1) and occupied 5 cm hand cells
   (`s0_measure` definitions), and the same two numbers for pass2 on the same 60 s (from its existing joint CSV
   `/secondary/hyst-data/body/k5p2/check/songs/instant-crush.pass2.csv`, or the pass2 rollouts) for reference. Test the render path first on
   the timed-round best.pkl (10 s is enough), then delete that test video.
4. **Report** to the overseer at each validation is not needed (the overseer reads `summary.txt`); report once when the watcher is armed
   (unit name, test results) and once when the round-400 clip exists (path, size, duration, the four numbers). Push and append the night
   log at each event.

## Done when

`body-s3r` pushed with the rules file, code + tests, night log; the watcher unit armed and its test on `train_timed/` reported; at round
400 the clip and its numbers reported.
