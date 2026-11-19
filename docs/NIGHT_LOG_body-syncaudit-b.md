# Night log: WO54 B (A2 AIST++, A3 per-song lag), branch body-syncaudit-b

Rules: `docs/SYNCAUDIT_RULES_B.md`. Code: `scripts/body/syncaudit_b.py`, `syncaudit_report.py`, tests `test_syncaudit_b.py` (6 pass). Data and full tables:
`/secondary/hyst-data/body/syncaudit/b/` (`a3_tables.md`, `a3_results.json`, `foil_table.md`, `foil.json`, `a2_tables.md`, `a2_results.json`, per-song npz).
Sign: positive = movement later than music. No pipeline code changed; Kosta's answers.csv not opened.

## Corrections to the rules note
- Foil reading: with c(L) = corr(m(t), e(t - L)), the foil (music at t + offset) is the real-music curve at **L = -offset**, not +offset. Verified by
  test and by the table (c_real(L=-offset) equals c_foil(0) for all 13 clips).
- AIST++: only 411 of 1408 sequences have SMPL motions locally, so the pipeline stages ran on 60 of them (6 per genre, seed 54201, selected among those 411);
  keypoint-only measures could be run on all but were not (the 60 serve both).
- AIST++ sequences are 5-13 s: lag window +-1.5 s, core = sequence minus 1.5 s each side (not +-3 s / [3, 17]).
- A2 adds a stage-to-stage lag (stage vs the previous stage's speed signal), because per-sequence lag against the music is noise (below).

## A3 headline (pooled lag of lamp speed vs raw mean joint speed of the same windows, no music; 95 % CI by song)
| dataset | V1 pooled lag s | V2 pooled lag s | per-song median V1 / V2 |
|---|---|---|---|
| finedance | +0.312 (0.275, 0.355) | +0.299 (0.287, 0.312) | 0.34 / 0.29 |
| aioz | +0.333 (0.297, 0.373) | +0.247 (0.241, 0.252) | 0.32 / 0.25 |
| phantom | +0.386 (0.339, 0.422) | +0.269 (0.258, 0.283) | 0.33 / 0.28 |
| motorica | +0.351 (0.280, 0.390) | +0.301 (0.281, 0.321) | 0.31 / 0.29 |

Lamp (realised arm) lags the raw human joints by 0.25-0.39 s in all four datasets.

Lamp / raw speed against the music (ear col 40): per-song peak lags spread over the whole +-1.5 s range (flat histograms), share within +-100 ms
0.03-0.11, peak heights equal to the chance heights (e.g. finedance lamp V1 0.038 vs 0.034 tempo / 0.036 shift; raw mean 0.052 vs 0.039 / 0.053),
pooled curves flat (height 0.002-0.02), pooled-lag CIs span about +-1 s. No stable music lag is measurable on the movement signals, raw or lamp.

## A2 headline (60 AIST++ sequences, lag of each stage vs the previous stage, median and CI of the median, s)
| stage | V1 | V2 |
|---|---|---|
| angles .. guard (retarget, lowpass, spline, guard) | 0.000 (|x| <= 0.004) | 0.000 |
| spinal | +0.084 (0.084, 0.085) | +0.083 (0.083, 0.084) |
| limiter | +0.069 (0.043, 0.105) | +0.044 (0.035, 0.058) |
| servo q50 | +0.114 (0.109, 0.122) | +0.070 (0.069, 0.071) |
| lamp (FK) | +0.008 | +0.027 |
| cumulative spinal..lamp | +0.275 | +0.224 |

BAS (sigma 0.1 s) excess over chance: raw keypoints +0.057 (CI +0.011..+0.103); V1 lamp -0.023 (-0.051..+0.003); V2 lamp +0.000 (-0.031..+0.037).
Per-sequence music peak lag on raw AIST++ keypoints is also noise (pooled CI about +-1 s), so the music-lag column of the A2 table does not resolve 20 ms.

## Findings
1. spinal layer (`motornet.spinal`, 3 Hz spring-damper): +84 ms, constant.
2. command limiter + servo (`retarget_limiter.simulate_goals`, v2p body): +44..114 ms depending on variant (nonlinear, not a pure delay).
3. Total retarget to realised lamp: about +0.22..0.28 s on AIST++ (stage sum) and +0.25..0.39 s on the dataset windows (lamp vs raw joints).
4. Stages with no lag (<= 4 ms): human angles, to_commands, lowpass (zero-phase filtfilt), 30 -> 100 Hz spline, guard.
5. Shifted-foil reading: no preference visible in the lamp-speed correlation: c_foil(0) - c_real(0) mean +0.011 (ear col 40, median -0.011, foil higher in 5/10 pairs),
   energy mean -0.064 (foil higher in 3/10); all |c| < 0.2. This audit does not explain the 8/8 foil picks.

FOR USER: (a) the 0.2-0.4 s is the realised arm's physical-style latency; R1 already plans audio delay to compensate servo travel, but the clips and the
WO47/52/53 measures used the undelayed music: decide whether to advance the movement or delay the music by the measured amount; (b) AIST++ global-orient
convention was taken from the AIOZ adapter (timing only, amplitudes not checked); (c) the librosa secondary onset envelope was not run (not needed given flat results).
