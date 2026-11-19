# Builder prompt: work order 2, builder 1, body track (M1 + K1, M3 benchmark, T-M3) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis`. `git fetch -q origin`, then make your worktree:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-m1m3 -b body-m1m3 origin/body`. Work only there.
  Push `body-m1m3` after every phase (`git push -u origin body-m1m3`; the remote is HTTPS with the gh login). Never touch `body`,
  `keys-decide`, `master` or the main checkout. Builder 2 works in parallel on `body-h2show`: do not edit its files (`core_b7.py`'s
  hippocampus, `scripts/brain/braindump*`, `mind_state` code).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Version 47 stays byte-identical in `Off` (you should not touch dance code; if
  you do, run the v47 check in `docs/OVERSEER_HANDOFF.md`). Data under `/secondary/hyst-data/body/` (never the root disk), outside git.
- Environments: `/secondary/hyst-env/body` (MuJoCo, MJX, JAX) and `/secondary/hyst-env/brain` (torch). Install nothing new without logging it;
  pin versions in `scripts/body/requirements.txt`. No paid services.
- **Your share of the machine: 12 threads, 14 GB.** Every run longer than 10 min goes through `scripts/compute/run_job.py`, as a detached
  memory-capped service: `systemd-run --user --unit=hyst-wo2b1-<fresh-name> -p MemoryMax=14G -p MemorySwapMax=0 <script>`. `python -u`.
  Judge memory by `anon` in the unit's `memory.stat`. Mains power only (`cat /sys/class/power_supply/AC*/online`): if 0, wait at most
  15 min, then skip the run and log FOR USER.
- Kaggle: user `kostavukicevic`, token in `~/.kaggle/access_token` (never print it). CLI in `/secondary/hyst-env/body` (needs `six`).
  Free quota only (GPU 30 h/week); log GPU hours per job. Never use the Kaggle "AI" credit.
- Log: `docs/NIGHT_LOG_body-m1m3.md`, MORNING SUMMARY on top, updated after every phase.

## Read first

1. `docs/BODY_BRAIN_PLAN.md` (version 2), all of it; your parts are §5, §6, §11. Then `docs/WORK_ORDER_2026-11-04.md` (builder 1 is you).
2. `docs/BRAIN_SPEC.md` §7.10–7.12. `docs/NIGHT_LOG.md` (step Z / M0 / M2 summary).
3. `scripts/body/` (`make_arm.py`, `arm_sim.py`, `cpg.py`, `BODY_NOTES.md`, `test_body.py`), `scripts/compute/README.md`,
   `scripts/brain/core.py`, `core_b7.py`, `train.py`, `toy_b7.py`, `bench_b7.py`.

## Rulings on the open points (BRAIN_SPEC §7.13, planner, 2026-11-04; binding)

- **D1, command space.** The cerebellum's "command" is the servo target (5 joint angles at 100 Hz, what the generators output), in babbling
  and in the v47 set alike. Efference copy = the last 10 targets (100 ms). In T-M3 and M3 the policy's commands pass through the generators, and the cerebellum still sees targets.
- **D2, the v47 set.** v47 is a six-arm hexagon per song. Use all six arms of each of the three danced songs (Instant Crush, Five Years,
  Presence): 18 trajectories, each replayed in physics as servo targets, split into 60 s segments. Find the trajectories from the v47 build
  (`$D/tracker-scratch/newsong/three.sh` and its outputs, `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`;
  a shell guard refuses commands mixing `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file). If a trajectory exceeds
  M0's limits in physics, keep it and report how much.
- **D3, K1 bootstrap.** Held-out babbling = 120 independent 60 s trajectories (own seed, own start pose); bootstrap over trajectories,
  10,000 resamples, 95 % interval. v47 set: two-level bootstrap, arms within song, then segments within arm, the 3 songs held fixed (not
  resampled), 10,000 resamples. The report states that the v47 interval is conditional on these three songs, and that arms in unison or
  mirrored formations are near-duplicates.
- **D4, Kaggle verify job (ruling of 2026-11-04).** First thing, before phase 1: a Kaggle kernel (no GPU needed: `--no-gpu`) that attaches
  `kostavukicevic/hyst-features` and runs `scripts/compute/manifest.py verify` on it. Log the result. If it fails, log FOR USER and continue.
- **D5, M3 benchmark memory.** If 256 environments do not fit in 14 GB, report the largest count that fits.

## Phases (the work order's, with its time boxes and defaults)

**Phase 0 (≤ 20 min):** D4.

**Phase 1, M1 toy (≤ 45 min).** Babbling generator: M2 commands as Ornstein–Uhlenbeck processes (time constant 1 s, full ranges, fixed
seeds) through M0 physics, logging proprioception and servo targets. Unit test: reproducible from a seed. 1 h of babbling; the small
forward model of plan §5 (input = proprioception + current target + last 10 targets; Gaussian outputs at +10, +50, +100 ms; β-NLL, β = 0.5);
it must beat persistence at +100 ms on 10 min of held-out babbling. If it fails: debug (the 10 ms proprioception delay alignment first),
30 min more. Still failing: log, skip to phase 3.

**Phase 2, M1 run and K1 (≤ 4 h).**
1. Data: 20 h train, 2 h held out (D3), the v47 set (D2). Fixed seeds.
2. Commit `scripts/body/check_m1.py` with K1 exactly as plan §5 (and D3) **before training**. Push that commit before training starts.
3. Train. If the projection exceeds 4 h on the laptop: a Kaggle job via `run_job.py`, checkpointed. Otherwise local.
4. Run K1. If it fails: round 2, limited to model width and training length, one rerun. Record both rounds.
5. Export the self-surprisal lane for the three danced songs (each arm replaying v47 in physics), 30 Hz, to `/secondary/hyst-data/body/m1/`.

**Phase 3, M3 step benchmark (≤ 45 min, report only).** One full step: B7 epoch 6 twin pass (moving and still) with the new zero-initialised
proprioceptive relay, relay backward, physics, basal ganglia + motor cortex + critic forward and backward, at 16, 64 and 256 environments,
laptop CPU (12 threads), and one Kaggle T4 job. Report seconds per simulated hour and peak memory. Identity test: with the relay at zero,
cortex outputs equal B7 epoch 6 (float64 max difference ≤ 1e-9; log float32 too).

**Phase 4, T-M3 build (≤ 2 h).** Plan §6 exactly: synthetic pulse-train features with slow tempo drift; reduced cortex (B7 architecture,
16 modes per layer), trained briefly on the synthetic stream, then frozen; K = 8 motor programs initialised from 8 babbling commands
(fixed seed), Go/NoGo selection every 0.5 s with switch cost; motor-cortex modulation at 10 Hz bounded to ±20 % of each command range;
critic; dopamine lane = TD error; reward with the S_still twin, LP from the M1 cerebellum (or a toy cerebellum if M1 failed: log it) and
energy; the SYNC term behind a flag, off. PPO with a hybrid action (clip 0.2, GAE λ 0.95, γ 0.99 per 0.1 s). Record every setting before
the first run. Unit tests: gating (only the chosen program reaches the generators), switch cost, reward pieces on synthetic values,
identity at step 0.

**Phase 5, T-M3 tries (two tries, 4 h box each).**
1. The grid of plan §6 (β ∈ {0, 0.1, 1}, λ ∈ {0.01, 0.1, 1}, c_sw ∈ {0, 0.1}, relative to the toy's mean |S_still − S_moving| at
   initialisation), in parallel within your threads. Pick the setting that maximises (a) subject to (b). Freeze it and record it.
2. Try 1 with that setting. Pass = (a) + (b) + (c) of plan §6. Report programs used, switches per minute, selection entropy.
3. If it fails: diagnose in ≤ 30 min (is S_still − S_moving ever non-zero? does the critic learn? does selection collapse to one
   program?). Then try 2 with one engineering change named in the log before the run (learning rates, entropy bonus or episode length;
   **not** the reward definition). Also run the γ grid for the SYNC fallback (flag on) as a separate toy run, report only, so γ is fixed
   before any real K2 result.
4. **Stop. Do not start the real M3 run.**

Defaults if blocked: Kaggle unavailable, so everything local, smaller sizes, logged. Physics or JAX trouble, so MuJoCo CPU only. A unit test
that cannot pass in 30 min: log it, skip the dependent phase, continue with the next independent one.

## Finish

Fill the MORNING SUMMARY. Report to the overseer in a few lines:
- D4's result;
- K1 per set with intervals, both rounds if run; M1 training time and where it ran; the self-surprisal lane files;
- the M3 benchmark table and the identity numbers;
- T-M3: the grid, the chosen β, λ, c_sw, γ; (a), (b), (c) per try; programs used, switches per minute, selection entropy;
- FOR USER items;
- branch, last commit, data paths, Kaggle GPU hours used.

Every body result states the provisional servo model. Never say something looks better. No claims beyond what a check passed. Do not edit
`docs/BODY_BRAIN_PLAN.md`, `docs/WORK_ORDER_2026-11-04.md`, `docs/BRAIN_SPEC.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
