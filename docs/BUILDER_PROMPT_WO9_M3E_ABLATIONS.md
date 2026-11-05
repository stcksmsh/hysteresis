# Builder prompt: work order 9, M3e ablations (report only) and the 60 s cerebellum check (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo9-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-m3e` (branch `body-m3e`, last commit 2884e74); first `git merge origin/body` to get §7.20. Push
  `body-m3e`. Agent 3 builds the K5 trainer on `body-k5train` and imports your `m3e*.py`: keep their public functions' signatures stable;
  ablation switches are new flags whose default reproduces try 1 exactly (a test proves it).
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body` (`XLA_PYTHON_CLIENT_PREALLOCATE=false`). Data under
  `/secondary/hyst-data/body/m3e/ablations/` and `.../m3e/cb60/`. Chain all runs into one detached capped service that starts on mains power
  and finishes without you; resume-safe. One arm.

## Read first

`docs/BRAIN_SPEC.md` §7.20 (binding: points 2, 4, 5), §7.19 B; `docs/NIGHT_LOG_body-m3e.md`; `docs/PLANNER_BRIEF_WO8_RESULTS.md`.

## The work

**Part 1, the 60 s cerebellum check (§7.20 point 4), first.** Run the frozen K1 round-2 cerebellum (your JAX port) continuously over full 60 s
episodes in the closed loop exactly as M3e runs it: the 16 held-out toy episodes with the try 1 policy (argmax), plus the 2 v47 60 s
trajectories used in the parity check (`/secondary/hyst-data/body/parity/traj.npz`). Report its prediction error (the NLL or squared error
M3e feeds the cortex) per 5 s bin over the episode, mean and 95 % interval over episodes, and a linear trend (slope per 10 s with interval).
If the error grows over the episode (slope interval above 0, or the last 10 s clearly above the first 10 s), **stop Part 2, report, and wait**
for a ruling. Otherwise continue.

**Part 2, ablations (§7.20 point 2), report only, not a try.** Retrain small copies from scratch, exactly as try 1 (λ 0.03, lr 1e-3, 40
epochs, same seeds and toy), each with one mechanism off:
- (A1) closed-loop inputs off (no proprioception, no cerebellum pose or error into the cortex);
- (A2) dopamine gating off (learning-rate multiplier fixed at 1.0; the critic may still train, its δ is not used);
- (A3) internal observer off (loss = external decoding − λ·energy; the internal decoding is still scored afterwards with the WO7 observer
  procedure).
Score each on the 16 held-out episodes with the WO7 observer procedure, argmax (sampled reported only), external and internal (a), (b), (c).
Report (a)_try1 − (a)_ablation, paired 95 % bootstrap over episodes (10,000 resamples), external and internal. Write the rule before the first
run: "credited" = paired interval above 0 in argmax for the external (a).

When finished, message the overseer: branch, last commit, the cerebellum table and trend, the ablation table with paired intervals, which
mechanisms are credited, tests run, wall time, peak memory.
