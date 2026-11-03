# Builder prompt: step Z (Z1–Z5), M0 and M2, local (2026-11-03)

## Kaggle access (done by the user, 2026-11-03)

- Kaggle user name: `kostavukicevic`. The token is a new-style access token in `~/.kaggle/access_token` (mode 600), not `kaggle.json`.
  Never print it, copy it into the repo, or put it in a log.
- Tested by the overseer: Kaggle CLI 2.2.5 authenticates with it (`kaggle datasets list --mine` answers "No datasets found").
  That CLI needs `six`, which it does not declare: install `kaggle==2.2.5 six` in `/secondary/hyst-env/body`.
- Quota (user, 2026-11-03): GPU 30 h/week, TPU 20 h/week. Log GPU hours used per job. Do not use the Kaggle "AI" credit.
- Keep the laptop on mains power for anything longer than a few minutes.

---

You are a builder for Hysteresis. Work alone, in order, without waiting for input except where this prompt says so.

## Where

- Repo: `/secondary/Programming/Github/Hysteresis`. Make your own worktree on a new branch `body-z` from origin `body`:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-z -b body-z origin/body`. Work only there.
  Never touch the main checkout, `keys-decide`, or `master`. Push `body-z` when you finish each phase.
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's standing rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` are read-only. Never drive hardware. Data, models, audio and videos stay outside git, under `/secondary/hyst-data/`
  (nothing on the root disk).
- The brain environment `/secondary/hyst-env/brain` (torch 2.15 CPU) must stay unchanged. Put MuJoCo, MJX and JAX (CPU) in a new venv
  `/secondary/hyst-env/body`. Pin exact versions in `scripts/body/requirements.txt`. Install nothing globally. No paid services, no cards,
  no new accounts.
- Every job longer than 10 min runs memory-capped as a detached user service:
  `systemd-run --user --unit=hyst-<fresh-name> -p MemoryMax=20G -p MemorySwapMax=0 <script>`. Use `python -u`. Judge memory by `anon` in the
  unit's `memory.stat`, not by MemoryCurrent. Long local runs only on mains power: check `cat /sys/class/power_supply/AC*/online` first;
  if 0, log it and wait at most 15 min for power, then skip the run and log FOR USER.

## Read first

1. `docs/BODY_BRAIN_PLAN.md` in full. It is the work order. §1 (rules), §4 (step Z), §6 (M0), §7 (M2), §12 (template) are yours.
2. `scripts/compute/README.md` and the code there (tests: `cd scripts/compute && python -m unittest -v test_compute`).
3. `docs/BRAIN_SPEC.md` §0 (8 training threads), §7.10, §7.11.
4. `scripts/brain/train.py`, `train_b7.py`, `core.py`, `core_b7.py`, `check_b7.py`, `scripts/brain/B7_NOTES.md`.
5. `crates/hyst-compile/src/ensemble.rs` (`Rig::illustrative_five_axis`, `Implement`), `crates/hyst-compile/src/body.rs` (`LIMITS`, `JOINTS`),
   `crates/hyst-cli/src/main.rs` (`hyst score-csv`, `hyst check-csv`).

## Overseer's corrections to the plan (apply these; they are facts about the code, not rule changes)

- **C1.** `/secondary/hyst-data/brain/corpus/feature_stats.npz` holds `mean` and `sd`, not `std`. `pack_features.py` reads `std` and falls back
  to 1.0, so its "std units" cast error would be raw units. Read `std` or `sd` (as `train.py:68` does). Add a test with an `sd` file.
- **C2.** The corpus manifest (`/secondary/hyst-data/brain/corpus/manifest.json`, 3,176 entries) has splits `train` (2,819) and `heldout` (357)
  only. Validation is a subset of train by `scripts/brain/val_artists.json`. Pack with no `--splits` filter. Paths in it are absolute.
- **C3.** Checkpoints today are per epoch only (`train.py` `fit`); a B7 epoch takes about 2 h. Z2's "every 30 min and on SIGTERM" means a
  mid-epoch checkpoint: model, optimiser, scheduler position, batch index within the epoch, and every RNG state, so the resumed run is
  identical. This is new code in `train.fit`, not a flag. The old per-epoch files and their names stay.
- **C4.** The evaluation sets are not in manifest form. DEAM and MERP features are read by `check_b7.py --precheck` (find where), Ballroom and GTZAN
  live in `/secondary/hyst-data/brain/testsets/`. For Z3, write a small manifest per set in `pack_features.py`'s input format, or skip the set and
  log it. Only sets a remote check needs must go up; nothing in this order runs a check remotely, so packing them is optional.
- **C5.** `jobs/bench_b7.json` sets `OMP_NUM_THREADS=4`. On the laptop, run the CPU benchmark at 8 threads (spec §0). On Kaggle, use the
  job as is and record the core count.

## Phases

Start: `docs/NIGHT_LOG.md` gets a new dated section for this order with a MORNING SUMMARY block on top (filled at the end). Commit it.

**Phase Z1 (time box 3 h): `--device {cpu,cuda}`** in `train.py`, `train_b7.py`, `core.py`, `core_b7.py`, `check_*.py`. Default `cpu`. Results on
cpu must not change: the existing golden and identity tests pass unchanged. The complex recurrence stays float32. No mixed precision in this
order. Manifest paths may be relative (resolve against the manifest's folder). Feature loaders cast to float32 on load. There is no GPU here:
test cuda paths with a guard that skips when cuda is absent, and confirm nothing on the cpu path calls cuda.
Failure default: if a file cannot take the flag without changing cpu results, leave that file out and log it.

**Phase Z2 (time box 3 h): mid-epoch checkpoints and resume** (correction C3). Every 30 min of wall time and on SIGTERM, atomic writes. Resume
from a `--ckpt DIR` (the runner's `{CKPT}`). Test: a toy run (small model, synthetic data, a few minutes) killed with SIGTERM mid-epoch, then
resumed, against an uninterrupted run: parameters equal up to float rounding (state the tolerance you use and the max difference you got).
Failure default: per-epoch resume only; log FOR USER.

**Phase Z3 (time box 1.5 h): pack the features.** Correction C1 first. Pack the corpus with `pack_features.py` (float16) into
`/secondary/hyst-data/pack/features`. Record the cast error it prints, the folder size and the track count. `manifest.py verify` passes.
Upload with the token above; the dataset is **private**; audio never goes up (the packer
nulls it; confirm no `.mp3`/`.wav` is in the folder). `manifest.py verify` on a download of it, if cheap; else log "not re-verified".

**Phase Z4 (time box 30 min): code snapshot** of the commit the Kaggle jobs will run, into `/secondary/hyst-data/pack/code`. Private upload.

**Phase M0 (time box 5 h): the body in physics**, plan §6, in `scripts/body/`:
- `arm.xml` (MJCF) generated from the rig numbers by a script (`make_arm.py`), so the numbers have one source. Axes, links and ranges as in
  `Rig::illustrative_five_axis()`. Base yaw and wrist roll are continuous. Implement: the rig default (`Implement::default()` = mirror ball).
- `BODY_NOTES.md`: every mass and inertia with its basis. No servo is chosen: use a typical 30 kg·cm-class bus servo, all its numbers marked
  provisional, with the datasheet you took them from (name, URL, the numbers). Same for encoder resolution.
- Actuators, limits, gravity, 2 ms timestep, 100 Hz control, proprioception with one-step delay and quantisation: exactly as plan §6, with
  `body.rs` `LIMITS` as the speed and acceleration limits.
- Export of a trajectory to the 50 Hz joint CSV that `hyst check-csv` reads. `hyst check-csv` passes on a physics trajectory.
- Tests (design, no claim): gravity sag at rest at neutral pose and at the worst-case pose (arm straight out), each joint's required torque
  against stall torque, and the sag in degrees; limits never exceeded on a 60 s random-command run; MuJoCo CPU against MJX (on CPU JAX) on a
  10 s trajectory, max joint difference, with the tolerance stated before you run it; mechanical power per step Σ|τ·ω|.
Failure defaults: if MJX does not install, do CPU only and log; if a joint's gravity torque exceeds the provisional stall torque, report the
number and do not change the geometry.

**Phase M2 (time box 3 h): spinal pattern generators**, plan §7, no learning, in `scripts/body/cpg.py`. One phase oscillator per joint, commands
at 10 Hz (frequency 0.1–4 Hz, amplitude, centre, neighbour lag 0–0.5 cycle), rate-limited so targets stay smooth and inside the limits.
Amplitude for the two continuous joints: cap at ±180° (overseer default; log it as FOR USER). Unit tests: smoothness (no target jump above the
speed limit × control period), limits never exceeded under random commands, coupling sign (a positive lag makes the neighbour trail).
Run M2 through M0 for 60 s of random commands and export the CSV; `hyst check-csv` passes on it.

**Phase Z5 (time box 2 h of builder time; Kaggle runs may take longer): the two benchmarks.**
- Write `scripts/brain/bench_b7.py` and `scripts/body/bench_physics.py` to the job contracts in `scripts/compute/` (`{DATA}`, `{OUT}`,
  `{CKPT}`, progress file, `results.json`).
- Run both locally through `scripts/compute/run_job.py`, memory-capped: B7 forward+backward per audio hour, peak memory, with and without
  gradient checkpointing, and forward-only per audio hour (8 threads, correction C5); physics steps per second at 1, 64, 512, 1,024 and 4,096
  environments on MuJoCo CPU (and MJX CPU if it installed).
- Kaggle: build kernels with `scripts/compute/kaggle/make_kernel.py`, push, fetch outputs to
  `/secondary/hyst-data/runs/<job-id>/`. First, check what the README lists as "to check on first use" and log the answers. If Kaggle refuses
  (auth, quota, GPU not granted), leave the kernels built (folders under `/secondary/hyst-data/pack/kernels/`) with the exact push commands
  and the error in the log, and finish.
- No long run of any kind after this phase. Nothing beyond these two benchmarks goes to Kaggle.

## Finish

Fill the MORNING SUMMARY: per phase, done or the default taken, numbers, FOR USER items, commits. Then report in a few lines:
- compute test results (`test_compute` and `scripts/brain` unittest counts);
- the two benchmark numbers, local and Kaggle, or what blocked them;
- M0 numbers: masses with their basis, gravity sag and torque margins, limit tests, CPU/MJX parity;
- M2 test results;
- FOR USER items;
- branch, last commit, data paths.

Never say something looks better or good. No claims beyond what a test checks. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`
or `docs/NEXT_DECODER_THEN_BRAIN.md`.
