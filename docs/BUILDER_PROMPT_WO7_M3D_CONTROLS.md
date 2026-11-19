# Builder prompt: work order 7, M3d report-only controls (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo7-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-m3d` (branch `body-m3d`, last commit 3b8ef08); first `git merge origin/body` to get §7.18. Push `body-m3d`.
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body` (`XLA_PYTHON_CLIENT_PREALLOCATE=false`). Data under
  `/secondary/hyst-data/body/m3d/controls/`. Chain all runs into one detached capped service.

## Read first

`docs/BRAIN_SPEC.md` §7.18 point 1 (binding), §7.16 point 2; `docs/NIGHT_LOG_body-m3d.md`; `scripts/body/m3d.py` (`evaluate`, `Trainer`),
`m3d_jax.py` (`motor_cortex`, kappa), `run_m3d.py`, `chain_m3d.py`; try 1 checkpoint `/secondary/hyst-data/body/m3d/try1/ckpt.pkl`.

## The work (§7.18 point 1, exactly; report only, no retraining, not a try; the toy pass stands)

On the same 16 held-out episodes, with the same observer procedure as try 1 (the final observer trained the same way on data from the policy
being scored; state exactly how you do it and use the same steps and seeds), both choice modes (argmax and sampled):
- (i) untrained motor cortex: the initial weights of try 1 (same seed), kappa as initialised;
- (ii) trained motor cortex (try 1 checkpoint) with kappa forced to 0;
- (iii) untrained motor cortex with kappa fixed at the trained per-joint means (1.41 / 0.42 / 0.28 / 0.45 / 2.02 rad/s, re-read from the run).
Report (a), (b), (c) for each, and (a)_trained − (a)_control per control with a paired 95 % bootstrap interval over the 16 episodes (same
episodes, same shifts). Add unit tests for the kappa override and for the paired difference. Write the table into the MORNING SUMMARY.

When finished, message the overseer: branch, last commit, the table (both modes), the paired differences with intervals, tests run, wall time,
peak memory.
