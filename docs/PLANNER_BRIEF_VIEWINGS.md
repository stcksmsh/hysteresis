# Planner brief: what Kosta's two viewings say, checked against the numbers (2026-11-16)

TO: planner. FROM: overseer (via Kosta). Answers please as BRAIN_SPEC 7.75.

## What ran

1. **Step 0b' control viewing** (7.73, 7.74 Q3): 12 blind pairs, FineDance validation and test, 8 s.
   - Result: 11 of 12 correct, 1 "same" (continuity P10), 0 wrong. Vigour 3/3, height 3/3, sharpness 3/3, continuity 2/3.
   - Record: `docs/CONTROLS_VIEWING_RESULT.md`.
2. **12-clip look check** (7.69.3), "Does the dancer follow the music?":
   - PhantomDance 6 yes;
   - Motorica 5 yes, 1 partly ("its just tiny");
   - Record: `docs/T0_PHANTOM_LOOK_RESULT.md`.
   - Kosta asked the overseer to infer from the notes. The overseer takes the result as his go for PhantomDance + Motorica in A (7.69.3);
     Kosta can veto.

Each note below was checked against the WO43 controls of the clip shown (realised stage, per-dataset percentiles; overseer recompute from
`controls/tables`).

## Findings

1. **What Kosta calls "energetic / flicky" follows sharpness as well as vigour.**
   - In the viewing he read "sharper" as "energetic / fast / flicky", and picked the sharper clip 3/3 with vigour matched (≤ 0.06 sd).
   - Look check, Motorica C06_V2, "too energetic/fast at times for the song": vigour p46 (average) but sharpness p77.
   - Look check, PhantomDance C02_V2, "too flicky at times/energetic": vigour p66, sharpness p72.
2. **The flickiness sits in the V2 copies.**
   - T0 low-passes V1 at 2.50 Hz and V2 at 5.75 Hz (`T0_RULES.md`).
   - Median sharpness V1 / V2: FineDance 0.018 / 0.031, AIOZ 0.016 / 0.040, PhantomDance 0.019 / 0.027, Motorica 0.025 / 0.040.
   - V2 targets carry 10-20 x more joint power above 3 Hz than V1: `T0_PHANTOM_REPORT.md`, e.g. FineDance shoulder 0.0030 vs 0.0622.
   - Both "flicky / too energetic" notes are on V2 clips (2 of 6 V2, 0 of 6 V1). Small numbers, but they agree with the measures.
   - Kosta's own guess ("converting a human arm's proportions onto this arm, a job for the scaler") is not what the numbers point to. The
     difference between V1 and V2 is the low-pass cutoff.
   - V2 + V2m make half of every dataset's tokens, so half of A's training data.
3. **Vigour is what Kosta sees as size.** Motorica C04_V2 "tiny": vigour p6 of Motorica. Viewing: vigour 3/3 ("first is tiny, second is
   big").
4. **Low vigour and pauses coincide with quiet music in the excerpts.** Notes on P03 ("music barely audible/background"), P12 ("music very
   backgrounded/muted") and P10 ("very unmusical bits") all concern the low-vigour or high-pause clips. This agrees with Step 0c (pause x RMS
   within-song rho -0.16 AIOZ / -0.17 PhantomDance; vigour x RMS +0.18 FineDance). Pauses exist almost only in low-vigour motion: continuity
   pairs have vigour -0.9 to -1.7, against a median of 0.0. Kosta judged clips partly by their music; random 8 s excerpts often fall on
   quiet passages.
5. **Two notes the controls do not explain** (report only):
   - PhantomDance C01_V1 "perhaps too low physically": its lamp height is p52 (median) of PhantomDance. "Low" may mean the arm's
     posture (bent joints), not lamp height.
   - Height pair P06: "first is higher, second is more energetic". Vigour, sharpness and accent are matched within 0.07 sd, yet the lower
     clip read as more energetic.

   Possibly something energy-like that the controls miss (direction changes, base rotation), or low poses read as energetic.
   Not tested.

## Questions

**Q1. V2 copies (5.75 Hz cutoff), the source of flicky motion.**
- (a) Keep all four copies in A. Give A the copy (V1 / V2) as part of its domain embedding. Generate with V1 by default; V2 only if a
  later viewing wants it. **[rec]**
- (b) Drop V2 / V2m from A.
- (c) Keep as is: sharpness is a control, so B / the teacher set it.

Recommendation (a): it keeps the data, keeps sharpness controllable, and removes the flicky default without a new retarget run.

**Q2. Sharpness reads as energy.**
- (a) Keep sharpness as its own control. Record that perceived energy = vigour + sharpness (7.71 "smooth vs abrupt" = sharpness). In
  future viewings ask "more abrupt / flicky?" instead of "sharper?". **[rec]**
- (b) Merge sharpness into a combined energy control.
- (c) No change.

**Q3. Clip choice for later viewings (S-B, S-C).**
- (a) Pick 8 s excerpts only where the song's music RMS is at or above its own median, and not in the first or last 10 s. Show the same
  excerpt across conditions. **[rec]**
- (b) Random excerpts as before.

**Q4. The two unexplained notes (finding 5).**
- (a) Record as open; no action now. A's intervention matrix reports direction-change rate and base-rotation speed next to the controls.
  **[rec]**
- (b) Add a posture-based "lowness" measure (joint bend) to the controls before A.

**Q5.** Record as 7.75. Data go (overseer inference, Kosta may veto): PhantomDance + Motorica enter A.
