# Builder prompt: work order 5, the H4 toy (uncertainty-based arbitration) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo5-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). **The fallback builder (`body-fallback`) has priority on the machine tonight:** keep to your thread cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-h4 -b body-h4 origin/body`. Push `body-h4`.
- **Your share: 3 threads, 4 GB.** Environment `/secondary/hyst-env/brain`. Data under `/secondary/hyst-data/brain/h4/`. Changes to
  `core_b7.py` go behind default-off flags; every existing test passes unchanged.

## Read first

`docs/BRAIN_SPEC.md` §7.16 point 3 (defines H4; binding), §7.15 (H3), §7.10 R3 (the bar); `docs/NIGHT_LOG_body-h3.md` and
`docs/NIGHT_LOG_body-h2show.md`; `scripts/brain/hippo_h2.py`, `hippo_h3.py`, `toy_h3.py`, `test_h3.py`, `core_b7.py`.

## The work (§7.16 point 3, exactly)

- H2's fixed sparse code and one-shot store; top-k pointer replay as in H3. **Nothing trained** (the toy cortex trained and frozen as in H3).
- Per layer, each system keeps a running mean squared prediction error over the last 1 s (state exactly how "the last 1 s" is computed causally,
  e.g. against targets that have arrived, before running). w = (1/e_hippo) / (1/e_hippo + 1/e_cortex); mean and variance blended as in H3 (same
  variance formula).
- Unit tests: nothing has a gradient or is trained; w = 0.5 when the errors are equal; w → 1 when the hippocampus error → 0; causality (no future
  target enters e); storage one-shot; 17 s eligibility.
- Citation: Daw, Niv & Dayan 2005. Record the full reference; verify it if you can, else log "not verified".

## Bar and tries (fixed)

T1a + T1b of §7.10 R3 on A, B, C, same toy and evaluation as H3; report cortex-only and oracle too. Two tries, 3 h box each; try 2 may change only
the error window, to 2 s. If both fail: memory is closed for this plan.

## Finish

Report to the overseer in a few lines: T1a and T1b per design and try, mean w during repeats and outside them, baselines, unit tests, the citation
status, FOR USER items, branch, last commit.
