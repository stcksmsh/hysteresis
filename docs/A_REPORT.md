# A report: motor grammar conditioned on controls (WO45 / WO45B)

Binding: `docs/A_RULES.md` with addendum 1. Numbers only, no verdict. Seeds 45101-45103; checks on 200 held-out starts (FineDance 100, AIOZ 50, PhantomDance 25, Motorica 25; validation + test; at most 2 per song), 2 samples each, nucleus 0.9, first 4 tokens teacher forced, style triple pinned to the window's own. Realised stage throughout (guard, spinal, limiter, servo, v2p). Control refinements: `docs/CONTROLS_REFINE_REPORT.md`.

## 1. Training

All three seeds ran to the 40-epoch cap and were still improving at the cap (validation total fell in the last epochs; see the last-5-epoch column); the cap is the rules' (A_RULES section 4), not an early stop. `best.pt` = the epoch with the lowest validation total (here the last or next-to-last epoch).

| seed | best epoch | val total | train eval-subset total | gap (val - train) | val no-controls total | aux train noisy | aux val | val total, last 5 epochs |
|---|---|---|---|---|---|---|---|---|
| 45101 | 40 | 18.417 | 16.220 | 2.197 | 21.790 | 0.865 | 1.076 | 18.462, 18.443, 18.436, 18.417, 18.417 |
| 45102 | 40 | 18.469 | 16.192 | 2.276 | 21.735 | 0.867 | 1.076 | 18.521, 18.509, 18.494, 18.481, 18.469 |
| 45103 | 40 | 18.446 | 16.172 | 2.275 | 21.753 | 0.873 | 1.077 | 18.496, 18.489, 18.474, 18.457, 18.446 |

Per head at the best epoch (validation / train eval-subset / gap), seed mean:

| head | validation | train subset | gap | validation without controls |
|---|---|---|---|---|
| code1 | 4.845 | 4.070 | 0.775 | 5.720 |
| code2 | 6.380 | 5.656 | 0.724 | 6.693 |
| vigour | 2.050 | 1.963 | 0.087 | 2.615 |
| posture1 | 1.695 | 1.376 | 0.319 | 2.348 |
| posture2 | 3.475 | 3.131 | 0.344 | 4.383 |

Per-epoch table (seed 45101; validation per head, no-controls total, aux), every 5th epoch:

| epoch | train noisy total | train subset total | val total | no controls | aux val | code1 | code2 | vigour | posture1 | posture2 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 25.269 | 23.350 | 23.656 | 24.918 | 1.081 | 6.62 | 6.91 | 2.30 | 3.06 | 4.77 |
| 5 | 21.501 | 20.446 | 21.171 | 23.253 | 1.075 | 5.84 | 6.76 | 2.14 | 2.20 | 4.24 |
| 10 | 20.255 | 18.984 | 20.125 | 22.498 | 1.073 | 5.44 | 6.65 | 2.10 | 1.99 | 3.96 |
| 15 | 19.448 | 18.007 | 19.447 | 22.178 | 1.074 | 5.19 | 6.54 | 2.08 | 1.87 | 3.77 |
| 20 | 18.927 | 17.375 | 19.025 | 22.054 | 1.075 | 5.04 | 6.47 | 2.07 | 1.80 | 3.65 |
| 25 | 18.599 | 16.941 | 18.764 | 21.851 | 1.074 | 4.95 | 6.43 | 2.06 | 1.74 | 3.58 |
| 30 | 18.351 | 16.643 | 18.605 | 21.910 | 1.075 | 4.89 | 6.40 | 2.05 | 1.72 | 3.53 |
| 35 | 18.177 | 16.389 | 18.477 | 21.804 | 1.074 | 4.86 | 6.39 | 2.05 | 1.70 | 3.49 |
| 40 | 18.032 | 16.220 | 18.417 | 21.790 | 1.076 | 4.83 | 6.38 | 2.05 | 1.69 | 3.47 |

The controls help: validation total without controls is higher by 3.37, 3.27, 3.31 nats (seeds, last epoch). Full per-epoch logs: `grammar/runs/seed*/log.json`.

## 2. A checks (200 held-out starts, 2 samples each, song bootstrap 95 % intervals, seeds shown separately)

### 2.1 Residual-code utilisation

| seed | stage-2 codes used | perplexity | H(c2) | H(c2 given c1) | mutual information | model entropy of the code-2 head | decoded stage-2 effect (RMS ratio, median [quartiles]) |
|---|---|---|---|---|---|---|---|
| 45101 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 6.03 | 0.167 [0.1354918805304948, 0.21874820915564605] |
| 45102 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 6.03 | 0.167 [0.1354918805304948, 0.21874820915564605] |
| 45103 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 6.02 | 0.167 [0.1354918805304948, 0.21874820915564605] |

### 2.2 Intervention matrix (effect = mean over starts of output(high) - output(low), in sd of the human starts' own window means; expected sign positive; accent = back-loaded minus front-loaded centre of mass)

**seed 45101**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.56 [2.51, 2.60] | 0.03 [-0.00, 0.07] | 0.59 [0.54, 0.64] | -0.38 [-0.43, -0.33] | -0.02 [-0.15, 0.11] | -0.58 [-0.71, -0.44] | 1.27 [1.18, 1.36] | 1.61 [1.45, 1.78] |
| height | -0.00 [-0.04, 0.03] | 4.50 [4.45, 4.55] | -0.21 [-0.26, -0.16] | 0.01 [-0.03, 0.04] | -0.00 [-0.13, 0.12] | -0.01 [-0.12, 0.10] | -0.21 [-0.30, -0.12] | 0.02 [-0.12, 0.16] |
| accent | 0.04 [0.01, 0.07] | 0.08 [0.06, 0.11] | 0.08 [0.04, 0.12] | -0.03 [-0.07, -0.01] | 0.02 [-0.09, 0.13] | 0.06 [-0.06, 0.18] | 0.18 [0.13, 0.24] | -0.11 [-0.20, -0.02] |
| sharp | 0.10 [0.07, 0.14] | -0.00 [-0.03, 0.03] | 0.61 [0.56, 0.66] | -0.01 [-0.04, 0.03] | -0.02 [-0.15, 0.10] | -0.23 [-0.34, -0.12] | 0.54 [0.47, 0.60] | -0.27 [-0.38, -0.16] |
| direction | -0.07 [-0.10, -0.04] | 0.04 [-0.01, 0.08] | 0.00 [-0.05, 0.05] | 0.02 [-0.03, 0.06] | 0.30 [0.15, 0.45] | -0.06 [-0.20, 0.08] | 0.00 [-0.07, 0.07] | -0.13 [-0.23, -0.05] |
| pause | 0.23 [0.18, 0.28] | -0.04 [-0.07, -0.01] | 0.55 [0.50, 0.60] | 0.05 [0.02, 0.09] | 0.03 [-0.11, 0.17] | -0.22 [-0.34, -0.10] | 0.69 [0.60, 0.78] | -0.91 [-1.05, -0.77] |
| pause_high_p99 | 0.23 [0.18, 0.28] | -0.04 [-0.07, -0.01] | 0.55 [0.50, 0.60] | 0.05 [0.02, 0.09] | 0.03 [-0.11, 0.17] | -0.22 [-0.34, -0.10] | 0.69 [0.60, 0.78] | -0.91 [-1.05, -0.77] |

**seed 45102**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.55 [2.50, 2.60] | 0.02 [-0.01, 0.05] | 0.56 [0.51, 0.61] | -0.37 [-0.43, -0.32] | -0.06 [-0.19, 0.06] | -0.56 [-0.68, -0.45] | 1.31 [1.21, 1.41] | 1.55 [1.41, 1.70] |
| height | 0.08 [0.05, 0.11] | 4.50 [4.45, 4.54] | -0.19 [-0.25, -0.14] | -0.03 [-0.07, 0.00] | 0.04 [-0.06, 0.15] | 0.10 [-0.02, 0.23] | -0.24 [-0.32, -0.15] | 0.41 [0.25, 0.58] |
| accent | 0.03 [-0.00, 0.05] | 0.01 [-0.02, 0.04] | 0.10 [0.06, 0.14] | -0.04 [-0.08, -0.01] | -0.05 [-0.17, 0.07] | 0.13 [0.02, 0.25] | 0.19 [0.12, 0.25] | -0.15 [-0.25, -0.06] |
| sharp | 0.14 [0.10, 0.17] | -0.06 [-0.09, -0.03] | 0.70 [0.65, 0.74] | -0.02 [-0.05, 0.02] | 0.00 [-0.11, 0.12] | -0.41 [-0.53, -0.30] | 0.54 [0.47, 0.61] | -0.26 [-0.36, -0.15] |
| direction | -0.06 [-0.08, -0.03] | 0.05 [0.02, 0.09] | -0.02 [-0.07, 0.04] | 0.01 [-0.02, 0.05] | 0.30 [0.16, 0.44] | -0.19 [-0.32, -0.07] | 0.10 [0.03, 0.17] | -0.20 [-0.29, -0.11] |
| pause | 0.72 [0.67, 0.77] | -0.17 [-0.21, -0.13] | 0.44 [0.38, 0.49] | 0.05 [0.02, 0.09] | 0.00 [-0.13, 0.13] | -0.05 [-0.17, 0.06] | 0.30 [0.22, 0.38] | -0.05 [-0.21, 0.11] |
| pause_high_p99 | 0.72 [0.67, 0.77] | -0.17 [-0.21, -0.13] | 0.44 [0.38, 0.49] | 0.05 [0.02, 0.09] | 0.00 [-0.13, 0.13] | -0.05 [-0.17, 0.06] | 0.30 [0.22, 0.38] | -0.05 [-0.21, 0.11] |

**seed 45103**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.52 [2.47, 2.56] | 0.16 [0.13, 0.19] | 0.59 [0.55, 0.63] | -0.31 [-0.36, -0.27] | 0.05 [-0.10, 0.19] | -0.75 [-0.87, -0.63] | 1.30 [1.21, 1.40] | 1.62 [1.46, 1.77] |
| height | 0.14 [0.10, 0.17] | 4.53 [4.48, 4.57] | -0.11 [-0.16, -0.06] | -0.03 [-0.06, -0.01] | -0.03 [-0.12, 0.06] | 0.05 [-0.08, 0.17] | -0.22 [-0.30, -0.13] | 0.45 [0.30, 0.62] |
| accent | 0.05 [0.02, 0.07] | 0.02 [-0.01, 0.05] | 0.07 [0.03, 0.11] | -0.05 [-0.08, -0.02] | -0.00 [-0.12, 0.10] | 0.05 [-0.07, 0.16] | 0.14 [0.08, 0.21] | -0.04 [-0.14, 0.06] |
| sharp | 0.15 [0.11, 0.19] | -0.06 [-0.09, -0.03] | 0.68 [0.63, 0.74] | -0.02 [-0.08, 0.04] | 0.04 [-0.09, 0.18] | -0.25 [-0.35, -0.15] | 0.56 [0.49, 0.63] | -0.34 [-0.44, -0.25] |
| direction | -0.02 [-0.05, 0.01] | 0.10 [0.07, 0.14] | 0.00 [-0.05, 0.05] | -0.01 [-0.07, 0.03] | 0.28 [0.14, 0.43] | -0.01 [-0.13, 0.10] | 0.03 [-0.05, 0.10] | -0.13 [-0.19, -0.07] |
| pause | 0.70 [0.64, 0.76] | 0.17 [0.14, 0.21] | 0.62 [0.56, 0.67] | 0.02 [-0.00, 0.04] | 0.03 [-0.10, 0.16] | -0.17 [-0.31, -0.04] | 0.83 [0.75, 0.91] | -1.02 [-1.17, -0.88] |
| pause_high_p99 | 0.70 [0.64, 0.76] | 0.17 [0.14, 0.21] | 0.62 [0.56, 0.67] | 0.02 [-0.00, 0.04] | 0.03 [-0.10, 0.16] | -0.17 [-0.31, -0.04] | 0.83 [0.75, 0.91] | -1.02 [-1.17, -0.88] |

Held-out combinations (effect of the first control at the other's low / high level, and of the second at the first's low / high):

**seed 45101**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.72 [2.67, 2.76] |
| vigourxheight | effect_vigour_at_height_hi | 2.64 [2.59, 2.69] |
| vigourxheight | effect_height_at_vigour_lo | 4.41 [4.36, 4.47] |
| vigourxheight | effect_height_at_vigour_hi | 4.44 [4.38, 4.49] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.41 [2.36, 2.47] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.55 [2.50, 2.60] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.34 [0.31, 0.38] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.75 [0.71, 0.80] |
| heightxpause | effect_height_at_pause_lo | 4.49 [4.44, 4.54] |
| heightxpause | effect_height_at_pause_hi | 3.94 [3.89, 4.01] |
| heightxpause | effect_pause_at_height_lo | 0.04 [-0.00, 0.07] |
| heightxpause | effect_pause_at_height_hi | -0.00 [-0.04, 0.03] |
| sharpxpause | effect_sharp_at_pause_lo | 0.63 [0.58, 0.68] |
| sharpxpause | effect_sharp_at_pause_hi | 0.34 [0.28, 0.40] |
| sharpxpause | effect_pause_at_sharp_lo | 0.07 [0.02, 0.13] |
| sharpxpause | effect_pause_at_sharp_hi | 0.04 [0.01, 0.06] |

**seed 45102**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.69 [2.64, 2.74] |
| vigourxheight | effect_vigour_at_height_hi | 2.64 [2.60, 2.68] |
| vigourxheight | effect_height_at_vigour_lo | 4.61 [4.56, 4.65] |
| vigourxheight | effect_height_at_vigour_hi | 4.39 [4.33, 4.44] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.41 [2.36, 2.46] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.65 [2.61, 2.69] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.54 [0.50, 0.58] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.71 [0.66, 0.75] |
| heightxpause | effect_height_at_pause_lo | 4.50 [4.45, 4.55] |
| heightxpause | effect_height_at_pause_hi | 4.34 [4.27, 4.40] |
| heightxpause | effect_pause_at_height_lo | 0.06 [0.01, 0.10] |
| heightxpause | effect_pause_at_height_hi | -0.00 [-0.06, 0.04] |
| sharpxpause | effect_sharp_at_pause_lo | 0.69 [0.65, 0.74] |
| sharpxpause | effect_sharp_at_pause_hi | 0.28 [0.23, 0.33] |
| sharpxpause | effect_pause_at_sharp_lo | 0.08 [0.04, 0.14] |
| sharpxpause | effect_pause_at_sharp_hi | 0.03 [-0.01, 0.08] |

**seed 45103**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.75 [2.70, 2.79] |
| vigourxheight | effect_vigour_at_height_hi | 2.57 [2.53, 2.61] |
| vigourxheight | effect_height_at_vigour_lo | 4.48 [4.42, 4.53] |
| vigourxheight | effect_height_at_vigour_hi | 4.45 [4.41, 4.50] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.37 [2.32, 2.41] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.58 [2.54, 2.62] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.48 [0.44, 0.53] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.69 [0.65, 0.74] |
| heightxpause | effect_height_at_pause_lo | 4.51 [4.46, 4.56] |
| heightxpause | effect_height_at_pause_hi | 4.77 [4.72, 4.83] |
| heightxpause | effect_pause_at_height_lo | 0.02 [-0.01, 0.05] |
| heightxpause | effect_pause_at_height_hi | -0.02 [-0.04, 0.00] |
| sharpxpause | effect_sharp_at_pause_lo | 0.69 [0.64, 0.74] |
| sharpxpause | effect_sharp_at_pause_hi | 0.52 [0.47, 0.57] |
| sharpxpause | effect_pause_at_sharp_lo | 0.03 [-0.00, 0.07] |
| sharpxpause | effect_pause_at_sharp_hi | 0.01 [-0.02, 0.05] |

### 2.3 Control substitution (std abs error between request and realised output, lower = closer; Pearson of the realised output with the request)

**seed 45101**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.41 [0.39, 0.44] | 0.81 [0.77, 0.85] | 0.66 [0.64, 0.69] | 0.67 [0.64, 0.70] |
| other | 0.82 [0.79, 0.86] | 0.43 [0.41, 0.45] | 0.80 [0.77, 0.84] | 0.79 [0.76, 0.83] |
| shuffled | 0.71 [0.69, 0.74] | 0.81 [0.77, 0.85] | 0.54 [0.52, 0.57] | 0.68 [0.65, 0.70] |
| constant | 0.49 [0.47, 0.51] | 0.61 [0.58, 0.65] | 0.43 [0.41, 0.45] | 0.37 [0.35, 0.39] |

Pearson of output with its own request: own: 0.56 [0.55, 0.58]; other: 0.55 [0.53, 0.56]; shuffled: 0.32 [0.30, 0.33]

**seed 45102**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.41 [0.39, 0.43] | 0.80 [0.76, 0.84] | 0.67 [0.64, 0.70] | 0.67 [0.65, 0.70] |
| other | 0.82 [0.79, 0.85] | 0.43 [0.41, 0.46] | 0.81 [0.77, 0.84] | 0.80 [0.77, 0.84] |
| shuffled | 0.71 [0.69, 0.74] | 0.80 [0.76, 0.84] | 0.55 [0.52, 0.57] | 0.68 [0.66, 0.71] |
| constant | 0.49 [0.47, 0.51] | 0.59 [0.56, 0.63] | 0.43 [0.41, 0.45] | 0.37 [0.35, 0.39] |

Pearson of output with its own request: own: 0.56 [0.55, 0.58]; other: 0.54 [0.52, 0.55]; shuffled: 0.31 [0.30, 0.32]

**seed 45103**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.41 [0.39, 0.44] | 0.80 [0.77, 0.84] | 0.67 [0.64, 0.69] | 0.67 [0.64, 0.70] |
| other | 0.82 [0.78, 0.85] | 0.43 [0.41, 0.45] | 0.80 [0.76, 0.83] | 0.80 [0.76, 0.84] |
| shuffled | 0.71 [0.68, 0.74] | 0.80 [0.77, 0.84] | 0.54 [0.52, 0.57] | 0.68 [0.65, 0.70] |
| constant | 0.49 [0.47, 0.51] | 0.60 [0.57, 0.64] | 0.43 [0.41, 0.45] | 0.36 [0.35, 0.38] |

Pearson of output with its own request: own: 0.55 [0.54, 0.57]; other: 0.55 [0.53, 0.56]; shuffled: 0.31 [0.30, 0.33]

### 2.4 Jitter and frozen share against re-joined human A1 (HJ), and the posture/gesture split (7.74 Q4, DIAG method)

A = A's posture + A's gestures; A_posture_human_gesture = A's posture knots with the human's gesture codes; human_posture_A_gesture = the reverse; HJ = the human window re-decoded by A1. p_gt3 = share of lamp speed power above 3 Hz.

**seed 45101**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.05 [0.98, 1.13] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.46 [1.40, 1.51] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0013, 0.0015] | 0.95 [0.92, 0.98] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.47 [1.41, 1.53] |
| human_posture_A_gesture | 0.0015 [0.0014, 0.0016] | 1.12 [1.05, 1.19] | 0.007 [0.000, 0.019] | 0.0033 [0.0000, 0.0096] | 1.44 [1.38, 1.50] |

**seed 45102**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.10 [1.03, 1.17] | 0.005 [0.000, 0.014] | 0.0008 [0.0000, 0.0023] | 1.44 [1.39, 1.49] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0012, 0.0015] | 0.95 [0.91, 0.98] | 0.007 [0.000, 0.019] | 0.0013 [0.0000, 0.0034] | 1.47 [1.40, 1.52] |
| human_posture_A_gesture | 0.0015 [0.0014, 0.0016] | 1.16 [1.09, 1.23] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0089] | 1.43 [1.37, 1.49] |

**seed 45103**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.06 [1.00, 1.11] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.46 [1.40, 1.51] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0012, 0.0015] | 0.93 [0.90, 0.96] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.45 [1.39, 1.50] |
| human_posture_A_gesture | 0.0015 [0.0014, 0.0016] | 1.14 [1.09, 1.20] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0089] | 1.44 [1.37, 1.50] |

### 2.5 Coherence over 2 s (L = 4 tokens) and 4 s (L = 8)

Control cosine = mean cosine between the standardised (vigour, height, sharpness, pause) vectors of tokens k and k + L; family repeat = share of tokens whose gesture family (code 1 in 32 k-means families) equals that L tokens earlier.

**seed 45101**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.378 [0.346, 0.409] | 0.315 [0.278, 0.351] | 0.056 [0.049, 0.065] | 0.057 [0.049, 0.065] |
| A_motif_ablated | 0.361 [0.329, 0.393] | 0.300 [0.265, 0.336] | 0.046 [0.040, 0.052] | 0.044 [0.037, 0.051] |
| ratio A / human | 1.03 [0.99, 1.08] | 1.02 [0.95, 1.09] | 0.86 [0.72, 1.01] | 1.08 [0.90, 1.32] |
| ratio ablated / human | 0.98 [0.94, 1.04] | 0.97 [0.91, 1.04] | 0.70 [0.59, 0.84] | 0.84 [0.70, 1.00] |

**seed 45102**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.375 [0.344, 0.408] | 0.312 [0.279, 0.345] | 0.055 [0.047, 0.065] | 0.055 [0.047, 0.065] |
| A_motif_ablated | 0.357 [0.327, 0.388] | 0.290 [0.253, 0.326] | 0.056 [0.048, 0.066] | 0.045 [0.037, 0.055] |
| ratio A / human | 1.02 [0.98, 1.07] | 1.01 [0.95, 1.07] | 0.84 [0.70, 1.00] | 1.05 [0.86, 1.31] |
| ratio ablated / human | 0.97 [0.93, 1.02] | 0.94 [0.88, 0.99] | 0.86 [0.71, 1.04] | 0.86 [0.67, 1.11] |

**seed 45103**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.369 [0.341, 0.399] | 0.306 [0.270, 0.340] | 0.056 [0.049, 0.064] | 0.053 [0.046, 0.061] |
| A_motif_ablated | 0.354 [0.325, 0.384] | 0.293 [0.260, 0.326] | 0.054 [0.047, 0.062] | 0.050 [0.043, 0.057] |
| ratio A / human | 1.01 [0.96, 1.05] | 0.99 [0.94, 1.05] | 0.85 [0.71, 1.02] | 1.01 [0.83, 1.25] |
| ratio ablated / human | 0.96 [0.92, 1.01] | 0.94 [0.89, 1.01] | 0.82 [0.69, 0.97] | 0.95 [0.78, 1.18] |

## 3. S-B clip candidates

Manifest `grammar/look/manifest.json` (not served). Excerpts (song, token start, song time, V1/V2 sharpness match):

- E01 fd_099 window 4 token 20 t = 90.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.01903 vs 0.01878 (|diff| 0.00026, best of 64 pairs); the 8 V1 samples span 0.019-0.035 (mean 0.028), the 8 V2 samples 0.019-0.036 (mean 0.027); requested-control sharpness 0.0467983924318105; gesture code-1 tokens differing between a V1 and a V2 sample: 0.90
- E02 fd_102 window 6 token 12 t = 126.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.02193 vs 0.02197 (|diff| 0.00004, best of 64 pairs); the 8 V1 samples span 0.019-0.039 (mean 0.028), the 8 V2 samples 0.022-0.029 (mean 0.026); requested-control sharpness 0.0730395044083707; gesture code-1 tokens differing between a V1 and a V2 sample: 0.90
- E03 fd_093 window 1 token 20 t = 30.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.02022 vs 0.01989 (|diff| 0.00033, best of 64 pairs); the 8 V1 samples span 0.020-0.037 (mean 0.028), the 8 V2 samples 0.020-0.037 (mean 0.024); requested-control sharpness 0.03258666588226333; gesture code-1 tokens differing between a V1 and a V2 sample: 0.88
- E04 fd_130 window 6 token 20 t = 130.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.02192 vs 0.02183 (|diff| 0.00008, best of 64 pairs); the 8 V1 samples span 0.015-0.032 (mean 0.025), the 8 V2 samples 0.020-0.035 (mean 0.027); requested-control sharpness 0.02931791932496708; gesture code-1 tokens differing between a V1 and a V2 sample: 0.90
- E05 fd_136 window 0 token 20 t = 10.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.04110 vs 0.04092 (|diff| 0.00018, best of 64 pairs); the 8 V1 samples span 0.019-0.067 (mean 0.036), the 8 V2 samples 0.022-0.063 (mean 0.038); requested-control sharpness 0.055227622389793396; gesture code-1 tokens differing between a V1 and a V2 sample: 0.85
- E06 fd_144 window 1 token 8 t = 24.0 s; V1 vs V2 matched on realised sharpness of the realised q50 of each candidate (token mean over the excerpt): chosen pair realised sharpness 0.02802 vs 0.02802 (|diff| 0.00000, best of 64 pairs); the 8 V1 samples span 0.022-0.035 (mean 0.029), the 8 V2 samples 0.021-0.049 (mean 0.031); requested-control sharpness 0.03498737787595019; gesture code-1 tokens differing between a V1 and a V2 sample: 0.90

A |diff| that rounds to 0.000 at three decimals is the minimum over 64 pairs of continuous values (about 1e-3 expected), so it is small by construction; the realised-sharpness spread of the candidates (above) shows the match is on motion produced, not on requested controls.

## 5. Fix 1 (A_RULES addendum 2)

1. Pause intervention now runs with low 0 / high 1.0 (rows `pause` and `pause_high_p99` of 2.2; the train p99 of pause is 1.0, so the two rows are identical by construction). The realised pause probability moves by only about 0.05 sd of the human spread (seed 45101: 0.05 [0.02, 0.09]) for a full pause request, while a full pause request lowers base-rotation speed (-0.9 to -1.0 sd) and raises direction-change rate; pause is the control A follows least. Numbers per seed in 2.2.
2. S-B V1 vs V2: matched on the realised sharpness of the realised q50 (as in the first run: a |diff| printed as 0.000 at three decimals was the best of 64 pairs, about 1e-3 by chance; now printed to five decimals with the candidate spread, the requested-control sharpness and the share of differing gesture tokens). V1 and V2 samples are different token sequences (about 0.9 of code-1 tokens differ). The selection is unchanged: all 42 clip CSVs are byte-identical to the first run, so no clip was re-rendered; only `excerpts.json` gained fields.
3. Coherence ratios are the ratio of the means over songs with the song-bootstrap interval of that ratio (section 2.5).
4. Per-start / per-song values behind every check: `grammar/checks/seed<S>_values.npz` (window measures `*__wm` (n, 8: vigour, height, sharp, pause, dirz, acccom, dirchg, basespeed), scalars `*__ws` (dirchg, base speed, lamp p_gt3, frozen flag, frozen share), token measures `*__tm` (n, 40, 6), intervention differences `iv_*__diff` in human-spread units, substitution `sub_err__*` / `sub_pearson__*`, coherence `coh__*`, `groups`, `dsid`, `idx`, `human_raw_ctl`). The first-run JSONs are kept in `grammar/checks_v1/`.
