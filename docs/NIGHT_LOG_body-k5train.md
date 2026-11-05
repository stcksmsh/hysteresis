# Night log, builder (body-k5train), work orders 9 and 10

## K5 RUN (WO10): THE FOUR COMMANDS (details: scripts/body/K5_RUN.md; run dir /secondary/hyst-data/body/k5/run1/; unit hyst-wo10-k5run)

1. **Pause**: `systemctl --user freeze hyst-wo10-k5run`  (instant; paused time is not compute)
2. **Continue**: `systemctl --user thaw hyst-wo10-k5run`
3. **Stop**: `systemctl --user stop hyst-wo10-k5run`  (finishes the round in progress, ~60 s, checkpoints, exits 0)
4. **Start again**: `/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-k5train/scripts/body/k5_run.sh start`  (resumes from the last checkpoint; also the command after a reboot)

Checkpoint after every round, atomic (temp file, fsync, rename; the previous kept as `ckpt.prev.pkl`). Mains only: waits on battery. Compute box 24 h (clock excludes pauses and battery waits).
Tests (WO10 1b): `test_k5_run` (real units: start, freeze, thaw, stop, start again; interrupted vs uninterrupted agree to 1e-9; found max difference 4.0e-12), `test_k5_train` 9 OK (in-process resume bit-identical).
**Finding**: two UNINTERRUPTED runs of the same command in separate processes give one of two reproducible results that differ by 4.0e-12 (float64 summation order in XLA CPU; alternates run to run on a quiet machine, same with PYTHONHASHSEED fixed). So bit-identity across processes is not available even without a stop; in one process a resume is bit-identical. FOR OVERSEER.

# WO9: the K5 trainer and the Kaggle check (2026-11-05)

Provisional servo model throughout: Feetech STS3215 12 V assumed. The installation is ONE arm. **K5 training was NOT launched.**

## MORNING SUMMARY

- **Code** (new files only; `m3e*.py` imported, not edited): `scripts/body/k5_train.py` (trainer), `k5_eval.py` (K5 check), `k5_bench.py` (speed check), `test_k5_train.py`; `scripts/compute/jobs/k5_bench.json` and a one-line change in `scripts/compute/kaggle/make_kernel.py` (the job may name its data dataset, `data_name`, default `hyst-features`).
- **Trainer**: M3e's `Trainer` is driven as is (try 1 architecture, lambda 0.03, lr 1e-3, closed loop, dopamine, causal 30 s normalisation, self-observer). A window = a 60 s M3e episode with real lanes as state (`WindowToy`). One round = 16 windows (8 + 8 observer groups) = one M3e epoch; the 15,624 windows in a fixed seeded order (seed 20261106) = 977 rounds (976 of 16 and one of 8); tau 1 -> 0.2 over the pass. Checkpoint every 25 rounds (400 windows), atomic. **Resume test: 2 rounds straight vs 1 round + kill + resume + 1 round give bit-identical parameters and key.** (A first run differed by 1e-15: `Trainer.load` turns Adam's step count into a JAX array; `k5_train` casts it back to `int`. FOR OVERSEER: the same would hit `run_m3e.py` resumes at the 1e-15 level; harmless there, noted.)
- **Early-stopping rule (fixed before any run)**: every 200 rounds (3,200 windows) and at the end of the pass, score the policy on the 217 validation windows (one per validation-artist song, start at 50 %, moved back to fit), ARGMAX, WO7 observer procedure (fresh external and internal observers, 600 steps, trained on 4 rollouts of 16 seeded training windows); figure = mean external (a) gap. best.pkl = highest. Stop when two validations in a row fail to beat the best (strictly). K5 scores best.pkl. Held-out artists are never read by the trainer.
- **K5 check** (`k5_eval.py`): 1,071 check windows, trained / untrained / trained with kappa = 0, argmax (sampled reported only), external and internal (a), per-song gaps (3 windows averaged), bootstrap over the 357 songs (10,000), paired differences on the same songs; `k5_pass` = external (a) interval above 0 AND paired (a)_trained - (a)_untrained above 0 (7.18 point 2); kappa = 0 difference reported (7.19 A1). Smoke run on 6 windows of the bench subset with an untrained policy: runs end to end (trained and untrained then score identically, as they must), 609 s.
- **Speed check, same code and same real windows** (`k5_bench.py`, 3 rounds, E = 16, x64 as M3e; details `docs/k5_bench_laptop_results.json`, `docs/k5_bench_kaggle_results.json`):

| | laptop CPU, 6 threads | Kaggle T4 (free tier) |
|---|---|---|
| JAX backend, MJX import | cpu, ok | gpu (jax 0.11.1, 2 x T4 visible, one used), ok |
| one K5 round (16 windows), median | **61.1 s** (first incl. compile 187 s) | **452 s** (first 712 s) |
| gradient steps/s, one 8-block chunk, E = 16 | 0.312 (40 window-blocks/s) | 0.066 (8.4 window-blocks/s) |
| E = 64 / 256 (capacity only, not the K5 recipe) | not run (memory cap) | 29 / 97 window-blocks/s (0.057 / 0.048 steps/s) |
| hard rollout, s per window | 0.60 | 0.77 |
| **one pass (977 rounds)** | **16.6 h** | **122.7 h** |
| 5 validations | 0.24 h | 0.31 h |
| K5 check, 3 policies argmax (sampled doubles it) | 0.57 h | 0.73 h |
| **one pass + check** | **17.4 h** | **123.7 h** |

  - The T4 is 7.4x SLOWER than the laptop at the K5 recipe (E = 16): M3e runs in float64 and the T4's float64 rate is a fraction of its float32 rate; a 16-window batch also leaves the GPU idle. Only a larger batch changes this: at E = 256 the T4 reaches 97 window-blocks/s against the laptop's 40 at E = 16 (2.4x), which would need about 5.4 h of gradient steps for one pass (1.875 M window-blocks) plus observers, validation and check, **but E = 256 means 61 optimiser rounds instead of 977, a different training recipe, not M3e's**. Not measured: the laptop at E = 64 or 256 (8 GB cap), a float32 variant.
  - Projection on the laptop: 17.4 h of compute, inside the 24 h box of 7.20 point 1, several nights with checkpoint resume (the 61 s round was measured while the machine was otherwise quiet; it is slower under load).
- **Kaggle**: job `kostavukicevic/hyst-job-k5-bench-001`, version 1 failed after 30 s (Kaggle skipped the `lanes/` subfolder of the dataset; fixed with `--dir-mode zip`, a first-use finding), version 2 complete, wall 2,695 s on one T4 (about 0.75 GPU hours; free tier, no spending). Logs: `/secondary/hyst-data/body/k5/kaggle_out/{hyst-job-k5-bench-001.log,out/}`. Datasets (private): `kostavukicevic/hyst-code` (commit b52839b), `kostavukicevic/hyst-k5` (11 MB bench subset: lanes of the songs of 64 training and 64 check windows, `cb_r2.npz`).
- **Tests run**: `test_k5_train` 9 tests OK (stop rule, order fixed and complete, 977 rounds, observer windows distinct songs, per-song statistics and paired difference, no held-out song in the training windows, window toy equals an M3e episode, causality, validation windows fit, kill-resume identical + a validation call writing best.pkl; 452 s + 532 s over two runs); `test_k5_data` 7 OK earlier; `scripts/compute` 14 OK.
- FOR OVERSEER: (1) path decision: laptop 17.4 h is inside the box; Kaggle at the K5 recipe is not viable (123.7 h); a large-batch variant is a recipe change needing a ruling. (2) With real data the observer is fitted on 16 training windows x 4 rollouts as in the toy (WO7); 64 windows would be less noisy, not changed. (3) The 60 s cerebellum check (7.20 point 4) is not part of this order and is not done here. (4) `k5_eval.py` has no run on a trained policy yet.
