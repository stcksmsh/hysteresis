# Builder prompt: work order 5, the M3d toy (learning to move by gradient) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo5-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). **The fallback builder (`body-fallback`) has priority on the machine tonight:** keep to your thread cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-m3d -b body-m3d origin/body`. Push `body-m3d`.
- **Your share: 8 threads, 10 GB.** Environment `/secondary/hyst-env/body` (JAX, MuJoCo MJX 3.17, CPU). Data under `/secondary/hyst-data/body/m3d/`.

## Read first

1. `docs/BRAIN_SPEC.md` §7.16 point 2 (defines M3d; binding), §7.15, §7.14.
2. `docs/NIGHT_LOG_body-m3c.md` (M3c: the descriptor port `scripts/body/bdesc.py` and its Rust parity test, the observer, why it failed) and
   `docs/PLANNER_BRIEF_WO4_RESULTS.md`.
3. `scripts/body/make_arm.py`, `arm.xml`, `arm_sim.py`, `cpg.py`, `tm3_world.py` (toy cortex and synthetic features), `test_body.py` (MJX parity).

## The work (§7.16 point 2, exactly)

- Pipeline, differentiable end to end in JAX: toy brain state → motor cortex → program mixture (Gumbel-softmax over 8 programs, temperature
  annealed; state the schedule before running) + bounded modulation → spinal generators with the L3 phase coupling (κ from the motor cortex;
  κ = 0 recovers the plain generators) → MJX physics of the M0 arm → descriptors in JAX (port `bdesc.py`, roll excluded; parity with Rust on the
  same 3 clips as M3c, tolerance stated first) → observer.
- Loss = observer decoding loss − λ·energy. Inner-state targets (arousal, total surprisal, L3 phase cos/sin, per-layer band power, 0.5 s) z-scored
  within each episode.
- Observer cross-fitted: trained on other episodes, frozen while it scores; refreshed each epoch.
- Toy: synthetic features with within-song state swings (cuts every 12 s; arousal and surprisal varying on a 1–4 s scale). State the generator before running.
- Gradient through long physics rollouts may explode: truncate or checkpoint the backward pass (state the horizon before running); this is engineering.
- Unit tests: JAX descriptor parity; gradient reaches the motor cortex and not the observer during scoring; κ = 0 identity; Gumbel-softmax
  hard sample at low temperature; the within-episode z-scoring; the time-shuffled control.

## Bar and tries (fixed)

- Pass: (a) held-out-episode decoding beats a time-shuffled control (state the shuffle, e.g. circular shift of the state targets by ≥ 4 s, and
  the metric before running), interval over episodes above 0; (b) RMS joint speed ≥ 10 °/s over the four non-roll joints; (c) the program
  choice (the hard argmax of the mixture at evaluation, and also the sampled choice; report both) carries information about the state: MI
  above 1,000 shuffles, p < 0.01 (same binning as the re-evaluation order: arousal quartiles × 4 L3 phase bins).
- λ chosen on the toy by a small grid (state it), frozen before try 1.
- Two tries, 4 h box each. Try 2 may change one engineering setting named before the run (learning rate, rollout horizon, temperature schedule,
  observer size), not the loss or the bar.
- **Stop after try 2 or a pass. No real run.** If both fail, write plainly: by §7.16, the self-driven body is closed for this plan.

## Finish

Report to the overseer in a few lines: parity; the grid and λ; (a)–(c) per try with intervals and p; per-joint RMS speeds; κ; programs used;
unit tests; FOR USER items; branch, last commit, data paths. Provisional servo model stated.
