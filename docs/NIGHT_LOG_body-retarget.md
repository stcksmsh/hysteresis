# Night log body-retarget (WO32B, WO32C)

## MORNING SUMMARY (WO32C)
**CLIPS READY d0644f0** (code commit; this log is the next commit on `body-retarget`). Clips are not shown to the user; the overseer checks first.

- **Gating on v2p** (rules (j), stream from candidate 1, both variants): 145 candidates used, **pass V1 13, V2 43, both 10**. Discards per gate: V1 limits 132, end stop 19; V2 limits 100, end stop 32, contact 2, clearance 2, guard 1 (a candidate can fail several).
  Guard (hold the last safe command): median share 0.0 for both variants, **maximum 0.0 over the 22 single clips** (it engaged on one discarded V2 candidate, > 10 %). Contact and clearance, the failures that blocked WO32B, are almost gone on v2p; what discards candidates now is the speed/acceleration limit and end stops.
  Limiter cut (share of the command the limiter removed) is small: at most 0.067 (6.7 %) on any joint of any of the 22 clips (checked over `numbers.json`), most values about 0, so the retargeted commands mostly stay within the limiter's speed and acceleration envelope. Mean hand speed C01_V1 0.35 m/s, C01_V2 0.15 m/s.
- **FOR USER / overseer: clip diversity.** Seven of the ten clips (C01, C02, C03, C05, C08, C09, C10) are windows of the same FineDance sequence **028** (genre `kun`, the only `kun` sequence, and a long one). The accepted replacement stream cycles the genre order, so `kun` came up many times and its windows pass the gates more often than most. Both reference clips (C01, C09) are windows of 028 too. Other clips: C04 dai 082, C06 hantang 027, C07 shenyun 110. Nothing was changed or re-picked (rules (e): no picking by hand). If a more varied set is wanted, a rule such as "one window per sequence" needs Kosta's/the overseer's decision.
- **Reference R1_S03** (round 1's S03 re-gated on v2p) on the music/window of C01 and C09: both pass all gates; rendered.
- **Renders:** `/secondary/hyst-data/body/retarget_look/clips/`: 22 mp4 (10 x V1, 10 x V2, 2 x R1_S03), 1280x720 h264 + aac, 20 s, the clip's FineDance music. CSVs in `work/`, `numbers.json` (per clip and variant: limiter share/cut per joint, guard share, every gate value, joint p5-p95, mean hand speed), `gating.json` (counts, genre order, picks), `manifest.json` (22 singles + 5 pairs, 32A's format).
- **Pairs:** clips C01, C02, C04, C05, C06 (seed 32031); **V1 first in 3 of 5** (C01, C05, C06; seed 32041), V2 first in C02 and C04: order is mixed (checked in `manifest.json`).
- **Frames looked at** (3 per clip at 2, 10 and 18 s, contact sheets in `frames/`; never to select or reshape): the pillar is visible at the old table height with the floor out of frame; the arm reaches below the column top beside the column without touching it; lamp, trail and projector patch as round 1; no clip shows interpenetration.
- **Camera:** unchanged (rules (j)). The page patch (`retarget_page.py`) failed twice during rendering (the `python -I` import path, then a wrong string match for the projector floor line); both fixed before any clip was rendered; the first render attempts produced no clips.
- **Battery:** gating and rendering ran on battery on the user's instruction (relayed by the overseer); the render script takes `HYST_BATTERY_OK=1`.
- Choices carried from (j), FOR USER: shoulder p1 exempt from the clearance margin, margins on p2-p4 and the hand ball (0.11 m), link segments covered by the contact gate.

## WO32B log
- 2026-11-13: branch body-retarget from origin/body. Rules file written and accepted (V2 elbow = lateral torso bend, FOR USER).
- FineDance READY; layout T x 315 = 3 root + 52 x 6D (first two ROWS, pytorch3d), joint order SMPL-H (rules (h)).
- Scale: window-start reference for yaw/twist (rules (i)); `docs/RETARGET_SCALE.json`: 203 sequences, 4,603 windows, base yaw scale 0.23.
- v2f gating failed (V1 passes 2, V2 13, both 1 of 200; contact 194/161): blocked, BRAIN_SPEC 7.51 (pillar mount).
