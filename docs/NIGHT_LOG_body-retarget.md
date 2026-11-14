# Night log body-retarget (WO32B, WO32C)

## MORNING SUMMARY (WO32D): CLIPS READY 0be1f71

**CLIPS READY 0be1f71** (code commit; this log is the next commit on `body-retarget`). Clips are not shown to the user; the overseer checks first. Rules: notes (k) limiter fix, (l) tolerance 1.25 and pick rule.

- **Re-gate** (fixed limiter, tolerance 1.25 on speed and acceleration, pick rule, v2p, stream from candidate 1; clips taken at candidates 0, 1, 4, 5, 13, 19, 21, 24, 25, 26): **27 candidates used; pass V1 14, V2 16, both 11; skipped by the pick rule 1 (sequence already taken); 10 taken.** Discards per gate (a candidate can fail several): V1 limits 12, end stop 2; V2 end stop 7, limits 8, contact 1, clearance 1, guard 1. Guard median 0.0 for both variants, maximum over the 22 clips 0.005. Highest realised ratios on any clip: speed 1.10, acceleration 1.247 (limit 1.25).
- **Picks:** 10 distinct sequences, genres kun, urban, korean, dunhuang (2), miao, hantang, jazz, dai, breaking (9 genres, none above 2): C01 kun 028 (53.1 s), C02 urban 204 (9.1), C03 korean 206 (11.9), C04 dunhuang 021 (33.2), C05 miao 136 (29.0), C06 hantang 044 (120.2), C07 dunhuang 051 (66.7), C08 jazz 125 (170.3), C09 dai 045 (240.0), C10 breaking 054 (21.0). (The street styles are in: urban, breaking.)
- **Reference R1_S03** (round 1's S03, on v2p, at 1.25) on the music/window of C01 (kun 028) and C09 (dai 045): both pass all gates (speed 0.42 / 0.44, acceleration 0.27 / 0.25 x limit). **FOR USER:** the reference now runs through the fixed limiter (`retarget_limiter.simulate_goals`, so all three variants share one body), so it is not byte-identical to the round-1 S03 clip Kosta saw.
- **Pairs** C01, C02, C04, C05, C06: **V1 first in 3** (C01, C05, C06), V2 first in C02 and C04 (checked in `manifest.json`). 10 distinct sequences, at most 2 per genre: checked.
- **Frames looked at** (3 per clip at 2, 10, 18 s, contact sheets in `frames/`, never to select or reshape): pillar at the old table height, arm reaching below the top beside the column without touching it, no interpenetration seen; the references look like round 1's (small, repeated hand loop).
- **Outputs:** `/secondary/hyst-data/body/retarget_look/`: `clips/` 22 mp4 (1280x720 h264 + aac, 20 s), `work/` CSVs, `numbers.json` (WO32C's numbers + `shoulder` per clip and variant), `gating.json`, `manifest.json` (22 singles + 5 pairs). WO32C outputs kept in `v2p_1.05/`; the aborted 1.25 run (gate verdict bug, then a NameError) in `v2p_1.25_aborted/` (`clips2.err` = the crash).
- **What the limiter cut (7.52.5):** the human shoulder command is far over the servo's limit: commanded shoulder acceleration p50 / p95 / max (x limit) V1 0.14-2.75 / 0.7-14.1 / 1.4-34.2, V2 0.07-1.38 / 0.55-5.4 / 1.2-26.2 (table below); the limiter changed the shoulder command in 40-100 % of 100 Hz frames (V1 76-100 % except C01 86 %; V2 40-100 %) with an RMS of (command - limiter output) of 1.4-23.6 deg (V1 1.6-23.6, V2 0.1-10.7). The realised shoulder acceleration stays at p95 <= 0.97 x limit, max <= 1.25 x.

Per clip: shoulder acceleration (x limit) commanded p50 / p95 / max | realised p50 / p95 / max | limiter share | RMS(command - limiter out) deg | worst realised speed ratio | worst realised accel ratio (any joint):

| clip | commanded | realised | limiter share | RMS deg | speed | accel |
|---|---|---|---|---|---|---|
| C01_V1 | 0.14 / 0.70 / 1.4 | 0.09 / 0.42 / 0.70 | 86 % | 1.6 | 1.00 | 0.70 |
| C01_V2 | 0.07 / 0.55 / 1.2 | 0.04 / 0.18 / 0.39 | 40 % | 0.1 | 0.65 | 0.41 |
| C01_R1S03 | (network output) | - | - | - | 0.42 | 0.27 |
| C02_V1 | 2.75 / 11.71 / 34.2 | 0.40 / 0.95 / 1.18 | 100 % | 19.9 | 1.00 | 1.18 |
| C02_V2 | 1.38 / 5.44 / 16.8 | 0.34 / 0.88 / 1.25 | 100 % | 9.8 | 1.03 | 1.25 |
| C03_V1 | 2.72 / 14.11 / 26.6 | 0.39 / 0.89 / 1.14 | 100 % | 16.0 | 1.00 | 1.14 |
| C03_V2 | 1.38 / 5.41 / 26.2 | 0.38 / 0.88 / 1.25 | 100 % | 9.9 | 1.00 | 1.25 |
| C04_V1 | 0.81 / 4.38 / 17.7 | 0.44 / 0.93 / 1.09 | 100 % | 20.0 | 1.10 | 1.09 |
| C04_V2 | 0.24 / 1.34 / 2.9 | 0.10 / 0.52 / 0.74 | 65 % | 1.6 | 1.00 | 0.89 |
| C05_V1 | 0.61 / 2.89 / 14.7 | 0.32 / 0.82 / 1.21 | 99 % | 12.6 | 1.03 | 1.21 |
| C05_V2 | 0.53 / 2.37 / 4.2 | 0.29 / 0.65 / 0.91 | 99 % | 2.4 | 0.98 | 0.91 |
| C06_V1 | 0.39 / 3.96 / 12.9 | 0.22 / 0.85 / 1.18 | 76 % | 11.9 | 1.01 | 1.18 |
| C06_V2 | 0.28 / 1.49 / 2.9 | 0.14 / 0.51 / 0.87 | 75 % | 1.4 | 1.02 | 0.90 |
| C07_V1 | 1.00 / 5.94 / 16.7 | 0.35 / 0.97 / 1.23 | 90 % | 15.3 | 1.04 | 1.23 |
| C07_V2 | 0.49 / 2.60 / 15.5 | 0.21 / 0.75 / 1.06 | 90 % | 7.9 | 1.03 | 1.06 |
| C08_V1 | 1.15 / 5.64 / 15.3 | 0.35 / 0.81 / 1.19 | 100 % | 13.6 | 1.10 | 1.19 |
| C08_V2 | 0.59 / 2.67 / 7.0 | 0.17 / 0.52 / 0.93 | 92 % | 2.3 | 0.72 | 0.93 |
| C09_V1 | 2.07 / 9.24 / 24.7 | 0.37 / 0.93 / 1.20 | 99 % | 23.6 | 1.03 | 1.20 |
| C09_V2 | 1.22 / 4.31 / 9.5 | 0.46 / 0.86 / 1.18 | 100 % | 10.7 | 1.06 | 1.18 |
| C09_R1S03 | (network output) | - | - | - | 0.44 | 0.25 |
| C10_V1 | 2.37 / 11.89 / 29.2 | 0.43 / 0.89 / 1.25 | 100 % | 16.0 | 0.96 | 1.25 |
| C10_V2 | 1.28 / 4.43 / 7.9 | 0.38 / 0.91 / 1.20 | 100 % | 9.8 | 0.99 | 1.20 |

(C01 is the one low-demand clip: its commanded shoulder acceleration stays near the limit, so the limiter hardly acts. In the others the command is 5-34 x over the limit at its peak and the limiter changes it in nearly every frame; the clip shows the arm's response to the limited command, not the human motion.)

## WO32D step A: LIMITER FIXED (see the commit that carries this line; rules notes (k) and (l))

A bug, not a measurement artefact: the command limiter clamps its target to the joint range with no braking for the edge and a stale velocity state (wind-up). Limiter output over the 290 candidate/variant pairs, gate measure: > 1.05 x the acceleration limit on 35 (shoulder 35: V1 8, V2 27; elbow 21, wrist bend 29; continuous joints 0); worst candidate 30 (V2) **3.20 x before, 1.000 x after**; after the fix **no joint exceeds 1.0 x on any of the 290**. Fix and test: `scripts/body/retarget_limiter.py`, `test_retarget_limiter.py` (4 tests, one fails on the round-1 limiter). Round-1 files untouched. Diagnostic: `retarget_limiter_diag.py`. Re-gate (tolerance 1.25, pick rule) follows.

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

## LIMITS BREAKDOWN be4a023 (report only, nothing adopted)

Re-ran the same 145 candidates, both variants (same stream, same v2p path, cores 6-11); script `scripts/body/retarget_limits.py`, full per-candidate data in
`/secondary/hyst-data/body/retarget_look/limits_breakdown.json` (outside git). Ratios as `dialstudy.gate_values`: realised 50 Hz rows, speed = diff x 50 / limit, acceleration = second difference x 2500 / limit.
Limits (deg/s, deg/s2): base 120/600, shoulder 90/300, elbow 150/1000, wrist bend 200/2000, wrist roll 250/3000. Medians over the 145 candidates.

**1 and 2 and 3, per joint** (realised ratio; limiter cut share = 1 - limiter-output p5-p95 / command p5-p95; overshoot = realised ratio - limiter-output ratio; command ratio = the retargeted command before the limiter):

| joint | V1 speed | V1 accel | V1 cut med (max) | V1 overshoot spd / acc | V1 command spd / acc | V2 speed | V2 accel | V2 cut med (max) | V2 overshoot spd / acc | V2 command spd / acc |
|---|---|---|---|---|---|---|---|---|---|---|
| base yaw | 0.59 | 0.42 | 0.000 (0.15) | -0.12 / -0.53 | 0.82 / 1.5 | 0.54 | 0.37 | 0.000 (0.08) | -0.11 / -0.60 | 0.79 / 1.5 |
| shoulder | 0.96 | **1.24** | 0.018 (0.35) | -0.04 / +0.23 | 3.3 / 21.8 | 0.83 | **1.14** | 0.002 (0.77) | -0.12 / +0.05 | 1.9 / 8.7 |
| elbow | **1.02** | 0.93 | 0.066 (0.40) | +0.02 / -0.07 | 4.4 / 15.2 | 0.97 | 0.90 | 0.005 (0.74) | -0.02 / -0.14 | 2.0 / 5.4 |
| wrist bend | 1.01 | 0.90 | 0.059 (0.47) | +0.01 / -0.10 | 5.2 / 14.6 | 0.99 | 0.89 | 0.013 (1.00) | 0.00 / -0.11 | 3.1 / 8.5 |
| wrist roll | 1.00 | 0.88 | 0.036 (0.21) | 0.00 / -0.12 | 4.8 / 10.5 | 1.00 | 0.88 | 0.028 (1.00) | 0.00 / -0.12 | 4.4 / 12.2 |

Which joint sets the failing maximum (candidates with a worst ratio > 1.05): **acceleration is the shoulder in every case** (V1 132 of 145, V2 97 of 145; no other joint ever sets it). Speed: shoulder 19 and elbow 18 (V1), shoulder 15 and elbow 17 (V2); never base, wrist bend or wrist roll.
The command limiter itself sits at its own acceleration bound on the shoulder (limiter-output accel ratio about 1.0, realised 1.24 / 1.14): the servo adds a median +0.23 (V1) / +0.05 (V2) of acceleration overshoot on that joint, and on speed adds at most a few hundredths. The limiter shrinks the p5-p95 range little (median cut 0 to 7 %; it delays the command rather than flattening it), but the raw retargeted shoulder command is far over the limits (median 3.3x speed, 22x acceleration on V1).

**4, per genre: median of the worst speed / worst acceleration ratio (9 candidates each; `kun` 10)** and "limits" passes at 1.05, V1 | V2:

| genre | V1 spd / acc | V1 pass | V2 spd / acc | V2 pass |
|---|---|---|---|---|
| breaking | 1.00 / 1.23 | 0 | 1.07 / 1.22 | 0 |
| chinese | 1.05 / 1.28 | 1 | 1.07 / 1.28 | 0 |
| choreography | 1.02 / 1.39 | 0 | 1.02 / 1.21 | 1 |
| dai | 1.03 / 1.16 | 1 | 1.06 / 1.06 | 4 |
| dunhuang | 1.07 / 1.26 | 0 | 1.03 / 1.03 | 5 |
| hantang | 1.05 / 1.22 | 1 | 1.03 / 1.00 | 4 |
| hiphop | 1.01 / 1.28 | 1 | 1.02 / 1.25 | 0 |
| jazz | 1.04 / 1.27 | 0 | 1.02 / 1.22 | 1 |
| korean | 1.03 / 1.30 | 0 | 1.00 / 1.18 | 2 |
| kun | 1.02 / 0.85 | 7 | 0.89 / 0.55 | 10 |
| locking | 1.00 / 1.28 | 0 | 1.01 / 1.37 | 0 |
| miao | 1.03 / 1.21 | 0 | 1.00 / 1.02 | 6 |
| popping | 0.99 / 1.25 | 0 | 1.01 / 1.09 | 2 |
| shenyun | 1.04 / 1.20 | 1 | 1.01 / 1.07 | 4 |
| urban | 1.00 / 1.27 | 1 | 1.01 / 1.32 | 1 |
| wei | 1.04 / 1.32 | 0 | 0.99 / 1.05 | 5 |

**5, "limits" gate pass counts at the tolerance on speed and acceleration ratios** (145 candidates; counts only):

| tolerance | V1 limits only | V2 limits only | V1 all gates (other gates as run) | V2 all gates | **both variants, all gates** |
|---|---|---|---|---|---|
| 1.05 (current) | 13 | 45 | 13 | 43 | **10** |
| 1.25 | 77 | 104 | 62 | 89 | **43** |
| 1.5 | 136 | 138 | 118 | 112 | **93** |

(V1 13 and V2 43 at 1.05 match the gating run's pass counts; "limits only" counts ignore every other gate, "all gates" holds the other gates as they were.)

## WO32B log
- 2026-11-13: branch body-retarget from origin/body. Rules file written and accepted (V2 elbow = lateral torso bend, FOR USER).
- FineDance READY; layout T x 315 = 3 root + 52 x 6D (first two ROWS, pytorch3d), joint order SMPL-H (rules (h)).
- Scale: window-start reference for yaw/twist (rules (i)); `docs/RETARGET_SCALE.json`: 203 sequences, 4,603 windows, base yaw scale 0.23.
- v2f gating failed (V1 passes 2, V2 13, both 1 of 200; contact 194/161): blocked, BRAIN_SPEC 7.51 (pillar mount).
