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

## Addendum 3, 2026-10-13 (night): every joint dances, the rule is rechecked, the arm stays in frame

Written after the run of commit `a86aae9` and the user's look at its three 16 s
clips, **before check 2b ran on anything**. Still round 1. Everything not named
here stands.

### Why

The user, on the three clips: a "fluid, but almost all is base moving, the elbow
joint not at all and almost no disc spin"; b "spin, stop, reposition, spin, stop,
reposition … only base and shoulder joint working really, mechanical looking,
like an assembly line machine"; c "somewhere in between … a bit of elbow
movement, some disc rotation, but still the same issues". Measured, total joint
motion per 16 s (degrees): v47 arm 0 over the three songs, median (p10) base 669
(386), shoulder 220 (148), elbow 442 (299), wrist bend 599 (454), roll 603 (370);
the sweep's low/high medians base 468–751, shoulder 98–148, elbow 93–126, wrist
bend 34–56, roll 91–260. Also: after the 26 centre replacements, 6 of 8 regions
had a mean within-region distance over a quarter of the mean centre-to-centre
distance (0.756–0.861 against 0.752); the rule was not rechecked. Clip b's disc
left the top of the frame at about 10 s.

### Per-joint motion floors (check 2a, new rule)

Every clip, on the final 16 s at 60 fps, total motion (sum of |Δ angle| per frame)
of each joint at least the v47 p10 above (54 whole 16 s windows, arm 0, the
three exports; knots interpolated linearly at 60 fps):

| Joint | Floor, degrees per 16 s |
|---|---|
| Base yaw | 386 |
| Shoulder | 148 |
| Elbow | 299 |
| Wrist bend | 454 |
| Wrist roll | 370 |

A clip below any floor fails check 2a like any other limit.

### In frame (check 2a, new rule)

Every world point of the arm and the disc's whole radius stay inside the
recorded frame at every 60 fps frame, with a 20 px margin, using the camera the
test clips are recorded with. The camera may be changed for the study (report
how); the shared preview template `crates/hyst-previz/src/ensemble.html` may not,
because v47's exports embed it byte for byte.

### Region rule after replacement

The quarter rule (mean within-region pairwise distance under a quarter of the
mean centre-to-centre distance, in every region) and the membership radius r are
checked on the **final** centres and members, after every replacement and fill.
If the final set breaks the rule, the study stops and reports.

## Addendum 4, 2026-10-13 (night): a region is one body vector, separated by its seed spread

Written after the run of commit `1b22eee` and the user's approval of its three
first-look clips, **before check 2b ran on anything**. Still round 1. It replaces
the region membership, r, the fill, the quarter rule and its recheck. Everything
not named here stands: rank-normalised descriptors, candidate centres, sampling,
check 2a with all its floors and the frame rule, triplets and check 2b.

### Why

The final region check of `1b22eee` failed: mean within-region distance
0.85–1.02 in all 8 regions, against a quarter of the mean centre-to-centre
distance, 0.633 (recomputed by the overseer: 0.86–1.04 against 0.632). The rule
cannot pass in this space: clips made from one body vector with fresh seeds sit
0.85–1.0 apart, so seed noise alone is over the limit; the median distance to a
clip's 9th nearest neighbour is 1.37, over r = 0.90, so no sweep clip but the
centre fell inside any region, and 814 centre replacements followed. The user
chose to anchor the rule to the seed noise: the test is about body parameters,
not about which seed a clip drew.

### Regions (replace membership, r, the fill and the quarter rule)

1. **Centres** as before: farthest-point sampling over the candidate centres (d9
   at or under the median, rank space over the 2,000 sweep clips).
2. **A region is one body vector**: its centre sweep clip plus 8 clips made from
   the same body vector with fresh content seeds (seed order fixed by seed
   20261015). Each made clip must pass check 2a exactly as a sweep clip does
   (stretch ladder, floors, frame); a seed that fails is skipped and counted.
   Up to 200 seeds per region. A region short of 9 clips after 200 seeds has its
   centre replaced (step 5).
3. Made clips are ranked against the 2,000 sweep clips: per descriptor,
   (number of sweep values below + 0.5) / 2,000.
4. For each region i: **seed spread** w_i = mean pairwise distance of its 9
   clips; **position** m_i = mean of its 9 rank vectors.
   **Separation rule:** for every pair of regions,
   |m_i − m_j| ≥ 1.5 × max(w_i, w_j).
5. **Replacement.** While a pair breaks the rule, take the pair with the smallest
   ratio |m_i − m_j| / max(w_i, w_j), replace the later-chosen of its two centres
   by the next candidate in farthest-point order (the candidate farthest from all
   centres kept), and build its region by step 2. Every replacement is reported
   with its pair, ratio and reason. If the candidates run out, the study stops and
   reports.
6. **Reported** for the final set: every w_i, every pairwise |m_i − m_j| and
   ratio, the smallest ratio, seeds tried and skipped per region (by reason), and
   the stretch of each of the 72 clips.

The factor 1.5 was proposed by the overseer and accepted by the user. A probe on
the made clips of `1b22eee` (approximate ranks, 7 regions) gave ratios 1.23 to
2.8, with 2 of 21 pairs under 1.5.

## Addendum 5, 2026-10-13 (night): test the last region set as built

Written after the run of commit `90cbec8`, **before check 2b ran on anything**.
Still round 1. Everything not named here stands; check 2b and its pass mark
(16 of 24) are unchanged.

### Why

The separation rule of addendum 4 failed with every candidate used: over 1,000
regions built, the worst pair's ratio never exceeded 0.86. Addendum 4's estimate of
the seed spread (0.85–1.0) was biased low: those clones had been kept only inside
r = 0.90 of their centre. The real seed spread is a median 1.93; two random sweep
clips are a median 2.41 apart; the variance inside a region is about 0.52 of the
sweep's. In descriptor space the seed explains about half of what the clips show.
The descriptors are not the judge (see Descriptors). The user chose to let their
eye decide whether body differences show through the seed.

### Regions (replace the separation factor)

- The 8 regions are **exactly the final set in `r5/regions.json`** of `90cbec8`:
  centres 1706, 1966, 529, 786, 1582, 365, 1919, 183 (in that slot order), each
  with its 9 clips (body vector, seed, stretch) as stored. Nothing is rebuilt or
  replaced.
- The factor becomes **0.6**. This value was set after the result, only to name
  the set tested; its smallest ratio is 0.618. It scores nothing: check 2b does.
- Ranks are as addendum 4 defines them for every clip. Three lag descriptors
  (33–35) take about 60 distinct values; the r4 centre selection broke their ties
  arbitrarily. This is recorded, not redone.
- Expected from the descriptors, stated before the test: a weak separation. A
  failing check 2b points at the generator (how much the seed decides against the
  body vector), not at the test.

## Addendum 6, 2026-10-13 (night): how a triplet is viewed

Written after commit `9337b00` and the user's first try of its answer page,
**before any answer was given** (the user stopped before answering; no check 2b
result exists). Still round 1. It replaces "plays once" (NEXT_BODY_THEN_MIND.md
step 1.5) and how a triplet is shown. Unchanged: the 72 clips, the 24 triplets,
the shuffle, `r5/key.json`, the pass mark of 16 of 24 (chance 1/3 per triplet,
p ≈ 0.0009).

### Why

The user: "This sort of comparison doesnt work without seek/pause etc, there are 3
videos running simultaneously, I cant keep up with all 3 and compare all of
them". Asked how to show a triplet, the user chose both views below.

### Viewing (replaces "plays once")

- The A | B | C stack plays with one shared bar: play, pause, seek, replay.
- Each of A, B and C has a [+] that opens that clip alone at 1280 x 720 with its
  own play, pause, seek and replay. The single clip is cut from the stack (same
  pixels, no ids).
- Viewing time, replays and single-clip views are unlimited and in any order.
- One triplet at a time, as before. An answer is final: no going back to an
  answered triplet.
- The answers file also records per triplet: time spent, plays of the stack, and
  opens of each single clip. These are data only, never a gate or a score.

## Addendum 7, 2026-10-13 (night): one clip at a time; the first answer counts

Written after addendum 6 and **before any answer was given**. Still round 1. It
replaces addendum 6's viewing in full (addendum 6 was never built). Unchanged: the
72 clips, the 24 triplets, the shuffle, `r5/key.json`, the pass mark of 16 of 24
(chance 1/3 per triplet, p ≈ 0.0009).

### Why

The user rejected the stack: three arms moving at once cannot be followed.
Unlimited viewing before answering lets a viewer compare details that come from
the seed (where the arm is at a given second) rather than the character of the
motion, which an installation viewer sees once, in passing. This follows the
sequential triangle test of sensory science. The user accepted this proposal.

### Viewing (replaces addendum 6)

1. **First pass.** A, B and C play one after another, each alone at 1280 x 720,
   16 s each, with 1 s of black between them. The current letter is shown beside
   the video, never on it. Pause is allowed; seek, rewind and replay are not.
   No two clips ever play at the same time.
2. **Counted answer.** After C ends, the viewer answers A, B or C. This answer is
   the one check 2b scores. It is final.
3. **After the counted answer.** Any single clip may be replayed, as often as
   wanted, one at a time, with play, pause and seek. An optional second answer and
   the optional free text ("what did the odd one look like?") are recorded as data
   only, never scored.
4. One triplet at a time, in the shuffled order; no going back to an answered
   triplet.
5. Progress is saved after every triplet and the test can resume, so it may be
   taken in sittings (suggested: two of 12).
6. Recorded per triplet: counted answer, second answer, free text, time to the
   counted answer, total time, pauses during the first pass, replays per clip.
   Data only.

The single clips are the 1280 x 720 crops of the stacks (frame-identical to their
third of the stack, no ids in names or metadata).
