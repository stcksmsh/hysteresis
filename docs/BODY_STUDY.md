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

## Addendum, 2026-10-13 (afternoon): limits for cheap hardware, check method, regions

Written after the first sweep and its stop at the region rule, **before check 2b
ran on anything**. It replaces the check 2a limits and the region rule above; the
rest stands. It is still round 1.

### Why

The first sweep (commit `db0c2b1`) measured that one 500 °/s² limit for every joint
flattens the body: clips high in "time" (sudden) moved less than sustained ones
(90th-percentile joint speed 19 against 42 °/s; total joint motion 12 against 38),
and "weight" changed nothing (23 against 24 °/s). Each move's size was capped by
the acceleration budget, so a fast move had to be tiny. That limit came from the
shoulder; the distal joints carry far less load. Separately, farthest-point
sampling picked single outlier clips as 7 of the 8 centres, and 4 regions had 1–2
members, so the study stopped.

### Hardware the limits assume (user: cheap equipment, light 3D-printed body)

Feetech STS3215-class bus servos (about 2.9 N·m stall, about 270 °/s unloaded);
the shoulder through a 2:1 reduction (or an STS3250-class servo); a micro servo
for the roll; base on a thrust bearing with a slip ring. Printed links 25–40 g,
the 30 g disc, the illustrative lengths. Each limit keeps its joint at or under
about 25 % of stall with the arm level. Servo figures are from memory; the masses
are invented. Bench-measure and update before hardware use.

### Check 2a limits (replace the table above)

| Joint | Speed | Acceleration | Torque at the limit, estimated |
|---|---|---|---|
| Base yaw | 120 °/s | 600 °/s² | 0.6 N·m, 20 % of stall |
| Shoulder | 90 °/s | 300 °/s² | 1.1 gravity + 0.3 = 1.4 N·m, 24 % with the reduction |
| Elbow | 150 °/s | 1,000 °/s² | 0.42 gravity + 0.21 = 0.6 N·m, 22 % |
| Wrist bend | 200 °/s | 2,000 °/s² | about 0.1 N·m |
| Wrist roll | 250 °/s | 3,000 °/s² | negligible |

Hand speed ≤ 1.2 m/s, hand jolt ≤ 9 m/s² (the `jolts.py` measure; printed links
flex, so an abrupt stop rings: the mark now has a physical reason too), floor 5 cm
(hand point 5 cm + disc radius), joint ranges unchanged.

### Check method

Joint speed and acceleration are measured on the **rendered curve** (the score's
quintic segments, sampled at 1 kHz; acceleration by second difference of the
sampled positions), not by the conservative hull proof, which overstates them by
up to about 1.5×. `EnsembleScore::validate` with the rig's own envelope still runs
and must pass. Hand checks stay at 60 fps.

### Regions (replace the region rule above)

1. Each of the 37 descriptors is **rank-normalised** over the 2,000 clips:
   value → (rank − 0.5) / 2,000. Distances are Euclidean in that space.
2. For every clip, d9 = distance to its 9th nearest other clip. **Candidate
   centres** are the clips with d9 at or under the median d9 (the denser half).
3. 8 centres by farthest-point sampling over the candidates only: the first is the
   candidate farthest from the mean, each next the candidate farthest from all
   chosen.
4. Membership, r, the 9-member requirement and the fill rule are as above.

Stretching, sampling (2,000 passing, seed 20261013), descriptors, triplets and
check 2b are unchanged.

## Addendum 2, 2026-10-13 (evening): clip length, minimum movement, region centres

Written after the rerun (commit `ee2d437`) and the user's first look at three
single clips, **before check 2b ran on anything**. Still round 1. Everything not
named here stands.

### Why

The user: "8 s and little to no movement"; the sudden, strong, free clip looked
"on some drugs, jittery or breaking". Measured per 8 s on the hand point: the
three first-look clips covered 0.95–1.89 m of path, a 21–49 cm box and 10–59° of
base turn; v47's Instant Crush (arm 0) covers a median 2.42 m, 78 cm and 178°.
v47 itself fits the cheap-servo limits nearly everywhere (base speed over its
limit 2.6 % of the time, shoulder 0.8 %, shoulder acceleration 1.7 %, the other
joints never), so the limits do not force small motion; the generator does.
Separately, the region rule stopped the rerun with 2 of 8 regions short of 9
members (6 and 7).

### Clip length: 16 s (user)

Clips are 16 s. Stretching maps clip time t to motion time 8 + (t − 8)/s. Triplets
are three 16 s clips side by side.

### Minimum movement (check 2a, new rule; user: the p10 of the dance)

Every clip, measured on the final 16 s at 60 fps, must reach the 10th percentile
of v47's whole 16 s windows on arm 0 over the three songs (`hexagon-47.html`,
`five-years-hexagon.html`, `presence-hexagon.html`, 54 windows):

| Measure | Floor |
|---|---|
| Hand path length | ≥ 3.67 m |
| Largest side of the box the hand covers | ≥ 0.74 m |
| Base turn range (max − min of base yaw) | ≥ 161° |

A clip below any floor fails check 2a like any other limit (the stretch ladder
applies; a vector failing at s = 1.95 is rejected and counted by reason).

### Region centres

If a centre's region stays under 9 members after the fill, that centre is
replaced by the next candidate in farthest-point order (the candidate farthest
from all centres kept), and its region is filled the same way. Every replacement
is reported with its reason.
