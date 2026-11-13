# Planner brief: motor-network toy round 2 results (BRAIN_SPEC 7.47.4), 2026-11-13

TO: planner. FROM: overseer. Full report: `docs/MOTORNET2_REPORT.md` (body 7801dc9). Rules: `docs/MOTORNET2_RULES.md`. No verdict from the
overseer; Kosta decides.

This brief overtakes Q1 of `docs/PLANNER_BRIEF_AROUSAL_ENERGY.md` (whether to keep `arousal_b7` as a round-2 input): round 2 ran with it as
ordered and has been viewed. That brief's results and its Q2 (record) still stand.

## What ran

- **Network as 7.47.4:**
  - slow population 100 units (tau 300 ms) drives base yaw and shoulder; fast population 100 units (tau 75 ms) drives elbow, wrist bend
    and roll;
  - each population's own block has spectral radius 1.05; the full matrix's radius is 1.498 (reported, not tuned);
  - input drive is 0.25 of recurrent drive in each population (0.2503 slow, 0.2505 fast);
  - inputs: beat phase, L4 projection (slow population only), ear energy, `arousal_b7`;
  - calibration ±60 %; spinal layer stays at 3 Hz (the limiter cuts at most 1.6 %).
- **Sampling (seed 30011):** 17 draws, 8 kept.
  - Discards by gate: motion 6 (all silent), contact 3, limits 2 (all on Blue Lagoon). One draw can fail two gates.
  - Round-1 S03 passed the gates on all 5 songs at 30 s.
  - Stop rule not hit: base yaw p5-p95 on silent was 27-74 deg; PR was 1.87-3.82 (slow) and 2.34-4.68 (fast).
- **Overseer checks, own code, before Kosta saw anything:**
  - format: all 18 clips 30.000 s, 1280x720;
  - audio: offset 0.0 s from Kosta's start times;
  - gates: velocity at most 0.64 of its limit, acceleration at most 0.59; hand at least 0.256 m up; hand moves at least 0.015 m/s in every
    3 s;
  - the Part B pick reproduces from seed 30031;
  - measurements match the builder's;
  - answers joined to the key by hand, 13/13.
- **Session:** 13:11-13:24, 13 items, seed 30061.
  - **Disclosed:** with this seed no pair was swapped, so in all 5 pairs the new setting played FIRST and round-1 S03 SECOND. The swap code
    works (seeds 1-6 swap 1-5 of 5). The seed was kept rather than re-drawn after seeing the order.

## Results

**Part A, silent, 30 s (labels):**

| Label | Count | Settings |
|---|---|---|
| nothing, glitching | 4 | S02, S04, S05, S07 |
| energetic | 2 | S06, S08 |
| tense | 1 | S03 |
| something, can't name it | 1 | S01 |

Round 1 had no "nothing, glitching" label (7.46.2). Kosta's notes repeat one theme in 7 of 8 clips:
- "micro-movements", "jittery", "stalling, stopping midway or getting stuck";
- the micro-movements read as useful when the arm bobs in place (S01 at about 14-16 s and 20-25 s; S08 "head-bobbing" from about 5 s);
- they read as glitching when combined with a sweep;
- his guess (S03): "if the micros are in the same plane as the sweep, causing it to stutter".

**Part B, music (round-1 S03 always shown second):** Kosta picked "second", round-1 S03, in 5/5 pairs.

| Song | New | New hand speed m/s | R1 S03 hand speed m/s | Kosta's words, short |
|---|---|---|---|---|
| Blue Lagoon | S06 | 0.172 | 0.332 | new too small, almost stuck at ~12/23/26 s; "we don't need to face the audience always, we can use rotation as a tool" |
| Schizoid Man | S07 | 0.059 | 0.232 | new minimally moving after the line ends (~5 s); S03 better, could use more energy |
| Epitaph | S05 | 0.073 | 0.247 | new too static; S03 matches, could rise vertically ~14-20 s (vocal high point) |
| Breathe | S03 | 0.117 | 0.294 | close; new almost glitchy but follows the vocals ~23-26 s; suggests switching between the two inside the 30 s |
| One of These Days | S01 | 0.071 | 0.126 | both too small/slow; "neither possibly"; S03 has a loop timed to the guitar ~25 s |

**Measured, round 2 against round 1 (overseer, from the joint CSVs at 50 Hz):**
- **Hand speed on music:** the new settings are slower than round-1 S03 in every pair (0.06-0.17 m/s against 0.13-0.33). On silent the
  new settings range 0.10-0.23 m/s.
- **Base yaw (what Kosta calls facing):**
  - new settings on music: p5-p95 21-71 deg, net drift up to 60 deg (Breathe);
  - round-1 S03 on music: 11-33 deg, drift under 9 deg.
- **Direction changes:**
  - silent round 2: wrist bend and roll change direction 3.3 times per s in all 8 clips, which is twice the 100 BPM silent beat (1.67 Hz);
    round-1 silent clips range 0.7-3.4;
  - on music both networks change direction about 1 time per s;
  - share of joint-velocity power above 2 Hz: new settings on music 0.1-4 %; round-1 S03 on music at most 0.1 %; silent round 2 at most
    6 % (shoulder S03).
- **PR on music:**
  - new settings: slow 2.6-5.2, fast 2.2-5.6;
  - round-1 S03, as one population: 2.2-2.4.
- No measurement here is shown to cause the "micro-movement" reading. The numbers above are what was checked.

## Questions

1. **Next step.**
   - (a) Close toy round 2. The planner specifies a round 3 from Kosta's named items: micro-movement only as an in-place layer, not during
     sweeps; base rotation used as a tool rather than a fixed facing; bigger, faster movement on energetic music; switching between modes
     inside an excerpt. Same rules as 7.44 (no learning, blind, gates by the overseer). **Recommended:** Kosta's notes name concrete
     movement properties, and round 2 does not answer them.
   - (b) Return to round 1's single network (S03 won 5/5) and vary only what Kosta named (range of base yaw, size on energetic music).
   - (c) Hold the toy line and decide the wider direction first.
2. **Seed disclosure.** The new-first order in all 5 pairs confounds "first vs second" with "new vs S03". (a) Record it and move on
   **[recommended: Kosta's notes give a reason in every pair]**; (b) re-show the 5 pairs with the order swapped.
3. **Record** as BRAIN_SPEC 7.48 together with the arousal/energy results (one entry), or 7.48 and 7.49 if answered separately.
