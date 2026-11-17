# Cortex surprisal as event detector: report (BRAIN_SPEC 7.79 Step 2)

Report only, no verdict. Rules: `docs/CORTEX_EVENTS_RULES.md` (pushed before any result, commit 81f82e6). Code
`scripts/body/cortexev.py`, test `scripts/body/test_cortexev.py`. Outputs in `/secondary/hyst-data/body/cortexev/`: `songs.json`,
`per_song.json` (events, peaks and per-pair counts per song), `results.json` (every score and the lag profiles), `tables.md` (the tables
below), `v4_events.md` (ear-check sheet for Kosta, not served).

## Data and song set

- Cortex surprisal: the stored T0 lanes (`s10`, B7 epoch 6, 10 Hz), all four datasets. Nothing in the cortex was recomputed.
- 210 songs: the 10 V4 songs + 200 sampled (seed 79203), 52-53 per dataset after adding the V4 songs (FineDance 53, AIOZ 52,
  PhantomDance 53, Motorica 52). Eligible pools (duration ≥ 28 s, V4 excluded, one AIOZ clip per YouTube id): FineDance 196,
  AIOZ 181, PhantomDance 253, Motorica 71. Scoring span 16 s to end; 6.35 h scored in total.
- Reference events found (in span): drop 292 (77 songs), dropout onset 76 (49 songs), dropout end 37 (23 songs), section change 817
  (193 songs); any = 1,222. Manifest boundaries: V4 songs only (10 songs).

## Headline: F1 at ±0.5 s, F1 (excess over circular-shift chance [95 % bootstrap CI over songs])

| detector | drop | dropout_on | dropout_end | section | any |
|---|---|---|---|---|---|
| L1 | 0.047 (+0.022 [+0.012, +0.032]) | 0.016 (+0.010 [+0.006, +0.013]) | 0.007 (+0.004 [+0.001, +0.006]) | 0.090 (+0.027 [+0.018, +0.037]) | 0.138 (+0.051 [+0.039, +0.064]) |
| L2 | 0.045 (+0.020 [+0.010, +0.032]) | 0.020 (+0.014 [+0.009, +0.020]) | 0.009 (+0.006 [+0.002, +0.011]) | 0.110 (+0.050 [+0.038, +0.062]) | 0.154 (+0.074 [+0.058, +0.090]) |
| L3 | 0.045 (+0.022 [+0.009, +0.036]) | 0.009 (+0.004 [-0.001, +0.010]) | 0.010 (+0.007 [+0.002, +0.013]) | 0.040 (-0.012 [-0.022, +0.000]) | 0.075 (+0.010 [-0.003, +0.024]) |
| L4 | 0.027 (+0.004 [-0.007, +0.015]) | 0.011 (+0.006 [-0.001, +0.015]) | 0.008 (+0.006 [-0.001, +0.015]) | 0.064 (+0.020 [+0.005, +0.037]) | 0.078 (+0.025 [+0.009, +0.040]) |
| total | 0.062 (+0.036 [+0.021, +0.053]) | 0.014 (+0.008 [+0.003, +0.015]) | 0.013 (+0.010 [+0.004, +0.016]) | 0.093 (+0.034 [+0.020, +0.049]) | 0.146 (+0.069 [+0.051, +0.087]) |
| E-onset | 0.040 (+0.014 [+0.008, +0.021]) | 0.001 (-0.006 [-0.008, -0.004]) | 0.005 (+0.002 [-0.000, +0.005]) | 0.069 (+0.006 [-0.001, +0.014]) | 0.102 (+0.014 [+0.005, +0.024]) |
| E-lowflux | 0.068 (+0.044 [+0.030, +0.061]) | 0.003 (-0.003 [-0.005, -0.001]) | 0.006 (+0.003 [+0.001, +0.005]) | 0.069 (+0.004 [-0.004, +0.012]) | 0.129 (+0.040 [+0.026, +0.057]) |
| E-change | 0.068 (+0.042 [+0.025, +0.063]) | 0.008 (+0.002 [-0.002, +0.006]) | 0.010 (+0.008 [+0.002, +0.014]) | 0.048 (-0.010 [-0.019, -0.000]) | 0.108 (+0.031 [+0.015, +0.047]) |
| drop (ear) | — | 0.005 (-0.003 [-0.012, +0.013]) | 0.006 (+0.001 [-0.008, +0.016]) | 0.029 (+0.007 [-0.010, +0.024]) | 0.029 (+0.006 [-0.011, +0.023]) |
| dropout_on (ear) | 0.005 (-0.003 [-0.012, +0.012]) | — | 0.335 (+0.320 [+0.183, +0.470]) | 0.014 (+0.008 [-0.001, +0.019]) | 0.039 (+0.032 [+0.015, +0.051]) |
| dropout_end (ear) | 0.006 (+0.001 [-0.008, +0.015]) | 0.335 (+0.321 [+0.184, +0.472]) | — | 0.002 (-0.001 [-0.004, +0.005]) | 0.036 (+0.031 [+0.014, +0.052]) |
| section (ear) | 0.029 (+0.007 [-0.010, +0.025]) | 0.014 (+0.009 [-0.000, +0.019]) | 0.002 (-0.001 [-0.004, +0.005]) | — | 0.037 (+0.012 [-0.006, +0.031]) |

Rows: L1-L4 and total = cortex surprisal peaks; E-* = simple ear peak detectors with the cortex's exact peak rule; the last four rows =
the ear event detectors scored against the other types ("any" excludes the detector's own type). Chance p (200 shifts) for every cortex
layer vs any is 0.005 (the floor) except L3 (0.100).

## F1 at ±1 s (same layout)

| detector | drop | dropout_on | dropout_end | section | any |
|---|---|---|---|---|---|
| L1 | 0.073 (+0.023 [+0.015, +0.031]) | 0.021 (+0.009 [+0.005, +0.012]) | 0.011 (+0.004 [+0.001, +0.008]) | 0.144 (+0.021 [+0.010, +0.031]) | 0.211 (+0.044 [+0.031, +0.056]) |
| L2 | 0.082 (+0.033 [+0.021, +0.045]) | 0.036 (+0.026 [+0.018, +0.035]) | 0.016 (+0.011 [+0.005, +0.018]) | 0.234 (+0.114 [+0.099, +0.128]) | 0.301 (+0.145 [+0.125, +0.164]) |
| L3 | 0.073 (+0.027 [+0.010, +0.045]) | 0.031 (+0.020 [+0.011, +0.029]) | 0.021 (+0.015 [+0.007, +0.023]) | 0.090 (-0.013 [-0.026, +0.001]) | 0.152 (+0.025 [+0.008, +0.042]) |
| L4 | 0.057 (+0.012 [-0.001, +0.025]) | 0.031 (+0.023 [+0.010, +0.037]) | 0.013 (+0.009 [+0.000, +0.019]) | 0.100 (+0.013 [-0.003, +0.031]) | 0.135 (+0.031 [+0.014, +0.049]) |
| total | 0.090 (+0.039 [+0.022, +0.057]) | 0.037 (+0.027 [+0.018, +0.039]) | 0.021 (+0.016 [+0.007, +0.025]) | 0.184 (+0.068 [+0.051, +0.087]) | 0.258 (+0.109 [+0.086, +0.133]) |
| E-onset | 0.066 (+0.015 [+0.006, +0.024]) | 0.007 (-0.005 [-0.007, -0.002]) | 0.006 (+0.000 [-0.002, +0.002]) | 0.130 (+0.006 [-0.003, +0.015]) | 0.182 (+0.013 [+0.002, +0.024]) |
| E-lowflux | 0.075 (+0.026 [+0.017, +0.037]) | 0.008 (-0.004 [-0.006, -0.001]) | 0.006 (+0.001 [-0.001, +0.002]) | 0.130 (+0.002 [-0.009, +0.012]) | 0.191 (+0.021 [+0.007, +0.035]) |
| E-change | 0.102 (+0.050 [+0.035, +0.065]) | 0.035 (+0.025 [+0.016, +0.033]) | 0.016 (+0.010 [+0.003, +0.019]) | 0.252 (+0.137 [+0.119, +0.155]) | 0.325 (+0.175 [+0.156, +0.194]) |
| drop (ear) | — | 0.011 (-0.004 [-0.019, +0.016]) | 0.006 (-0.004 [-0.015, +0.011]) | 0.063 (+0.020 [+0.001, +0.039]) | 0.062 (+0.016 [-0.001, +0.032]) |
| dropout_on (ear) | 0.011 (-0.005 [-0.020, +0.015]) | — | 0.512 (+0.483 [+0.317, +0.609]) | 0.020 (+0.010 [-0.001, +0.024]) | 0.062 (+0.047 [+0.022, +0.075]) |
| dropout_end (ear) | 0.006 (-0.004 [-0.015, +0.011]) | 0.512 (+0.483 [+0.317, +0.609]) | — | 0.007 (+0.001 [-0.005, +0.011]) | 0.055 (+0.046 [+0.022, +0.070]) |
| section (ear) | 0.063 (+0.020 [+0.001, +0.038]) | 0.020 (+0.011 [-0.001, +0.024]) | 0.007 (+0.002 [-0.005, +0.011]) | — | 0.076 (+0.028 [+0.008, +0.049]) |

## Detail vs `any` (precision, recall, peak counts)

| detector | peaks | P ±0.5 | R ±0.5 | F1 ±0.5 [CI] | chance | P ±1 | R ±1 | F1 ±1 [CI] | chance |
|---|---|---|---|---|---|---|---|---|---|
| L1 | 5600 | 0.083 | 0.402 | 0.138 [0.123, 0.153] | 0.087 | 0.128 | 0.604 | 0.211 [0.193, 0.229] | 0.167 |
| L2 | 3880 | 0.100 | 0.336 | 0.154 [0.137, 0.172] | 0.080 | 0.196 | 0.646 | 0.301 [0.279, 0.323] | 0.156 |
| L3 | 1885 | 0.060 | 0.100 | 0.075 [0.062, 0.090] | 0.065 | 0.121 | 0.203 | 0.152 [0.132, 0.170] | 0.127 |
| L4 | 1200 | 0.077 | 0.079 | 0.078 [0.062, 0.096] | 0.054 | 0.133 | 0.136 | 0.135 [0.115, 0.156] | 0.103 |
| total | 2842 | 0.103 | 0.251 | 0.146 [0.127, 0.165] | 0.077 | 0.181 | 0.446 | 0.258 [0.236, 0.280] | 0.148 |
| E-onset | 6394 | 0.060 | 0.328 | 0.102 [0.091, 0.113] | 0.088 | 0.108 | 0.570 | 0.182 [0.166, 0.199] | 0.168 |
| E-lowflux | 6991 | 0.075 | 0.448 | 0.129 [0.110, 0.152] | 0.088 | 0.112 | 0.649 | 0.191 [0.170, 0.216] | 0.170 |
| E-change | 3031 | 0.075 | 0.191 | 0.108 [0.087, 0.130] | 0.077 | 0.228 | 0.563 | 0.325 [0.300, 0.349] | 0.150 |

The detectors fire at very different rates (L1 5,600 peaks vs L4 1,200 over 6.35 h, against 1,222 reference events); F1 and chance
F1 both depend on that rate, which is why the excess column is the one that compares detectors.

## Manifest boundaries (10 V4 songs, partly circular in the cortex's favour; rules section 4)

| detector | F1 ±0.5 (excess [CI]) | F1 ±1 (excess [CI]) |
|---|---|---|
| L1 | 0.074 (+0.022 [-0.020, +0.060]) | 0.115 (+0.013 [-0.017, +0.035]) |
| L2 | 0.057 (+0.009 [-0.027, +0.062]) | 0.160 (+0.067 [+0.005, +0.127]) |
| L3 | 0.056 (+0.011 [-0.018, +0.042]) | 0.124 (+0.040 [-0.011, +0.084]) |
| L4 | 0.033 (-0.002 [-0.034, +0.047]) | 0.049 (-0.021 [-0.066, +0.029]) |
| total | 0.052 (+0.008 [-0.029, +0.044]) | 0.168 (+0.080 [+0.020, +0.128]) |
| E-onset | 0.032 (-0.016 [-0.031, +0.005]) | 0.089 (-0.009 [-0.036, +0.021]) |
| E-lowflux | 0.059 (+0.011 [-0.008, +0.034]) | 0.114 (+0.015 [-0.008, +0.036]) |
| E-change | 0.034 (-0.012 [-0.037, +0.017]) | 0.127 (+0.036 [-0.024, +0.124]) |
| section (ear) | 0.602 (+0.574 [+0.426, +0.717]) | 0.645 (+0.585 [+0.445, +0.712]) |

The ear section detector and the manifest are the same family of novelty (8 s checkerboard on 0.5 s tokens), so their 0.60 agreement
measures shared method, not truth.

## Event-locked surprisal (within-song z of the smoothed lane): lag of the maximum in −4..+12 s, its z, and z at lag 0

| layer | drop (n 292) | dropout_on (n 76) | dropout_end (n 37) | section (n 817) |
|---|---|---|---|---|
| L1 | +0.1 s, z 1.09, z0 0.72 | +0.1 s, z 3.31, z0 3.24 | +0.2 s, z 3.39, z0 0.45 | +0.0 s, z 0.41, z0 0.41 |
| L2 | +0.0 s, z 0.69, z0 0.69 | +0.5 s, z 6.56, z0 1.74 | +0.0 s, z 3.11, z0 3.11 | +0.5 s, z 1.23, z0 0.35 |
| L3 | +3.9 s, z 0.32, z0 0.17 | +2.1 s, z 4.23, z0 1.18 | +0.4 s, z 2.57, z0 2.02 | +2.5 s, z 1.01, z0 −0.11 |
| L4 | +1.9 s, z 0.17, z0 0.14 | +2.0 s, z 2.57, z0 0.96 | +2.9 s, z 2.08, z0 1.00 | +8.1 s, z 0.42, z0 0.05 |
| total | +0.1 s, z 0.75, z0 0.68 | +0.6 s, z 4.99, z0 2.37 | +0.1 s, z 3.47, z0 3.05 | +0.5 s, z 0.44, z0 0.23 |

The slow layers peak after the event (L3 about +2 to +4 s, L4 about +2 to +8 s), as section 0 of the rules expects from their target
windows; the ±0.5 / ±1 s hit windows do not reach these lags.

## What the numbers do and do not cover

- **Circularity.** Every reference is built from the same ear features the cortex reads. The ear peak detectors that read a defining
  column (E-lowflux, column 32, is in the drop rule) have a built-in advantage on that type. The ear event detectors scored against each
  other mostly measure co-occurrence: dropout onset vs end is high only because an end follows an onset by 0.4-2 s (median 0.6 s); the
  other cross-type cells are near chance. No held-out (human) reference exists yet; `v4_events.md` is prepared for Kosta's ear check.
- **Few dropouts.** The dropout rule (low band < 25 % and onset < 50 % of the past 10 s median, ≥ 0.4 s) found 76 onsets in 210
  songs. Beat dropouts that keep hats, percussion or vocals do not meet the onset condition (Kosta heard such dropouts in fd_053; the
  detector found only one onset there, at 3:40.5, near the song end). 39 of the 76 onsets have no end inside the song: most start in the
  last 3 s (song endings); 5 start 5-19 s before the end.
- **Drops** are the rule's "low band back after ≥ 1 s reduced": 292 events; they are not checked against any human label.
- **Implementation detail not in the rules text:** on a plateau (equal smoothed values) only the first stamp counts as a peak (a peak
  must exceed the previous 1 s strictly). The scoring span starting at 16 s drops the first 16 s of every song, including intros.
- **Skipped:** the V4 / pulse-flash ear notes give no timestamps and were not scored. Nothing was trained, downloaded or installed.
