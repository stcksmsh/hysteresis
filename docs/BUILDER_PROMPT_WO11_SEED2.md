# Builder prompt: work order 11, seed 2 of M3e try 1 and ablations A1-A3 (send only after K5 try 1 has finished) (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo11-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-m3e` (branch `body-m3e`, last commit 7430377); first `git merge origin/body` to get §7.21. Push
  `body-m3e`.
- **Your share: 8 threads, 14 GB.** Do not start while the K5 run (`hyst-wo10-*`, agent 3) is running: check first; this order is sent
  after K5 finishes. Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3e/seed2/`. One detached capped service,
  mains power only, resume-safe. One arm.

## Read first

`docs/BRAIN_SPEC.md` §7.21 (binding: points 1, 3), §7.20 point 2; `docs/NIGHT_LOG_body-m3e.md` (try 1, A1-A3, `m3e_ablate.py`, `chain_wo9.py`).

## The work

Exactly as try 1 and A1, A2, A3 (λ 0.03, lr 1e-3, 40 epochs, same toy, same held-out 16 episodes, WO7 observer procedure per decoder), with
**seed 1** for training (state every seed you change and every one you keep, before running). Score each in argmax (sampled reported only):
external and internal (a), (b), (c); paired (a)_try1seed2 − (a)_ablation seed 2, 10,000 resamples. Then apply the §7.21 point 1 rule across
both seeds and write the verdict per mechanism and per decoding (credited / present), and the dopamine fact if both seeds show it lowers
decoding. Also report try 1 seed 1 vs seed 2 (the run-to-run spread). Tests as before.

When finished, message the overseer: branch, last commit, the seed-2 table with paired intervals, the two-seed verdicts, the try 1 spread, tests
run, wall time.
