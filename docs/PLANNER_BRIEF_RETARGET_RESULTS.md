# Planner brief: retarget look test results (BRAIN_SPEC 7.49.5 / 7.51 / 7.52), 2026-11-13

TO: planner. FROM: overseer. Kosta has labelled all 27 items. Full tables: `docs/RETARGET_REPORT.md` (body d683cf6), whose last section
holds the overseer's per-clip shoulder and smoothness numbers.

## What ran

- **Limiter bug fixed (7.52 Q3, a bug, recorded as rules note (k)).** At the edge of a joint's range, the limiter clamped the position but
  kept the velocity, so the target stopped dead in one frame (up to 5.8x the acceleration limit). Only the joints with a limited range were
  affected. Fixed in a new module; round-1 code untouched. The worst candidate went from 3.20x to 1.00x. Over all 290 candidate/variant runs
  the limiter output is now <= 1.0x on every joint. The S03 reference also uses the fixed limiter, so it is not byte-identical to the round-1
  clip Kosta saw.
- **Re-gate at 1.25 (look-test exception) with the pick rule** (at most one window per sequence, two per genre), seed 32011 from candidate 1.
  It took 27 candidates to fill the 10 clips: pass V1 14, V2 16, both 11, one skipped by the pick rule. The 10 clips are 10 different
  sequences in 9 genres: kun, urban, korean, dunhuang x2, miao, hantang, jazz, dai, breaking.
- **Overseer checks before the session:**
  - every gate recomputed by the overseer's own code from the CSVs: 0 fails at 1.25, values equal the builder's;
  - no joint within 1 deg of an end stop;
  - all clips 20.000 s, audio offset 0.0 s against the FineDance music;
  - V1 shown first in 3 of 5 pairs;
  - both S03 references pass.
- **Session:** 22 singles + 5 pairs, seed 32051. Kosta answered all 27 (15:55-16:00 and 20:12-20:23).

## Results

**Singles:**

| variant | yes | sort of | no |
|---|---|---|---|
| V1 (arm as arm) | 4 | 6 | 0 |
| V2 (arm as whole body) | 2 | 8 | 0 |
| round-1 S03 reference | 0 | 2 | 0 |

- V1 "yes": C01 kun, C03 korean, C06 hantang, C10 breaking.
- V2 "yes": C04 dunhuang, C07 dunhuang.

**Pairs:** V1 named 3 (C01, C02, C06), V2 named 2 (C04, C05).

**Kosta's notes, grouped by the overseer** (verbatim in the report):

- **Strongest comment, C04_V2:** "This is the best one so far, its even better than v47 (not really too close of a contest there
  either) ... its actually good".
- **Jitter, micro-movements, "mechanical", "not smooth": 12 of 27 notes.** His reading (C05_V1, pair C02): "barely perceptible micro
  movements that read as jitter to a human", "stuff that humans cant do by design so we dont, and since we cant we dont see it as truly
  dance". Two more notes say "missing the human/natural element" and "organic dance".
- **Flicks too aggressive: 10 notes.**
- **Energy wrong for the song: 4 notes** (C02_V1, C05_V2, C08_V1, C09_V1). In C09_V1 Kosta guesses that birdsong in the music fed
  "energy or arousal". Fact: nothing in this test reads the audio. The arm replays the recorded human dancer's motion for that song,
  scaled and limited.
- **Timing: 5 notes** (not on the beat; C10_V2 "misses the obvious cues, the dropouts of elements").
- **Height:** C03_V1 "too low" for an upbeat song.
- **S03 references:** "repetitive", "loops", "almost no base movement", "little speed/accel variation"; C09 S03 "more on beat than 2".
- **Positive:** C09_V2 "Base moves now, thats nice".

**Overseer numbers on the realised motion** (50 Hz CSVs, report only):

| | acceleration sign changes per second (shoulder / elbow / wrist bend) | joint-speed power above 3 Hz |
|---|---|---|
| retargeted clips | 2.0-4.2 / 2.3-5.6 / 3.2-8.4 | 0.4-10.4 % |
| S03 references | about 1 / 1 / 1 | 0.1-0.2 % |

- **Speed saturation does not track the jitter notes.** C04_V2 spends 15.6 % of frames at the speed limit and was called the best clip;
  C10_V1 spends 0 % and was called "unsmooth".
- **Shoulder cut by the limiter** (RMS of command minus limiter output): V1 street clips 16-24 deg, V2 1.4-10.7 deg, kun C01 0.1-1.6 deg.
  The commanded shoulder acceleration peaks at 25-34x the servo limit on V1 street clips.
- **The source of the micro-movements is not known.** Candidates: the human motion data itself, the 30 fps to 100 Hz resampling, the limiter,
  the servo model.

## Questions

1. **Next step.**
   - (a) **A report-only jitter diagnosis first** (agent 1): find which stage adds the high-frequency motion Kosta calls jitter (human
     data, 30 to 100 Hz resampling, limiter, servo). Use the same 20 clips, with numbers per stage and no change adopted. Then Kosta rules
     on a fix and, if wanted, a short re-look on 4-6 clips. **[recommended]** Jitter is the most common note (12/27). Training a network
     to imitate motion that carries this jitter would likely learn it too, and the diagnosis is cheap (simulation only, about an hour).
   - (b) Declare the look test passed (no "no" at all, 6 "yes") and go to step 3 (imitation training, 7.49 a). Handle smoothness inside
     training.
   - (c) Another look test with a fixed smoothing filter chosen now (e.g. low-pass the command at 3 Hz). Not recommended before (a): the
     cutoff would be a guess.
2. **V1 or V2 for training.** V1 has 4 yes, V2 2 yes; pairs 3-2 for V1; the single best clip is V2 (C04). With n = 10 and 5 pairs, the
   difference is small.
   - (a) Keep both until after the jitter step. **[recommended]**
   - (b) Choose V1 now.
   - (c) Choose V2 now.
3. **Notes that need a ruling or a record:**
   - "energy wrong for the song" and "not on the beat": this is the human dancer's own motion. Music-conditioned choice of motion is the
     job of step 3 (cortex conditioning), not of the retargeting. **Record only. [recommended]**
   - C03_V1 "too low": record for later (posture or height by music). **Record only. [recommended]**
4. **Record** as BRAIN_SPEC 7.53, including that the look test showed no "no" answer at the 1.25 look-test tolerance, and the shoulder
   actuator note of 7.52.6.
