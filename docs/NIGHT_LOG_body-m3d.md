# Night log, builder (body-m3d), work order 5, M3d toy (2026-11-04)

Provisional servo model throughout: Feetech STS3215 12 V assumed (kp, rotor inertia, damping 1.5, acceleration share 0.25), until the user chooses a servo.

## MORNING SUMMARY

Provisional servo model: Feetech STS3215 12 V assumed. **Try 1 passes (a), (b), (c) in both choice modes on 16 held-out toy episodes; try 2 not run (rule).** Toy only; no real run; no claim beyond the toy bar.
- Grid (tune episodes, 8, 12 epochs, argmax mode): lambda 0.03: (a) +0.437 [0.326, 0.553], (b) 48.8 deg/s; lambda 0.3: (a) +0.612 [0.509, 0.733], (b) 42.8; lambda 3: (a) +0.401 [0.281, 0.555], (b) 18.3. Rule (largest (a) among (b) passes): **lambda 0.3**, frozen.
- Try 1 (lambda 0.3, lr 1e-3, 40 epochs, horizon 8 blocks, 1,558 s of training compute, 1,614 s with evaluation), held-out episodes, control = the same observer scored against targets circularly shifted by 4 s or more (20 shifts per episode):
  - argmax: (a) +0.480 [0.422, 0.541] (matched loss 0.792; mean predictor 1.0), (b) 32.95 deg/s (per joint 23.8 / 9.6 / 42.8 / 43.1, roll 36.2), (c) MI 0.536 nats, null mean 0.057, p 0.001. Programs 1135/34/0/0/4/185/418/144 of 1,920 decisions (6 used).
  - sampled: (a) +0.498 [0.418, 0.583] (matched 0.705), (b) 39.28 deg/s (27.7 / 13.4 / 33.4 / 64.1, roll 40.3), (c) MI 0.0552, null mean 0.0182, p 0.001; 8 programs used, 175-333 each.
  - kappa (mean, rad/s, per joint) 1.41 / 0.42 / 0.28 / 0.45 / 2.02: the coupling is used (start 0.30).
- Caveats, not tuned away: arousal and surprisal enter through arcsinh; the physics uses one solver iteration; the argmax program choice is concentrated (one program 59 %) while the sampled one is near uniform, so the sampled MI is small though significant; the observer sees true (unquantised) joint positions; the p floor of 1,000 shuffles is 0.001.
- Tests: 10 in `test_m3d.py`. First full run (14 GB cap, 802 s): 9 pass, 1 fail (a test flaw: at tau 0.01 two near-tied samples are not low temperature); test fixed to require a 0.05 gap and rerun alone: OK. Peak memory of the tests unit 14.0 GB (cgroup MemoryPeak, includes file cache).
- FOR USER: none. Data `/secondary/hyst-data/body/m3d/` (toy.npz, grid_*/, try1/, chain.json, unittest.log).

## Log

### Phase 1: toy states, JAX body, descriptors (commit df9e73a)
Environments: `/secondary/hyst-env/brain` (torch, for the frozen toy cortex and the brain states) and `/secondary/hyst-env/body` (JAX 0.12, MJX 3.17, for everything else).
- `m3d_toy.py`: the toy generator (stated in its docstring before any run): 60 s episodes, 12 s segments (tempo U(80,140) per segment, base log pulse gain N(0,0.5), base log noise gain N(0,0.2)), plus
  two independent OU swings inside a segment (SD 0.5 pulse gain, 0.25 noise gain, tau U(1,4) s). Brain state per 0.5 s block from the frozen T-M3 cortex (`m3c/cortex.pt`, listening to the song alone) via `tm3c.brain_state`.
  A first version with noise swings SD 0.5 / base 0.4 was rebuilt narrower before any use (arousal and surprisal reach 4e4 either way: the spikes come from pulse onsets, not from the noise). 16 training, 8 tune, 16 held-out episodes (seeds 100.., 500.., 900..) in `/secondary/hyst-data/body/m3d/toy.npz`.
  Engineering deviation, stated: arcsinh on arousal and total surprisal before the within-episode z-scoring (heavy tails), z clipped to +-5.
- `m3d_jax.py`: x64. Generators with the L3 coupling (port of `cpg.CPG` + the kappa term of `tm3c.CPGK`), the arm (port of `ArmSim.step`: braking-aware target limiter, 5 MJX substeps, power), descriptors (port of `bdesc`, 31 numbers, roll excluded).
  - Descriptor parity with Rust on the same 3 clips as M3c, tolerance stated first (|jax - rust| <= 1e-6 x max(1, |rust|)): max relative difference 2.6e-8, pass.
  - `mjx.step`'s constraint solver is a `lax.while_loop` (not reverse-differentiable); set `opt.iterations = 1` (one Newton iteration). Effect: the +-110 deg joint limits are enforced by one iteration only (the servo targets are clipped at +-110, so the limits are active only at overshoot). The unit test measures the difference against the numpy `ArmSim`.
  - Differences from the numpy side kept for differentiability: `sqrt(x + 1e-12)` where a sqrt of a possibly-zero value is differentiated; the observer reads true joint positions (the numpy proprioception quantises them).
  - The two lag-type descriptors (`best_lag`) use argmax: they pass no gradient.
  - Speed: gradient through 8 blocks (4 s, 400 control steps, 2,000 MJX substeps) for 2 episodes in 1.4 s after 41 s compile; E = 8 episodes: one epoch (16 episodes x 60 s, 30 gradient steps) 132 s at 8 threads.

### Stated before the first run (full design: docstring of `m3d.py`)
- Motor cortex: MLP 16 -> 64 -> 33 (8 program logits, 20 modulation, 5 kappa), input the last finished block's state (globally standardised) and its change; kappa = 2 pi sigmoid(a), bias -3 (a relu would be dead at the start and pass no gradient).
- Program mixture: Gumbel-softmax over the 8 T-M3 programs; temperature schedule tau_e = 1.0 x 0.2^(e/(EPOCHS-1)), soft while training, hard (argmax, Gumbel-max sample) at evaluation.
- Backward horizon: 8 blocks = 4 s, carry stop-gradient at the chunk edge. Policy Adam lr 1e-3, clip 1.
- Observer: MLP 31 -> 64 -> 64 -> 8 (tanh), Adam 1e-3, weight decay 1e-3; two groups of 8 training episodes, each group scored by the observer trained on the other, refreshed after every epoch (200 steps, last 4 epochs of data).
- Loss = observer MSE on the z-scored target + lambda x (block energy / E0).
- (a) metric: per held-out episode, loss with targets circularly shifted by s >= 8 blocks (4 s), minus matched loss, over blocks from 4 s, 20 seeded shifts averaged; bootstrap 95 % interval over episodes. (c) MI: program vs (arousal quartile x 4 L3-phase bins of the previous block), 1,000 circular shifts >= 4 s of the state-bin sequence, p = (1 + #null >= obs)/1001.
- **Lambda grid (tune episodes, 12 epochs each, tau schedule over the 12): lambda in {0.03, 0.3, 3}.** Selection rule, fixed now: among the cells whose (b) passes in the argmax mode, take the largest argmax-mode (a) mean gap; if no cell passes (b), take the one with the largest (b). Frozen before try 1.
- Smoke run (not a result): one epoch at lambda 0.3 gave (a) +0.135 on the tune episodes in argmax mode: the pipeline learns something within an epoch, or the untrained policy already maps state to movement; the grid and the tries decide nothing from it.

### Phase 2: code, tests, grid launch, the memory kills
- `m3d.py` (training, evaluation, statistics), `run_m3d.py`, `test_m3d.py`, `grid_m3d.sh`. One-epoch smoke run on the tune episodes (lambda 0.3, 8 threads): 132 s per epoch; calibration E0 0.476 J/block, untrained RMS speed 65.7 deg/s. Not a result.
- **Kills, not a try (BRAIN_SPEC 7.17 point 2):** `hyst-wo5-m3d-grid-0`, `-1`, `-2` (lambda 0.03 / 0.3 / 3, 12 epochs, `--eval tune`, 3 cores each, `MemoryMax=3G`) were OOM-killed on 2026-11-04 at 23:49-23:51 CET after 2.5-4 min of CPU (grid-1: killed 23:49:54, 4 min 19 s CPU), in the first backward pass. No result.
- Relaunch at 2026-11-05 00:17 as one sequential unit `hyst-wo5-m3d-grid` (the three lambdas one after another, 8 cores, `MemoryMax=9G`, swap 0), by the overseer's note "keep it". Measured peak of the running unit (cgroup `memory.peak`) 2.67 GB early in the first cell; the final peak is recorded below when the cell ends. Nothing trained differs from the stated design.
- Unit tests: the first run (one shared core, 1,700 s timeout) was killed by its timeout before finishing (exit 143); rerun when cores are free.

### Phase 3: chained, detached run (overseer: usage limit coming)
`chain_m3d.py` / `chain_m3d.sh`, one unit `hyst-wo5-m3d-chain-<HHMM>` (9 GB cap, 8 cores): waits for the running grid unit, finishes any missing grid cell, picks lambda by the rule stated above, runs try 1 (40 epochs, lr 1e-3, held-out episodes), and only if try 1 does not pass (a), (b) and (c) in the argmax mode runs try 2.
**Try 2's one changed engineering setting, named before any run: policy learning rate 1e-3 -> 3e-3** (loss, bar, horizon 8 blocks, tau schedule, observer unchanged). Then the unit tests (`unittest.log`). Output in `/secondary/hyst-data/body/m3d/`: `chain.json` (summary and verdict), `chain.log`, `grid_*/`, `try1/`, `try2/`, `unittest.log`. To resume after an interruption run `bash scripts/body/chain_m3d.sh` again (finished steps are skipped, runs resume from their checkpoints).

### Phase 4: results
Chain (unit hyst-wo5-m3d-chain-0027, 00:27-01:27) finished grid and try 1, wrote `chain.json` (verdict pass), then was OOM-killed at 01:27 in the unit-test step (9 GB cap). Tests rerun in `hyst-wo7-m3d-tests` (14 GB): see the summary. Nothing else was missing.
