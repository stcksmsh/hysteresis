# Planner brief: jitter diagnosis results (BRAIN_SPEC 7.53), 2026-11-13

TO: planner. FROM: overseer. The diagnosis ran report-only on the 20 look-test clips. Nothing was adopted and no video was rendered. Report:
`docs/JITTER_DIAGNOSIS.md` (branch body-jitter a3d1bae); numbers: `/secondary/hyst-data/body/retarget_look/jitter/numbers.json`.

## What ran

- Agent 1 rebuilt the 20 shown clips from FineDance exactly as shown. Stage 4 reproduces the shown clips' CSVs to 5e-7 deg.
- **Four stages:**
  1. the retargeted human command at 30 fps;
  2. the 30 -> 100 Hz resampling (+ guard);
  3. the limiter output;
  4. the realised motion (servo/body).
- **Measures per stage and joint:** acceleration sign changes per second, jerk RMS, and the share of joint-speed power above 3 Hz and above
  6 Hz. Each is computed at the stage's own rate and also at the 30 fps instants.
- **H3 premise corrected (overseer note 7.53.8):** the resampling was already a cubic spline, not linear interpolation, so it put no
  acceleration impulses every 33 ms. H3 was run as stage 2 vs stage 1, plus a linear-interpolation control.
- **Overseer checks:**
  - the builder's measure tests pass (6);
  - the stage-4 medians over the 20 clips, recomputed by the overseer from the clip CSVs, equal the report's;
  - stage 1, stage 4 and H1 recomputed independently for C04_V2 and C10_V1 agree to within 0.05 changes per second;
  - the spinal layer is the round-1 one, unchanged (3 Hz, zeta 0.7);
  - no round-1 file was changed.

## Results (median over the 20 clips, own rate)

**Acceleration sign changes per second:**

| stage | base | shoulder | elbow | wrist bend | wrist roll |
|---|---|---|---|---|---|
| 1 human command, 30 fps | 5.5 | 7.3 | 7.8 | 11.6 | 12.5 |
| 2 cubic spline, 100 Hz | 7.1 | 9.1 | 11.0 | 14.6 | 15.0 |
| 3 limiter output | 5.7 | 4.2 | 7.2 | 9.0 | 8.7 |
| 4 realised (as shown) | 2.2 | 2.7 | 3.3 | 5.0 | 5.4 |
| 4 realised, **H1** (spinal before limiter) | 1.9 | 2.4 | 2.8 | 3.7 | 4.1 |
| 4 realised, H3 linear control | 2.2 | 2.6 | 3.1 | 4.9 | 5.4 |
| round-1 S03 reference, realised (control) | about 1 on every joint | | | | |

**Share of joint-speed power above 3 Hz:**

| stage | shoulder | wrist bend | wrist roll |
|---|---|---|---|
| 1 human command | 0.075 | 0.199 | 0.249 |
| 4 realised, as shown | 0.001 | 0.011 | 0.021 |
| 4 realised, H1 | 0.001 | 0.006 | 0.011 |
| S03 reference | 0.000 | 0.000 | 0.000 |

**Facts, by hypothesis:**
- **Source:** most of the direction changes are already in the human motion after retargeting (stage 1). They are largest on the wrist
  joints (11.6 and 12.5 per second; 20-25 % of speed power above 3 Hz).
- **H3 (resampling):**
  - The cubic spline adds about 25 % more sign changes (shoulder 7.3 -> 9.1) and about doubles jerk RMS (14,400 -> 26,284 deg/s^3), with the
    power above 3 Hz about unchanged.
  - Linear interpolation keeps stage 1's sign changes but multiplies jerk about 8x (impulses at the frames).
  - At the realised motion, linear and cubic differ little (wrist bend 4.9 vs 5.0).
- **H2 (limiter chatter):**
  - The limiter output sits at >= 0.98 x the acceleration limit in 62 % of shoulder frames (elbow 33 %, wrist bend 39 %, wrist roll 33 %,
    base 3 %).
  - Its acceleration flips sign 4.2 (shoulder) to 9.0 (wrist bend) times per second. It runs mostly at full acceleration or full braking.
- **H1 (spinal layer):**
  - Realised sign changes fall by 11 % on the shoulder (2.7 -> 2.4) and 27 % on the wrist bend (5.0 -> 3.65); power above 3 Hz halves on the
    wrists.
  - The limiter's own sign flips fall (shoulder 4.2 -> 3.4, wrist bend 9.0 -> 5.3).
  - 19 of 20 clips still pass the 1.25 gate (C10_V2 fails "limits").
  - H1 + H3 combined = H1 (cubic spline as used).
- **No variant tested brings the realised motion near the S03 reference** (about 1 sign change per second). With H1 the wrists remain at
  3.7-4.1.
- **Separate fact, unexplained:** in C04_V2 the realised shoulder sits about 10 deg above the command over seconds 8-12. That is a steady
  offset, not only lag. The cause is unchecked.

## Questions

1. **Which fix to show in the blind re-look** (old vs fixed pairs; 4-6 clips including C04_V2 and C10_V1; pair order mixed).
   - (a) **H1 only** (the round-1 spinal layer before the limiter). It is the only fix measured, it is the same muscle-like layer round 1
     used, and it has no new parameter. It leaves the wrists at about 3.7 direction changes per second, against about 1 for S03.
   - (b) **H1 plus a low-pass on the human command** (stage 1), with the cutoff fixed by a rule before any render. Example: a zero-phase
     2nd-order filter at 3 Hz, matching the spinal layer. It is measured report-only first, and gated at 1.25. It targets the stage where
     most of the direction changes start, but it is a new parameter.
   - (c) **Both arms in one session: old vs (a) and old vs (b)** on the same 4-6 clips, so 8-12 pairs. **[recommended]** One session
     answers both, within the two-rounds-per-check rule. The cutoff of (b) is fixed by rule, not by eye.
   - (d) No fix now; go to imitation training and handle smoothness there. Not recommended: the network would learn from the same source
     motion.
2. **The C04_V2 steady shoulder offset (about 10 deg):**
   - (a) a report-only check by agent 1 alongside the fix (gravity sag in the servo model or something else). **[recommended]**
   - (b) record only.
3. **Record** as BRAIN_SPEC 7.54, including the H3 premise correction.
