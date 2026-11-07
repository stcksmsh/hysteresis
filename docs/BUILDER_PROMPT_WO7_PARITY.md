# Builder prompt: work order 7, MJX one-iteration vs full MuJoCo parity (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo7-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-parity -b body-parity origin/body`. Push
  `body-parity`. Never touch `body`, `keys-decide`, `master` or the main checkout. Agent 1 works on `body-m3d` (`scripts/body/m3d*`): do
  not edit those files; import them.
- **Your share: 4 threads, 6 GB.** Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/parity/`.

## Read first

`docs/BRAIN_SPEC.md` §7.18 point 2 (binding), §7.16 point 2; `docs/NIGHT_LOG_body-m3d.md`; `scripts/body/m3d_jax.py` (the MJX arm, one solver
iteration), `scripts/body/arm_sim.py` (the CPU MuJoCo arm it ports).

## The work

Before the real M3d run (K5), compare the MJX arm as M3d uses it (one solver iteration) against full MuJoCo (default solver iterations) on
60 s trajectories: the same initial state and the same per-step servo targets in both. Inputs: at least 6 trajectories of 60 s, made from the
M3d generators (try 1 checkpoint `/secondary/hyst-data/body/m3d/try1/ckpt.pkl` on held-out toy episodes, argmax and sampled) plus 2 from
v47 targets (`build_v47`). Report per joint: max and RMS absolute joint-angle difference (degrees) and joint-velocity difference (deg/s), over
the whole 60 s and at 1, 10, 60 s; also the M3d descriptors (31) computed from both, as relative differences. No pass bar was set: report the
numbers, no claim. Unit test: identical inputs and solver settings give identical output. MORNING SUMMARY with the table.

When finished, message the overseer: branch, last commit, the table, tests run.
