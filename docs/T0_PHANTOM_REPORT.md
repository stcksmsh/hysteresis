# T0 for PhantomDance and Motorica: report (work order 42, BRAIN_SPEC 7.69; numbers only, no verdict)

Rules and mapping `T0_PHANTOM_RULES.md`; T0 as `T0_RULES.md` (gates at 1.25, V1 / V2 + mirror, cutoffs 2.50 / 5.75 Hz). FineDance = the reference, same measures, same code. Aggregates only:
Motorica data and anything derived stay on this laptop; no per-file Motorica numbers are written here.

## phantom

- Sequences 260, 9.502 h, split seed 42001, groups per split {'train': 195, 'validation': 26, 'test': 39}. Missing npz: 0. Excluded as check / danced song: []. Also in FineDance by name: [] (PhantomDance carries no names; by audio hash none can match, the sample rates differ).

### Hours kept after the gates (20 s windows, per copy)

| copy | windows | kept | share | usable h |
|---|---|---|---|---|
| V1 | 1582 | 723 | 0.46 | 4.02 |
| V2 | 1582 | 954 | 0.60 | 5.30 |
| V1m | 1582 | 831 | 0.53 | 4.62 |
| V2m | 1582 | 963 | 0.61 | 5.35 |

Four copies together: 19.28 usable hours.

### By split

| copy | split | dancers | windows | kept | usable h | failed parts |
|---|---|---|---|---|---|---|
| V1m | test | 39 | 224 | 119 | 0.66 | clearance 4, endstop 33, limits 63, motion 16 |
| V1m | train | 195 | 1233 | 646 | 3.59 | clearance 26, endstop 174, limits 354, motion 122, guard 5 |
| V1m | validation | 26 | 125 | 66 | 0.37 | clearance 2, endstop 14, limits 35, motion 17 |
| V1 | test | 39 | 224 | 112 | 0.62 | clearance 2, endstop 34, limits 75, motion 17 |
| V1 | train | 195 | 1233 | 561 | 3.12 | clearance 33, endstop 167, limits 461, motion 113, guard 4 |
| V1 | validation | 26 | 125 | 50 | 0.28 | clearance 6, endstop 12, limits 47, motion 20 |
| V2m | test | 39 | 224 | 155 | 0.86 | clearance 1, contact 2, endstop 42, limits 29, motion 10, guard 1 |
| V2m | train | 195 | 1233 | 723 | 4.02 | clearance 6, contact 26, endstop 328, limits 208, motion 102, guard 10 |
| V2m | validation | 26 | 125 | 85 | 0.47 | contact 1, endstop 25, limits 14, motion 9 |
| V2 | test | 39 | 224 | 157 | 0.87 | clearance 2, contact 3, endstop 33, limits 35, motion 13, guard 1 |
| V2 | train | 195 | 1233 | 716 | 3.98 | clearance 6, contact 29, endstop 314, limits 225, motion 104, guard 4 |
| V2 | validation | 26 | 125 | 81 | 0.45 | clearance 1, contact 3, endstop 25, limits 15, motion 10 |

### Genres (V1 copy)

| genre | dancers | hours | usable h | kept share |
|---|---|---|---|---|
| unlabelled | 260 | 9.50 | 4.02 | 0.46 |
## motorica

- Sequences 74, 3.558 h, split seed 42002, groups per split {'train': 56, 'validation': 7, 'test': 11}. Missing npz: 0. Excluded as check / danced song: []. Also in FineDance by name: [].

### Hours kept after the gates (20 s windows, per copy)

| copy | windows | kept | share | usable h |
|---|---|---|---|---|
| V1 | 607 | 442 | 0.73 | 2.46 |
| V2 | 607 | 418 | 0.69 | 2.32 |
| V1m | 607 | 463 | 0.76 | 2.57 |
| V2m | 607 | 416 | 0.69 | 2.31 |

Four copies together: 9.66 usable hours.

### By split

| copy | split | dancers | windows | kept | usable h | failed parts |
|---|---|---|---|---|---|---|
| V1m | test | 11 | 98 | 71 | 0.39 | endstop 7, limits 20, motion 1 |
| V1m | train | 56 | 456 | 345 | 1.92 | endstop 8, limits 96, motion 9 |
| V1m | validation | 7 | 53 | 47 | 0.26 | limits 6 |
| V1 | test | 11 | 98 | 75 | 0.42 | limits 22, motion 1 |
| V1 | train | 56 | 456 | 328 | 1.82 | endstop 3, limits 120, motion 6 |
| V1 | validation | 7 | 53 | 39 | 0.22 | endstop 1, limits 13 |
| V2m | test | 11 | 98 | 73 | 0.41 | clearance 1, contact 1, endstop 11, limits 18 |
| V2m | train | 56 | 456 | 311 | 1.73 | clearance 2, contact 2, endstop 62, limits 104, motion 1 |
| V2m | validation | 7 | 53 | 32 | 0.18 | endstop 9, limits 16 |
| V2 | test | 11 | 98 | 70 | 0.39 | contact 1, endstop 16, limits 15 |
| V2 | train | 56 | 456 | 319 | 1.77 | contact 2, endstop 65, limits 96, motion 3 |
| V2 | validation | 7 | 53 | 29 | 0.16 | endstop 9, limits 20 |

### Genres (V1 copy)

| genre | dancers | hours | usable h | kept share |
|---|---|---|---|---|
| jazz | 17 | 0.99 | 0.67 | 0.71 |
| street | 57 | 2.56 | 1.79 | 0.74 |

## FineDance reference (kept share per copy)

| copy | windows | kept | share |
|---|---|---|---|
| V1 | 1279 | 806 | 0.63 |
| V2 | 1279 | 852 | 0.67 |
| V1m | 1279 | 889 | 0.70 |
| V2m | 1279 | 849 | 0.66 |

## Jitter of the stored targets (median over dancers; 100 Hz; acc sign changes per s | power > 3 Hz)

| variant | joint | FineDance | PhantomDance | Motorica |
|---|---|---|---|---|
| V1 | base_yaw | 2.75 \| 0.0010 | 2.57 \| 0.0026 | 3.18 \| 0.0022 |
| V1 | shoulder | 3.24 \| 0.0030 | 2.98 \| 0.0052 | 3.61 \| 0.0059 |
| V1 | elbow | 3.18 \| 0.0037 | 2.94 \| 0.0065 | 3.71 \| 0.0085 |
| V1 | wrist_bend | 3.68 \| 0.0092 | 3.04 \| 0.0137 | 3.91 \| 0.0130 |
| V1 | wrist_roll | 3.74 \| 0.0079 | 3.09 \| 0.0110 | 4.09 \| 0.0176 |
| V2 | base_yaw | 4.76 \| 0.0334 | 4.75 \| 0.0502 | 6.62 \| 0.0622 |
| V2 | shoulder | 5.10 \| 0.0622 | 5.19 \| 0.0771 | 6.27 \| 0.0668 |
| V2 | elbow | 5.51 \| 0.0700 | 5.52 \| 0.1066 | 6.64 \| 0.0964 |
| V2 | wrist_bend | 6.89 \| 0.1364 | 5.17 \| 0.0944 | 7.42 \| 0.1669 |
| V2 | wrist_roll | 7.68 \| 0.1647 | 5.08 \| 0.0944 | 7.09 \| 0.1290 |

## Gesture amplitude (target minus 0.5 Hz posture; kept windows only; median over dancers; deg; rms, p5 .. p95)

| variant | joint | FineDance | PhantomDance | Motorica |
|---|---|---|---|---|
| V1 | base_yaw | 2.7, -4.4 .. 4.5 | 2.5, -4.1 .. 4.1 | 2.6, -4.4 .. 4.4 |
| V1 | shoulder | 7.9, -13.7 .. 12.8 | 7.8, -13.5 .. 12.5 | 7.6, -13.5 .. 12.6 |
| V1 | elbow | 15.7, -26.7 .. 27.4 | 18.2, -31.5 .. 30.9 | 17.3, -28.2 .. 29.9 |
| V1 | wrist_bend | 14.7, -24.7 .. 24.4 | 16.6, -26.9 .. 27.6 | 16.6, -28.4 .. 28.8 |
| V1 | wrist_roll | 18.0, -31.7 .. 28.9 | 26.8, -46.2 .. 43.9 | 19.0, -32.7 .. 30.3 |
| V2 | base_yaw | 2.4, -4.0 .. 4.0 | 2.3, -3.8 .. 3.9 | 2.4, -3.9 .. 3.9 |
| V2 | shoulder | 4.4, -7.0 .. 6.8 | 4.5, -6.6 .. 6.7 | 5.1, -8.1 .. 8.1 |
| V2 | elbow | 7.9, -12.5 .. 12.6 | 6.5, -10.3 .. 10.1 | 10.0, -16.4 .. 16.0 |
| V2 | wrist_bend | 11.5, -18.5 .. 18.6 | 11.4, -18.9 .. 17.8 | 10.4, -17.2 .. 17.4 |
| V2 | wrist_roll | 18.4, -29.8 .. 29.9 | 18.4, -30.1 .. 29.5 | 25.4, -41.4 .. 43.2 |

## Band limit (7.69 overseer note)

5 FineDance songs (fd_033, fd_046, fd_051, fd_126, fd_211), first 120 s each, original against the same audio low-passed at 8 kHz (zero-phase Butterworth order 8). Differences are in the standardised units of the cortex input (46 columns = 44 ear features + 2 beat-phase columns); mean over the 5 songs.

| column | rms difference | correlation |
|---|---|---|
| logmel0 | 0.000 | 1.000 |
| logmel1 | 0.000 | 1.000 |
| logmel2 | 0.000 | 1.000 |
| logmel3 | 0.000 | 1.000 |
| logmel4 | 0.000 | 1.000 |
| logmel5 | 0.000 | 1.000 |
| logmel6 | 0.000 | 1.000 |
| logmel7 | 0.000 | 1.000 |
| logmel8 | 0.000 | 1.000 |
| logmel9 | 0.000 | 1.000 |
| logmel10 | 0.000 | 1.000 |
| logmel11 | 0.000 | 1.000 |
| logmel12 | 0.000 | 1.000 |
| logmel13 | 0.000 | 1.000 |
| logmel14 | 0.000 | 1.000 |
| logmel15 | 0.000 | 1.000 |
| logmel16 | 0.000 | 1.000 |
| logmel17 | 0.000 | 1.000 |
| logmel18 | 0.000 | 1.000 |
| logmel19 | 0.000 | 1.000 |
| logmel20 | 0.000 | 1.000 |
| logmel21 | 0.000 | 1.000 |
| logmel22 | 0.000 | 1.000 |
| logmel23 | 0.001 | 1.000 |
| logmel24 | 0.009 | 1.000 |
| logmel25 | 0.071 | 0.999 |
| logmel26 | 0.319 | 0.991 |
| logmel27 | 0.867 | 0.974 |
| logmel28 | 1.654 | 0.908 |
| logmel29 | 2.125 | 0.583 |
| logmel30 | 2.100 | 0.051 |
| logmel31 | 1.883 | 0.004 |
| flux0 | 0.000 | 1.000 |
| flux1 | 0.000 | 1.000 |
| flux2 | 0.000 | 1.000 |
| flux3 | 0.000 | 1.000 |
| flux4 | 0.000 | 1.000 |
| flux5 | 0.000 | 1.000 |
| flux6 | 0.521 | 0.926 |
| flux7 | 1.230 | 0.027 |
| onset | 0.128 | 0.987 |
| rms | 0.011 | 1.000 |
| centroid | 0.507 | 0.908 |
| flatness | 0.203 | 0.857 |
| beat_a | 0.576 | 0.658 |
| beat_b | 0.569 | 0.667 |

Cortex lane shift (mean abs difference; the lane's own standard deviation in brackets; mean over the 5 songs):

- arousal_b7: 0.2864 (0.7914), correlation 0.943
- s10: 0.2495 (0.8971)
- ee: 0.1949 (0.6081)
- h_abs: 0.5091 (3.0130)
- y: 0.3248 (1.9105)

Share of the power above 8 kHz in the source audio (20 songs each, first 60 s): finedance: median 5.42e-03, p90 1.71e-02, max 3.79e-02; phantom: median 3.76e-13, p90 5.18e-09, max 3.85e-05; motorica: median 3.13e-03, p90 6.48e-03, max 2.20e-02.
