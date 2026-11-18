# Planner brief: raw-joint rhythm rerun (BRAIN_SPEC 7.84 item 3), 2026-11-18

TO: planner. FROM: overseer (via Kosta). Report only; no verdict was given by the builder.

## What ran

WO53 part B (`docs/BUILDER_PROMPT_WO53_MISMATCH.md`, rules `docs/RAWRHYTHM_RULES.md`, report `docs/RAWRHYTHM_REPORT.md`, merged in
`body` 5dd8d9f). WO52's rhythm definitions unchanged (3 s windows, hop 1 s, autocorrelation period 0.2-2.5 s, ratio to beat period,
bins 1/2, 1, 2, other, none). Only the signal changed: the speed of raw human joints before retargeting (both wrists, both ankles,
pelvis, head, and their mean), on all 310,065 of WO52's windows, 2,128 performances, four datasets, 0 failures. Positions come from
approximate forward kinematics with generic bone lengths (FineDance, AIOZ, PhantomDance: no body model is available locally) and from
Motorica's own skeleton.

## Results (overseer recomputed every point estimate below from the saved per-song counts; all match)

"Excess" = share of rhythmic windows in {1/2, 1, 2} minus chance. Chance 1 = a beat period from another song with similar tempo
(± 10 %; WO52's main chance). Chance 2 = beat periods shuffled within the dataset. Raw = the mean of the six joints. 95 % intervals by
song bootstrap.

| dataset | beat | raw, chance 1 | lamp, chance 1 | raw, chance 2 | lamp, chance 2 |
|---|---|---|---|---|---|
| FineDance | librosa | +0.004 [+0.001, +0.007] | +0.002 (incl. 0) | +0.083 [+0.059, +0.108] | +0.008 (incl. 0) |
| FineDance | pulse v2 | +0.011 [-0.001, +0.022] | -0.001 (incl. 0) | +0.053 | +0.007 (incl. 0) |
| AIOZ | librosa | -0.008 [-0.014, -0.004] | +0.001 (incl. 0) | +0.095 | +0.026 [+0.013, +0.040] |
| AIOZ | pulse v2 | +0.010 [+0.002, +0.018] | +0.003 (incl. 0) | +0.082 | +0.023 (above 0) |
| PhantomDance | librosa | -0.003 (incl. 0) | -0.000 (incl. 0) | +0.030 | +0.006 (incl. 0) |
| PhantomDance | pulse v2 | +0.001 (incl. 0) | -0.003 (incl. 0) | +0.038 | +0.007 (incl. 0) |
| Motorica | librosa | +0.006 (incl. 0) | +0.003 (incl. 0) | +0.113 | +0.014 (incl. 0) |
| Motorica | pulse v2 | +0.005 (incl. 0) | -0.009 (incl. 0) | +0.075 | -0.001 (incl. 0) |
| all | librosa | -0.004 [-0.007, -0.001] | +0.001 [-0.001, +0.003] | +0.084 [+0.069, +0.100] | +0.018 [+0.010, +0.027] |
| all | pulse v2 | +0.008 [+0.002, +0.014] | +0.000 [-0.003, +0.004] | +0.070 [+0.056, +0.082] | +0.015 [+0.008, +0.022] |

Other numbers:
- Raw movement periods are shorter than the lamp's: median 1.07 s vs 1.24 s.
- Share of rhythmic windows at 1/2 beat: raw 0.090, lamp 0.020.
- Per window, raw and lamp fall in the same bin 0.333 of the time; 0.276 if they were independent.
- Item 3's condition as worded (a raw signal's lower bound > 0 and the lamp's interval includes 0; 13 raw signals, no correction for
  multiple comparisons):
  - against chance 2 it holds in FineDance, PhantomDance and Motorica, and fails in AIOZ and pooled, where the lamp also clusters;
  - against chance 1 it holds in FineDance (both beat sources) and with pulse v2 in AIOZ and pooled. Raw excess is at most +0.012
    there, and pooled with librosa the raw mean is below chance.

Reading of the numbers (not a ruling): the large raw excess appears only against shuffled periods (chance 2). That comparison also
rewards any movement whose period follows its song's tempo class. Against similar-tempo songs (chance 1) the raw excess is about one
percentage point or less. The retarget visibly removes fast movement (1/2-beat share 0.090 to 0.020).

## Questions

**Q1. Which chance model decides item 3?**
- (a) Chance 1 (similar-tempo song), as in WO52's main analysis. Raw clustering is then ≤ +0.012 and mixed in sign. Item 3 is recorded
  as "not shown": the arm/retarget is not recorded as the bottleneck for beat-ratio clustering. **[recommended]** This is consistent with
  WO52 and the BAS results, which also found no beat coupling beyond tempo.
- (b) Chance 2 (shuffled). The arm/retarget is recorded as the bottleneck in three of four datasets.
- (c) Both are reported, and no bottleneck is recorded either way.

**Q2. The retarget removes fast movement (1/2-beat share 0.090 to 0.020; median period 1.07 to 1.24 s).**
- (a) Report only. A3's intervention matrix already requests rhythm 1/2; it will show whether the arm can produce half-beat movement
  when asked. **[recommended]**
- (b) A work order now to measure where the retarget loses fast movement (filtering, speed limits, joint mapping), before A3.

**Q3. Timing of the combined ruling.** The mismatch test (7.84 item 1) is not built yet. Should this result wait and go into the combined
"A3 controls and B senses" ruling together with the A2 and CORTEX_EVENTS briefs?
- (a) Yes, one ruling. **[recommended]**
- (b) Rule on Q1-Q2 now.
