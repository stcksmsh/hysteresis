# T0 report (work order 37, BRAIN_SPEC 7.59 / 7.60; numbers only, no verdict)

Rules `T0_RULES.md`. Groups per split: {'train': 303, 'validation': 40, 'test': 60}. Missing npz: 0. Run time of the sequence stage: 728 s. Data: `t0/numbers.json`.

## Per dataset, copy and split

| dataset | copy | split | dancers | windows | kept | usable h | weighted usable h | tails dropped | tokens | masked tokens | failed parts |
|---|---|---|---|---|---|---|---|---|---|---|---|
| aioz | V1 | test | 413 | 559 | 486 | 2.70 | 1.14 | 413 | 30221 | 12322 | limits 72, motion 2 |
| aioz | V1 | train | 1336 | 1808 | 1586 | 8.81 | 3.87 | 1334 | 99959 | 39274 | endstop 3, limits 217, motion 2 |
| aioz | V1 | validation | 103 | 151 | 122 | 0.68 | 0.33 | 103 | 8340 | 3182 | endstop 2, limits 21, motion 7 |
| aioz | V1m | test | 413 | 559 | 459 | 2.55 | 1.02 | 413 | 30221 | 12322 | limits 99, motion 2 |
| aioz | V1m | train | 1336 | 1808 | 1551 | 8.62 | 3.79 | 1334 | 99959 | 39274 | endstop 1, limits 255, motion 1 |
| aioz | V1m | validation | 103 | 151 | 116 | 0.64 | 0.32 | 103 | 8340 | 3182 | endstop 3, limits 26, motion 6 |
| aioz | V2 | test | 413 | 559 | 553 | 3.07 | 1.27 | 413 | 30221 | 12322 | endstop 5, limits 1 |
| aioz | V2 | train | 1336 | 1808 | 1775 | 9.86 | 4.32 | 1334 | 99959 | 39274 | endstop 26, limits 17, motion 3 |
| aioz | V2 | validation | 103 | 151 | 142 | 0.79 | 0.39 | 103 | 8340 | 3182 | endstop 2, limits 3, motion 5 |
| aioz | V2m | test | 413 | 559 | 551 | 3.06 | 1.26 | 413 | 30221 | 12322 | endstop 8, limits 1 |
| aioz | V2m | train | 1336 | 1808 | 1774 | 9.86 | 4.32 | 1334 | 99959 | 39274 | endstop 23, limits 7, motion 8 |
| aioz | V2m | validation | 103 | 151 | 142 | 0.79 | 0.39 | 103 | 8340 | 3182 | endstop 3, motion 6 |
| finedance | V1 | test | 23 | 145 | 88 | 0.49 | 0.41 | 23 | 6166 | 713 | endstop 16, limits 40, motion 4 |
| finedance | V1 | train | 154 | 963 | 603 | 3.35 | 2.83 | 152 | 41520 | 4774 | endstop 126, limits 251, motion 34 |
| finedance | V1 | validation | 26 | 171 | 115 | 0.64 | 0.49 | 26 | 7266 | 806 | endstop 17, limits 37, motion 9 |
| finedance | V1m | test | 23 | 145 | 112 | 0.62 | 0.51 | 23 | 6166 | 713 | endstop 14, limits 21, motion 3 |
| finedance | V1m | train | 154 | 963 | 663 | 3.68 | 3.11 | 152 | 41520 | 4774 | clearance 1, endstop 90, limits 208, motion 38 |
| finedance | V1m | validation | 26 | 171 | 114 | 0.63 | 0.47 | 26 | 7266 | 806 | endstop 13, limits 36, motion 10 |
| finedance | V2 | test | 23 | 145 | 107 | 0.59 | 0.49 | 23 | 6166 | 713 | clearance 2, contact 3, endstop 26, limits 15, motion 4 |
| finedance | V2 | train | 154 | 963 | 637 | 3.54 | 2.98 | 152 | 41520 | 4774 | clearance 26, contact 30, endstop 245, limits 143, motion 29, guard 8 |
| finedance | V2 | validation | 26 | 171 | 108 | 0.60 | 0.46 | 26 | 7266 | 806 | clearance 2, contact 2, endstop 49, limits 26, motion 5, guard 1 |
| finedance | V2m | test | 23 | 145 | 99 | 0.55 | 0.45 | 23 | 6166 | 713 | clearance 1, contact 2, endstop 32, limits 22, motion 4, guard 1 |
| finedance | V2m | train | 154 | 963 | 641 | 3.56 | 3.00 | 152 | 41520 | 4774 | clearance 25, contact 27, endstop 239, limits 131, motion 29, guard 4 |
| finedance | V2m | validation | 26 | 171 | 109 | 0.61 | 0.47 | 26 | 7266 | 806 | clearance 6, contact 3, endstop 50, limits 19, motion 6, guard 2 |

## Per dataset, genre and copy

| dataset | genre | copy | dancers | windows | kept | usable h | failed parts |
|---|---|---|---|---|---|---|---|
| aioz | aerobic | V1 | 547 | 765 | 661 | 3.67 | endstop 2, limits 102, motion 1 |
| aioz | aerobic | V1m | 547 | 765 | 642 | 3.57 | endstop 3, limits 119, motion 1 |
| aioz | aerobic | V2 | 547 | 765 | 745 | 4.14 | endstop 15, limits 15 |
| aioz | aerobic | V2m | 547 | 765 | 751 | 4.17 | endstop 10, limits 3, motion 3 |
| aioz | bollywood | V1 | 91 | 128 | 111 | 0.62 | limits 15, motion 2 |
| aioz | bollywood | V1m | 91 | 128 | 113 | 0.63 | limits 14, motion 1 |
| aioz | bollywood | V2 | 91 | 128 | 128 | 0.71 | - |
| aioz | bollywood | V2m | 91 | 128 | 127 | 0.71 | motion 1 |
| aioz | commercial | V1 | 551 | 614 | 534 | 2.97 | endstop 3, limits 71, motion 7 |
| aioz | commercial | V1m | 551 | 614 | 520 | 2.89 | endstop 1, limits 87, motion 7 |
| aioz | commercial | V2 | 551 | 614 | 597 | 3.32 | endstop 10, limits 3, motion 6 |
| aioz | commercial | V2m | 551 | 614 | 595 | 3.31 | endstop 14, limits 2, motion 5 |
| aioz | irish | V1 | 7 | 8 | 8 | 0.04 | - |
| aioz | irish | V1m | 7 | 8 | 8 | 0.04 | - |
| aioz | irish | V2 | 7 | 8 | 8 | 0.04 | - |
| aioz | irish | V2m | 7 | 8 | 8 | 0.04 | - |
| aioz | rumba | V1 | 149 | 233 | 201 | 1.12 | limits 32 |
| aioz | rumba | V1m | 149 | 233 | 196 | 1.09 | limits 37 |
| aioz | rumba | V2 | 149 | 233 | 233 | 1.29 | - |
| aioz | rumba | V2m | 149 | 233 | 230 | 1.28 | motion 3 |
| aioz | samba | V1 | 56 | 90 | 81 | 0.45 | limits 9 |
| aioz | samba | V1m | 56 | 90 | 79 | 0.44 | limits 11 |
| aioz | samba | V2 | 56 | 90 | 88 | 0.49 | endstop 2, limits 1 |
| aioz | samba | V2m | 56 | 90 | 88 | 0.49 | endstop 2 |
| aioz | zumba | V1 | 451 | 680 | 598 | 3.32 | limits 81, motion 1 |
| aioz | zumba | V1m | 451 | 680 | 568 | 3.16 | limits 112 |
| aioz | zumba | V2 | 451 | 680 | 671 | 3.73 | endstop 6, limits 2, motion 2 |
| aioz | zumba | V2m | 451 | 680 | 668 | 3.71 | endstop 8, limits 3, motion 2 |
| finedance | breaking | V1 | 13 | 38 | 17 | 0.09 | endstop 18, limits 7, motion 2 |
| finedance | breaking | V1m | 13 | 38 | 16 | 0.09 | endstop 11, limits 13, motion 2 |
| finedance | breaking | V2 | 13 | 38 | 10 | 0.06 | clearance 2, contact 1, endstop 24, limits 18, motion 3, guard 2 |
| finedance | breaking | V2m | 13 | 38 | 12 | 0.07 | clearance 1, contact 2, endstop 23, limits 19, motion 2 |
| finedance | chinese | V1 | 4 | 28 | 20 | 0.11 | limits 7, motion 1 |
| finedance | chinese | V1m | 4 | 28 | 22 | 0.12 | endstop 1, limits 4, motion 1 |
| finedance | chinese | V2 | 4 | 28 | 21 | 0.12 | endstop 6, limits 2, motion 1 |
| finedance | chinese | V2m | 4 | 28 | 18 | 0.10 | endstop 8, limits 3, motion 1 |
| finedance | choreography | V1 | 6 | 33 | 20 | 0.11 | limits 10, motion 3 |
| finedance | choreography | V1m | 6 | 33 | 20 | 0.11 | endstop 1, limits 9, motion 3 |
| finedance | choreography | V2 | 6 | 33 | 23 | 0.13 | endstop 4, limits 4, motion 3 |
| finedance | choreography | V2m | 6 | 33 | 24 | 0.13 | clearance 1, endstop 4, limits 4, motion 3 |
| finedance | dai | V1 | 10 | 100 | 60 | 0.33 | endstop 26, limits 23, motion 4 |
| finedance | dai | V1m | 10 | 100 | 60 | 0.33 | endstop 24, limits 19, motion 6 |
| finedance | dai | V2 | 10 | 100 | 53 | 0.29 | clearance 11, contact 2, endstop 38, limits 10, motion 4, guard 4 |
| finedance | dai | V2m | 10 | 100 | 50 | 0.28 | clearance 8, contact 3, endstop 44, limits 11, motion 5, guard 2 |
| finedance | dunhuang | V1 | 2 | 12 | 5 | 0.03 | endstop 4, limits 5, motion 1 |
| finedance | dunhuang | V1m | 2 | 12 | 7 | 0.04 | endstop 1, limits 3, motion 1 |
| finedance | dunhuang | V2 | 2 | 12 | 9 | 0.05 | endstop 2, limits 2, motion 1 |
| finedance | dunhuang | V2m | 2 | 12 | 6 | 0.03 | endstop 3, limits 2, motion 2 |
| finedance | hantang | V1 | 11 | 105 | 62 | 0.34 | endstop 17, limits 20, motion 11 |
| finedance | hantang | V1m | 11 | 105 | 62 | 0.34 | endstop 10, limits 24, motion 12 |
| finedance | hantang | V2 | 11 | 105 | 64 | 0.36 | clearance 8, contact 6, endstop 34, limits 13, motion 6, guard 2 |
| finedance | hantang | V2m | 11 | 105 | 58 | 0.32 | clearance 3, contact 6, endstop 35, limits 10, motion 7, guard 2 |
| finedance | hiphop | V1 | 18 | 138 | 90 | 0.50 | limits 42, motion 8 |
| finedance | hiphop | V1m | 18 | 138 | 104 | 0.58 | limits 29, motion 7 |
| finedance | hiphop | V2 | 18 | 138 | 80 | 0.44 | endstop 44, limits 30, motion 7 |
| finedance | hiphop | V2m | 18 | 138 | 81 | 0.45 | endstop 44, limits 28, motion 6 |
| finedance | jazz | V1 | 21 | 105 | 69 | 0.38 | endstop 9, limits 30, motion 1 |
| finedance | jazz | V1m | 21 | 105 | 76 | 0.42 | endstop 7, limits 24, motion 2 |
| finedance | jazz | V2 | 21 | 105 | 70 | 0.39 | clearance 2, contact 1, endstop 26, limits 20, motion 3 |
| finedance | jazz | V2m | 21 | 105 | 66 | 0.37 | clearance 2, contact 1, endstop 25, limits 23, motion 3, guard 1 |
| finedance | korean | V1 | 35 | 171 | 103 | 0.57 | endstop 9, limits 58, motion 6 |
| finedance | korean | V1m | 35 | 171 | 114 | 0.63 | clearance 1, endstop 13, limits 46, motion 5 |
| finedance | korean | V2 | 35 | 171 | 119 | 0.66 | contact 1, endstop 28, limits 33, motion 2 |
| finedance | korean | V2m | 35 | 171 | 130 | 0.72 | clearance 1, endstop 22, limits 20, motion 2 |
| finedance | kun | V1 | 1 | 8 | 6 | 0.03 | endstop 2 |
| finedance | kun | V1m | 1 | 8 | 6 | 0.03 | endstop 2 |
| finedance | kun | V2 | 1 | 8 | 8 | 0.04 | - |
| finedance | kun | V2m | 1 | 8 | 8 | 0.04 | - |
| finedance | locking | V1 | 3 | 21 | 14 | 0.08 | limits 7 |
| finedance | locking | V1m | 3 | 21 | 13 | 0.07 | limits 8 |
| finedance | locking | V2 | 3 | 21 | 16 | 0.09 | endstop 4, limits 4 |
| finedance | locking | V2m | 3 | 21 | 15 | 0.08 | clearance 1, endstop 4, limits 4 |
| finedance | miao | V1 | 10 | 79 | 41 | 0.23 | endstop 18, limits 29 |
| finedance | miao | V1m | 10 | 79 | 58 | 0.32 | endstop 2, limits 19 |
| finedance | miao | V2 | 10 | 79 | 72 | 0.40 | endstop 2, limits 5 |
| finedance | miao | V2m | 10 | 79 | 73 | 0.41 | clearance 1, endstop 3, limits 2 |
| finedance | popping | V1 | 21 | 115 | 84 | 0.47 | endstop 3, limits 22, motion 6 |
| finedance | popping | V1m | 21 | 115 | 87 | 0.48 | endstop 5, limits 19, motion 6 |
| finedance | popping | V2 | 21 | 115 | 93 | 0.52 | contact 1, endstop 16, limits 5, motion 4 |
| finedance | popping | V2m | 21 | 115 | 92 | 0.51 | endstop 16, limits 11, motion 4 |
| finedance | shenyun | V1 | 34 | 219 | 141 | 0.78 | endstop 43, limits 44, motion 4 |
| finedance | shenyun | V1m | 34 | 219 | 156 | 0.87 | endstop 35, limits 31, motion 6 |
| finedance | shenyun | V2 | 34 | 219 | 134 | 0.74 | clearance 6, contact 17, endstop 77, limits 24, motion 3, guard 1 |
| finedance | shenyun | V2m | 34 | 219 | 129 | 0.72 | clearance 12, contact 15, endstop 79, limits 28, motion 3, guard 2 |
| finedance | urban | V1 | 6 | 31 | 21 | 0.12 | limits 10 |
| finedance | urban | V1m | 6 | 31 | 31 | 0.17 | - |
| finedance | urban | V2 | 6 | 31 | 20 | 0.11 | contact 2, endstop 3, limits 8, motion 1 |
| finedance | urban | V2m | 6 | 31 | 20 | 0.11 | clearance 1, contact 1, endstop 5, limits 4, motion 1 |
| finedance | wei | V1 | 8 | 76 | 53 | 0.29 | endstop 10, limits 14 |
| finedance | wei | V1m | 8 | 76 | 57 | 0.32 | endstop 5, limits 17 |
| finedance | wei | V2 | 8 | 76 | 60 | 0.33 | clearance 1, contact 4, endstop 12, limits 6 |
| finedance | wei | V2m | 8 | 76 | 67 | 0.37 | clearance 1, contact 4, endstop 6, limits 3 |

## Weights (V1 copy; 1.0 = uncapped)

- finedance: {'n': 203, 'mean': 0.8649369591262915, 'min': 0.5, 'capped_dancers': 62}
- aioz: {'n': 1852, 'mean': 0.43412526997840173, 'min': 0.14285714285714285, 'capped_dancers': 1570}

## Jitter of the stored targets (median over dancers; 100 Hz; V1, V2 copies; report only, AIOZ vs FineDance)

| variant | joint | FineDance acc sign changes /s | AIOZ | FineDance power > 3 Hz | AIOZ |
|---|---|---|---|---|---|
| V1 | base_yaw | 2.75 | 2.84 | 0.0010 | 0.0008 |
| V1 | shoulder | 3.24 | 3.11 | 0.0030 | 0.0009 |
| V1 | elbow | 3.18 | 3.24 | 0.0037 | 0.0017 |
| V1 | wrist_bend | 3.68 | 4.01 | 0.0092 | 0.0118 |
| V1 | wrist_roll | 3.74 | 4.02 | 0.0079 | 0.0139 |
| V2 | base_yaw | 4.76 | 5.12 | 0.0334 | 0.0200 |
| V2 | shoulder | 5.10 | 5.87 | 0.0622 | 0.0573 |
| V2 | elbow | 5.51 | 5.66 | 0.0700 | 0.0368 |
| V2 | wrist_bend | 6.89 | 7.33 | 0.1364 | 0.2033 |
| V2 | wrist_roll | 7.68 | 6.75 | 0.1647 | 0.1084 |

## Notes

- Token coverage: a masked token has at least one surprisal layer undefined (clip starts; the deeper layers have longer horizons); its undefined columns are 0 after standardising.
- Gate parts count windows that failed that part (a window can fail several). Usable hours = kept windows x 20 s.
- Estimate from one long FineDance sequence: see `numbers.json` key `estimate`.
