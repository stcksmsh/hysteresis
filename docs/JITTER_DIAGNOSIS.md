# Jitter diagnosis on the 20 retarget look-test clips (work order 33, BRAIN_SPEC 7.53; report only)

No verdict, nothing adopted, no video rendered. Code: `scripts/body/jitter_diag.py` (+ `test_jitter_diag.py`). Data: `/secondary/hyst-data/body/retarget_look/jitter/numbers.json`, plots there (not in git).

## Method

- Clips: C01-C10 x V1, V2, the windows of `manifest.json`, rebuilt from FineDance exactly as `retarget_run.py` builds them (v2p body, guard, fixed limiter of rules (k)). Everything is measured over the shown 20 s.
- Stages: **1** the retargeted command at the dataset's 30 fps; **2** after the 30 -> 100 Hz resampling (`retarget.to_100hz`, a cubic spline) and the guard; **3** the limiter output (100 Hz); **4** the realised joint angles (servo/body, 50 Hz). Variant H1 has a stage **2s**, the round-1 spinal layer output.
- Measures per stage and joint: acceleration sign changes per second (second difference at the stage's rate; accelerations below 1 deg/s^2 count as zero); jerk RMS in deg/s^3 (difference of the acceleration); share of joint-speed power above 3 Hz and above 6 Hz (mean removed, Welch, Hann window, 5 s segments = 0.2 Hz bins).
- Each is computed at the stage's own rate ("own") and, for stages 2-4, at the 30 fps instants of the dataset frames ("at 30 fps": the stage's rows linearly interpolated to the instants k/30 s, so stage 1 compares like for like). Tables give the **median over the 20 clips**; per-clip numbers are in `numbers.json` and the appendix.
- Variants: **baseline** (as shown); **H1** the round-1 `motornet.spinal` (3 Hz, zeta 0.7, unchanged) applied to the 100 Hz command before the fixed limiter, stages 3-4 re-run; **H3 linear** linear interpolation instead of the cubic spline (control showing the size of the effect H3 describes; the shown clips already use the cubic spline); **H1 + H3 combined** = H1 with the cubic spline as used (the H1 tables); `H1_linear` (H1 with linear interpolation) is added as an extra control.
- 7.52 gate (speed and acceleration at 1.25, every other gate as run) pass/fail per variant run is reported, not used to select anything.

## Baseline reproduction (stage 4 vs `work/<id>.csv`)

Maximum absolute difference between the rebuilt stage-4 rows and the CSV of the shown clip, over the 20 clips: **0.0000 deg** (worst clip C10_V2; the CSV is written with fixed decimals).

## Gate verdicts (7.52, 1.25) per variant, 20 clips

| variant | passes | failing clips (failed parts) |
|---|---|---|
| baseline | 20 / 20 | - |
| H1 | 19 / 20 | C10_V2 (limits) |
| H3_linear | 19 / 20 | C03_V2 (limits) |
| H1_linear | 19 / 20 | C10_V2 (limits) |

Guard: baseline guard share median 0.0000, max 0.0051; the guard changed the command by at most 39.643 deg on any clip.

## Baseline (as shown)

### Own rate (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 1 retargeted command, 30 fps | base_yaw | 5.47 | 3592 | 0.018 | 0.001 |
| 1 retargeted command, 30 fps | shoulder | 7.28 | 14400 | 0.075 | 0.009 |
| 1 retargeted command, 30 fps | elbow | 7.78 | 28939 | 0.104 | 0.015 |
| 1 retargeted command, 30 fps | wrist_bend | 11.60 | 109252 | 0.199 | 0.077 |
| 1 retargeted command, 30 fps | wrist_roll | 12.50 | 138564 | 0.249 | 0.082 |
| 2 resampled to 100 Hz (+guard) | base_yaw | 7.05 | 5276 | 0.018 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 9.05 | 26284 | 0.072 | 0.010 |
| 2 resampled to 100 Hz (+guard) | elbow | 10.97 | 52799 | 0.105 | 0.016 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 14.64 | 204855 | 0.194 | 0.086 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 15.04 | 259697 | 0.266 | 0.094 |
| 3 limiter output | base_yaw | 5.70 | 5548 | 0.013 | 0.001 |
| 3 limiter output | shoulder | 4.15 | 6766 | 0.008 | 0.001 |
| 3 limiter output | elbow | 7.15 | 25297 | 0.015 | 0.003 |
| 3 limiter output | wrist_bend | 8.97 | 61049 | 0.061 | 0.010 |
| 3 limiter output | wrist_roll | 8.72 | 91386 | 0.087 | 0.015 |
| 4 realised (50 Hz) | base_yaw | 2.20 | 604 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.72 | 1218 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 3.32 | 3410 | 0.002 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 4.95 | 10764 | 0.011 | 0.001 |
| 4 realised (50 Hz) | wrist_roll | 5.44 | 17862 | 0.021 | 0.001 |

### Stages 2-4 at the 30 fps instants (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.43 | 3518 | 0.018 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 7.18 | 15025 | 0.074 | 0.008 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.95 | 28112 | 0.102 | 0.014 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.38 | 104843 | 0.196 | 0.073 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 12.15 | 133838 | 0.243 | 0.077 |
| 3 limiter output | base_yaw | 4.57 | 2668 | 0.012 | 0.001 |
| 3 limiter output | shoulder | 3.70 | 3377 | 0.008 | 0.001 |
| 3 limiter output | elbow | 5.58 | 11571 | 0.014 | 0.002 |
| 3 limiter output | wrist_bend | 6.97 | 26402 | 0.058 | 0.007 |
| 3 limiter output | wrist_roll | 7.30 | 41465 | 0.077 | 0.010 |
| 4 realised (50 Hz) | base_yaw | 2.15 | 608 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.48 | 1157 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 3.03 | 3236 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 4.70 | 9965 | 0.011 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 5.15 | 15644 | 0.019 | 0.001 |

## H1: spinal layer (3 Hz, zeta 0.7) before the limiter = H1 + H3 combined (cubic spline as used)

### Own rate (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 1 retargeted command, 30 fps | base_yaw | 5.47 | 3592 | 0.018 | 0.001 |
| 1 retargeted command, 30 fps | shoulder | 7.28 | 14400 | 0.075 | 0.009 |
| 1 retargeted command, 30 fps | elbow | 7.78 | 28939 | 0.104 | 0.015 |
| 1 retargeted command, 30 fps | wrist_bend | 11.60 | 109252 | 0.199 | 0.077 |
| 1 retargeted command, 30 fps | wrist_roll | 12.50 | 138564 | 0.249 | 0.082 |
| 2 resampled to 100 Hz (+guard) | base_yaw | 7.05 | 5276 | 0.018 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 9.05 | 26284 | 0.072 | 0.010 |
| 2 resampled to 100 Hz (+guard) | elbow | 10.97 | 52799 | 0.105 | 0.016 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 14.64 | 204855 | 0.194 | 0.086 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 15.04 | 259697 | 0.266 | 0.094 |
| 2s spinal layer output (H1) | base_yaw | 3.47 | 1887 | 0.005 | 0.000 |
| 2s spinal layer output (H1) | shoulder | 4.37 | 6524 | 0.021 | 0.000 |
| 2s spinal layer output (H1) | elbow | 4.60 | 11548 | 0.025 | 0.000 |
| 2s spinal layer output (H1) | wrist_bend | 5.77 | 29758 | 0.057 | 0.002 |
| 2s spinal layer output (H1) | wrist_roll | 6.92 | 38247 | 0.054 | 0.003 |
| 3 limiter output | base_yaw | 3.35 | 3666 | 0.004 | 0.000 |
| 3 limiter output | shoulder | 3.35 | 5702 | 0.006 | 0.001 |
| 3 limiter output | elbow | 4.15 | 16985 | 0.008 | 0.001 |
| 3 limiter output | wrist_bend | 5.25 | 37700 | 0.026 | 0.003 |
| 3 limiter output | wrist_roll | 5.95 | 51171 | 0.038 | 0.004 |
| 4 realised (50 Hz) | base_yaw | 1.90 | 517 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.42 | 1057 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 2.75 | 2923 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 3.65 | 8580 | 0.006 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 4.10 | 11203 | 0.011 | 0.000 |

### Stages 2-4 at the 30 fps instants (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.43 | 3518 | 0.018 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 7.18 | 15025 | 0.074 | 0.008 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.95 | 28112 | 0.102 | 0.014 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.38 | 104843 | 0.196 | 0.073 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 12.15 | 133838 | 0.243 | 0.077 |
| 2s spinal layer output (H1) | base_yaw | 3.42 | 1715 | 0.004 | 0.000 |
| 2s spinal layer output (H1) | shoulder | 3.95 | 5933 | 0.019 | 0.000 |
| 2s spinal layer output (H1) | elbow | 4.45 | 9786 | 0.024 | 0.000 |
| 2s spinal layer output (H1) | wrist_bend | 5.35 | 24212 | 0.061 | 0.002 |
| 2s spinal layer output (H1) | wrist_roll | 6.15 | 30600 | 0.051 | 0.002 |
| 3 limiter output | base_yaw | 3.23 | 1871 | 0.004 | 0.000 |
| 3 limiter output | shoulder | 3.15 | 2929 | 0.006 | 0.001 |
| 3 limiter output | elbow | 3.73 | 7875 | 0.008 | 0.001 |
| 3 limiter output | wrist_bend | 4.80 | 17844 | 0.026 | 0.002 |
| 3 limiter output | wrist_roll | 4.95 | 24280 | 0.035 | 0.003 |
| 4 realised (50 Hz) | base_yaw | 1.88 | 526 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.33 | 1075 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 2.73 | 2928 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 3.58 | 8073 | 0.006 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 3.90 | 10360 | 0.011 | 0.000 |

## H3: linear interpolation instead of the cubic spline (control)

### Own rate (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 1 retargeted command, 30 fps | base_yaw | 5.47 | 3592 | 0.018 | 0.001 |
| 1 retargeted command, 30 fps | shoulder | 7.28 | 14400 | 0.075 | 0.009 |
| 1 retargeted command, 30 fps | elbow | 7.78 | 28939 | 0.104 | 0.015 |
| 1 retargeted command, 30 fps | wrist_bend | 11.60 | 109252 | 0.199 | 0.077 |
| 1 retargeted command, 30 fps | wrist_roll | 12.50 | 138564 | 0.249 | 0.082 |
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.52 | 33671 | 0.017 | 0.002 |
| 2 resampled to 100 Hz (+guard) | shoulder | 7.30 | 112044 | 0.069 | 0.012 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.90 | 203473 | 0.095 | 0.018 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.62 | 521437 | 0.180 | 0.073 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 12.49 | 740097 | 0.239 | 0.082 |
| 3 limiter output | base_yaw | 5.42 | 11145 | 0.012 | 0.001 |
| 3 limiter output | shoulder | 4.15 | 7951 | 0.008 | 0.001 |
| 3 limiter output | elbow | 6.70 | 26788 | 0.014 | 0.003 |
| 3 limiter output | wrist_bend | 8.17 | 65361 | 0.058 | 0.009 |
| 3 limiter output | wrist_roll | 8.22 | 106848 | 0.083 | 0.014 |
| 4 realised (50 Hz) | base_yaw | 2.17 | 595 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.62 | 1192 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 3.07 | 3300 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 4.90 | 10578 | 0.010 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 5.44 | 17291 | 0.019 | 0.001 |

### Stages 2-4 at the 30 fps instants (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.15 | 3332 | 0.017 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 6.92 | 14298 | 0.070 | 0.007 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.38 | 26427 | 0.096 | 0.012 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.03 | 95015 | 0.184 | 0.064 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 11.85 | 122168 | 0.225 | 0.066 |
| 3 limiter output | base_yaw | 4.40 | 2561 | 0.012 | 0.001 |
| 3 limiter output | shoulder | 3.45 | 3319 | 0.007 | 0.001 |
| 3 limiter output | elbow | 5.40 | 11130 | 0.013 | 0.002 |
| 3 limiter output | wrist_bend | 6.78 | 25263 | 0.052 | 0.006 |
| 3 limiter output | wrist_roll | 6.88 | 38832 | 0.073 | 0.009 |
| 4 realised (50 Hz) | base_yaw | 2.00 | 600 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.50 | 1146 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 2.92 | 3185 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 4.62 | 9853 | 0.010 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 5.03 | 15226 | 0.017 | 0.001 |

## Extra control: H1 with linear interpolation

### Own rate (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 1 retargeted command, 30 fps | base_yaw | 5.47 | 3592 | 0.018 | 0.001 |
| 1 retargeted command, 30 fps | shoulder | 7.28 | 14400 | 0.075 | 0.009 |
| 1 retargeted command, 30 fps | elbow | 7.78 | 28939 | 0.104 | 0.015 |
| 1 retargeted command, 30 fps | wrist_bend | 11.60 | 109252 | 0.199 | 0.077 |
| 1 retargeted command, 30 fps | wrist_roll | 12.50 | 138564 | 0.249 | 0.082 |
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.52 | 33671 | 0.017 | 0.002 |
| 2 resampled to 100 Hz (+guard) | shoulder | 7.30 | 112044 | 0.069 | 0.012 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.90 | 203473 | 0.095 | 0.018 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.62 | 521437 | 0.180 | 0.073 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 12.49 | 740097 | 0.239 | 0.082 |
| 2s spinal layer output (H1) | base_yaw | 3.42 | 1835 | 0.004 | 0.000 |
| 2s spinal layer output (H1) | shoulder | 4.15 | 6212 | 0.019 | 0.000 |
| 2s spinal layer output (H1) | elbow | 4.50 | 11000 | 0.022 | 0.000 |
| 2s spinal layer output (H1) | wrist_bend | 5.42 | 26778 | 0.053 | 0.002 |
| 2s spinal layer output (H1) | wrist_roll | 6.35 | 34627 | 0.048 | 0.002 |
| 3 limiter output | base_yaw | 3.27 | 3713 | 0.004 | 0.000 |
| 3 limiter output | shoulder | 3.22 | 5706 | 0.006 | 0.001 |
| 3 limiter output | elbow | 3.95 | 16231 | 0.008 | 0.001 |
| 3 limiter output | wrist_bend | 4.90 | 35992 | 0.026 | 0.003 |
| 3 limiter output | wrist_roll | 5.57 | 47112 | 0.037 | 0.003 |
| 4 realised (50 Hz) | base_yaw | 1.87 | 510 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.37 | 1049 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 2.75 | 2907 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 3.62 | 8332 | 0.006 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 3.95 | 10948 | 0.011 | 0.000 |

### Stages 2-4 at the 30 fps instants (median over 20 clips)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| 2 resampled to 100 Hz (+guard) | base_yaw | 5.15 | 3332 | 0.017 | 0.001 |
| 2 resampled to 100 Hz (+guard) | shoulder | 6.92 | 14298 | 0.070 | 0.007 |
| 2 resampled to 100 Hz (+guard) | elbow | 7.38 | 26427 | 0.096 | 0.012 |
| 2 resampled to 100 Hz (+guard) | wrist_bend | 11.03 | 95015 | 0.184 | 0.064 |
| 2 resampled to 100 Hz (+guard) | wrist_roll | 11.85 | 122168 | 0.225 | 0.066 |
| 2s spinal layer output (H1) | base_yaw | 3.42 | 1664 | 0.004 | 0.000 |
| 2s spinal layer output (H1) | shoulder | 3.83 | 5669 | 0.018 | 0.000 |
| 2s spinal layer output (H1) | elbow | 4.35 | 9354 | 0.022 | 0.000 |
| 2s spinal layer output (H1) | wrist_bend | 5.10 | 22115 | 0.057 | 0.001 |
| 2s spinal layer output (H1) | wrist_roll | 5.85 | 28847 | 0.045 | 0.002 |
| 3 limiter output | base_yaw | 3.20 | 1820 | 0.004 | 0.000 |
| 3 limiter output | shoulder | 3.10 | 2881 | 0.006 | 0.001 |
| 3 limiter output | elbow | 3.73 | 7711 | 0.008 | 0.001 |
| 3 limiter output | wrist_bend | 4.60 | 17632 | 0.026 | 0.002 |
| 3 limiter output | wrist_roll | 4.80 | 23385 | 0.034 | 0.002 |
| 4 realised (50 Hz) | base_yaw | 1.83 | 519 | 0.000 | 0.000 |
| 4 realised (50 Hz) | shoulder | 2.30 | 1071 | 0.001 | 0.000 |
| 4 realised (50 Hz) | elbow | 2.70 | 2914 | 0.001 | 0.000 |
| 4 realised (50 Hz) | wrist_bend | 3.53 | 7873 | 0.006 | 0.000 |
| 4 realised (50 Hz) | wrist_roll | 3.85 | 10294 | 0.010 | 0.000 |

## H2: limiter output at the acceleration limit (baseline, median over 20 clips)

Share of frames where |limiter output acceleration| >= 0.98 x the limit (100 Hz frames, and the gate's 50 Hz measure) and sign flips per second of the 100 Hz limiter output acceleration.

| joint | share >= 0.98 limit, 100 Hz | share >= 0.98 limit, gate 50 Hz | acceleration sign flips /s |
|---|---|---|---|
| base_yaw | 0.033 | 0.021 | 5.70 |
| shoulder | 0.615 | 0.580 | 4.15 |
| elbow | 0.327 | 0.279 | 7.15 |
| wrist_bend | 0.394 | 0.307 | 8.97 |
| wrist_roll | 0.330 | 0.247 | 8.72 |

Same measures with H1 (median over 20 clips):

| joint | share >= 0.98 limit, 100 Hz | share >= 0.98 limit, gate 50 Hz | acceleration sign flips /s |
|---|---|---|---|
| base_yaw | 0.012 | 0.007 | 3.35 |
| shoulder | 0.597 | 0.567 | 3.35 |
| elbow | 0.207 | 0.175 | 4.15 |
| wrist_bend | 0.173 | 0.131 | 5.25 |
| wrist_roll | 0.120 | 0.091 | 5.95 |

## Control: round-1 S03 reference clips at stage 4 as they are

| clip | joint | acc sign changes /s | jerk RMS deg/s^3 | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|
| C01_R1S03 | base_yaw | 1.20 | 274 | 0.000 | 0.000 |
| C01_R1S03 | shoulder | 1.05 | 120 | 0.000 | 0.000 |
| C01_R1S03 | elbow | 1.25 | 263 | 0.000 | 0.000 |
| C01_R1S03 | wrist_bend | 0.90 | 208 | 0.000 | 0.000 |
| C01_R1S03 | wrist_roll | 1.50 | 816 | 0.000 | 0.000 |
| C09_R1S03 | base_yaw | 1.10 | 236 | 0.000 | 0.000 |
| C09_R1S03 | shoulder | 1.10 | 126 | 0.000 | 0.000 |
| C09_R1S03 | elbow | 0.90 | 202 | 0.000 | 0.000 |
| C09_R1S03 | wrist_bend | 0.80 | 164 | 0.000 | 0.000 |
| C09_R1S03 | wrist_roll | 1.05 | 708 | 0.000 | 0.000 |

## Appendix: per clip, baseline, shoulder and wrist bend (own rate)

| clip | stage | shoulder sign/s | shoulder jerk RMS | shoulder >3 Hz | wrist bend sign/s | wrist bend jerk RMS | wrist bend >3 Hz |
|---|---|---|---|---|---|---|---|
| C01_V1 | s1 | 5.70 | 1590 | 0.005 | 8.15 | 24151 | 0.038 |
| C01_V1 | s2 | 6.60 | 2499 | 0.004 | 11.09 | 45706 | 0.065 |
| C01_V1 | s3 | 4.70 | 2323 | 0.003 | 9.60 | 25669 | 0.041 |
| C01_V1 | s4 | 2.75 | 409 | 0.000 | 4.25 | 3602 | 0.006 |
| C01_V2 | s1 | 5.40 | 1515 | 0.064 | 6.50 | 6645 | 0.063 |
| C01_V2 | s2 | 6.65 | 2174 | 0.064 | 8.95 | 10241 | 0.064 |
| C01_V2 | s3 | 6.15 | 2706 | 0.061 | 8.75 | 11159 | 0.062 |
| C01_V2 | s4 | 2.75 | 325 | 0.005 | 4.40 | 2255 | 0.011 |
| C02_V1 | s1 | 7.00 | 46662 | 0.168 | 14.05 | 277081 | 0.498 |
| C02_V1 | s2 | 9.00 | 68915 | 0.183 | 16.69 | 499668 | 0.519 |
| C02_V1 | s3 | 3.25 | 8431 | 0.005 | 9.20 | 71403 | 0.077 |
| C02_V1 | s4 | 2.55 | 1338 | 0.001 | 5.34 | 12978 | 0.020 |
| C02_V2 | s1 | 8.10 | 20880 | 0.196 | 11.65 | 148738 | 0.454 |
| C02_V2 | s2 | 9.75 | 28615 | 0.212 | 14.79 | 243290 | 0.443 |
| C02_V2 | s3 | 4.55 | 9124 | 0.018 | 7.40 | 69582 | 0.118 |
| C02_V2 | s4 | 3.45 | 1612 | 0.006 | 5.00 | 13663 | 0.035 |
| C03_V1 | s1 | 7.70 | 46860 | 0.232 | 13.00 | 261266 | 0.528 |
| C03_V1 | s2 | 9.70 | 62438 | 0.234 | 16.24 | 445631 | 0.537 |
| C03_V1 | s3 | 3.50 | 9177 | 0.008 | 7.75 | 78328 | 0.082 |
| C03_V1 | s4 | 2.90 | 1473 | 0.002 | 5.54 | 13826 | 0.021 |
| C03_V2 | s1 | 7.90 | 23066 | 0.143 | 11.55 | 166895 | 0.374 |
| C03_V2 | s2 | 10.09 | 33018 | 0.161 | 14.49 | 269033 | 0.395 |
| C03_V2 | s3 | 3.90 | 9336 | 0.010 | 6.60 | 69700 | 0.065 |
| C03_V2 | s4 | 3.55 | 1728 | 0.002 | 4.90 | 14364 | 0.019 |
| C04_V1 | s1 | 5.05 | 11185 | 0.017 | 9.35 | 81008 | 0.191 |
| C04_V1 | s2 | 6.60 | 16353 | 0.018 | 11.89 | 128128 | 0.186 |
| C04_V1 | s3 | 2.05 | 5854 | 0.002 | 8.10 | 53737 | 0.034 |
| C04_V1 | s4 | 1.95 | 1139 | 0.000 | 4.80 | 9954 | 0.007 |
| C04_V2 | s1 | 6.45 | 4290 | 0.024 | 8.35 | 26938 | 0.056 |
| C04_V2 | s2 | 8.00 | 6904 | 0.031 | 10.29 | 44813 | 0.064 |
| C04_V2 | s3 | 6.65 | 5288 | 0.015 | 9.30 | 43029 | 0.059 |
| C04_V2 | s4 | 3.55 | 741 | 0.001 | 5.59 | 6861 | 0.011 |
| C05_V1 | s1 | 6.00 | 8328 | 0.020 | 13.95 | 102648 | 0.490 |
| C05_V1 | s2 | 8.20 | 12294 | 0.020 | 16.94 | 194075 | 0.494 |
| C05_V1 | s3 | 3.10 | 5711 | 0.005 | 13.34 | 83820 | 0.260 |
| C05_V1 | s4 | 2.50 | 1153 | 0.001 | 8.39 | 12510 | 0.065 |
| C05_V2 | s1 | 6.75 | 7100 | 0.089 | 9.15 | 85756 | 0.196 |
| C05_V2 | s2 | 9.05 | 10342 | 0.082 | 11.14 | 136430 | 0.188 |
| C05_V2 | s3 | 5.05 | 6174 | 0.011 | 5.65 | 46145 | 0.032 |
| C05_V2 | s4 | 2.60 | 1172 | 0.003 | 3.95 | 10699 | 0.008 |
| C06_V1 | s1 | 6.70 | 9666 | 0.021 | 11.80 | 78096 | 0.108 |
| C06_V1 | s2 | 8.65 | 12693 | 0.021 | 15.19 | 130479 | 0.120 |
| C06_V1 | s3 | 6.05 | 6316 | 0.005 | 9.80 | 53557 | 0.039 |
| C06_V1 | s4 | 3.05 | 1055 | 0.001 | 4.85 | 8073 | 0.006 |
| C06_V2 | s1 | 8.15 | 4655 | 0.040 | 9.65 | 36171 | 0.078 |
| C06_V2 | s2 | 10.54 | 7023 | 0.042 | 12.74 | 58198 | 0.084 |
| C06_V2 | s3 | 7.65 | 6426 | 0.026 | 9.80 | 50062 | 0.066 |
| C06_V2 | s4 | 3.75 | 846 | 0.003 | 5.59 | 8033 | 0.012 |
| C07_V1 | s1 | 7.90 | 18632 | 0.054 | 14.95 | 131733 | 0.181 |
| C07_V1 | s2 | 10.34 | 27437 | 0.053 | 17.74 | 255249 | 0.224 |
| C07_V1 | s3 | 3.80 | 6182 | 0.004 | 11.84 | 87039 | 0.061 |
| C07_V1 | s4 | 2.35 | 1298 | 0.001 | 6.14 | 10829 | 0.010 |
| C07_V2 | s1 | 7.90 | 10545 | 0.036 | 9.65 | 45454 | 0.126 |
| C07_V2 | s2 | 11.39 | 1373525 | 0.039 | 11.84 | 225659 | 0.126 |
| C07_V2 | s3 | 5.85 | 6458 | 0.006 | 9.45 | 45936 | 0.058 |
| C07_V2 | s4 | 2.40 | 1028 | 0.001 | 4.65 | 8155 | 0.011 |
| C08_V1 | s1 | 6.80 | 18356 | 0.094 | 10.80 | 115855 | 0.167 |
| C08_V1 | s2 | 9.05 | 26476 | 0.090 | 14.49 | 192652 | 0.179 |
| C08_V1 | s3 | 3.75 | 8249 | 0.006 | 7.60 | 64323 | 0.049 |
| C08_V1 | s4 | 2.40 | 1275 | 0.001 | 4.60 | 11306 | 0.011 |
| C08_V2 | s1 | 9.70 | 12351 | 0.159 | 0.00 | 0 | 0.989 |
| C08_V2 | s2 | 12.59 | 21201 | 0.176 | 0.00 | 0 | 0.990 |
| C08_V2 | s3 | 8.25 | 10265 | 0.046 | 0.00 | 0 | 0.990 |
| C08_V2 | s4 | 4.10 | 1125 | 0.006 | 7.49 | 463 | 0.173 |
| C09_V1 | s1 | 5.95 | 30064 | 0.075 | 12.80 | 169024 | 0.203 |
| C09_V1 | s2 | 7.80 | 40870 | 0.076 | 15.54 | 294898 | 0.197 |
| C09_V1 | s3 | 3.35 | 7907 | 0.007 | 5.65 | 59709 | 0.031 |
| C09_V1 | s4 | 2.70 | 1264 | 0.001 | 3.20 | 10484 | 0.007 |
| C09_V2 | s1 | 8.75 | 16448 | 0.075 | 13.05 | 131913 | 0.207 |
| C09_V2 | s2 | 11.89 | 26092 | 0.069 | 15.89 | 224105 | 0.191 |
| C09_V2 | s3 | 3.35 | 7074 | 0.005 | 7.40 | 62389 | 0.040 |
| C09_V2 | s4 | 2.55 | 1417 | 0.001 | 4.50 | 12180 | 0.008 |
| C10_V1 | s1 | 7.55 | 37564 | 0.159 | 13.05 | 127462 | 0.493 |
| C10_V1 | s2 | 9.05 | 51175 | 0.164 | 15.84 | 215635 | 0.506 |
| C10_V1 | s3 | 2.90 | 8886 | 0.009 | 10.39 | 78961 | 0.125 |
| C10_V1 | s4 | 2.70 | 1479 | 0.001 | 6.49 | 13577 | 0.032 |
| C10_V2 | s1 | 9.30 | 17887 | 0.089 | 16.00 | 141997 | 0.509 |
| C10_V2 | s2 | 13.44 | 27984 | 0.120 | 19.39 | 262483 | 0.548 |
| C10_V2 | s3 | 4.40 | 8824 | 0.011 | 12.14 | 100472 | 0.243 |
| C10_V2 | s4 | 3.45 | 1885 | 0.005 | 7.74 | 15153 | 0.070 |
