# Planner brief: low-pass re-look results, BRAIN_SPEC 7.55, 2026-11-14

TO: planner. FROM: overseer. The low-pass fix ran and Kosta did the blind re-look (6 pairs). Report: `docs/LOWPASS_REPORT.md` (branch
body), section 4 for the session; data `/secondary/hyst-data/body/retarget_look/lowpass/`. The installation is one arm; nothing here
concerns more than one.

## What ran

- Rules note (n): 2nd-order Butterworth, zero phase (filtfilt), 30 fps, on the whole-sequence stage-1 angles of V1 and V2. Cutoff =
  the highest on the 0.5-14.5 Hz grid at which the median lamp-path power share above 3 Hz (10 windows) is <= the human end point's
  (column 0r of Step A). Then spline to 100 Hz, guard, H1 spinal layer, fixed limiter, servo, v2p body, gates at 1.25.
- Cutoffs: **V1 2.50 Hz** (lamp 0.0254 <= human 0.0290; 2.75 Hz gives 0.0344). **V2 5.75 Hz** (0.0804 <= 0.0851; 6.0 Hz gives 0.0854).
  Overseer recomputed both with his own filter and measure on the builder's windows: equal.
- Gate at 1.25: 19 of 20 pass. C10_V2 fails on acceleration (1.28 x limit); it was not in the re-look.
- Re-look pairs by seed 32071: C04_V2 and C10_V1 (named in 7.55), plus C09_V2, C09_V1, C04_V1, C06_V2. LP first in 3 of 6 (seed 32081).
  Clips 20 s, 1280x720, same camera and music as the look test, audio offset 0.0 s against the old clips (overseer check).

## Results

Jitter at the realised stage, median over the 10 clips (wrist bend, direction changes of acceleration per second):

| | LP + H1 | look-test baseline | baseline + H1 | round-1 S03 refs |
|---|---|---|---|---|
| V1 | 2.70 | 5.09 | 3.67 | 0.85 |
| V2 | 3.60 | 4.95 | 3.60 | 0.85 |

V1 wrist-bend jerk RMS: LP + H1 6,210 deg/s^3, baseline 11,068, S03 186. On V2 the low-pass adds nothing over H1 alone on this measure
(cutoff 5.75 Hz is above most of the jitter band). LP + H1 is still 3-4x the S03 references on direction changes and 30x on jerk.

Kosta's answers (joined by the overseer from answers.csv x key):

| pair | first / second | picked | note (verbatim) |
|---|---|---|---|
| C04_V1 | old / LP | LP | |
| C10_V1 | old / LP | LP | |
| C04_V2 | LP / old | LP | Almost the same, perhaps first a bit better, unsure |
| C06_V2 | LP / old | LP | First may be a bit better, very close |
| C09_V2 | LP / old | old | Similar, perhaps second? |
| C09_V1 | old / LP | same | cant tell... |

LP 4, old 1, same 1. V1: LP 2, same 1. V2: LP 2, old 1. LP won 2 of 3 in each position. The two answers without notes (C04_V1, C10_V1,
both V1, the pairs 7.55 named first) were given on 2026-11-13; the machine then rebooted and the other four were given on 2026-11-14,
all with "close / unsure" notes. With 6 pairs, 4 of 6 for LP is not distinguishable from chance (P = 0.34 for >= 4 of 6 under 50/50,
ties dropped: 4 of 5, P = 0.19).

## Corrections and caveats for the record

- **7.55.7 wording correction:** the brief that led to 7.55 said "the lowest cutoff"; the intended and applied rule is the highest
  cutoff (least smoothing) that meets the human's power. The error was the overseer's.
- **V2 cutoff sensitivity:** V2's 5.75 Hz sits 0.0003 under the boundary; a 601-frame measurement window moves it to 6.0 Hz. Small
  either way, since V2's low-pass barely changes the realised measures.

## Questions

1. **Does the result meet 7.55.5 ("fixed at least as good")?**
   - (a) Yes: LP + H1 is at least as good (4 for, 1 against, 1 same); it becomes the training-data pipeline, retargeting ends, the
     planner writes the imitation-training plan (7.49 a). **[recommended: by the stated rule the fixed version is not worse; the
     closeness of four answers argues that the remaining jitter is not removed, which the training plan should note]**
   - (b) Inconclusive: run more pairs before deciding.
   - (c) Ask Kosta for a direct verdict ("is LP + H1 good enough to train on?").
2. **Remaining jitter.** LP + H1 stays 3-4x the S03 references on direction changes. (a) Carry this into the training plan as a known
   gap, to be judged again on the trained model's output **[recommended]** / (b) another retarget variant first (needs Kosta's ruling
   per 7.55.5).
3. **Gate failure in training data.** C10_V2 fails at 1.25 after the low-pass. (a) Training windows are gated the same way and failures
   dropped, counted in the plan **[recommended]** / (b) other.
4. **Confirm the 7.55.7 cutoff rule (highest cutoff) and V2 = 5.75 Hz as recorded.** [recommended: confirm]
5. **Record as 7.56.**
