# Builder prompt: work order 8, the K5 data: B7 lanes for the real run (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo8-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-k5data -b body-k5data origin/body`. Push
  `body-k5data`. Never touch `body`, `keys-decide`, `master` or the main checkout. Agent 1 works on `body-m3e` (`scripts/body/m3*`): do
  not edit those files.
- **Your share: 6 threads, 8 GB.** Environment `/secondary/hyst-env/brain` (B7) and `/secondary/hyst-env/body` if needed. Data under
  `/secondary/hyst-data/body/k5/` (nothing on the root disk; check free space on /secondary first and report it). Long runs as one detached
  capped service, mains power only, resume-safe. The installation is ONE arm.

## Read first

1. `docs/BRAIN_SPEC.md` §7.19 (binding; A3 defines the K5 data), §1.4 (corpus, held-out = 73 artists / 357 songs), the B3/B7 split and
   validation-artist rules (§4, §7); `docs/BODY_BRAIN_PLAN.md` §0 rules (never tune on held-out artists).
2. `scripts/brain/B7_NOTES.md`, `scripts/brain/brain_mindstate.py` and `docs/NIGHT_LOG_body-h2show.md` (how B7 epoch-6 lanes are exported);
   `scripts/body/m3d_toy.py` and `scripts/body/m3d.py` (what the toy state looks like, so the real state matches its interface).

## The work

1. **Splits.** Build the song lists exactly from the existing split files: training artists minus validation artists = K5 training; the 357
   held-out songs = K5 check. Assert no artist overlap; write `splits.json` with counts and hours.
2. **Lanes.** Run B7 epoch 6 over every K5 training song and every held-out song and save the inner-state lanes the toy uses as state and
   targets (same names, same 0.5 s block / 0.1 s lane timing; list them), plus whatever M3e's closed loop needs from the brain side. No
   normalisation in the stored files (causal normalisation happens in the arm's loop, §7.19 B3). Store per song, compressed, with a manifest.
3. **Windows.** Training: an index of 60 s windows over the training songs (state the stride). Check: three 60 s windows per held-out song,
   starting at 25 %, 50 %, 75 % of its length (songs shorter than needed: log them and the rule you apply).
4. **Projection.** Measure B7's throughput and M3d's per-window training cost (from M3d's logs, or a 10-window timing with the try 1
   checkpoint), and project K5 wall time for one try on the laptop. If it exceeds 8 h, prepare (do not launch) a Kaggle job via
   `scripts/compute/run_job.py` and say so (§7.19 A3). No spending.
5. Tests: split disjointness, window starts, lane shapes and timing against the toy's interface, a manifest check.

When finished, message the overseer: branch, last commit, counts (songs, artists, hours) per split, lane list and sizes on disk, free space,
the K5 projection with its inputs, any Kaggle job prepared, tests run.
