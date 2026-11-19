# Builder prompt: work order 5, the sampled re-evaluation of the M3-family policies (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo5-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). **The fallback builder (`body-fallback`) has priority on the machine tonight:** keep to your thread cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-reeval -b body-reeval origin/body`. Push `body-reeval`.
- **Your share: 2 threads, 4 GB.** Environment `/secondary/hyst-env/brain`. `tm3_world` patches `core.N` and `core_b7.BLOCK` on import: run it in its own process.

## Read first

`docs/BRAIN_SPEC.md` §7.16 point 1 (binding); `docs/PLANNER_BRIEF_WO4_RESULTS.md` section 1; `scripts/body/tm3.py` (`evaluate`, `block`), the M3b and M3c
equivalents, and the night logs `docs/NIGHT_LOG_body-m1m3.md`, `docs/NIGHT_LOG_body-m3b.md`, `docs/NIGHT_LOG_body-m3c.md`.

## The work (≤ 3 h)

- Add a sampled mode to each family's evaluation (program sampled from the softmax, as in training; the modulation either sampled or mean, state
  which, the same for all). The argmax mode stays as it is.
- Add the metric to both modes: mutual information between the chosen program and the brain state (arousal binned in quartiles, L3 phase in
  4 bins, so 16 states; state the binning before running), with a shuffle control (1,000 shuffles of the program sequence within episode; p value).
- Re-evaluate, with no retraining and nothing tuned, every saved policy: T-M3 try 1 and try 2 (`/secondary/hyst-data/body/tm3/try1.pt`, `try2.pt`),
  any saved M3b policy, M3c try 1 and try 2 (`/secondary/hyst-data/body/m3c/`), with the same evaluation seeds as the originals.
- Report both versions per policy: (a), (b), (c), (d) (where defined), programs used and counts, switches per minute, selection entropy, the MI and its p.
  Both rounds stand as they were; no pass is claimed.
- Unit tests: sampled mode samples (not argmax) on flat logits; the MI is 0 within noise for an independent synthetic choice and > 0 for a dependent one.

## Finish

Report to the overseer in a few lines: one table, per policy and mode; unit tests; branch, last commit.
