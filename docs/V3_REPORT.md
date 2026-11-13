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
