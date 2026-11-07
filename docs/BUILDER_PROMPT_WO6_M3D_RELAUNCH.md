# Builder prompt: work order 6, M3d relaunch after the memory kills (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo6-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-m3d` (branch `body-m3d`; first commit df9e73a; uncommitted work there is yours: commit it first).
  Then `git merge origin/body` to get §7.17. Push `body-m3d`.
- **Your share: 9 threads, 18 GB (3 runs × 3 threads × 6 GB).** Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3d/`.

## Read first

`docs/BRAIN_SPEC.md` §7.17 point 2 (binding), §7.16 point 2 (defines M3d), `docs/BUILDER_PROMPT_WO5_M3D.md` (your original order: still valid
except where this prompt changes it), `docs/NIGHT_LOG_body-m3d.md` in your worktree.

## What happened

The three grid runs `hyst-wo5-m3d-grid-{0,1,2}` (λ 0.03 / 0.3 / 3, 12 epochs, `--eval tune`) were killed by the OOM killer at 23:49–23:51 on
2026-11-04, each under `MemoryMax=3G`, after 2.5–6 min of CPU. No result was produced.

## The work

1. Per §7.17 point 2, these kills are **not a try**. Log them in the night log with the unit names and times.
2. Before relaunching, measure the peak memory of one run (`anon` in the unit's `memory.stat`, or a short capped run of 1 epoch). If one run
   needs more than 6 GB, reduce memory (batch, episode chunking, JAX preallocation off: `XLA_PYTHON_CLIENT_PREALLOCATE=false`) without changing
   what is trained, and log the change.
3. Relaunch the grid as 3 runs, each `MemoryMax=6G -p MemorySwapMax=0`, 3 threads, fresh unit names `hyst-wo6-m3d-<name>`.
4. The 4 h box counts compute actually spent (wall time of runs that produce results). Then continue your original order (try 1, evaluation,
   pass bar (a)–(c) of §7.16 point 2, try 2 if needed).

When finished (or when a try's result is in), message the overseer: branch, last commit, per try (a) mean and interval, (b) °/s, (c) MI and p,
peak memory, wall time spent, tests run.
