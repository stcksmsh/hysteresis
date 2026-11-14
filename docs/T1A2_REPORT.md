# T1a2 report (work order 39, BRAIN_SPEC 7.61; numbers only, no verdict)

Rules `T1A2_RULES.md`; Step 1 `T1A2_STEP1.md`. Both runs: AIOZ capped at 50 % of train weight (factor 0.732), Bailando loss, spline decoder, 80-epoch cap, 4 threads each. Gate rule applied as pass share >= 0.95 (default).

## Run A: K = 1024 single codebook

Epochs 26 (early_stop); best validation error (weighted MSE, scaled, capped weights) 0.3967; FineDance 0.4662, AIOZ 0.1814; code usage (validation) 1.000.

| rule | value | passes |
|---|---|---|
| code usage >= 0.60 | 1.000 | True |
| jitter ratios <= 1.1 (worst acc sign changes / worst power > 3 Hz) | 3.54 / 7.43 | False |
| joint ranges within 10 % (min / max ratio) | 0.943 / 1.000 | True |
| gates at 1.25 (reconstructed pass share; FineDance / AIOZ; control 1.000) | 0.979 (0.948 / 0.985) | True |
| variance explained >= 0.85 on every joint, FineDance validation (min) | 0.659 | False |

### Variance explained per joint

| split | dataset | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|---|
| validation | finedance | 0.765 | 0.659 | 0.705 | 0.733 | 0.742 |
| validation | aioz | 0.820 | 0.784 | 0.757 | 0.570 | 0.635 |
| test | finedance | 0.774 | 0.664 | 0.700 | 0.708 | 0.705 |
| test | aioz | 0.803 | 0.767 | 0.755 | 0.545 | 0.646 |

### Jitter and range ratios (recon / original, test windows; medians over windows)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range ratio |
|---|---|---|---|---|
| all | base_yaw | 3.538 | 7.427 | 1.000 |
| all | shoulder | 3.180 | 5.192 | 0.970 |
| all | elbow | 3.124 | 5.609 | 0.966 |
| all | wrist_bend | 2.648 | 2.222 | 0.943 |
| all | wrist_roll | 2.617 | 1.987 | 0.968 |
| finedance | base_yaw | 4.164 | 14.265 | 1.000 |
| finedance | shoulder | 3.679 | 9.378 | 0.968 |
| finedance | elbow | 3.513 | 6.713 | 0.959 |
| finedance | wrist_bend | 3.273 | 3.429 | 0.945 |
| finedance | wrist_roll | 3.167 | 2.684 | 0.966 |
| aioz | base_yaw | 3.366 | 5.667 | 1.000 |
| aioz | shoulder | 2.948 | 3.598 | 0.973 |
| aioz | elbow | 2.978 | 5.305 | 0.967 |
| aioz | wrist_bend | 2.522 | 1.841 | 0.922 |
| aioz | wrist_roll | 2.491 | 1.726 | 0.970 |

## Run B: 2 x 1024 residual

Epochs 19 (early_stop); best validation error (weighted MSE, scaled, capped weights) 0.1816; FineDance 0.2122, AIOZ 0.0822; code usage (validation) 1.000, 1.000 (stage 1, stage 2).

| rule | value | passes |
|---|---|---|
| code usage >= 0.60 | 1.000 | True |
| jitter ratios <= 1.1 (worst acc sign changes / worst power > 3 Hz) | 3.50 / 7.98 | False |
| joint ranges within 10 % (min / max ratio) | 0.975 / 1.000 | True |
| gates at 1.25 (reconstructed pass share; FineDance / AIOZ; control 1.000) | 0.983 (0.948 / 0.990) | True |
| variance explained >= 0.85 on every joint, FineDance validation (min) | 0.855 | True |

### Variance explained per joint

| split | dataset | base_yaw | shoulder | elbow | wrist_bend | wrist_roll |
|---|---|---|---|---|---|---|
| validation | finedance | 0.889 | 0.855 | 0.873 | 0.877 | 0.878 |
| validation | aioz | 0.917 | 0.910 | 0.895 | 0.785 | 0.839 |
| test | finedance | 0.892 | 0.847 | 0.864 | 0.864 | 0.859 |
| test | aioz | 0.907 | 0.900 | 0.891 | 0.772 | 0.837 |

### Jitter and range ratios (recon / original, test windows; medians over windows)

| source | joint | acc sign changes ratio | power > 3 Hz ratio | range ratio |
|---|---|---|---|---|
| all | base_yaw | 3.500 | 7.980 | 1.000 |
| all | shoulder | 2.955 | 4.469 | 0.985 |
| all | elbow | 3.045 | 5.173 | 0.984 |
| all | wrist_bend | 2.380 | 2.017 | 0.975 |
| all | wrist_roll | 2.449 | 1.926 | 0.984 |
| finedance | base_yaw | 4.179 | 15.222 | 1.000 |
| finedance | shoulder | 3.474 | 7.768 | 0.986 |
| finedance | elbow | 3.481 | 6.054 | 0.982 |
| finedance | wrist_bend | 3.000 | 3.208 | 0.979 |
| finedance | wrist_roll | 3.000 | 2.623 | 0.979 |
| aioz | base_yaw | 3.305 | 6.119 | 1.001 |
| aioz | shoulder | 2.729 | 3.109 | 0.986 |
| aioz | elbow | 2.903 | 4.910 | 0.984 |
| aioz | wrist_bend | 2.257 | 1.678 | 0.968 |
| aioz | wrist_roll | 2.321 | 1.671 | 0.985 |

## Result by rule

| run | usage | jitter | ranges | gates | variance >= 0.85 | all |
|---|---|---|---|---|---|---|
| A | True | False | True | True | False | False |
| B | True | False | True | True | True | False |

S1 candidate (smaller passing model, A before B): **none: neither run passes; report and hold**.

## Realised-stage jitter (appended; report only)

Stage: after guard, spinal layer (H1), limiter, servo and v2p body (the gate's own simulation, `q50` at 50 Hz), test windows (2,455), medians over windows; the rebuilds go through the same chain as the original windows (Run A / Run B reconstructions).

| source | joint | metric | original | Run A | Run B | A / original | B / original |
|---|---|---|---|---|---|---|---|
| all | base_yaw | acc sign changes /s | 2.1978 | 1.7982 | 1.8981 | 0.82 | 0.86 |
| all | base_yaw | power > 3 Hz | 0.0002 | 0.0002 | 0.0002 | 1.29 | 1.29 |
| all | shoulder | acc sign changes /s | 2.7972 | 2.5475 | 2.5974 | 0.91 | 0.93 |
| all | shoulder | power > 3 Hz | 0.0010 | 0.0007 | 0.0007 | 0.66 | 0.68 |
| all | elbow | acc sign changes /s | 2.7972 | 2.5475 | 2.5974 | 0.91 | 0.93 |
| all | elbow | power > 3 Hz | 0.0010 | 0.0008 | 0.0008 | 0.81 | 0.80 |
| all | wrist_bend | acc sign changes /s | 3.7463 | 3.1469 | 3.2967 | 0.84 | 0.88 |
| all | wrist_bend | power > 3 Hz | 0.0064 | 0.0036 | 0.0041 | 0.56 | 0.64 |
| all | wrist_roll | acc sign changes /s | 3.6464 | 3.0969 | 3.1968 | 0.85 | 0.88 |
| all | wrist_roll | power > 3 Hz | 0.0080 | 0.0037 | 0.0040 | 0.46 | 0.50 |
| finedance | base_yaw | acc sign changes /s | 2.0979 | 1.8482 | 1.9481 | 0.88 | 0.93 |
| finedance | base_yaw | power > 3 Hz | 0.0001 | 0.0002 | 0.0002 | 1.58 | 1.54 |
| finedance | shoulder | acc sign changes /s | 2.4476 | 2.4476 | 2.4476 | 1.00 | 1.00 |
| finedance | shoulder | power > 3 Hz | 0.0007 | 0.0006 | 0.0006 | 0.80 | 0.81 |
| finedance | elbow | acc sign changes /s | 2.5475 | 2.5475 | 2.4975 | 1.00 | 0.98 |
| finedance | elbow | power > 3 Hz | 0.0008 | 0.0007 | 0.0007 | 0.97 | 0.86 |
| finedance | wrist_bend | acc sign changes /s | 3.2967 | 3.0470 | 3.1469 | 0.92 | 0.95 |
| finedance | wrist_bend | power > 3 Hz | 0.0047 | 0.0033 | 0.0035 | 0.70 | 0.74 |
| finedance | wrist_roll | acc sign changes /s | 3.3467 | 3.0969 | 3.1469 | 0.93 | 0.94 |
| finedance | wrist_roll | power > 3 Hz | 0.0074 | 0.0042 | 0.0051 | 0.56 | 0.68 |
| aioz | base_yaw | acc sign changes /s | 2.1978 | 1.7982 | 1.8981 | 0.82 | 0.86 |
| aioz | base_yaw | power > 3 Hz | 0.0002 | 0.0002 | 0.0002 | 1.25 | 1.26 |
| aioz | shoulder | acc sign changes /s | 2.8472 | 2.5475 | 2.5974 | 0.89 | 0.91 |
| aioz | shoulder | power > 3 Hz | 0.0012 | 0.0007 | 0.0007 | 0.59 | 0.62 |
| aioz | elbow | acc sign changes /s | 2.7972 | 2.5974 | 2.5974 | 0.93 | 0.93 |
| aioz | elbow | power > 3 Hz | 0.0011 | 0.0009 | 0.0009 | 0.77 | 0.78 |
| aioz | wrist_bend | acc sign changes /s | 3.8961 | 3.1469 | 3.3467 | 0.81 | 0.86 |
| aioz | wrist_bend | power > 3 Hz | 0.0077 | 0.0037 | 0.0042 | 0.47 | 0.55 |
| aioz | wrist_roll | acc sign changes /s | 3.6963 | 3.0969 | 3.1968 | 0.84 | 0.86 |
| aioz | wrist_roll | power > 3 Hz | 0.0081 | 0.0036 | 0.0039 | 0.44 | 0.47 |

Gate share (realised simulation, same windows): original: all 1.000, FineDance 1.000, AIOZ 1.000; runA: all 0.979, FineDance 0.948, AIOZ 0.985; runB: all 0.983, FineDance 0.948, AIOZ 0.990.
