# Builder prompt: work order 9, the K5 trainer and the Kaggle check (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo9-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-k5train -b body-k5train origin/body`. Push
  `body-k5train`. Agent 1 works on `body-m3e` (`scripts/body/m3e*.py`): **import** M3e's code, never edit it; your code goes in new files
  (`k5_train.py`, `k5_eval.py`, tests). If you need a change in `m3e*.py`, write it in your night log as FOR OVERSEER and work around it.
- **Your share: 6 threads, 8 GB** on the laptop. Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/k5/`. Kaggle:
  free tier only, via `scripts/compute/run_job.py`; no spending. One arm.

## Read first

1. `docs/BRAIN_SPEC.md` §7.20 (binding: point 1), §7.19 A (K5 bar, argmax mode, observer procedure) and C (claims), §7.18 point 2.
2. `docs/NIGHT_LOG_body-m3e.md` and `scripts/body/m3e.py`, `m3e_jax.py`, `run_m3e.py`, `m3e_controls.py` (the trained policy, loss,
   observers, controls); `docs/NIGHT_LOG_body-k5data.md`, `scripts/body/k5_data.py` and `/secondary/hyst-data/body/k5/` (splits, lanes,
   windows); `scripts/compute/run_job.py` and `make_kernel.py` (Kaggle path), `scripts/compute/README` if present.

## The work

**Phase 1, the trainer.** `k5_train.py`: M3e exactly (try 1's architecture, λ 0.03, lr 1e-3, the §7.19 B mechanisms) trained on the K5
training windows (B7 epoch-6 lanes as the state, read from the stored files; causal 30 s normalisation in the loop as in M3e), one pass over
all 15,624 windows in a fixed seeded order, early stopping on the validation songs (state the rule before any run), checkpoint every N
windows, resume-safe (a test kills and resumes and gets identical parameters). `k5_eval.py`: the K5 check on the 1,071 check windows with the
WO7 observer procedure (fresh observer per scored policy, hard rollouts of the fixed policy, trained on training windows only), argmax
(sampled reported only), external and internal (a), the time-shifted control and the untrained-policy control, per-song paired bootstrap
(10,000 resamples), plus the kappa = 0 report (§7.19 A1). Unit tests on small synthetic windows.

**Phase 2, the Kaggle check (§7.20 point 1).** A short Kaggle job (free tier): JAX with GPU and MJX import, and training steps per second on a
batch of real K5 windows (upload only what is needed, with the existing dataset folder `HYST_DATASET.json` name hyst-k5). Measure the same on
the laptop (6 threads). Project one full pass plus the check on each. **Do not launch K5 training.** Report the projections; the overseer
decides the path after the 60 s cerebellum check (§7.20 point 4) is in.

When finished, message the overseer: branch, last commit, the early-stopping rule, the Kaggle and laptop steps/s and projections, the Kaggle job
id and log path, tests run.
