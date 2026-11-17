# A2 report: A retrained to convergence with pause up-weighting (WO49)

Binding: `docs/A_RULES.md` with addenda 1-3. Numbers only, no verdict. Seeds 49101-49103; checks as WO45B (200 held-out starts, 2 samples each, nucleus 0.9, song bootstrap 95 %, same starts and check seeds). Per-start values: `grammar2/checks/seed<S>_values.npz`.

## 1. Training

All three seeds stopped early (patience 5 on the validation total) before the 100-epoch cap; `best.pt` = the epoch with the lowest validation total. Pause up-weighting as A_RULES addendum 3 (f = 1.471 / 1.268 / 1.000 / 1.935).

| seed | best epoch | val total | train eval-subset total | gap (val - train) | val no-controls total | aux train noisy | aux val | val total, last 5 epochs |
|---|---|---|---|---|---|---|---|---|
| 49101 | 73 | 18.315 | 15.561 | 2.754 | 21.717 | 0.881 | 1.075 | 18.317, 18.315, 18.316, 18.315, 18.315 |
| 49102 | 75 | 18.277 | 15.448 | 2.829 | 21.721 | 0.880 | 1.076 | 18.278, 18.278, 18.278, 18.278, 18.277 |
| 49103 | 69 | 18.295 | 15.462 | 2.833 | 21.595 | 0.882 | 1.075 | 18.296, 18.296, 18.296, 18.295, 18.295 |

Per head at the best epoch (validation / train eval-subset / gap), seed mean:

| head | validation | train subset | gap | validation without controls |
|---|---|---|---|---|
| code1 | 4.817 | 3.864 | 0.953 | 5.702 |
| code2 | 6.379 | 5.490 | 0.889 | 6.719 |
| vigour | 2.032 | 1.922 | 0.109 | 2.598 |
| posture1 | 1.659 | 1.259 | 0.401 | 2.278 |
| posture2 | 3.410 | 2.956 | 0.454 | 4.381 |

Per-epoch table (seed 45101; validation per head, no-controls total, aux), every 5th epoch:

| epoch | train noisy total | train subset total | val total | no controls | aux val | code1 | code2 | vigour | posture1 | posture2 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 25.279 | 23.416 | 23.734 | 24.912 | 1.080 | 6.63 | 6.90 | 2.30 | 3.13 | 4.77 |
| 5 | 21.550 | 20.513 | 21.272 | 23.257 | 1.073 | 5.87 | 6.77 | 2.14 | 2.23 | 4.27 |
| 10 | 20.298 | 19.048 | 20.239 | 22.507 | 1.073 | 5.48 | 6.66 | 2.11 | 2.00 | 3.99 |
| 15 | 19.468 | 18.037 | 19.553 | 22.107 | 1.071 | 5.22 | 6.56 | 2.09 | 1.88 | 3.80 |
| 20 | 18.937 | 17.402 | 19.138 | 21.942 | 1.073 | 5.07 | 6.49 | 2.07 | 1.81 | 3.68 |
| 25 | 18.584 | 16.933 | 18.859 | 21.838 | 1.074 | 4.98 | 6.45 | 2.06 | 1.77 | 3.60 |
| 30 | 18.330 | 16.621 | 18.691 | 21.787 | 1.075 | 4.92 | 6.42 | 2.06 | 1.74 | 3.55 |
| 35 | 18.149 | 16.374 | 18.572 | 21.752 | 1.075 | 4.89 | 6.41 | 2.05 | 1.72 | 3.51 |
| 40 | 18.000 | 16.189 | 18.507 | 21.730 | 1.075 | 4.87 | 6.40 | 2.04 | 1.71 | 3.49 |
| 45 | 17.885 | 16.033 | 18.454 | 21.701 | 1.075 | 4.86 | 6.40 | 2.04 | 1.69 | 3.46 |
| 50 | 17.789 | 15.912 | 18.425 | 21.706 | 1.073 | 4.85 | 6.39 | 2.04 | 1.69 | 3.45 |
| 55 | 17.565 | 15.738 | 18.361 | 21.723 | 1.075 | 4.83 | 6.39 | 2.04 | 1.67 | 3.43 |
| 60 | 17.517 | 15.674 | 18.353 | 21.713 | 1.074 | 4.83 | 6.39 | 2.03 | 1.67 | 3.43 |
| 65 | 17.410 | 15.604 | 18.331 | 21.705 | 1.075 | 4.82 | 6.39 | 2.03 | 1.67 | 3.42 |
| 70 | 17.329 | 15.568 | 18.316 | 21.715 | 1.075 | 4.82 | 6.39 | 2.03 | 1.66 | 3.42 |
| 75 | 17.304 | 15.558 | 18.315 | 21.716 | 1.075 | 4.82 | 6.39 | 2.03 | 1.66 | 3.42 |

The controls help: validation total without controls is higher by 3.40, 3.44, 3.30 nats (seeds, last epoch). Full per-epoch logs: `grammar2/runs/seed*/log.json`.

## 2. A checks (200 held-out starts, 2 samples each, song bootstrap 95 % intervals, seeds shown separately)

### 2.1 Residual-code utilisation

| seed | stage-2 codes used | perplexity | H(c2) | H(c2 given c1) | mutual information | model entropy of the code-2 head | decoded stage-2 effect (RMS ratio, median [quartiles]) |
|---|---|---|---|---|---|---|---|
| 49101 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 5.91 | 0.167 [0.1354918805304948, 0.21874820915564605] |
| 49102 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 5.89 | 0.167 [0.1354918805304948, 0.21874820915564605] |
| 49103 | 1.000 | 1012 | 6.92 | 5.82 | 1.10 | 5.92 | 0.167 [0.1354918805304948, 0.21874820915564605] |

### 2.2 Intervention matrix (effect = mean over starts of output(high) - output(low), in sd of the human starts' own window means; expected sign positive; accent = back-loaded minus front-loaded centre of mass)

**seed 49101**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.60 [2.56, 2.64] | 0.03 [-0.00, 0.06] | 0.61 [0.56, 0.66] | -0.40 [-0.46, -0.35] | -0.03 [-0.15, 0.09] | -0.67 [-0.81, -0.53] | 1.37 [1.28, 1.48] | 1.48 [1.34, 1.63] |
| height | 0.03 [0.00, 0.06] | 4.40 [4.36, 4.44] | -0.12 [-0.17, -0.07] | -0.01 [-0.04, 0.03] | 0.10 [-0.02, 0.22] | 0.11 [-0.01, 0.21] | -0.17 [-0.25, -0.09] | 0.06 [-0.05, 0.18] |
| accent | 0.01 [-0.01, 0.04] | 0.08 [0.05, 0.11] | 0.02 [-0.02, 0.06] | -0.05 [-0.08, -0.01] | -0.07 [-0.19, 0.06] | 0.07 [-0.04, 0.18] | 0.09 [0.03, 0.16] | -0.01 [-0.09, 0.08] |
| sharp | 0.11 [0.08, 0.14] | -0.03 [-0.06, 0.00] | 0.66 [0.62, 0.71] | 0.05 [0.01, 0.10] | 0.00 [-0.10, 0.10] | -0.27 [-0.38, -0.15] | 0.51 [0.44, 0.59] | -0.28 [-0.38, -0.18] |
| direction | -0.04 [-0.06, -0.01] | 0.14 [0.10, 0.17] | 0.03 [-0.02, 0.08] | 0.07 [0.03, 0.11] | 0.29 [0.13, 0.45] | -0.17 [-0.30, -0.05] | 0.11 [0.05, 0.18] | -0.22 [-0.29, -0.15] |
| pause | 0.14 [0.10, 0.18] | -0.20 [-0.23, -0.17] | 0.43 [0.37, 0.49] | 0.12 [0.09, 0.17] | 0.04 [-0.11, 0.19] | -0.18 [-0.29, -0.07] | 0.27 [0.18, 0.35] | -0.83 [-0.97, -0.70] |
| pause_high_p99 | 0.14 [0.10, 0.18] | -0.20 [-0.23, -0.17] | 0.43 [0.37, 0.49] | 0.12 [0.09, 0.17] | 0.04 [-0.11, 0.19] | -0.18 [-0.29, -0.07] | 0.27 [0.18, 0.35] | -0.83 [-0.97, -0.70] |

**seed 49102**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.61 [2.55, 2.66] | 0.06 [0.02, 0.10] | 0.60 [0.56, 0.65] | -0.42 [-0.48, -0.36] | -0.02 [-0.15, 0.10] | -0.56 [-0.69, -0.43] | 1.35 [1.26, 1.45] | 1.47 [1.32, 1.61] |
| height | 0.05 [0.01, 0.09] | 4.52 [4.48, 4.57] | -0.17 [-0.23, -0.12] | -0.03 [-0.07, 0.01] | 0.12 [0.01, 0.24] | 0.08 [-0.05, 0.21] | -0.15 [-0.23, -0.06] | 0.22 [0.08, 0.36] |
| accent | 0.04 [0.01, 0.06] | 0.05 [0.03, 0.08] | 0.09 [0.06, 0.13] | -0.05 [-0.08, -0.02] | 0.08 [-0.03, 0.18] | -0.03 [-0.15, 0.08] | 0.18 [0.12, 0.24] | -0.05 [-0.14, 0.03] |
| sharp | 0.14 [0.11, 0.17] | -0.02 [-0.05, 0.00] | 0.70 [0.65, 0.75] | -0.01 [-0.05, 0.02] | 0.02 [-0.12, 0.16] | -0.29 [-0.39, -0.18] | 0.56 [0.49, 0.63] | -0.30 [-0.40, -0.20] |
| direction | -0.03 [-0.06, -0.00] | 0.14 [0.11, 0.18] | -0.01 [-0.07, 0.05] | 0.03 [-0.01, 0.08] | 0.26 [0.11, 0.41] | -0.09 [-0.22, 0.05] | 0.16 [0.09, 0.23] | -0.18 [-0.25, -0.12] |
| pause | 0.26 [0.22, 0.31] | -0.06 [-0.10, -0.03] | 0.53 [0.48, 0.57] | 0.08 [0.05, 0.11] | 0.15 [-0.00, 0.29] | -0.06 [-0.18, 0.05] | 0.49 [0.42, 0.57] | -0.75 [-0.90, -0.62] |
| pause_high_p99 | 0.26 [0.22, 0.31] | -0.06 [-0.10, -0.03] | 0.53 [0.48, 0.57] | 0.08 [0.05, 0.11] | 0.15 [-0.00, 0.29] | -0.06 [-0.18, 0.05] | 0.49 [0.42, 0.57] | -0.75 [-0.90, -0.62] |

**seed 49103**

| varied control | vigour | height | sharp | pause | dirz | acccom | dirchg | basespeed |
|---|---|---|---|---|---|---|---|---|
| vigour | 2.57 [2.53, 2.62] | 0.07 [0.04, 0.10] | 0.63 [0.58, 0.68] | -0.39 [-0.45, -0.33] | -0.09 [-0.24, 0.04] | -0.58 [-0.70, -0.46] | 1.35 [1.26, 1.45] | 1.42 [1.28, 1.58] |
| height | 0.02 [-0.01, 0.05] | 4.50 [4.46, 4.55] | -0.10 [-0.14, -0.05] | -0.01 [-0.03, 0.02] | 0.07 [-0.03, 0.18] | 0.01 [-0.11, 0.13] | -0.17 [-0.25, -0.09] | 0.12 [-0.01, 0.25] |
| accent | 0.05 [0.03, 0.08] | 0.01 [-0.01, 0.04] | 0.03 [-0.01, 0.07] | -0.06 [-0.09, -0.03] | 0.03 [-0.09, 0.15] | 0.14 [0.01, 0.28] | 0.19 [0.12, 0.27] | 0.05 [-0.04, 0.14] |
| sharp | 0.13 [0.09, 0.16] | -0.01 [-0.04, 0.01] | 0.65 [0.61, 0.70] | 0.01 [-0.02, 0.04] | 0.05 [-0.06, 0.17] | -0.25 [-0.36, -0.13] | 0.61 [0.53, 0.68] | -0.15 [-0.25, -0.04] |
| direction | -0.05 [-0.08, -0.02] | 0.11 [0.07, 0.15] | 0.05 [0.01, 0.10] | 0.05 [0.00, 0.10] | 0.34 [0.20, 0.47] | -0.05 [-0.19, 0.10] | 0.10 [0.03, 0.18] | -0.12 [-0.19, -0.07] |
| pause | 0.47 [0.43, 0.51] | -0.02 [-0.04, 0.01] | 0.57 [0.51, 0.63] | 0.09 [0.06, 0.13] | -0.14 [-0.27, -0.01] | -0.38 [-0.51, -0.25] | 0.38 [0.31, 0.46] | -0.54 [-0.67, -0.41] |
| pause_high_p99 | 0.47 [0.43, 0.51] | -0.02 [-0.04, 0.01] | 0.57 [0.51, 0.63] | 0.09 [0.06, 0.13] | -0.14 [-0.27, -0.01] | -0.38 [-0.51, -0.25] | 0.38 [0.31, 0.46] | -0.54 [-0.67, -0.41] |

Held-out combinations (effect of the first control at the other's low / high level, and of the second at the first's low / high):

**seed 49101**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.77 [2.74, 2.81] |
| vigourxheight | effect_vigour_at_height_hi | 2.74 [2.69, 2.78] |
| vigourxheight | effect_height_at_vigour_lo | 4.35 [4.31, 4.39] |
| vigourxheight | effect_height_at_vigour_hi | 4.25 [4.21, 4.30] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.50 [2.45, 2.55] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.65 [2.60, 2.68] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.41 [0.36, 0.45] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.72 [0.68, 0.76] |
| heightxpause | effect_height_at_pause_lo | 4.39 [4.35, 4.43] |
| heightxpause | effect_height_at_pause_hi | 4.04 [3.98, 4.10] |
| heightxpause | effect_pause_at_height_lo | 0.12 [0.06, 0.20] |
| heightxpause | effect_pause_at_height_hi | 0.06 [0.01, 0.10] |
| sharpxpause | effect_sharp_at_pause_lo | 0.66 [0.62, 0.71] |
| sharpxpause | effect_sharp_at_pause_hi | 0.51 [0.45, 0.57] |
| sharpxpause | effect_pause_at_sharp_lo | 0.17 [0.11, 0.24] |
| sharpxpause | effect_pause_at_sharp_hi | 0.13 [0.09, 0.17] |

**seed 49102**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.80 [2.75, 2.85] |
| vigourxheight | effect_vigour_at_height_hi | 2.71 [2.66, 2.76] |
| vigourxheight | effect_height_at_vigour_lo | 4.42 [4.38, 4.47] |
| vigourxheight | effect_height_at_vigour_hi | 4.39 [4.35, 4.44] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.47 [2.42, 2.52] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.71 [2.67, 2.75] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.45 [0.41, 0.50] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.73 [0.69, 0.78] |
| heightxpause | effect_height_at_pause_lo | 4.50 [4.46, 4.55] |
| heightxpause | effect_height_at_pause_hi | 3.73 [3.68, 3.78] |
| heightxpause | effect_pause_at_height_lo | 0.08 [0.04, 0.13] |
| heightxpause | effect_pause_at_height_hi | 0.08 [0.05, 0.13] |
| sharpxpause | effect_sharp_at_pause_lo | 0.68 [0.63, 0.73] |
| sharpxpause | effect_sharp_at_pause_hi | 0.58 [0.52, 0.64] |
| sharpxpause | effect_pause_at_sharp_lo | 0.10 [0.06, 0.14] |
| sharpxpause | effect_pause_at_sharp_hi | 0.07 [0.03, 0.11] |

**seed 49103**

| pair | effect | value |
|---|---|---|
| vigourxheight | effect_vigour_at_height_lo | 2.76 [2.72, 2.81] |
| vigourxheight | effect_vigour_at_height_hi | 2.69 [2.65, 2.74] |
| vigourxheight | effect_height_at_vigour_lo | 4.44 [4.40, 4.47] |
| vigourxheight | effect_height_at_vigour_hi | 4.44 [4.39, 4.48] |
| vigourxsharp | effect_vigour_at_sharp_lo | 2.46 [2.41, 2.51] |
| vigourxsharp | effect_vigour_at_sharp_hi | 2.64 [2.60, 2.68] |
| vigourxsharp | effect_sharp_at_vigour_lo | 0.46 [0.42, 0.50] |
| vigourxsharp | effect_sharp_at_vigour_hi | 0.72 [0.67, 0.76] |
| heightxpause | effect_height_at_pause_lo | 4.49 [4.44, 4.53] |
| heightxpause | effect_height_at_pause_hi | 4.56 [4.50, 4.62] |
| heightxpause | effect_pause_at_height_lo | 0.10 [0.06, 0.16] |
| heightxpause | effect_pause_at_height_hi | 0.04 [-0.01, 0.08] |
| sharpxpause | effect_sharp_at_pause_lo | 0.66 [0.61, 0.70] |
| sharpxpause | effect_sharp_at_pause_hi | 0.39 [0.33, 0.44] |
| sharpxpause | effect_pause_at_sharp_lo | 0.09 [0.05, 0.14] |
| sharpxpause | effect_pause_at_sharp_hi | 0.06 [0.01, 0.11] |

### 2.3 Control substitution (std abs error between request and realised output, lower = closer; Pearson of the realised output with the request)

**seed 49101**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.40 [0.38, 0.43] | 0.81 [0.77, 0.85] | 0.67 [0.64, 0.70] | 0.67 [0.65, 0.70] |
| other | 0.82 [0.79, 0.85] | 0.43 [0.41, 0.45] | 0.81 [0.78, 0.85] | 0.80 [0.77, 0.84] |
| shuffled | 0.72 [0.69, 0.75] | 0.81 [0.77, 0.85] | 0.54 [0.52, 0.57] | 0.68 [0.65, 0.71] |
| constant | 0.50 [0.48, 0.52] | 0.61 [0.57, 0.65] | 0.43 [0.42, 0.46] | 0.37 [0.35, 0.39] |

Pearson of output with its own request: own: 0.58 [0.56, 0.59]; other: 0.54 [0.53, 0.56]; shuffled: 0.32 [0.31, 0.33]

**seed 49102**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.40 [0.38, 0.42] | 0.80 [0.77, 0.85] | 0.68 [0.65, 0.71] | 0.68 [0.65, 0.71] |
| other | 0.82 [0.79, 0.86] | 0.42 [0.40, 0.45] | 0.81 [0.78, 0.84] | 0.81 [0.77, 0.85] |
| shuffled | 0.71 [0.69, 0.74] | 0.81 [0.77, 0.85] | 0.54 [0.52, 0.58] | 0.68 [0.66, 0.71] |
| constant | 0.50 [0.48, 0.52] | 0.61 [0.58, 0.65] | 0.44 [0.42, 0.47] | 0.38 [0.36, 0.40] |

Pearson of output with its own request: own: 0.59 [0.57, 0.60]; other: 0.55 [0.54, 0.57]; shuffled: 0.32 [0.31, 0.34]

**seed 49103**

| request \ output of | own | other | shuffled | constant |
|---|---|---|---|---|
| own | 0.40 [0.38, 0.43] | 0.80 [0.77, 0.85] | 0.67 [0.65, 0.70] | 0.68 [0.65, 0.70] |
| other | 0.82 [0.79, 0.85] | 0.42 [0.40, 0.44] | 0.81 [0.77, 0.84] | 0.80 [0.76, 0.84] |
| shuffled | 0.71 [0.69, 0.74] | 0.81 [0.77, 0.85] | 0.54 [0.52, 0.57] | 0.68 [0.66, 0.71] |
| constant | 0.50 [0.48, 0.52] | 0.61 [0.57, 0.65] | 0.44 [0.42, 0.46] | 0.37 [0.35, 0.39] |

Pearson of output with its own request: own: 0.58 [0.57, 0.59]; other: 0.55 [0.53, 0.56]; shuffled: 0.32 [0.30, 0.33]

### 2.4 Jitter and frozen share against re-joined human A1 (HJ), and the posture/gesture split (7.74 Q4, DIAG method)

A = A's posture + A's gestures; A_posture_human_gesture = A's posture knots with the human's gesture codes; human_posture_A_gesture = the reverse; HJ = the human window re-decoded by A1. p_gt3 = share of lamp speed power above 3 Hz.

**seed 49101**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.05 [0.99, 1.11] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.45 [1.39, 1.50] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0013, 0.0015] | 0.96 [0.93, 0.99] | 0.002 [0.000, 0.007] | 0.0004 [0.0000, 0.0013] | 1.47 [1.40, 1.53] |
| human_posture_A_gesture | 0.0015 [0.0014, 0.0016] | 1.11 [1.05, 1.18] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.42 [1.36, 1.49] |

**seed 49102**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.04 [0.98, 1.11] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.44 [1.38, 1.49] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0013, 0.0015] | 0.96 [0.92, 0.99] | 0.000 [0.000, 0.000] | 0.0000 [0.0000, 0.0000] | 1.45 [1.39, 1.51] |
| human_posture_A_gesture | 0.0014 [0.0013, 0.0015] | 1.09 [1.03, 1.16] | 0.007 [0.000, 0.019] | 0.0030 [0.0000, 0.0088] | 1.42 [1.36, 1.48] |

**seed 49103**

| condition | p_gt3 | ratio to HJ | frozen windows (share with a >3 s run) | frozen frame share | direction changes /s |
|---|---|---|---|---|---|
| A | 0.0014 [0.0013, 0.0015] | 1.06 [0.99, 1.12] | 0.002 [0.000, 0.007] | 0.0004 [0.0000, 0.0011] | 1.46 [1.40, 1.51] |
| HJ | 0.0015 [0.0014, 0.0016] | 1.00 [1.00, 1.00] | 0.005 [0.000, 0.014] | 0.0030 [0.0000, 0.0090] | 1.45 [1.38, 1.52] |
| A_posture_human_gesture | 0.0014 [0.0013, 0.0015] | 0.96 [0.93, 0.99] | 0.002 [0.000, 0.007] | 0.0004 [0.0000, 0.0011] | 1.46 [1.39, 1.52] |
| human_posture_A_gesture | 0.0015 [0.0014, 0.0016] | 1.11 [1.04, 1.18] | 0.005 [0.000, 0.014] | 0.0029 [0.0000, 0.0086] | 1.42 [1.36, 1.49] |

### 2.5 Coherence over 2 s (L = 4 tokens) and 4 s (L = 8)

Control cosine = mean cosine between the standardised (vigour, height, sharpness, pause) vectors of tokens k and k + L; family repeat = share of tokens whose gesture family (code 1 in 32 k-means families) equals that L tokens earlier.

**seed 49101**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.373 [0.342, 0.403] | 0.302 [0.267, 0.337] | 0.061 [0.054, 0.069] | 0.049 [0.042, 0.056] |
| A_motif_ablated | 0.363 [0.331, 0.394] | 0.303 [0.270, 0.337] | 0.057 [0.051, 0.065] | 0.049 [0.043, 0.056] |
| ratio A / human | 1.02 [0.97, 1.06] | 0.97 [0.93, 1.03] | 0.94 [0.81, 1.09] | 0.93 [0.78, 1.11] |
| ratio ablated / human | 0.99 [0.94, 1.04] | 0.98 [0.92, 1.04] | 0.88 [0.72, 1.05] | 0.94 [0.76, 1.18] |

**seed 49102**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.363 [0.333, 0.394] | 0.302 [0.266, 0.338] | 0.052 [0.044, 0.061] | 0.055 [0.048, 0.063] |
| A_motif_ablated | 0.361 [0.331, 0.390] | 0.295 [0.260, 0.330] | 0.056 [0.048, 0.066] | 0.047 [0.039, 0.055] |
| ratio A / human | 0.99 [0.95, 1.03] | 0.97 [0.92, 1.03] | 0.79 [0.66, 0.95] | 1.05 [0.86, 1.30] |
| ratio ablated / human | 0.98 [0.94, 1.03] | 0.95 [0.90, 1.01] | 0.86 [0.71, 1.03] | 0.89 [0.72, 1.12] |

**seed 49103**

| source | ctl cos L4 | ctl cos L8 | family same L4 | family same L8 |
|---|---|---|---|---|
| human | 0.367 [0.335, 0.400] | 0.310 [0.274, 0.346] | 0.065 [0.057, 0.075] | 0.053 [0.043, 0.063] |
| A | 0.372 [0.341, 0.403] | 0.313 [0.278, 0.346] | 0.057 [0.047, 0.067] | 0.055 [0.047, 0.065] |
| A_motif_ablated | 0.371 [0.341, 0.401] | 0.302 [0.270, 0.335] | 0.052 [0.046, 0.059] | 0.051 [0.044, 0.058] |
| ratio A / human | 1.01 [0.97, 1.06] | 1.01 [0.96, 1.07] | 0.87 [0.73, 1.02] | 1.05 [0.85, 1.33] |
| ratio ablated / human | 1.01 [0.97, 1.06] | 0.98 [0.92, 1.04] | 0.80 [0.67, 0.95] | 0.97 [0.81, 1.19] |

## 3. Side by side: A1 (WO45B fix 1, seeds 45101-3) vs A2 (this run, seeds 49101-3), mean over seeds (each seed's own song-bootstrap interval is in section 2)

A1 numbers are those of `grammar/checks/seed451*.json` after addendum 2 (pause 0 / 1.0). The first-run table of `A_REPORT.md` at commit 1250e2c used pause = p10 / p90 (both 0), so its pause effect was exactly 0.

- A1: epochs 40, 40, 40; best validation total 18.417, 18.469, 18.446
- A2: epochs 78, 80, 74; best validation total 18.315, 18.277, 18.295

### 3.1 Intervention diagonal (effect of varying a control on its own measure, sd units; expected positive)

| control | A1 | A2 |
|---|---|---|
| vigour | 2.541 | 2.594 |
| height | 4.508 | 4.476 |
| accent | 0.079 | 0.060 |
| sharp | 0.666 | 0.673 |
| direction | 0.296 | 0.297 |
| pause | 0.040 | 0.099 |
| pause (high = train p99) | 0.040 | 0.099 |

Largest absolute off-diagonal effect per varied control (cross-talk, report only):

| control | A1 (measure: effect) | A2 (measure: effect) |
|---|---|---|
| vigour | basespeed: 1.59 | basespeed: 1.46 |
| height | basespeed: 0.29 | dirchg: -0.17 |
| accent | dirchg: 0.17 | dirchg: 0.16 |
| sharp | dirchg: 0.55 | dirchg: 0.56 |
| direction | basespeed: -0.15 | basespeed: -0.17 |
| pause | basespeed: -0.66 | basespeed: -0.71 |

### 3.2 Substitution (std abs error of the request against the realised output of the same sequence; lower is closer)

| request / output | A1 | A2 |
|---|---|---|
| request own, output own | 0.410 | 0.400 |
| request other, output own | 0.819 | 0.821 |
| request shuffled, output own | 0.712 | 0.713 |
| request constant, output own | 0.491 | 0.497 |
| Pearson, output own vs request own | 0.560 | 0.581 |

### 3.3 Jitter, frozen share, split (A / HJ ratio of p_gt3; frozen windows share)

| condition | ratio A1 | ratio A2 | frozen windows A1 | frozen windows A2 |
|---|---|---|---|---|
| A | 1.068 | 1.049 | 0.002 | 0.001 |
| HJ | 1.000 | 1.000 | 0.005 | 0.005 |
| A_posture_human_gesture | 0.942 | 0.959 | 0.002 | 0.002 |
| human_posture_A_gesture | 1.141 | 1.103 | 0.006 | 0.006 |

### 3.4 Coherence ratio A / human (ratio of means over songs)

| measure | A1 | A2 |
|---|---|---|
| ctl_cos_L4 | 1.020 | 1.006 |
| ctl_cos_L8 | 1.004 | 0.986 |
| family_same_L4 | 0.850 | 0.866 |
| family_same_L8 | 1.050 | 1.008 |

## 4. S-B clip candidates (not served)

Manifest `grammar2/look/manifest.json`; room left for the motor-clock pairs of 7.78 Q7. Excerpts:

- E01 fd_099 window 4 token 20 t = 90.0 s; V1/V2 realised sharpness 0.0241 vs 0.0240 (|diff| 0.0001); requested 0.0467983924318105
- E02 fd_102 window 6 token 12 t = 126.0 s; V1/V2 realised sharpness 0.0250 vs 0.0252 (|diff| 0.0001); requested 0.0730395044083707
- E03 fd_093 window 1 token 20 t = 30.0 s; V1/V2 realised sharpness 0.0216 vs 0.0216 (|diff| 0.0000); requested 0.03258666588226333
- E04 fd_130 window 6 token 20 t = 130.0 s; V1/V2 realised sharpness 0.0305 vs 0.0308 (|diff| 0.0003); requested 0.02931791932496708
- E05 fd_136 window 0 token 20 t = 10.0 s; V1/V2 realised sharpness 0.0304 vs 0.0302 (|diff| 0.0001); requested 0.055227622389793396
- E06 fd_144 window 1 token 8 t = 24.0 s; V1/V2 realised sharpness 0.0255 vs 0.0254 (|diff| 0.0001); requested 0.03498737787595019

Note: train pause p99 = 1.0 exactly (5.4 % of tokens have pause > 0 and those are mostly 1), so the p99 condition equals the 0 / 1.0 one in both A1 and A2. Pause effect (own measure) A1 0.040 -> A2 0.099 sd, still small against vigour 2.6 and height 4.5. Train sum of the five heads: A2 val 18.28-18.32 vs A1 18.42-18.47 (A1 stopped by the cap, A2 by early stopping at epochs 78/80/74, best 73/75/69).
