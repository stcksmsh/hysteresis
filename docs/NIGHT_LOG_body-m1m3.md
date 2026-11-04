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
