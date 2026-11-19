# Builder prompt: work order 6, the H4 diagnostic (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo6-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-h4` (branch `body-h4`, last commit b80197b); first `git merge origin/body` to get §7.17. If the
  worktree is gone: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-h4 body-h4`. Push `body-h4`.
- **Your share: 3 threads, 4 GB.** Environment `/secondary/hyst-env/brain`. Data under `/secondary/hyst-data/brain/h4/`.

## Read first

`docs/BRAIN_SPEC.md` §7.17 point 1 (binding), §7.16 point 3, §7.15, §7.10 R3; `docs/NIGHT_LOG_body-h4.md`, `docs/NIGHT_LOG_body-h3.md`;
`scripts/brain/hippo_h4.py`, `toy_h4.py`, `test_h4.py`, `hippo_h3.py`, `toy_h3.py`, `toy_b7.py` (`t1_eval`), `core_b7.py`.

## The work (§7.17 point 1, exactly). One diagnostic, no new try.

1. **Top-k.** Check, in the code and at run time (log the actual tensor shapes), how many sources the replay reads. The spec: top-k = 4 sources.
   "k 64" is the sparse-code k, not the number of replayed sources. State what the H4 runs used.
2. **Replay error against the oracle.** Inside the repeat (from its 2nd second, as for mean w), on the same frames, report per layer L1–L3 and per
   design A, B, C: the mean squared error of the hippocampal replay's own prediction, and the mean squared error of the oracle replay (H2's
   oracle path), and the cortex's own error. Use the try 1 settings (window 1 s).
3. **The 1.000 cortex-only control.** H4's control (`arbitrate = False`) gives a repeat/first ratio of 1.000 on all designs; H3's control on
   the same cortex files (blend weight forced to 0) gave 0.881 | 0.656 | 0.566. Find out why, by reading and running both paths. State which is
   correct and why.
4. **Decision rule.** If any implementation deviates from the spec (top-k, the control, the error bookkeeping, the blend), fix it, add a unit
   test that would have caught it, and rerun try 1 and try 2 with their committed parameters. These reruns count as the same tries (bugs are not
   tries). If nothing deviates, write "memory closed for this plan" in the MORNING SUMMARY, with the discrepancy explained.
5. Report T1a and T1b per design for any rerun, next to the earlier numbers. All existing tests pass unchanged (`test_h3`, `test_h4`, and
   `cd scripts/brain && python -m unittest`).

When finished, message the overseer: branch, last commit, the three answers (top-k used, replay vs oracle error table, the control's cause),
any rerun's T1a/T1b, tests run.
