# Builder prompt: work order 10, the K5 run, try 1, on the laptop (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo10-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-k5train` (branch `body-k5train`, last commit 2793701); first `git merge origin/body`. Push
  `body-k5train`. Do not edit `m3e*.py` (agent 1).
- **Your share: 6 threads, 8 GB** (agent 1's ablations may run alongside with 8 threads). Environment `/secondary/hyst-env/body`. Data
  under `/secondary/hyst-data/body/k5/run1/`. One arm.

## Read first

`docs/BRAIN_SPEC.md` §7.20 (binding: point 1, the 24 h compute box counted as compute actually spent, resumable), §7.19 A and C (bar,
argmax, observer procedure, claims), §7.18 point 2; `docs/NIGHT_LOG_body-k5train.md` (your trainer, the early-stopping rule, the speed check).

## Path decided (overseer, per §7.20 point 1)

The laptop: 61.1 s per 16-window round, one pass + validations + check ≈ 17.4 h, inside the 24 h box. Kaggle T4 at M3e's recipe is 7.4×
slower; a large-batch GPU recipe would change training and is not allowed for this try.

## The work

1. Launch try 1 exactly as committed: one full pass over the 15,624 windows in the fixed seeded order, checkpoint every 25 rounds, the
   early-stopping rule in your night log (validation every 200 rounds on the 217 validation windows, stop after two non-improving validations
   in a row). One detached capped service (`MemoryMax=8G`, `MemorySwapMax=0`, 6 threads), **mains power only**: the script pauses at the
   next checkpoint while `ADP1/online` = 0 and resumes when it is 1; it resumes from the last checkpoint after a kill or reboot (a wrapper
   relaunches it on the next session or by the overseer; write the exact relaunch command into the night log).
2. Log compute actually spent (wall time with mains on, excluding pauses) against the 24 h box; stop at the box.
3. Then the K5 check on `best.pkl` with `k5_eval.py` (trained, untrained, kappa 0; argmax pass/fail, sampled reported only; external and
   internal (a); per-song bootstrap over 357 songs × 10,000), chained in the same service.
4. Push the night log after every validation (figure, round, compute spent).
5. Render the three danced songs from `best.pkl` with the new one-arm camera for the user's eye (§7.19 C), next to the fallback videos, if a
   render path from a trained policy exists; if not, write what is missing as FOR OVERSEER and stop there.

When each validation is in, a one-line message to the overseer is enough. When finished, message the overseer: branch, last commit, compute
spent, the validation curve, the K5 table (external and internal (a) with intervals, paired vs untrained and vs kappa 0), the verdict per
§7.19 C, video paths, tests run.
