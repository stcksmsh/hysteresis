# Night log, builder 1 (body-m3b), work order 3, 2026-11-04

Provisional servo model throughout: Feetech STS3215 12 V assumed (kp, rotor inertia, damping 1.5, acceleration share 0.25), until the user chooses a servo.

## MORNING SUMMARY

(in progress: code and unit tests done, calibration and grid next)

## Log

### Phase 1: code and unit tests (before any run)
New files beside T-M3 (T-M3 files untouched): `scripts/body/tm3b.py`, `run_tm3b.py`, `test_tm3b.py`. Data under `/secondary/hyst-data/body/m3b/`.
Stated before the first run:
- **Shift rule.** S_shifted = the cortex fed the same environment's relay input (standardised proprioception + cerebellum error, 30 columns) delayed by
  Delta_e, Delta_e ~ U(2, 8) s per environment (rounded to 10 ms), fixed seeds: 11 for training and for (a), 22 for the second-shift control. A delay is a
  circular shift of a stationary stream; a training episode is endless, so the shift is causal: frames before Delta_e have no history (zeros), their
  reward is 0 (masked). Evaluation skips the first 10 s (> 8 s), so (a) never contains masked frames. Twin pass rows are [moving, shifted]; no S_still.
- **Roll.** `CortexB` zeroes the relay input's six roll columns (index 4 of each 5-joint block: position, velocity, load, and the three cerebellum errors), so
  the roll is absent from every cortex call (block, relay training, evaluation). (b) is the RMS over joints 0-3, (c) uses the dominant of joints 0-3. The
  roll still costs energy; the cerebellum and the policy input z still see it. The per-joint RMS (all five) is reported.
- **Entropy weight scale.** loss = PPO clip loss (advantages normalised to unit SD per update) + 0.5 * value MSE - ent * H, H = mean Shannon entropy of the
  8-way program softmax over decision rows (max ln 8 = 2.079 nats). Same code path as T-M3 (`tm3.ppo_update`, T-M3 default 0.01). Grid: 0.01 and 0.05.
- **(d) mode.** Evaluated from the policy's mean action (argmax program), as T-M3 did; the sampling policy's mean probabilities and entropy are reported next to it.
- **Toy cerebellum:** the K1 round-2 bundle `/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt` (GRU 256; T-M3 used round 1). Cortex: the T-M3 pretrained reduced
  cortex (copied to `m3b/cortex.pt`). New calibration (R0 = mean |S_shifted - S_moving| per 0.1 s at initialisation after 15 windows of relay learning, LP0, E0).
- Unit tests (`test_tm3b.py`, 10, all pass, own process): delay shape; shifts in 2-8 s and fixed by seed; non-roll stats ignore a fast roll; (d) on synthetic choice
  sequences (counts, entropy, switches, the 5 % rule); identity at step 0 (d exactly 0); roll absent from the relay input (changing only roll columns changes
  nothing, a non-roll column does); the shifted row equals the same episode's relay input delayed by the stated shift (block buffer vs `delay`); reward is 0 until
  the shifted row has history and non-zero after (non-zero relay); the entropy bonus changes the PPO gradient (ent 1 vs 0; ent 0 twice identical).
