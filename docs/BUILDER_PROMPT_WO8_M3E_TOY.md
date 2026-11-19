# Builder prompt: work order 8, the M3e toy rerun (closed loop, dopamine, causal normalisation, self-observer) (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo8-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-m3e -b body-m3e origin/body`. Push `body-m3e`.
  Never touch `body`, `keys-decide`, `master` or the main checkout. Build on M3d's code (`scripts/body/m3d*.py`); new behaviour goes behind
  flags whose default reproduces M3d exactly (a test proves it), or into new files `m3e*.py`.
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body` (`XLA_PYTHON_CLIENT_PREALLOCATE=false`). Data under
  `/secondary/hyst-data/body/m3e/`. Chain every long run (grid, try 1, controls, try 2 if needed, tests) into one detached capped service that
  starts only on mains power and runs to the end without you; checkpoint/resume-safe; save rollouts before scoring so a scoring bug never forces a
  retrain. The installation is ONE arm.

## Read first

1. `docs/BRAIN_SPEC.md` §7.19 (binding; part B is this order), §7.18, §7.16 point 2.
2. `docs/NIGHT_LOG_body-m3d.md` (M3d toy, try 1, the WO7 controls and their observer procedure); `docs/PLANNER_BRIEF_WO7_RESULTS.md`.
3. `scripts/body/m3d.py`, `m3d_jax.py`, `m3d_toy.py`, `m3d_controls.py`, `run_m3d.py`, `chain_m3d.py`, `test_m3d.py`;
   `scripts/body/cerebellum.py` and the K1 round-2 bundle `m1_r2.pt` (`docs/NIGHT_LOG_body-m1m3.md`); `scripts/body/selfsurprisal.py`.

## The work (§7.19 part B, exactly)

Write every rule and parameter you choose into the night log, committed, **before** the first recorded run.

1. **Closed loop.** The motor cortex also receives (a) proprioception: joint positions and velocities of all five joints (roll included),
   quantised (state the step) and delayed 10 ms; (b) the frozen K1 round-2 cerebellum's predicted pose and its prediction error. The new input
   weights start at zero. The cerebellum is a torch model: port its forward pass to JAX with a parity test (max abs difference stated), frozen.
2. **Dopamine.** A critic predicts the next 2 s of legibility (state your definition, e.g. minus the external decoding loss over the next 4
   blocks) from the motor cortex's input. δ = realised − predicted. The learning rate of the basal-ganglia selection parameters (the program
   logits path; name the parameters) is base rate × (0.5 + clip(|δ| / σ_δ, 0, 2)), σ_δ a running SD. Export δ per block as the dopamine lane.
   If it cannot be built cleanly, stop this item, log why, and say so in the report (§7.19 B2: dopamine is then removed).
3. **Causal normalisation.** Every inner-state input and every target z-scored with running statistics over the past 30 s only; no
   whole-episode statistics anywhere in the arm's loop (a unit test feeds a future change and checks the past outputs are unchanged).
4. **Self-observer.** A second observer decodes the same inner-state targets from proprioception alone (quantised, delayed, roll included),
   cross-fitted like the external one (which sees the 31 visible descriptors, no roll). Loss = external decoding loss + internal decoding loss
   − λ·energy, equal weights.
5. **Toy and bar unchanged** (M3d's toy, §7.16 point 2 (a)–(c)); **mode ARGMAX** for every pass/fail (§7.19 A2); sampled reported only. Every (a)
   uses the WO7 controls' observer procedure (§7.19 A4), for the external and the internal observer separately.
6. λ: one small grid on the tune episodes as in M3d (state the cells and the rule before running), then try 1 on the 16 held-out episodes.
   Two tries, 4 h box each; a try 2 may change only λ or the learning rate (state which before running).
7. **Controls, report only, for each try that is scored:** the WO7 set (i) untrained, (ii) trained with kappa = 0, (iii) untrained with kappa at
   the trained means, for both the external and the internal decoding, with paired (a)_trained − (a)_control intervals (10,000 resamples).
8. Report also: the dopamine lane's summary (mean |δ|, the share of blocks where the rate multiplier is clipped), the learned weights on the new
   inputs (norm per input group), and per-joint kappa.

When finished (or after each try), message the overseer: branch, last commit, per try both decodings (a)/(b)/(c) in argmax and sampled, the
controls table with paired intervals, the dopamine summary or why it was dropped, tests run, wall time, peak memory.
