# Body study: rules fixed before any result (step 1 of `docs/NEXT_BODY_THEN_MIND.md`)

Committed 2026-10-13, before the generator ran on any body vector. Nothing below
may change after a result it scores has been computed. Round 2 (if any) may only
change what a failing check names, and says so here in a dated addendum.

## Rig and implement for the study

- Rig: `Rig::illustrative_five_axis()` geometry, **implement: the 6 cm mirror disc**
  (user, 2026-10-13: cheap servos and light materials to begin with, no mirror ball).
- One arm at the origin, yaw 0, the preview's solo camera, no audio.

## Check 2a: feasibility (user's limits, 2026-10-13)

The brief's 240 °/s and 8,000 °/s² are the illustrative rig's hard envelope. The
user chose limits for cheap bus servos instead (estimate: shoulder gravity torque
alone about 40 % of a 2.9 N·m stall; peaks without strain near 500 °/s²):

| Limit | Value | How it is measured |
|---|---|---|
| Joint speed, every channel | ≤ 150 °/s | the score's own continuous proof (`EnsembleScore::validate`, quintic hulls) |
| Joint acceleration, every channel | ≤ 500 °/s² | same |
| Joint range | shoulder, elbow, wrist bend ±110°; base yaw and wrist roll unbounded | same |
| Hand speed | ≤ 1.2 m/s | hand point (last world point), finite differences at 60 fps, as the preview samples it |
| Hand jolt | ≤ 9 m/s² | change of hand speed per frame × 60, at 60 fps: the `jolts.py` measure |
| Floor | every link endpoint above the base ≥ 5 cm; the hand point ≥ 5 cm + 6 cm (disc radius) | at 60 fps |

**Stretching.** A clip that fails is slowed about its centre (clip time t maps to
motion time 4 + (t − 4)/s, so the 8 s clip shows the middle 8/s seconds, slower).
s is tried in the order 1, 1.1, 1.1², … up to 1.1⁷ = 1.95. The first s that passes
is kept. **A body vector that does not pass at s ≤ 1.95 is rejected**: stretching
it further would show less than half its phrase, which is a different motion, not a
slower one. Rejections are counted and reported (per parameter, by decile). A clip
is never shown raw if it fails.

## Sampling

Body vectors are drawn uniformly from [0, 1]¹² (fixed seed 20261013), each with its
own content seed, until **2,000 pass check 2a**.

## Descriptors (per clip, on the final 8 s at 60 fps)

37 numbers, standardised (z-score) over the 2,000 before any distance:
- per channel (5): joint speed, acceleration and jerk, each mean and 90th
  percentile (30);
- posture: mean hand height, mean extension (shoulder-to-hand distance over the
  arm's straight reach), mean curl (|elbow| + |wrist bend|, degrees) (3);
- joint-to-joint lag: the lag in −0.5..0.5 s of best cross-correlation of joint
  speed, base→shoulder, shoulder→elbow, elbow→wrist bend (3);
- periodicity: the highest autocorrelation of hand speed at lags 0.3–3 s (1).

They are not the judge. They build the regions and show what differs.

## Regions

- **8 centres** by farthest-point sampling in descriptor space: the first is the
  clip farthest from the mean, each next the clip farthest from all chosen.
- A clip belongs to a region if it is nearer that centre than any other centre and
  within radius r of it.
- **r** is the largest value on a grid of 200 steps from 0 to the smallest
  centre-to-centre distance such that, in every region, the mean within-region
  pairwise distance is under a quarter of the mean centre-to-centre distance. Both
  distances are reported.
- A region needs 9 members (3 as the odd one, 6 as pairs). If it has fewer, more
  clips are made from its members' body vectors with fresh seeds, kept if they fall
  inside its ball, up to 200 tries per region. A region still short is reported and
  the study stops there.

## Triplets

- **24 triplets.** Triplet i (0..23) has its pair from region p = i mod 8 and its
  odd one from region (p + k) mod 8, k = 1, 3, 5 for i in 0–7, 8–15, 16–23. So every
  region is the pair 3 times and the odd one 3 times. Every clip is used once; all
  72 are different (body vector, seed) pairs.
- Triplet order and the odd one's position (A, B or C) are shuffled with seed
  20261014. The key goes to a file the user does not open until all answers are in.
- Rendering: the existing preview template and `$D/record-ensemble.cjs`, one arm,
  same camera, disc, light, silent audio, 8 s each, three side by side as A | B | C.
  On-screen text is the same for every clip.

## Check 2b: the user tells them apart (from the brief, unchanged)

- **Pass: at least 16 of 24 correct** (chance 8; p ≈ 0.0009 under guessing).
- Reported per region: how often it was found as the odd one, and which
  descriptors separate the regions found from those missed.

## ★ Stops (brief)

1. After the generator and the 2a sweep: ranges, stretching per region, descriptor
   spread, two or three single clips (not part of the test).
2. Triplets and page ready: the user takes the test.
3. After scoring.
