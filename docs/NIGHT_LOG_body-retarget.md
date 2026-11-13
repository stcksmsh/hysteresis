# Night log body-retarget (WO32B)

## MORNING SUMMARY
**BLOCKED, FOR USER / overseer: the accepted mapping + scale drive the arm into the table, so the gates cannot be met.** No clip is rendered.
Over the first 200 seeded candidates (the pick stream of RETARGET_RULES (e), 20 s windows, both variants simulated and gated as 7.44):
V1 passes 2, V2 passes 13, **both passes: 1** (10 needed). Failures per gate (200 candidates): V1 contact 194, limits 196, end stop 30, clearance 15, motion 1;
V2 contact 161, limits 184, end stop 40, clearance 1. The minimum hand height sits at the gate floor (0.11 m) in nearly every window. The "limits" fails are the contact impacts
(acceleration ratio 5-15 with contact substeps in the thousands, speed ratio 1.0-1.16); the limiter itself holds speed and acceleration (limiter share per joint 0.65-1.2).
Cause: the scale of (c) fills +-80 % of the distance from round 1's centre to the joint limit on the shoulder, elbow and wrist (shoulder -20..-100, elbow -34..94, wrist -91..61), and
pooled human reach covers all of it, so a large part of every window folds the hand to the table. Not a bug in the mapping code (angles sane: elbow flexion median 61 deg, all rotations orthonormal).
Nothing was changed after the rules push (the rules say so): options for the overseer, not tried:
(1) a smaller share than 80 % (or a shifted centre) for the three ranged joints; (2) a floor guard in the command path (clamp the commanded pose so FK keeps hand >= 0.11 m and links >= 0.05 m) —
a new mechanism, but the real installation will have red zones; (3) keep the scale and relax the contact gate (clips then show the arm pressing into the table; not recommended).
Code is in `scripts/body/retarget*.py` (pushed); `retarget_run.py clips|prep|refs|manifest` is ready to run once the choice is made. needs input: option 1, 2 or 3 (or other).

## Log
- 2026-11-13: branch body-retarget from origin/body 566071d. Rules file written, accepted (V2 elbow = lateral torso bend, FOR USER, kept).
- FineDance READY (origin/body-data b224446). Layout T x 315 = 3 root + 52 x 6D (first two ROWS of R, pytorch3d convention, read online); joint order SMPL-H; rules (h).
- Scale step: pooled yaw (accumulated spin, thousands of degrees) made the 5 s reference useless (scale 0.04); changed yaw/twist reference to the window start before computing (rules (i)).
  `docs/RETARGET_SCALE.json`: 203 sequences, 4,603 windows; base yaw scale 0.23 (heavy-tailed spins), others 0.56-5.1.
- Genres: 16 (case-insensitive). Stream of 200 candidates exhausted without 10 double passes (first run STOPped at candidate 200).
