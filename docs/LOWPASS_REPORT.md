# Low-pass to the human's smoothness: report (work order 36, BRAIN_SPEC 7.55; no verdict)

Rules `RETARGET_RULES.md` (n). 2nd-order Butterworth, zero phase, 30 fps, on the whole-sequence stage-1 angles; cutoffs **V1 2.50 Hz, V2 5.75 Hz** (highest cutoff at which the median lamp-path power above 3 Hz of the 10 windows is <= the human end point's: V1 0.0290, V2 0.0851). Then cubic spline to 100 Hz, guard, round-1 spinal layer (H1), fixed limiter (k), servo, v2p body, gates at 1.25 (l). The same 20 windows as the look test. Medians over the 10 clips of the variant; own rate unless stated. Data: `lowpass/numbers.json`.

## 1. Gate (1.25) per clip and shoulder numbers (7.52.5)

| clip | gate | failed parts | speed x | accel x | guard share | shoulder commanded p50 / p95 / max (x limit) | shoulder realised p50 / p95 / max | limiter share | RMS limiter in - out (deg) |
|---|---|---|---|---|---|---|---|---|---|
| C01_V1 | pass | - | 1.00 | 0.66 | 0.0000 | 0.11 / 0.61 / 0.9 | 0.08 / 0.41 / 0.66 | 86 % | 1.5 |
| C01_V2 | pass | - | 0.63 | 0.32 | 0.0000 | 0.07 / 0.49 / 0.9 | 0.04 / 0.16 / 0.25 | 37 % | 0.1 |
| C02_V1 | pass | - | 1.00 | 1.07 | 0.0000 | 1.51 / 5.56 / 9.1 | 0.40 / 0.88 / 1.07 | 97 % | 18.1 |
| C02_V2 | pass | - | 1.02 | 1.18 | 0.0000 | 1.10 / 4.27 / 8.6 | 0.31 / 0.87 / 1.18 | 98 % | 8.9 |
| C03_V1 | pass | - | 1.00 | 1.06 | 0.0000 | 1.34 / 5.27 / 8.0 | 0.38 / 0.85 / 1.06 | 100 % | 14.0 |
| C03_V2 | pass | - | 1.00 | 1.08 | 0.0000 | 1.19 / 4.23 / 11.1 | 0.37 / 0.86 / 1.08 | 100 % | 9.4 |
| C04_V1 | pass | - | 1.11 | 1.12 | 0.0000 | 0.77 / 3.32 / 7.7 | 0.43 / 0.90 / 1.12 | 99 % | 18.9 |
| C04_V2 | pass | - | 1.00 | 0.89 | 0.0000 | 0.21 / 1.16 / 2.0 | 0.10 / 0.48 / 0.77 | 60 % | 1.5 |
| C05_V1 | pass | - | 1.02 | 1.04 | 0.0000 | 0.59 / 1.99 / 6.5 | 0.30 / 0.78 / 1.04 | 98 % | 11.5 |
| C05_V2 | pass | - | 0.98 | 0.89 | 0.0000 | 0.47 / 2.17 / 3.3 | 0.28 / 0.63 / 0.88 | 98 % | 1.9 |
| C06_V1 | pass | - | 1.01 | 1.04 | 0.0000 | 0.30 / 3.04 / 5.6 | 0.22 / 0.88 / 1.04 | 72 % | 10.9 |
| C06_V2 | pass | - | 1.02 | 0.90 | 0.0000 | 0.23 / 1.08 / 2.4 | 0.13 / 0.48 / 0.86 | 68 % | 1.3 |
| C07_V1 | pass | - | 1.04 | 1.18 | 0.0000 | 0.79 / 3.22 / 6.2 | 0.37 / 0.96 / 1.18 | 88 % | 14.4 |
| C07_V2 | pass | - | 1.03 | 1.04 | 0.0051 | 0.38 / 1.99 / 205.0 | 0.20 / 0.73 / 1.04 | 86 % | 5.8 |
| C08_V1 | pass | - | 1.11 | 1.03 | 0.0000 | 0.71 / 3.21 / 6.0 | 0.32 / 0.79 / 1.03 | 97 % | 11.9 |
| C08_V2 | pass | - | 0.72 | 0.94 | 0.0000 | 0.43 / 1.84 / 5.4 | 0.15 / 0.45 / 0.94 | 83 % | 2.1 |
| C09_V1 | pass | - | 1.02 | 1.15 | 0.0000 | 1.50 / 5.22 / 8.4 | 0.36 / 0.96 / 1.15 | 99 % | 22.5 |
| C09_V2 | pass | - | 1.04 | 1.13 | 0.0000 | 1.00 / 3.32 / 7.3 | 0.42 / 0.85 / 1.13 | 99 % | 10.3 |
| C10_V1 | pass | - | 0.96 | 1.18 | 0.0000 | 1.55 / 5.52 / 7.1 | 0.47 / 0.86 / 1.18 | 100 % | 14.0 |
| C10_V2 | FAIL | limits | 0.96 | 1.28 | 0.0000 | 0.99 / 3.04 / 5.3 | 0.35 / 0.83 / 1.28 | 100 % | 9.0 |

## 2. V1 (cutoff 2.50 Hz): jitter measures per stage (median over the 10 clips; gate passes 10 / 10)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|
| 1 filtered stage-1 angles (30 fps) | base_yaw | 2.80 | 1105 | 0.000 | 0.000 |
| 1 filtered stage-1 angles (30 fps) | shoulder | 2.92 | 4701 | 0.002 | 0.000 |
| 1 filtered stage-1 angles (30 fps) | elbow | 3.27 | 12661 | 0.003 | 0.000 |
| 1 filtered stage-1 angles (30 fps) | wrist_bend | 3.48 | 11687 | 0.008 | 0.000 |
| 1 filtered stage-1 angles (30 fps) | wrist_roll | 3.65 | 17298 | 0.004 | 0.000 |
| 2 spline (100 Hz, guard) | base_yaw | 2.80 | 1134 | 0.000 | 0.000 |
| 2 spline (100 Hz, guard) | shoulder | 2.95 | 4810 | 0.002 | 0.000 |
| 2 spline (100 Hz, guard) | elbow | 3.30 | 12979 | 0.003 | 0.000 |
| 2 spline (100 Hz, guard) | wrist_bend | 3.50 | 12122 | 0.008 | 0.000 |
| 2 spline (100 Hz, guard) | wrist_roll | 3.70 | 17881 | 0.004 | 0.000 |
| spinal layer | base_yaw | 2.62 | 991 | 0.000 | 0.000 |
| spinal layer | shoulder | 2.77 | 4304 | 0.001 | 0.000 |
| spinal layer | elbow | 2.95 | 11529 | 0.001 | 0.000 |
| spinal layer | wrist_bend | 3.17 | 10074 | 0.003 | 0.000 |
| spinal layer | wrist_roll | 3.37 | 15424 | 0.002 | 0.000 |
| limiter output | base_yaw | 2.75 | 2919 | 0.001 | 0.000 |
| limiter output | shoulder | 2.65 | 5638 | 0.004 | 0.000 |
| limiter output | elbow | 2.92 | 17497 | 0.006 | 0.001 |
| limiter output | wrist_bend | 3.65 | 27766 | 0.014 | 0.002 |
| limiter output | wrist_roll | 3.32 | 45763 | 0.017 | 0.002 |
| realised (50 Hz) | base_yaw | 1.47 | 396 | 0.000 | 0.000 |
| realised (50 Hz) | shoulder | 2.10 | 1009 | 0.000 | 0.000 |
| realised (50 Hz) | elbow | 2.32 | 3196 | 0.001 | 0.000 |
| realised (50 Hz) | wrist_bend | 2.70 | 6210 | 0.003 | 0.000 |
| realised (50 Hz) | wrist_roll | 2.85 | 10046 | 0.005 | 0.000 |

Lamp-path speed power above 3 Hz at each stage (V1, median): filtered stage 1 0.0254, spline 0.0372, spinal 0.0277, limiter 0.0092, realised 0.0013.

### 3. V1: realised stage next to the look-test baseline, baseline + H1 and the S03 references (median over the clips)

| joint | metric | low-pass + H1 | look-test baseline | baseline + H1 | S03 refs (2) |
|---|---|---|---|---|---|
| base_yaw | acc sign changes /s | 1.47 | 2.17 | 1.80 | 1.15 |
| base_yaw | jerk RMS | 396 | 604 | 517 | 255 |
| base_yaw | power > 3 Hz | 0.000 | 0.000 | 0.000 | 0.000 |
| shoulder | acc sign changes /s | 2.10 | 2.62 | 2.10 | 1.07 |
| shoulder | jerk RMS | 1009 | 1269 | 1098 | 123 |
| shoulder | power > 3 Hz | 0.000 | 0.001 | 0.001 | 0.000 |
| elbow | acc sign changes /s | 2.32 | 3.35 | 2.70 | 1.07 |
| elbow | jerk RMS | 3196 | 3714 | 3359 | 232 |
| elbow | power > 3 Hz | 0.001 | 0.001 | 0.001 | 0.000 |
| wrist_bend | acc sign changes /s | 2.70 | 5.09 | 3.67 | 0.85 |
| wrist_bend | jerk RMS | 6210 | 11068 | 8860 | 186 |
| wrist_bend | power > 3 Hz | 0.003 | 0.010 | 0.007 | 0.000 |
| wrist_roll | acc sign changes /s | 2.85 | 5.89 | 4.00 | 1.27 |
| wrist_roll | jerk RMS | 10046 | 17862 | 12449 | 762 |
| wrist_roll | power > 3 Hz | 0.005 | 0.017 | 0.009 | 0.000 |
| lamp path | power > 3 Hz (FK of realised angles) | 0.0013 | 0.0030 | 0.0024 | 0.0000 |

## 2. V2 (cutoff 5.75 Hz): jitter measures per stage (median over the 10 clips; gate passes 9 / 10)

| stage | joint | acc sign changes /s | jerk RMS deg/s^3 | power > 3 Hz | power > 6 Hz |
|---|---|---|---|---|---|
| 1 filtered stage-1 angles (30 fps) | base_yaw | 4.15 | 2289 | 0.011 | 0.000 |
| 1 filtered stage-1 angles (30 fps) | shoulder | 5.08 | 5264 | 0.047 | 0.001 |
| 1 filtered stage-1 angles (30 fps) | elbow | 5.07 | 10052 | 0.057 | 0.001 |
| 1 filtered stage-1 angles (30 fps) | wrist_bend | 5.95 | 26175 | 0.106 | 0.003 |
| 1 filtered stage-1 angles (30 fps) | wrist_roll | 7.28 | 39072 | 0.167 | 0.010 |
| 2 spline (100 Hz, guard) | base_yaw | 4.30 | 3027 | 0.012 | 0.000 |
| 2 spline (100 Hz, guard) | shoulder | 5.25 | 7417 | 0.053 | 0.001 |
| 2 spline (100 Hz, guard) | elbow | 5.45 | 12834 | 0.054 | 0.001 |
| 2 spline (100 Hz, guard) | wrist_bend | 6.27 | 40203 | 0.097 | 0.003 |
| 2 spline (100 Hz, guard) | wrist_roll | 7.77 | 53642 | 0.172 | 0.011 |
| spinal layer | base_yaw | 3.47 | 1937 | 0.003 | 0.000 |
| spinal layer | shoulder | 3.97 | 4388 | 0.018 | 0.000 |
| spinal layer | elbow | 4.15 | 7000 | 0.018 | 0.000 |
| spinal layer | wrist_bend | 4.60 | 14736 | 0.019 | 0.000 |
| spinal layer | wrist_roll | 5.90 | 20879 | 0.050 | 0.001 |
| limiter output | base_yaw | 3.47 | 3529 | 0.004 | 0.000 |
| limiter output | shoulder | 3.80 | 5574 | 0.010 | 0.001 |
| limiter output | elbow | 4.12 | 10987 | 0.009 | 0.001 |
| limiter output | wrist_bend | 4.52 | 28907 | 0.020 | 0.002 |
| limiter output | wrist_roll | 5.02 | 35537 | 0.038 | 0.003 |
| realised (50 Hz) | base_yaw | 2.10 | 457 | 0.000 | 0.000 |
| realised (50 Hz) | shoulder | 2.62 | 894 | 0.001 | 0.000 |
| realised (50 Hz) | elbow | 2.77 | 2075 | 0.001 | 0.000 |
| realised (50 Hz) | wrist_bend | 3.60 | 6642 | 0.005 | 0.000 |
| realised (50 Hz) | wrist_roll | 3.65 | 10030 | 0.011 | 0.000 |

Lamp-path speed power above 3 Hz at each stage (V2, median): filtered stage 1 0.0804, spline 0.0845, spinal 0.0283, limiter 0.0151, realised 0.0023.

### 3. V2: realised stage next to the look-test baseline, baseline + H1 and the S03 references (median over the clips)

| joint | metric | low-pass + H1 | look-test baseline | baseline + H1 | S03 refs (2) |
|---|---|---|---|---|---|
| base_yaw | acc sign changes /s | 2.10 | 2.40 | 2.10 | 1.15 |
| base_yaw | jerk RMS | 457 | 564 | 465 | 255 |
| base_yaw | power > 3 Hz | 0.000 | 0.000 | 0.000 | 0.000 |
| shoulder | acc sign changes /s | 2.62 | 3.45 | 2.67 | 1.07 |
| shoulder | jerk RMS | 894 | 1149 | 909 | 123 |
| shoulder | power > 3 Hz | 0.001 | 0.003 | 0.001 | 0.000 |
| elbow | acc sign changes /s | 2.77 | 3.22 | 2.90 | 1.07 |
| elbow | jerk RMS | 2075 | 3073 | 2161 | 232 |
| elbow | power > 3 Hz | 0.001 | 0.003 | 0.001 | 0.000 |
| wrist_bend | acc sign changes /s | 3.60 | 4.95 | 3.60 | 0.85 |
| wrist_bend | jerk RMS | 6642 | 9427 | 7290 | 186 |
| wrist_bend | power > 3 Hz | 0.005 | 0.012 | 0.006 | 0.000 |
| wrist_roll | acc sign changes /s | 3.65 | 5.00 | 4.20 | 1.27 |
| wrist_roll | jerk RMS | 10030 | 18574 | 11046 | 762 |
| wrist_roll | power > 3 Hz | 0.011 | 0.025 | 0.013 | 0.000 |
| lamp path | power > 3 Hz (FK of realised angles) | 0.0023 | 0.0052 | 0.0028 | 0.0000 |

## 4. Blind re-look (7.55.4), Kosta, 2026-11-13 21:46 to 2026-11-14 14:19

Session `/secondary/hyst-data/body/retarget_look/lowpass/session_2026-11-13/` (seed 32091, tool archive `lowpass/tool_f1d1906`). 6 pairs,
"Which looks more like a person dancing?", first / second / same. LP = low-pass + H1; old = the look-test mp4 as shown. LP played first in
3 of 6. Pairs 1-2 were answered on 2026-11-13; the machine rebooted, and pairs 3-6 were answered on 2026-11-14 in the same session
(it resumes at the first unanswered item). Joined by the overseer from `answers.csv` and `key/key.json`.

| order | pair | first / second | answer | picked | replays | note (verbatim) |
|---|---|---|---|---|---|---|
| 1 | C04_V1 | old / LP | second | LP | 1 | |
| 2 | C10_V1 | old / LP | second | LP | 0 | |
| 3 | C04_V2 | LP / old | first | LP | 1 | Almost the same, perhaps first a bit better, unsure |
| 4 | C06_V2 | LP / old | first | LP | 0 | First may be a bit better, very close |
| 5 | C09_V2 | LP / old | second | old | 0 | Similar, perhaps second? |
| 6 | C09_V1 | old / LP | same | same | 0 | cant tell... |

Totals: LP 4, old 1, same 1. By variant: V1 LP 2, same 1; V2 LP 2, old 1. By position: first 2, second 3, same 1. LP was picked in 2 of
the 3 pairs where it played first, and in 2 of the 3 where it played second. The notes on pairs 3-6 say the two were close or that Kosta
was unsure; pairs 1-2 have no note.
