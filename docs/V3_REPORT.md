# V3 report (work order 35, BRAIN_SPEC 7.54; report only)

No verdict, no video, no blind session. Code: `scripts/body/v3_lib.py`, `v3_stepa.py` (+ tests). Per-clip numbers: `/secondary/hyst-data/body/retarget_look/v3/numbers.json`.

## A. End-point smoothness (Step A)

Same 20 clips and windows as the look test, dataset frames k/30 s inside the shown 20 s. Signals: **(0w)** the human end point in world space (right wrist, joint 21, for V1 clips; head, joint 15, for V2 clips; root translation included); **(0r)** the same end point relative to its origin (right shoulder, joint 17, for V1; pelvis, joint 0, for V2), the signal V3 follows; **(1)** the stage-1 joint angles (the V1/V2 retargeted command at 30 fps); **(1e)** the robot lamp position by arm FK (point p5) of the stage-1 angles. Human FK uses the canonical T-pose offsets of the WO34 viewing figure (no SMPL model file; scale cancels in the reach normalisation).

Measures: acceleration sign changes per second (second difference at 30 fps; angles: accelerations below 1 deg/s^2 count as zero, positions: below 0.01 m/s^2, the same deadband in the sense that 1 deg/s^2 at a 0.57 m radius is 0.01 m/s^2 (FOR USER: default)); for positions per axis (x left, y up, z forward for the human; robot X forward, Y left, Z up for the lamp) and the mean over axes; share of speed power above 3 and 6 Hz (Welch, Hann, 5 s segments, mean removed; for positions the power of the speed vector = the three axes summed). Medians over the clips.

### All 20 clips

| signal | sign changes /s x | y | z | mean over axes | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|---|
| (0w) human end point, world | 7.08 | 5.55 | 7.38 | 6.52 | 0.031 | 0.003 |
| (0r) human end point relative to origin | 6.28 | 6.20 | 7.03 | 6.28 | 0.048 | 0.004 |
| (1e) robot lamp position, FK of stage-1 angles | 8.10 | 8.47 | 9.18 | 8.75 | 0.150 | 0.029 |

(1) stage-1 joint angles (per joint; jerk and power as `JITTER_DIAGNOSIS.md`):

| joint | sign changes /s | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| base_yaw | 5.47 | 0.018 | 0.001 |
| shoulder | 7.28 | 0.075 | 0.009 |
| elbow | 7.78 | 0.104 | 0.015 |
| wrist_bend | 11.60 | 0.199 | 0.077 |
| wrist_roll | 12.50 | 0.249 | 0.082 |
| mean over the 5 joints | 8.93 | 0.129 | 0.037 |

### V1 clips (10): end point = right wrist, origin = right shoulder

| signal | sign changes /s x | y | z | mean over axes | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|---|
| (0w) human end point, world | 5.40 | 5.17 | 6.35 | 5.59 | 0.022 | 0.002 |
| (0r) human end point relative to origin | 5.12 | 5.40 | 5.75 | 5.43 | 0.029 | 0.002 |
| (1e) robot lamp position, FK of stage-1 angles | 8.55 | 8.47 | 9.25 | 8.75 | 0.183 | 0.031 |

(1) stage-1 joint angles (per joint; jerk and power as `JITTER_DIAGNOSIS.md`):

| joint | sign changes /s | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| base_yaw | 5.33 | 0.013 | 0.001 |
| shoulder | 6.75 | 0.065 | 0.008 |
| elbow | 7.28 | 0.106 | 0.015 |
| wrist_bend | 12.90 | 0.197 | 0.077 |
| wrist_roll | 12.50 | 0.155 | 0.060 |
| mean over the 5 joints | 8.95 | 0.107 | 0.032 |

### V2 clips (10): end point = head, origin = pelvis

| signal | sign changes /s x | y | z | mean over axes | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|---|
| (0w) human end point, world | 9.53 | 6.03 | 10.15 | 8.44 | 0.045 | 0.011 |
| (0r) human end point relative to origin | 9.15 | 8.52 | 9.27 | 9.03 | 0.085 | 0.024 |
| (1e) robot lamp position, FK of stage-1 angles | 7.07 | 8.68 | 8.95 | 8.75 | 0.147 | 0.025 |

(1) stage-1 joint angles (per joint; jerk and power as `JITTER_DIAGNOSIS.md`):

| joint | sign changes /s | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| base_yaw | 5.72 | 0.019 | 0.001 |
| shoulder | 8.00 | 0.082 | 0.012 |
| elbow | 9.07 | 0.101 | 0.016 |
| wrist_bend | 9.65 | 0.201 | 0.068 |
| wrist_roll | 12.35 | 0.408 | 0.192 |
| mean over the 5 joints | 8.96 | 0.162 | 0.058 |

### Per clip (sign changes mean over axes / power > 3 Hz)

| clip | (0w) | (0r) | (1e) | (1) mean over joints |
|---|---|---|---|---|
| C01_V1 | 5.38 / 0.002 | 4.53 / 0.002 | 5.97 / 0.011 | 6.59 / 0.015 |
| C01_V2 | 6.20 / 0.004 | 5.98 / 0.071 | 5.70 / 0.067 | 6.18 / 0.045 |
| C02_V1 | 6.32 / 0.083 | 5.72 / 0.092 | 8.25 / 0.268 | 9.51 / 0.253 |
| C02_V2 | 9.67 / 0.092 | 9.57 / 0.114 | 9.35 / 0.302 | 9.78 / 0.252 |
| C03_V1 | 6.72 / 0.089 | 6.70 / 0.105 | 9.48 / 0.337 | 9.41 / 0.280 |
| C03_V2 | 9.98 / 0.162 | 10.30 / 0.173 | 9.42 / 0.324 | 10.35 / 0.259 |
| C04_V1 | 4.78 / 0.009 | 5.02 / 0.010 | 6.58 / 0.114 | 6.74 / 0.067 |
| C04_V2 | 6.03 / 0.028 | 5.42 / 0.013 | 6.50 / 0.036 | 6.61 / 0.031 |
| C05_V1 | 4.78 / 0.013 | 4.28 / 0.016 | 9.70 / 0.142 | 9.88 / 0.180 |
| C05_V2 | 7.47 / 0.084 | 8.50 / 0.117 | 7.55 / 0.188 | 9.03 / 0.182 |
| C06_V1 | 4.95 / 0.004 | 5.53 / 0.006 | 8.87 / 0.068 | 8.79 / 0.057 |
| C06_V2 | 6.20 / 0.014 | 7.22 / 0.018 | 6.95 / 0.041 | 8.29 / 0.072 |
| C07_V1 | 5.80 / 0.008 | 5.02 / 0.012 | 10.80 / 0.123 | 10.20 / 0.097 |
| C07_V2 | 7.33 / 0.014 | 6.82 / 0.025 | 8.15 / 0.079 | 8.40 / 0.063 |
| C08_V1 | 6.97 / 0.034 | 6.58 / 0.049 | 8.63 / 0.257 | 8.22 / 0.105 |
| C08_V2 | 9.47 / 0.103 | 11.00 / 0.249 | 9.38 / 0.135 | 5.17 / 0.482 |
| C09_V1 | 5.30 / 0.030 | 5.33 / 0.042 | 9.45 / 0.225 | 8.79 / 0.111 |
| C09_V2 | 9.42 / 0.034 | 10.22 / 0.078 | 10.28 / 0.171 | 10.72 / 0.174 |
| C10_V1 | 6.80 / 0.033 | 5.68 / 0.047 | 8.45 / 0.275 | 9.86 / 0.254 |
| C10_V2 | 10.97 / 0.057 | 12.47 / 0.092 | 11.55 / 0.158 | 12.19 / 0.299 |

## Q2. C04_V2 shoulder offset (seconds 8-12), report only

Script `scripts/body/v3_q2.py`; data `/secondary/hyst-data/body/retarget_look/v3/q2.json`. The shown clip was rebuilt and matches `work/C04_V2.csv` to 5e-07 deg, then the same clip was re-simulated with bookkeeping.

| check | result |
|---|---|
| command vs limiter output (shoulder, window mean) | -40.64 vs -40.69 deg: mean difference -0.05 deg, largest 2.8 deg (the limiter is not the source) |
| realised vs command (window) | realised mean -35.85 vs command -40.64: **realised is +4.8 deg higher (less negative = the upper arm sags toward the horizontal)**, range -4.4 to +12.4 deg across the window, +4.9 deg mean over the whole clip |
| gravity switched off, same clip | realised minus command in the window **+0.10 deg** mean (whole clip -0.09 deg); the offset disappears |
| static servo model | gravity torque on the shoulder at the window's mean pose -1.55 N m (MuJoCo `qfrc_bias`), servo stiffness kp = 16.86 N m/rad (stall torque 2.94 N m at 10 deg error) -> -1.55 / 16.86 = **5.3 deg of sag** (measured mean 4.8 deg); in the window the gravity torque on the shoulder is -1.14 to -1.58 N m, i.e. 39-54 % of the stall torque |
| guard | 0 frames held in the whole clip |
| end stops | the shoulder stays between -48.3 and -28.0 deg (range +-110): 61.7 deg from the nearest limit |
| column / floor contact | no contact of any geom pair in the whole clip |

**Cause: gravity sag of the position servo model** (a proportional servo holding a load needs an error of torque / kp). The realised minus command spread (-4.4 to +12.4 deg) follows the pose-dependent gravity torque and the dynamics; the "about 10 deg" read from the plot was the upper part of that spread (mean 4.8 deg). Not the limiter, the guard, the end stops or the column.

## B. V3 space retarget (Step B)

Rules: `RETARGET_RULES.md` (m). V3a = lamp follows the right wrist relative to the right shoulder, V3b = the head relative to the pelvis; IK on the v2p arm; then guard, round-1 spinal layer (H1), fixed limiter, servo, v2p body; gates at 1.25 (l). The same 10 seeded windows C01-C10 as the look test, nothing re-picked, no video. Medians are over the 10 clips of the variant. The baseline columns are the look-test V1 (for V3a) and V2 (for V3b) clips of the same windows, `JITTER_DIAGNOSIS.md` baseline and H1 runs.

### B1. Gate (1.25) and IK residual, per clip

| clip | gate | failed parts | speed x | accel x | guard share | IK frames > 2 cm (shown 20 s) | IK frames > 2 cm (all 21.5 s) | IK error median / p95 / max (cm) |
|---|---|---|---|---|---|---|---|---|
| C01_V3a | FAIL | contact, endstop, limits | 1.02 | 8.09 | 0.0000 | 414 / 2001 | 441 / 2151 | 0.0 / 15.7 / 27.1 |
| C01_V3b | FAIL | endstop | 1.00 | 0.78 | 0.0000 | 397 / 2001 | 403 / 2151 | 0.1 / 6.1 / 10.0 |
| C02_V3a | FAIL | clearance, contact, endstop, limits | 1.02 | 8.78 | 0.0000 | 1140 / 2001 | 1198 / 2151 | 4.5 / 65.8 / 91.4 |
| C02_V3b | FAIL | endstop | 1.00 | 0.87 | 0.0000 | 216 / 2001 | 217 / 2151 | 0.4 / 4.1 / 11.0 |
| C03_V3a | FAIL | clearance, contact, endstop, limits | 1.00 | 9.77 | 0.0005 | 331 / 2001 | 355 / 2151 | 0.0 / 7.0 / 14.5 |
| C03_V3b | FAIL | endstop | 1.01 | 1.01 | 0.0000 | 80 / 2001 | 118 / 2151 | 0.1 / 1.7 / 5.4 |
| C04_V3a | FAIL | contact, endstop, limits | 1.07 | 10.32 | 0.0000 | 481 / 2001 | 481 / 2151 | 0.0 / 10.1 / 24.7 |
| C04_V3b | FAIL | endstop | 1.00 | 1.19 | 0.0000 | 317 / 2001 | 319 / 2151 | 0.0 / 6.9 / 19.8 |
| C05_V3a | FAIL | contact, endstop, limits | 1.37 | 10.78 | 0.0000 | 352 / 2001 | 411 / 2151 | 0.0 / 7.5 / 15.1 |
| C05_V3b | FAIL | endstop | 1.00 | 1.03 | 0.0000 | 71 / 2001 | 72 / 2151 | 0.0 / 0.8 / 4.4 |
| C06_V3a | FAIL | clearance, contact, endstop, limits | 1.02 | 12.99 | 0.0000 | 125 / 2001 | 199 / 2151 | 0.0 / 2.7 / 15.8 |
| C06_V3b | FAIL | endstop | 1.00 | 0.88 | 0.0000 | 3 / 2001 | 78 / 2151 | 0.1 / 0.5 / 2.0 |
| C07_V3a | FAIL | clearance, contact, endstop, limits | 1.09 | 12.59 | 0.0000 | 211 / 2001 | 225 / 2151 | 0.0 / 6.5 / 23.5 |
| C07_V3b | FAIL | endstop | 1.01 | 1.02 | 0.0000 | 114 / 2001 | 127 / 2151 | 0.0 / 2.5 / 6.4 |
| C08_V3a | FAIL | clearance, contact, endstop, limits | 1.08 | 13.94 | 0.0000 | 698 / 2001 | 830 / 2151 | 0.3 / 11.6 / 39.1 |
| C08_V3b | FAIL | endstop | 0.95 | 0.84 | 0.0000 | 6 / 2001 | 7 / 2151 | 0.6 / 1.1 / 2.3 |
| C09_V3a | FAIL | clearance, contact, endstop, limits | 1.06 | 7.03 | 0.0483 | 512 / 2001 | 623 / 2151 | 0.0 / 16.4 / 46.8 |
| C09_V3b | FAIL | endstop | 1.01 | 1.03 | 0.0000 | 80 / 2001 | 94 / 2151 | 0.0 / 1.3 / 8.4 |
| C10_V3a | FAIL | clearance, contact, endstop, limits | 1.03 | 8.22 | 0.0000 | 802 / 2001 | 934 / 2151 | 0.0 / 38.9 / 50.8 |
| C10_V3b | FAIL | endstop | 1.00 | 0.91 | 0.0000 | 329 / 2001 | 329 / 2151 | 0.5 / 7.1 / 14.5 |

### B2. V3a: jitter measures per stage (median over the 10 clips; own rate)

Gate passes: **0 / 10**; IK frames > 2 cm (shown 20 s): median 448 of 2001.

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| IK output | base_yaw | 9.47 | 2390097 | 0.350 | 0.214 |
| IK output | shoulder | 11.24 | 932563 | 0.283 | 0.199 |
| IK output | elbow | 11.84 | 1225485 | 0.459 | 0.282 |
| IK output | wrist_bend | 13.14 | 1333198 | 0.578 | 0.290 |
| IK output | wrist_roll | 14.27 | 1817047 | 0.417 | 0.206 |
| spinal layer output | base_yaw | 4.25 | 58205 | 0.055 | 0.003 |
| spinal layer output | shoulder | 4.72 | 35390 | 0.040 | 0.002 |
| spinal layer output | elbow | 5.12 | 44365 | 0.104 | 0.004 |
| spinal layer output | wrist_bend | 5.35 | 37241 | 0.121 | 0.008 |
| spinal layer output | wrist_roll | 5.40 | 86118 | 0.092 | 0.005 |
| limiter output | base_yaw | 2.45 | 11282 | 0.004 | 0.000 |
| limiter output | shoulder | 2.12 | 6030 | 0.002 | 0.000 |
| limiter output | elbow | 4.35 | 20958 | 0.015 | 0.002 |
| limiter output | wrist_bend | 4.82 | 33610 | 0.050 | 0.004 |
| limiter output | wrist_roll | 3.90 | 57643 | 0.030 | 0.003 |
| realised | base_yaw | 2.07 | 1990 | 0.000 | 0.000 |
| realised | shoulder | 2.47 | 9219 | 0.007 | 0.002 |
| realised | elbow | 3.55 | 9320 | 0.004 | 0.001 |
| realised | wrist_bend | 3.70 | 8459 | 0.014 | 0.000 |
| realised | wrist_roll | 3.22 | 14059 | 0.009 | 0.000 |

End point (lamp position, per axis mean; medians over the clips): target path at 30 fps / IK output at 100 Hz / realised at 50 Hz

| signal | sign changes /s (mean over axes) | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| target path (30 fps) | 5.89 | 0.049 | 0.003 |
| lamp FK of the IK output (100 Hz) | 11.68 | 0.246 | 0.183 |
| lamp FK of the realised angles (50 Hz) | 3.42 | 0.006 | 0.001 |

### B3. V3a next to V1 (baseline), V1 + H1 and the S03 references (stage 4 realised, median over clips; own rate)

| joint | metric | V3a | V1 baseline | V1 + H1 | S03 refs (2 clips) |
|---|---|---|---|---|---|
| base_yaw | acc sign changes /s | 2.07 | 2.17 | 1.80 | 1.15 |
| base_yaw | jerk RMS | 1990 | 604 | 517 | 255 |
| base_yaw | power > 3 Hz | 0.000 | 0.000 | 0.000 | 0.000 |
| shoulder | acc sign changes /s | 2.47 | 2.62 | 2.10 | 1.07 |
| shoulder | jerk RMS | 9219 | 1269 | 1098 | 123 |
| shoulder | power > 3 Hz | 0.007 | 0.001 | 0.001 | 0.000 |
| elbow | acc sign changes /s | 3.55 | 3.35 | 2.70 | 1.07 |
| elbow | jerk RMS | 9320 | 3714 | 3359 | 232 |
| elbow | power > 3 Hz | 0.004 | 0.001 | 0.001 | 0.000 |
| wrist_bend | acc sign changes /s | 3.70 | 5.09 | 3.67 | 0.85 |
| wrist_bend | jerk RMS | 8459 | 11068 | 8860 | 186 |
| wrist_bend | power > 3 Hz | 0.014 | 0.010 | 0.007 | 0.000 |
| wrist_roll | acc sign changes /s | 3.22 | 5.89 | 4.00 | 1.27 |
| wrist_roll | jerk RMS | 14059 | 17862 | 12449 | 762 |
| wrist_roll | power > 3 Hz | 0.009 | 0.017 | 0.009 | 0.000 |

### B4. V3a shoulder numbers (7.52.5): acceleration as multiples of the limit (p50 / p95 / max), limiter share, RMS (limiter input - output)

| clip | commanded (IK output) | realised | limiter share | RMS deg |
|---|---|---|---|---|
| C01_V3a | 0.22 / 3.57 / 208.2 | 0.13 / 0.67 / 8.09 | 89 % | 11.2 |
| C02_V3a | 5.51 / 62.71 / 269.3 | 0.40 / 0.94 / 8.78 | 100 % | 58.3 |
| C03_V3a | 4.93 / 28.16 / 84.6 | 0.38 / 0.88 / 9.77 | 100 % | 38.1 |
| C04_V3a | 1.54 / 16.88 / 248.5 | 0.29 / 0.87 / 10.32 | 95 % | 38.0 |
| C05_V3a | 2.28 / 18.71 / 221.5 | 0.31 / 0.86 / 10.78 | 99 % | 22.7 |
| C06_V3a | 0.65 / 9.15 / 127.4 | 0.18 / 0.82 / 12.99 | 85 % | 38.7 |
| C07_V3a | 1.59 / 15.82 / 177.1 | 0.33 / 0.87 / 12.59 | 98 % | 30.8 |
| C08_V3a | 2.35 / 22.75 / 182.0 | 0.22 / 0.89 / 13.94 | 99 % | 55.2 |
| C09_V3a | 3.94 / 32.63 / 250.2 | 0.38 / 0.86 / 7.03 | 96 % | 42.6 |
| C10_V3a | 5.04 / 51.90 / 414.5 | 0.44 / 0.87 / 8.22 | 100 % | 33.8 |

### B2. V3b: jitter measures per stage (median over the 10 clips; own rate)

Gate passes: **0 / 10**; IK frames > 2 cm (shown 20 s): median 97 of 2001.

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | speed power > 3 Hz | speed power > 6 Hz |
|---|---|---|---|---|---|
| IK output | base_yaw | 13.99 | 4162535 | 0.523 | 0.356 |
| IK output | shoulder | 11.32 | 159185 | 0.270 | 0.099 |
| IK output | elbow | 14.59 | 253876 | 0.344 | 0.125 |
| IK output | wrist_bend | 14.12 | 150814 | 0.311 | 0.116 |
| IK output | wrist_roll | 13.09 | 961795 | 0.389 | 0.186 |
| spinal layer output | base_yaw | 5.22 | 47060 | 0.068 | 0.004 |
| spinal layer output | shoulder | 5.02 | 6920 | 0.042 | 0.002 |
| spinal layer output | elbow | 5.37 | 9286 | 0.072 | 0.003 |
| spinal layer output | wrist_bend | 5.20 | 5031 | 0.062 | 0.002 |
| spinal layer output | wrist_roll | 5.57 | 33873 | 0.064 | 0.004 |
| limiter output | base_yaw | 2.45 | 9638 | 0.004 | 0.001 |
| limiter output | shoulder | 4.17 | 6077 | 0.012 | 0.001 |
| limiter output | elbow | 5.42 | 10719 | 0.024 | 0.002 |
| limiter output | wrist_bend | 5.47 | 6094 | 0.059 | 0.003 |
| limiter output | wrist_roll | 5.57 | 41070 | 0.043 | 0.004 |
| realised | base_yaw | 1.85 | 1205 | 0.000 | 0.000 |
| realised | shoulder | 2.27 | 1000 | 0.001 | 0.000 |
| realised | elbow | 3.17 | 1763 | 0.003 | 0.000 |
| realised | wrist_bend | 3.65 | 1819 | 0.016 | 0.000 |
| realised | wrist_roll | 3.77 | 8922 | 0.013 | 0.000 |

End point (lamp position, per axis mean; medians over the clips): target path at 30 fps / IK output at 100 Hz / realised at 50 Hz

| signal | sign changes /s (mean over axes) | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| target path (30 fps) | 9.24 | 0.101 | 0.025 |
| lamp FK of the IK output (100 Hz) | 14.71 | 0.274 | 0.102 |
| lamp FK of the realised angles (50 Hz) | 3.16 | 0.002 | 0.000 |

### B3. V3b next to V2 (baseline), V2 + H1 and the S03 references (stage 4 realised, median over clips; own rate)

| joint | metric | V3b | V2 baseline | V2 + H1 | S03 refs (2 clips) |
|---|---|---|---|---|---|
| base_yaw | acc sign changes /s | 1.85 | 2.40 | 2.10 | 1.15 |
| base_yaw | jerk RMS | 1205 | 564 | 465 | 255 |
| base_yaw | power > 3 Hz | 0.000 | 0.000 | 0.000 | 0.000 |
| shoulder | acc sign changes /s | 2.27 | 3.45 | 2.67 | 1.07 |
| shoulder | jerk RMS | 1000 | 1149 | 909 | 123 |
| shoulder | power > 3 Hz | 0.001 | 0.003 | 0.001 | 0.000 |
| elbow | acc sign changes /s | 3.17 | 3.22 | 2.90 | 1.07 |
| elbow | jerk RMS | 1763 | 3073 | 2161 | 232 |
| elbow | power > 3 Hz | 0.003 | 0.003 | 0.001 | 0.000 |
| wrist_bend | acc sign changes /s | 3.65 | 4.95 | 3.60 | 0.85 |
| wrist_bend | jerk RMS | 1819 | 9427 | 7290 | 186 |
| wrist_bend | power > 3 Hz | 0.016 | 0.012 | 0.006 | 0.000 |
| wrist_roll | acc sign changes /s | 3.77 | 5.00 | 4.20 | 1.27 |
| wrist_roll | jerk RMS | 8922 | 18574 | 11046 | 762 |
| wrist_roll | power > 3 Hz | 0.013 | 0.025 | 0.013 | 0.000 |

### B4. V3b shoulder numbers (7.52.5): acceleration as multiples of the limit (p50 / p95 / max), limiter share, RMS (limiter input - output)

| clip | commanded (IK output) | realised | limiter share | RMS deg |
|---|---|---|---|---|
| C01_V3b | 0.03 / 0.19 / 14.2 | 0.02 / 0.09 / 0.38 | 19 % | 0.0 |
| C02_V3b | 0.82 / 4.43 / 22.5 | 0.21 / 0.65 / 0.87 | 88 % | 3.7 |
| C03_V3b | 0.78 / 4.48 / 41.4 | 0.15 / 0.60 / 1.01 | 85 % | 4.2 |
| C04_V3b | 0.22 / 4.50 / 98.4 | 0.20 / 0.73 / 1.19 | 81 % | 7.0 |
| C05_V3b | 0.72 / 4.80 / 95.2 | 0.18 / 0.59 / 1.03 | 95 % | 4.7 |
| C06_V3b | 0.30 / 1.76 / 9.9 | 0.12 / 0.49 / 0.80 | 67 % | 2.9 |
| C07_V3b | 0.30 / 4.26 / 31.8 | 0.18 / 0.70 / 1.02 | 81 % | 7.2 |
| C08_V3b | 0.72 / 3.18 / 9.3 | 0.13 / 0.40 / 0.81 | 80 % | 1.3 |
| C09_V3b | 1.21 / 6.41 / 32.0 | 0.31 / 0.81 / 1.03 | 97 % | 9.9 |
| C10_V3b | 0.77 / 4.22 / 18.0 | 0.18 / 0.68 / 0.91 | 84 % | 5.1 |
