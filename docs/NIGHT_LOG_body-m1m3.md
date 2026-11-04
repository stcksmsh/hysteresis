# Night log, builder 1 (body-m1m3), work order 2, 2026-11-04

Provisional servo model throughout: Feetech STS3215 12 V assumed; kp, rotor inertia, damping 1.5, acceleration share 0.25 (until the user chooses a servo).

## MORNING SUMMARY

(in progress; phases 0 and 1 below)

## Log

### Phase 0: D4, Kaggle verify of `hyst-features`
Kernel `kostavukicevic/hyst-job-verify-features-001` (CPU, no GPU) pushed; it attaches `hyst-code` and `hyst-features` and runs `manifest.py verify` on the features. Result (kernel ran 1,169 s on a CPU worker, hyst-code commit db1e4c2): `manifest.py verify` exit 1 with exactly one problem, `missing dataset-metadata.json`; every other manifest entry exists with an identical SHA-256. Kaggle consumes `dataset-metadata.json` on upload and does not store it, so the one mismatch is the metadata file, not data. FOR USER: `manifest.py` should skip `dataset-metadata.json` in `build`/`verify` (not changed here: scripts/compute is outside this order).
(Mains power: `/sys/class/power_supply/ADP1/online` = 1; the `AC*` path in the prompt does not exist on this machine.)

### Phase 1: M1 toy
- `scripts/body/babble.py`: OU commands (tau 1 s, 10 Hz, stationary N(0,1) squashed by the normal CDF to the full command ranges), own seed and own start pose per trajectory, logs obs (15 = pos, vel, load as the sim returns them, one step old) and the generator target (pre-limiter) at 100 Hz. `test_babble.py`: reproducible from a seed, OU autocorrelation, shapes.
- `scripts/body/cerebellum.py`: GRU(128) + linear skip path from the inputs; inputs = proprioception + current target + last 10 targets; Gaussian outputs for the change of proprioception at +10/+50/+100 ms, standardised by the training SD of that change; beta-NLL (0.5). Baselines: persistence (zero change, constant fitted variance), ridge (alpha 1.0, same inputs, constant fitted variance).
- Toy (1 h train, 10 min held out, 20 epochs, 12 threads, 111 s): mean per-trajectory (NLL, MSE) in standardised units, model / ridge / persistence:
  +10 ms (-0.001, 0.230) / (-0.132, 0.165) / (1.410, 0.983); +50 ms (-0.107, 0.229) / (-0.424, 0.192) / (1.416, 0.994); +100 ms (0.044, 0.216) / (-0.180, 0.224) / (1.417, 0.997).
  Toy bar (beats persistence at +100 ms): PASS. The model does not yet beat ridge on NLL at 1 h of data; that is K1's question at 20 h.
- Without the skip path, the same toy gave +100 ms (0.064, 0.219): the skip path was added before the K1 check was committed.

### Phase 2 start (data, v47 set, K1 check committed)
- Data (outside the repo, `/secondary/hyst-data/body/`): `train20h.npz` (1,200 trajectories x 60 s, seeds `1000 + i * 1,000,003`), `held2h.npz` (120 x 60 s, seeds `7,000,000,000 + i * 1,000,003`: no overlap with train seeds, own start pose each), `toy_*.npz`.
- v47 set (D2): `ensemble_preview` from this branch reproduces `hexagon-47.html`, `five-years-hexagon.html` and `presence-hexagon.html` byte for byte (cmp), so the three scores are v47. The 18 arm trajectories (3 songs x 6 hexagon arms) were exported at 100 Hz with `hyst score-csv --hz 100 --agent N` (new optional flag, default 0 = unchanged output; new `score_csv::export_agent`; hyst-compile score_csv tests pass), replayed in physics as servo targets (`build_v47.py`) and split into whole 60 s segments: 78 segments (partial tails dropped). Files `v47set.npz`, `v47set.excess.json`.
- v47 raw targets against M0's limits (mode Off, before the sim's limiter), over the 18 trajectories: fraction of 100 Hz steps above the speed limit: base_yaw 5.2 % (worst trajectory 11.5 %), shoulder 0.6 %, elbow 0.04 %; above the acceleration limit: base_yaw 0.7 %, shoulder 4.5 % (worst 6.5 %), elbow 0.6 %; none outside a joint range. Worst single step: shoulder acceleration 9.9 x its limit, shoulder speed 2.1 x. Trajectories kept. The sim's limiter makes the applied target differ from the raw one by RMS 6.0 deg (base_yaw, up to 10.0), 2.3 (shoulder), 1.1 (elbow), 0.9, 1.1 deg. The cerebellum's command is the raw target (D1).
- `check_m1.py` (K1) committed in 3dfcdc2 before training. As committed: per set, all three horizons (+10, +50, +100 ms) must pass: NLL gain over persistence and over ridge with the 95 % bootstrap lower bound above 0, and MSE at least 5 % below the better baseline (point estimate). I chose "all three horizons on both sets" because the plan names no horizon; it is stricter than a pooled reading.
- Environment change: `uv pip install mujoco==3.17.0` into `/secondary/hyst-env/brain` (adds absl-py 2.5.1, etils 1.15.0, glfw 2.11.0, pyopengl 3.1.10, websockets 17.4, zipp 4.1.2; no existing package changed) so one interpreter has torch and MuJoCo.
- M1 round 1: `hyst-wo2b1-m1r1` (systemd user unit, MemoryMax 14G, run_job), GRU 128, 30 epochs, about 160 s/epoch on the laptop (12 threads), about 80 min; `/secondary/hyst-data/body/runs/m1-r1/`.

### Phase 2: M1 round 1 and K1
- Round 1: GRU 128 + skip, 30 epochs, trained locally (12 threads, 3,588 s, unit hyst-wo2b1-m1r1), bundle `/secondary/hyst-data/body/runs/m1-r1/m1_r1.pt`. K1 as committed (`k1_round1.json`): **FAIL**.
- Held-out babbling (120 trajectories), gain = baseline NLL minus model NLL, 95 % interval: +10 ms vs persistence 1.92 [1.91, 1.93], vs ridge 0.33 [0.32, 0.34], MSE 0.039 vs ridge 0.142 (-73 %): pass. +50 ms vs persistence 1.73 [1.72, 1.74], **vs ridge -0.17 [-0.18, -0.16]: fail** (MSE 0.084 vs 0.170, -51 %). +100 ms vs persistence 1.69, vs ridge 0.043 [0.036, 0.050], MSE 0.125 vs 0.209 (-40 %): pass. So the babbling set fails on one condition: the model's predicted variance is worse calibrated than ridge's constant one at +50 ms, although its error is half.
- v47 set (78 segments, two-level bootstrap): **fail on every condition.** NLL gains negative (vs persistence -36.6 [-64, -11] at +10 ms; -6.2 at +50 ms; -7.9 at +100 ms), MSE model 0.75 / 0.77 / 0.66 against persistence 0.66 / 0.68 / 0.70 and ridge 0.33 / 0.32 / 0.59. Out of distribution the model does worse than persistence; the v47 trajectories (raw targets that the sim's limiter changes by up to 10 deg RMS, speeds and accelerations above M0's limits, long smooth stretches unlike OU babbling) are far from the training babbling.
- Round 2 (the one allowed rerun, width and training length only): hidden 256, 30 epochs, unit hyst-wo2b1-m1r2, 7 threads, `/secondary/hyst-data/body/runs/m1-r2/`. Nothing else changes (data, inputs, loss, baselines, check). I expect the v47 set to stay failed; capacity does not change what the training data covers. If K1 fails again, M1's claim stays unlicensed and T-M3 uses the better bundle as a toy cerebellum (logged).

### Phase 3: M3 step benchmark (report only)
One step = one 2 s block per environment (200 frames), E environments: physics (E arms x 200 control steps, 12 worker processes) + B7 epoch 6 twin pass (moving and still, batch 2E, gradient checkpointing) with the proprioceptive relays + backward into the relays (cortex frozen) + basal ganglia / motor cortex / critic forward and backward on E x 20 samples. Non-zero relays and synthetic standardised features (cost does not depend on content). "Per simulated hour" = wall seconds to produce one hour of experience summed over environments = step seconds x 3600 / (2E).

| E | device | physics s | cortex twin fwd s | relay bwd s | policy s | step s | wall s per simulated hour | peak memory |
|---|---|---|---|---|---|---|---|---|
| 16 | laptop CPU, 12 threads | 0.104 | 0.141 | 0.189 | 0.006 | 0.454 | 51.1 | 1.0 GB RSS (main process) |
| 64 | laptop CPU | 0.329 | 0.600 | 1.119 | 0.012 | 2.05 | 57.7 | 2.1 GB |
| 256 | laptop CPU | 1.283 | 2.748 | 4.376 | 0.034 | 8.47 | 59.5 | 6.7 GB (256 environments fit in 14 GB) |
| 16 | Kaggle T4 (4 CPU cores for physics) | 0.295 | 0.029 | 0.037 | 0.004 | 0.368 | 41.4 | 0.39 GB GPU |
| 64 | T4 | 1.311 | 0.067 | 0.105 | 0.004 | 1.511 | 42.5 | 1.41 GB GPU |
| 256 | T4 | 4.907 | 0.278 | 0.386 | 0.005 | 5.576 | 39.2 | 5.53 GB GPU |

Reading: on the laptop the cortex twin pass plus relay backward is about 85 % of the step; on the T4 the cortex costs 0.66 s at 256 environments and the 4 Kaggle CPU cores doing physics (4.9 s) dominate. The two machines differ by about 1.5x per simulated hour as measured. The T4 job ran 59 s of kernel time (the first attempt, 40 s, failed on a benchmark bug fixed in c087504): GPU hours used about 0.05. Peak RSS above is the main process only (ru_maxrss of children is not counted); the 12 physics workers each hold small arm models.
Real-M3 caveat found while building T-M3: B7 runs in blocks of 200 frames (2 s) and a chunk must start on a block edge, so with epoch 6 unchanged the policy sees the cortex state of the previous block (up to 2 s stale). The toy uses 0.5 s blocks (its cortex is retrained, so that is allowed there); the real run does not have that option without changing the frozen cortex.
