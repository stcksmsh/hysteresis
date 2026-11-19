# Planner brief: motor-network toy test, Kosta's blind labels of Parts 1, 2 and 4 (2026-11-13)

From the overseer, for the planning agent. Paste-ready. One arm only. Rules: BRAIN_SPEC 7.44 and 7.45. Report:
`docs/MOTORNET_REPORT.md` (body 77cc84c).

## What ran

The re-run under 7.45:
- **Input scale:** Win x 0.0428, so the input drive std is 0.25 x the recurrent drive std at gain 1, silent.
- **Spinal layer:** stays at 3 Hz. The command limiter keeps 0.977-0.997 of the target range on every joint, so the 1.5 Hz rule did not
  trigger.
- **Calibration and gate:** back to the defaults, +-60 % and 0.10 m minimum motion (gain-1 hand extent 0.182 m).
- **Sampling:** seed 29011. 10 of 41 draws kept; discards by gate: motion 20, limits 11, contact 9, clearance 1, end stop 1.
- **Extremes:** S11 (all low) failed motion; S12 (all high) failed contact and limits. Neither was shown.
- **Stop rule 7.45.5:** not triggered. Every joint peaks at 0.25-0.50 Hz, except the elbow of S01 and S10 at 1.66 Hz (the beat input).
  PR is 1.97-2.64.

The session:
- 16 clips, blind, in seeded order (29051): Part 1 (10 lamp), Part 2 (2 ball), Part 4 (4 round-1 clips).
- Kosta answered all 16, with no second answers. Kosta's own comment: "unsure of all the results, imperfect probably".
- Part 3 (music) was not run: no audio files or excerpt times yet.

**Checks by the overseer:**
- Labels: the answers joined with the key by the overseer's own code, 16/16 the same as the report.
- Mean hand speed and height recomputed from the CSVs: the same as the report.
- Gates recomputed before the session.

## Results (numbers only)

Part 1, silent, lamp. All 10 settings have regime "cycles".

| Setting | Label | Mean hand speed m/s | Hand height m | Peak Hz | PR | Straightness (mean) |
|---|---|---|---|---|---|---|
| S08 | tense ("tense but also perhaps a bit energetic? Like anxious almost, but not dark") | 0.247 | 0.514 | 0.42 | 2.38 | 0.93 |
| S03 | tense | 0.318 | 0.509 | 0.42 | 2.02 | 0.96 |
| S06 | light ("look most like dances, the entire body dances/moves/undulates ... energetic and light") | 0.338 | 0.517 | 0.42 | 2.18 | 0.94 |
| S09 | light ("light/energetic, upbeat?") | 0.391 | 0.278 | 0.25 | 1.97 | 0.89 |
| S07 | energetic | 0.488 | 0.508 | 0.50 | 2.21 | 0.95 |
| S01 | energetic | 0.526 | 0.508 | 0.42 | 2.21 | 0.87 |
| S10 | energetic | 0.646 | 0.503 | 0.50 | 2.18 | 0.90 |
| S04 | energetic ("perhaps even angry? ... music is like 95% of the context") | 0.664 | 0.481 | 0.42 | 2.64 | 0.81 |
| S05 | energetic | 0.855 | 0.476 | 0.50 | 2.17 | 0.84 |
| S02 | energetic | 0.856 | 0.463 | 0.42 | 2.18 | 0.71 |

- **Label counts:** energetic 6, tense 2, light 2. Calm, sad, "nothing, glitching" and "something, can't name it" were not used.
- **Ordered by mean hand speed, the labels form three runs with no overlap:** tense 0.25-0.32, light 0.34-0.39, energetic 0.49-0.86.
  This is an observation on 10 clips, not a tested claim.
- **Activity:** every setting cycles at 0.25-0.50 Hz with PR about 2. The gains change the speed and size of what looks like one
  low-dimensional cycle.

**Part 2, ball vs lamp:** S01 and S02 were labelled energetic with both effectors.

**Part 4, round-1 clips again (round 1 -> now):**

| Clip | Round 1 | Now |
|---|---|---|
| A_neutral | calm | calm |
| A_vigour_high | tense | tense |
| A_lag_low | tense | sad |
| A_posture_high | light | tense |

2 of 4 are the same.

## Questions

**Q1. Next step.** Kosta's call. Options:
- (a) Part 3 (music, 5 pairs, same 12 settings) as soon as Kosta supplies the five files and the excerpt start times. It completes the
  7.44 question "with and without music". Kosta noted "music is like 95 % of the context".
- (b) Close the toy test on Parts 1, 2 and 4 and go to the next design step (planner proposal 7.44.2: gains set by a limbic part, trained by
  Kosta's labels). This is a build decision, not yet ruled.
- (c) A second silent round with a new sampling seed, to see whether the speed-to-label ordering holds on new settings.

*Recommendation: (a), then decide between (b) and (c) with all four parts in hand.* Nothing is built or run until Kosta answers.

**Q2. Low-dimensional activity** (PR about 2 for every setting). Options:
- (a) Keep the network as it is for Part 3, so the music result is comparable with the labels above.
- (b) Change it now (e.g. spectral radius or input fraction) to get richer movement before Part 3. That would mean new settings, new clips
  and a new silent session.

*Recommendation: (a).* Whether richer dynamics are needed is a question for after Part 3.

**Q3. Record.** Record these results and answers as BRAIN_SPEC 7.46. *Recommendation: yes.*

## State

- **Merged:** body-mnet and body-mnettool into body (f78a90a); report at body 77cc84c.
- **Running:** nothing. The session server is stopped. Both builders are idle.
- **Data:** `/secondary/hyst-data/body/motornet_toy/` (clips, clips_v1, session_2026-11-13, measurements.json, settings.json).
