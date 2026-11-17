# Control refinements (WO45 step 2b; report only, nothing adopted)

Sample: 300 random kept windows per dataset (one per file, seed 45010), realised stage, tokens of 0.5 s; code `scripts/body/controls_refine.py`, numbers in `grammar/refine.json`. Motorica: aggregates only.

## 1. Vigour split into amplitude and speed

Amplitude = diagonal of the lamp's bounding box over the token (m); speed = lamp RMS speed `vl` (m/s); vigour = the combined control. Correlations over tokens (Pearson / Spearman).

| dataset | tokens | amp-speed | amp-vigour | speed-vigour | R^2 of vigour on log amp + log speed | amp median m | speed median m/s |
|---|---|---|---|---|---|---|---|
| finedance | 12000 | 0.96 / 0.96 | 0.70 / 0.86 | 0.76 / 0.91 | 0.883 | 0.162 | 0.444 |
| aioz | 12000 | 0.96 / 0.96 | 0.76 / 0.86 | 0.82 / 0.92 | 0.868 | 0.110 | 0.304 |
| phantom | 12000 | 0.97 / 0.97 | 0.67 / 0.87 | 0.72 / 0.92 | 0.872 | 0.148 | 0.410 |
| motorica | 11760 | 0.95 / 0.96 | 0.71 / 0.86 | 0.78 / 0.91 | 0.875 | 0.162 | 0.461 |

## 2. Sharpness cutoff (median over tokens; undefined share in brackets)

`target` = forward kinematics of the human-retargeted target rows (every second 100 Hz row), before guard, spinal layer, limiter and servo. `noise s` = realised lamp plus white Gaussian noise of s mm per axis (50 Hz samples).

### finedance

| source | 2 Hz | 3 Hz | 4 Hz | 6 Hz |
|---|---|---|---|---|
| real | 0.105 (0.01) | 0.024 (0.01) | 0.006 (0.01) | 0.001 (0.01) |
| target | 0.335 (0.00) | 0.120 (0.00) | 0.042 (0.00) | 0.005 (0.00) |
| noise0.01 | 0.107 (0.01) | 0.025 (0.01) | 0.007 (0.01) | 0.001 (0.01) |
| noise0.03 | 0.113 (0.00) | 0.029 (0.00) | 0.009 (0.00) | 0.002 (0.00) |
| noise0.1 | 0.134 (0.00) | 0.043 (0.00) | 0.020 (0.00) | 0.010 (0.00) |
| noise0.3 | 0.215 (0.00) | 0.116 (0.00) | 0.088 (0.00) | 0.071 (0.00) |
| noise1.0 | 0.573 (0.00) | 0.505 (0.00) | 0.478 (0.00) | 0.425 (0.00) |

### aioz

| source | 2 Hz | 3 Hz | 4 Hz | 6 Hz |
|---|---|---|---|---|
| real | 0.113 (0.00) | 0.025 (0.00) | 0.007 (0.00) | 0.001 (0.00) |
| target | 0.327 (0.00) | 0.114 (0.00) | 0.042 (0.00) | 0.006 (0.00) |
| noise0.01 | 0.114 (0.00) | 0.026 (0.00) | 0.007 (0.00) | 0.001 (0.00) |
| noise0.03 | 0.118 (0.00) | 0.029 (0.00) | 0.010 (0.00) | 0.003 (0.00) |
| noise0.1 | 0.147 (0.00) | 0.052 (0.00) | 0.029 (0.00) | 0.017 (0.00) |
| noise0.3 | 0.276 (0.00) | 0.177 (0.00) | 0.147 (0.00) | 0.123 (0.00) |
| noise1.0 | 0.703 (0.00) | 0.650 (0.00) | 0.620 (0.00) | 0.558 (0.00) |

### phantom

| source | 2 Hz | 3 Hz | 4 Hz | 6 Hz |
|---|---|---|---|---|
| real | 0.102 (0.03) | 0.023 (0.03) | 0.006 (0.03) | 0.001 (0.03) |
| target | 0.412 (0.03) | 0.169 (0.03) | 0.064 (0.03) | 0.009 (0.03) |
| noise0.01 | 0.105 (0.02) | 0.025 (0.02) | 0.007 (0.02) | 0.001 (0.02) |
| noise0.03 | 0.114 (0.00) | 0.029 (0.00) | 0.010 (0.00) | 0.002 (0.00) |
| noise0.1 | 0.139 (0.00) | 0.045 (0.00) | 0.021 (0.00) | 0.011 (0.00) |
| noise0.3 | 0.226 (0.00) | 0.126 (0.00) | 0.097 (0.00) | 0.080 (0.00) |
| noise1.0 | 0.596 (0.00) | 0.536 (0.00) | 0.507 (0.00) | 0.452 (0.00) |

### motorica

| source | 2 Hz | 3 Hz | 4 Hz | 6 Hz |
|---|---|---|---|---|
| real | 0.134 (0.00) | 0.032 (0.00) | 0.009 (0.00) | 0.001 (0.00) |
| target | 0.422 (0.00) | 0.175 (0.00) | 0.068 (0.00) | 0.010 (0.00) |
| noise0.01 | 0.135 (0.00) | 0.033 (0.00) | 0.009 (0.00) | 0.001 (0.00) |
| noise0.03 | 0.137 (0.00) | 0.035 (0.00) | 0.011 (0.00) | 0.002 (0.00) |
| noise0.1 | 0.152 (0.00) | 0.046 (0.00) | 0.019 (0.00) | 0.008 (0.00) |
| noise0.3 | 0.217 (0.00) | 0.106 (0.00) | 0.073 (0.00) | 0.058 (0.00) |
| noise1.0 | 0.531 (0.00) | 0.453 (0.00) | 0.421 (0.00) | 0.371 (0.00) |

## 3. Pause as occupancy and duration

| dataset | scale | blocks | mean occupancy | median / p90 / p99 | share of blocks > 0.5 paused | Spearman(token pause prob, block occupancy) |
|---|---|---|---|---|---|---|
| finedance | 2 s | 3000 | 0.041 | 0.00 / 0.07 / 0.92 | 0.029 | 1.00 |
| finedance | 4 s | 1500 | 0.041 | 0.00 / 0.12 / 0.70 | 0.026 | 1.00 |
| finedance | 8 s | 600 | 0.047 | 0.00 / 0.18 / 0.53 | 0.015 | 1.00 |
| aioz | 2 s | 3000 | 0.024 | 0.00 / 0.00 / 0.51 | 0.011 | 1.00 |
| aioz | 4 s | 1500 | 0.024 | 0.00 / 0.08 / 0.43 | 0.005 | 1.00 |
| aioz | 8 s | 600 | 0.026 | 0.00 / 0.08 / 0.30 | 0.002 | 1.00 |
| phantom | 2 s | 3000 | 0.067 | 0.00 / 0.25 / 1.00 | 0.049 | 1.00 |
| phantom | 4 s | 1500 | 0.067 | 0.00 / 0.25 / 0.81 | 0.038 | 1.00 |
| phantom | 8 s | 600 | 0.070 | 0.00 / 0.26 / 0.83 | 0.022 | 1.00 |
| motorica | 2 s | 2940 | 0.031 | 0.00 / 0.00 / 0.68 | 0.020 | 1.00 |
| motorica | 4 s | 1470 | 0.031 | 0.00 / 0.09 / 0.56 | 0.014 | 1.00 |
| motorica | 8 s | 588 | 0.033 | 0.00 / 0.11 / 0.39 | 0.005 | 1.00 |

Pause-run durations (s, p10 / p50 / p90 / p99) and share of runs over 1 s: finedance: [0.28, 0.5, 1.72, 4.5] , 0.23255813953488372; aioz: [0.26, 0.36, 0.78, 2.3660000000000014] , 0.06529209621993128; phantom: [0.3, 0.54, 1.8539999999999999, 4.325399999999998] , 0.2725225225225225; motorica: [0.28, 0.46, 1.3860000000000001, 2.8921999999999946] , 0.16791044776119404

Nothing in A changes because of this report without a ruling (BRAIN_SPEC 7.76.3).
