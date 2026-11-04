# Night log, builder 1 (body-reeval), work order 5, 2026-11-04

Provisional servo model throughout: Feetech STS3215 12 V assumed (kp, rotor inertia, damping 1.5, acceleration share 0.25).

## MORNING SUMMARY

Sampled re-evaluation of the saved T-M3, M3b and M3c policies, no retraining, nothing tuned. Both rounds stand as they were; no pass is claimed. Results: `/secondary/hyst-data/body/reeval/*.json`, driver `scripts/body/reeval.py`.

Definitions (fixed before running). Same evaluation seed (999), 8 episodes x 90 s, first 10 s skipped, as the originals. **argmax**: program = argmax of the logits, modulation = mean (the original evaluation). **sampled**: program sampled from the softmax, modulation = mean (same in all three families; torch seed 2026). **MI**: plug-in mutual information (nats) between the program chosen at a 0.5 s block start and the brain state at that moment; state = 4 x arousal bin + L3-phase bin (16 states). Arousal = one-pole of the total music surprisal (rise 1 s, decay 8 s, as `tm3c.brain_state`), quartile edges pooled over the evaluation; L3 phase = angle of the dominant L3 mode at the previous block's last frame, 4 equal sectors. Shuffle control: program sequence permuted within each episode, 1,000 times, p = (1 + #(shuffled >= observed)) / 1,001. T-M3's saved `.pt` has no cerebellum weights: both modes use the calibration cerebellum (original used the online-trained one; argmax numbers match the originals closely: try 1 (a) 0.795 vs 0.799, (b) 42.1 same).

| policy | mode | (a) | (b) deg/s | (c) p | (d) | programs | switches/min | entropy nats | MI nats (shuffle mean) | MI p |
|---|---|---|---|---|---|---|---|---|---|---|
| T-M3 try 1 | argmax | 0.795 P | 42.1 P | 0.016 F | n/a | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| T-M3 try 1 | sampled | 0.710 P | 57.0 P | 0.529 F | n/a | 8 | 90.8 | 1.58 | 0.007 (0.009) | 0.67 |
| T-M3 try 2 | argmax | 0.644 P | 46.7 P | 0.693 F | n/a | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| T-M3 try 2 | sampled | 0.526 P | 61.8 P | 0.246 F | n/a | 8 | 99.3 | 1.88 | 0.014 (0.008) | 0.032 |
| M3b g_b0_l0.01_c0.1_e0.01 | argmax | -0.003 F | 55.7 P | 0.008 P | F | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| M3b g_b0_l0.01_c0.1_e0.01 | sampled | +0.002 F | 48.6 P | 0.728 F | P | 8 | 99.8 | 2.00 | 0.010 (0.008) | 0.285 |
| M3b g_b0_l0.01_c0_e0.01 | argmax | -0.002 F | 53.4 P | 0.289 F | F | 4 | 3.7 | 0.17 | 0.017 (0.003) | 0.001 |
| M3b g_b0_l0.01_c0_e0.01 | sampled | +0.004 P | 47.1 P | 0.325 F | P | 8 | 102.6 | 2.06 | 0.008 (0.008) | 0.494 |
| M3b g_b0_l0.01_c0_e0.05 | argmax | -0.002 F | 42.2 P | 0.621 F | F | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| M3b g_b0_l0.01_c0_e0.05 | sampled | +0.003 P | 47.4 P | 0.657 F | P | 8 | 103.6 | 2.07 | 0.006 (0.008) | 0.80 |
| M3b g_b0_l0.1_c0_e0.01 | argmax | -0.004 F | 51.0 P | 0.290 F | F | 3 | 5.1 | 0.61 | 0.155 (0.003) | 0.001 |
| M3b g_b0_l0.1_c0_e0.01 | sampled | +0.003 P | 47.7 P | 0.696 F | P | 8 | 102.5 | 2.06 | 0.008 (0.008) | 0.50 |
| M3c try 1 | argmax | +0.0003 F | 28.3 P | 0.596 F | n/a | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| M3c try 1 | sampled | +0.0007 F | 32.1 P | 0.904 F | n/a | 8 | 48.3 | 0.73 | 0.008 (0.009) | 0.57 |
| M3c try 2 | argmax | -0.0003 F | 28.1 P | 0.686 F | n/a | 2 | 0.7 | 0.03 | 0.000 (0.000) | 1.00 |
| M3c try 2 | sampled | +0.0008 F | 33.3 P | 0.061 F | n/a | 7 | 57.4 | 0.75 | 0.004 (0.005) | 0.81 |

(a) for M3b is S_shifted - S_moving; for M3c the matched-versus-song-shuffled observer loss difference; (c) for M3c is the report-only K3-style PLV (p = k3_p); (d) = at least 4 programs each above 5 % of decisions (M3b only). Per-policy interval and per-joint values are in the JSON files.

Reading (measurement only):
- The argmax counts (2 programs, 0.7 switches/min, 0.03 nats) are reproduced for every policy except two M3b grid policies, so the "selection collapse" was the argmax; sampled, every policy uses 7-8 programs, 48-104 switches per minute, entropy 0.7-2.07 nats (M3c lower: its logits are less flat).
- Program choice carries no information about the brain state beyond the shuffle in 13 of 16 policy-mode pairs. T-M3 try 2 sampled has MI 0.0137 against a shuffle mean of 0.0082, p = 0.032: not below 0.01. M3b's two argmax policies with MI p = 0.001 (MI 0.017 and 0.155 nats) use 3-4 programs over a few decisions; with so few switches that MI is carried by a small number of decisions and is argmax-only; the sampled versions of the same policies show none (p 0.49, 0.50).
- (a) of T-M3 survives sampling (0.71, 0.53), smaller than under argmax; (c) fails in both modes for both tries. M3b's (a) reads positive but near 0 (+0.002 to +0.004; two to four of the sampled versions have an interval above 0, see JSON): its argmax versions fail (a). M3c (a) fails in both modes.
- No claim of a pass: the original tries and their rounds stand as recorded.

## Log

### Work done
- `tm3.py`, `tm3b.py`, `tm3c.py`: `block(..., sample_prog=False)` (program sampled, modulation mean), `evaluate(..., sample_prog=False)`; each `evaluate` now also returns `mi_nats`, `mi_shuffle_mean`, `mi_shuffle_max`, `mi_p`, `mi_n_decisions`, `sampled`. New in `tm3.py`: `mutual_information`, `mi_with_shuffle`, `brain_state_bins`, `program_state_mi`. Per-block records gained `s_state` and `h3_state` (moving row's total surprisal and L3 state).
- `reeval.py`: loads each saved policy and runs both modes (resumable).
- Unit tests (`test_tm3.py`): sampled mode samples on flat logits and argmax does not; MI is within noise for an independent synthetic choice, above the shuffle for a dependent one; MI of a constant choice is 0. `test_tm3` 13 tests, `test_tm3b` 10, `test_tm3c` 11, all pass.
- Run: unit `hyst-wo5-b1-reeval`, 2 threads, 4 GB cap, mains power.
