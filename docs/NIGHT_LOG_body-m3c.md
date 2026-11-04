# Night log, builder 1 (body-m3c), work order 4, 2026-11-04

Provisional servo model throughout: Feetech STS3215 12 V assumed (kp, rotor inertia, damping 1.5, acceleration share 0.25), until the user chooses a servo.

## MORNING SUMMARY

(in progress: code and unit tests done, calibration and grid next)

## Log

### Phase 0: M3b stopped
By the overseer's message (user pivot): M3b units stopped, log line committed and pushed on `body-m3b` (343e8f5). Generic pieces reused here from body-m3b commit d160afd
(`tm3b.py`): `selection_stats` (renamed `c_pass`), `nonroll_stats`, `boot_ci`, and the K3-style PLV/surrogate code in `evaluate`.

### Phase 1: descriptors in Python (commit before this log: "M3c: Python port of the body-study descriptors")
`scripts/body/bdesc.py`: the 31 descriptors (Rust's 37 minus the roll's 6). Parity test `test_bdesc.py`, on 3 fixed 8 s clips (body [0.5]*15 seed 7, [0.2]*15 seed 11,
[0.85]*15 seed 23): reference values exported once by a scratch crate outside the repo (`/secondary/hyst-data/body/m3c/parity_rs`, path dependency on hyst-compile, calling
`body::{clip, frames, descriptors}`; no file under `crates/` touched) into `scripts/body/descriptor_ref.json` (each clip's 481 frames and Rust's 37 values).
Tolerance stated before the comparison: |python - rust| <= 1e-6 * max(1, |rust|), per descriptor. Result: all 31 x 3 pass, max relative difference 2.6e-8 (frames rounded to 1e-12 deg in the file).
Undefined on 2 s: Rust's periodicity lags (0.3-3 s) do not fit a 2 s window (its loop would underflow on 120 hand-speed samples). On the 2 s window the lags run 0.3-1.0 s (half the
window); the parity test uses Rust's own 3.0 s on the 8 s clips. All other descriptors are defined on 2 s unchanged (lag search +-0.5 s). Roll: the hand point does not depend on the roll, so
height, extension and periodicity are unchanged by it; tested with a violent roll (descriptors bit-identical).

### Phase 2: code and unit tests (before any run)
New files: `tm3c.py`, `run_tm3c.py`, `test_tm3c.py` (T-M3 untouched). Stated before the first run:
- **Observer architecture:** MLP 31 -> 64 -> 64 -> 8, tanh, MSE on standardised targets, Adam 1e-3, batch 128, 30 steps per iteration from a replay buffer of the last 4,000
  training blocks (training episodes only). Descriptors standardised by the calibration's mean and SD. It is given nothing but the 31 descriptors of the last 2 s of joint positions.
- **Brain state (8 numbers per 0.5 s block, standardised by calibration mean/SD):** arousal (total surprisal through a follower, rise tau 1 s, decay tau 8 s, value at block end), mean
  total surprisal, cos and sin of the L3 phase (phase of the L3 mode with the largest block-mean magnitude, frames averaged), log band power L1..L4 (mean over 16 modes of |h|^2, block mean).
  Cortex: the frozen toy cortex of T-M3 listening to the synthetic pulse song alone (no proprioception, relays zero).
- **Reward:** r = legibility - lambda*R0*E/E0 + beta*R0*LP/LP0 - c_sw*R0*[switch] per 0.1 s step (tm3.reward_terms), R0 = 1: legibility = -(observer MSE on standardised targets of the block), so the
  mean predictor scores -1 and lambda = 1 means the mean energy per step costs one unit of that loss. Blocks before 2 s of movement exist score -1. LP: the cerebellum round-2 bundle
  `/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt` (online learning progress, as T-M3).
- **Entropy weight scale:** loss = PPO clip loss (advantages normalised to unit SD per update) + 0.5 value MSE - ent * H, H = mean entropy of the 8-way program softmax over decision rows (max ln 8 = 2.079 nats);
  same code path as T-M3 (tm3.ppo_update); grid 0.01 and 0.05.
- **kappa:** dphase_i/dt += kappa_i * sin(phi_L3 - phase_i); kappa_i = KAPPA_MAX * relu(tanh(a_i)), bound **KAPPA_MAX = 2 pi rad/s** (a 1 Hz capture range), a = five extra outputs of the motor cortex
  (final-layer bias -2, so kappa starts mostly 0). phi_L3 = last measured L3 phase extrapolated at its last measured rate (causal). kappa = 0 adds exactly 0.0 to the phase (unit test: bit-identical to cpg.CPG).
- **(a) metric:** per held-out episode, mean over blocks (after 10 s) of [loss with episode i's brain state paired to episode j's movement, j = fixed partner != i from seed 0] minus [loss with matched pairs], under the
  trained observer (standardised units); mean over episodes, 95 % bootstrap interval over episodes; pass if the lower bound > 0. Held-out = fresh arms and songs (seed 999), policy's mean action, 8 episodes x 90 s.
  (b) RMS joint speed over joints 0-3. (c) programs from the policy's mean action (argmax), at least 4 each in >= 5 % of decisions. Report only: K3-style PLV of the dominant non-roll joint's velocity to the pulse phase
  against 1,000 circular-shift surrogates; kappa used.
- **Unit tests** (`test_tm3c.py`, 11, own process; `test_bdesc.py`, 4): descriptor parity; observer input is a function of the last 2 s of joint positions only and the observer module takes 31 numbers; roll motion does not change
  the descriptors; brain targets are the same whatever the policy does (the cortex never sees the arm); kappa = 0 identical to the old generator (generator level and a full block of arm trajectory); kappa bounded; the coupling pulls the phase;
  the shuffled control pairs i with j != i (fixed seed, a derangement) and its loss is computed on that pairing; (c) on synthetic choice sequences; a full iteration trains observer and policy.

### Phase 3: calibration and grid (24 runs, 30 iterations each, 8 envs x 300 steps, evaluation 8 x 90 s)
Calibration (`/secondary/hyst-data/body/m3c/calib.json`): R0 = 1 (by construction), LP0 0.0540, E0 0.0692; observer loss on random movement during calibration about 0.45 (training episodes).

Grid, a = mean (shuffled - matched) loss, 95 % interval; b = RMS non-roll deg/s; programs used / above 5 %; kappa active share was 0.00 in every run:

- l0.01_b0.1_e0.01_c0.1: a -0.0019 [-0.0041, +0.0004], matched loss 1.016, b 33.1, programs 2/1, entropy 0.03
- l0.01_b0.1_e0.01_c0: a -0.0020 [-0.0063, +0.0026], matched loss 1.017, b 35.8, programs 2/1, entropy 0.03
- l0.01_b0.1_e0.05_c0.1: a +0.0001 [-0.0014, +0.0016], matched loss 1.011, b 51.7, programs 1/1, entropy -0.00
- l0.01_b0.1_e0.05_c0: a +0.0004 [-0.0018, +0.0030], matched loss 1.024, b 51.5, programs 1/1, entropy -0.00
- l0.01_b0_e0.01_c0.1: a +0.0004 [-0.0022, +0.0033], matched loss 1.007, b 52.0, programs 1/1, entropy -0.00
- l0.01_b0_e0.01_c0: a -0.0002 [-0.0028, +0.0020], matched loss 1.008, b 52.9, programs 1/1, entropy -0.00
- l0.01_b0_e0.05_c0.1: a +0.0001 [-0.0021, +0.0022], matched loss 1.038, b 50.9, programs 2/2, entropy 0.48
- l0.01_b0_e0.05_c0: a +0.0008 [-0.0006, +0.0023], matched loss 1.025, b 46.2, programs 1/1, entropy -0.00
- l0.1_b0.1_e0.01_c0.1: a -0.0005 [-0.0034, +0.0026], matched loss 1.034, b 42.7, programs 2/1, entropy 0.03
- l0.1_b0.1_e0.01_c0: a -0.0013 [-0.0045, +0.0011], matched loss 1.031, b 51.0, programs 1/1, entropy -0.00
- l0.1_b0.1_e0.05_c0.1: a -0.0010 [-0.0058, +0.0038], matched loss 1.035, b 28.3, programs 2/1, entropy 0.03
- l0.1_b0.1_e0.05_c0: a -0.0010 [-0.0064, +0.0039], matched loss 0.995, b 47.3, programs 1/1, entropy -0.00
- l0.1_b0_e0.01_c0.1: a -0.0001 [-0.0027, +0.0027], matched loss 1.027, b 27.6, programs 2/1, entropy 0.03
- l0.1_b0_e0.01_c0: a +0.0006 [-0.0015, +0.0024], matched loss 1.013, b 27.7, programs 2/1, entropy 0.03
- l0.1_b0_e0.05_c0.1: a -0.0006 [-0.0027, +0.0021], matched loss 1.029, b 27.8, programs 2/1, entropy 0.03
- l0.1_b0_e0.05_c0: a +0.0006 [-0.0011, +0.0023], matched loss 1.019, b 27.7, programs 2/1, entropy 0.03
- l1_b0.1_e0.01_c0.1: a +0.0001 [-0.0012, +0.0015], matched loss 1.033, b 28.0, programs 2/1, entropy 0.03
- l1_b0.1_e0.01_c0: a +0.0017 [-0.0008, +0.0041], matched loss 1.026, b 27.9, programs 2/1, entropy 0.03
- l1_b0.1_e0.05_c0.1: a +0.0001 [-0.0012, +0.0015], matched loss 1.024, b 27.9, programs 2/1, entropy 0.03
- l1_b0.1_e0.05_c0: a -0.0016 [-0.0033, -0.0001], matched loss 1.027, b 28.3, programs 2/1, entropy 0.03
- l1_b0_e0.01_c0.1: a -0.0009 [-0.0023, +0.0003], matched loss 1.043, b 27.7, programs 2/1, entropy 0.03
- l1_b0_e0.01_c0: a -0.0003 [-0.0016, +0.0010], matched loss 1.037, b 27.6, programs 2/1, entropy 0.03
- l1_b0_e0.05_c0.1: a +0.0000 [-0.0012, +0.0010], matched loss 1.031, b 27.6, programs 2/1, entropy 0.03
- l1_b0_e0.05_c0: a +0.0004 [-0.0007, +0.0014], matched loss 1.022, b 27.6, programs 2/1, entropy 0.03

Reading: no setting has an interval above 0 for (a); held-out matched loss is about 1.0 (the mean predictor's value) in every run while the training-episode observer loss is about 0.4, so the observer does not carry over to fresh songs; (c) fails in all 24 (at most 2 programs above 5 %); kappa is never used. **Chosen by the rule (no setting meets (c): maximise (a) subject to (b)): lambda 1, beta 0.1, entropy weight 0.01, c_sw 0** (a +0.0017 [-0.0008, +0.0041], b 27.9). Differences between settings are within noise. Frozen here, before try 1.

### Phase 4: try 1 and diagnosis
Try 1 (frozen setting, seed 1, 30 iterations, 8 x 90 s evaluation; `m3c/try1.result.json`): **(a) FAIL** +0.0005 [-0.0010, +0.0019] (matched loss 1.036, shuffled 1.037); (b) pass 28.3 deg/s over joints 0-3 (per joint 53.5 / 13.6 / 0.17 / 12.8, roll 93.1); (c) **FAIL**: 2 programs used, counts 8 / 1432, 1 above 5 %, 0.67 switches/min, entropy 0.034 nats; kappa 0.0 in every joint; K3-style PLV 0.0056 (surrogate mean 0.0066, max 0.021, p 0.57), report only.
Diagnosis (about 10 min, `diag_random`: initial random policy kept, observer trains for 30 iterations, same evaluation): (1) the observer does NOT beat the control with random movement either: a +0.0005 [-0.0026, +0.0037], matched loss 1.039. (2) Policy collapses as in T-M3: training entropy 0.71 nats but the mean action picks one program (value loss 70, |delta| 0.75: the critic does not keep up). (3) kappa is not used (training mean 0.002). The observer's training-episode loss falls to about 0.43 while its loss on fresh episodes is about 1.04: it memorises the training episodes (8 environments, a 4,000-block replay buffer, slowly varying targets, movement statistics that identify an episode), so the legibility the policy is paid is mostly episode identity, not a state read from movement.
Try 2: one change, **observer size, hidden width 64 -> 16** (`--obs-hidden 16`; architecture otherwise as stated: 31 -> 16 -> 16 -> 8), to limit memorisation. Calibration repeated with the small observer (`m3c/t2/`). Reward definition, bar, setting (lambda 1, beta 0.1, ent 0.01, c_sw 0), seed 1, iterations and evaluation unchanged. Named before the run.
