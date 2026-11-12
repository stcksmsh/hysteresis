# Dial study: dials, ranges, presets (work order 28A, 2026-11-12)

Code: `scripts/body/dialstudy.py` (movement, dials, simulation, gates), `dialstudy_render.sh`, `dialstudy_manifest.py`. Rules and gates:
`docs/DIALSTUDY_RULES.md`. Dial value d in [-1, +1]: -1 low, 0 neutral, +1 high. Underlying movement: seed 28011, 12 poses, 100 BPM, one move
per two beats (1.2 s), the same normalised sequence in every clip. No reading of the clips is given here.

## The five dials (two lines each: how, numeric range)

1. **Vigour.** Scales each pose's excursion about the posture centre and sets the share of the 1.2 s interval a move takes (a move ends
   early in its interval and the pose is held); the servo limiter keeps speed and acceleration inside `make_arm.LIMITS`.
   Range: excursion scale 0.35 / 1.0 / 1.7; move share 0.95 / 0.70 / 0.45 (neutral amplitudes 30, 12, 16, 16, 45 deg for base, shoulder, elbow,
   wrist bend, wrist roll).
2. **Stiffness.** Servo gain `kp = KP * kp_scale` and damping `kv = 2 zeta sqrt(kp I)` set per clip in the MuJoCo position actuators.
   Range: kp_scale 0.45 / 1.0 / 2.5 (KP = 16.8 N.m/rad, stall at 10 deg error), zeta 0.3 / 1.5 / 1.0 (loose: overshoots and settles; rigid: stops dead).
3. **Roundness.** Blend between joint-linear segments with a 15 % trapezoid ease that stop at every pose (angular) and a C1 Catmull-Rom
   spline through the same poses at their arrival times that never stops (round). Range: blend 0 / 0.5 / 1 (rho = (d + 1) / 2).
4. **Lead/lag.** Per-joint start delay, base leads and the wrist follows late. Range: delays (base, shoulder, elbow, wrist bend, wrist roll) =
   lag01 x (0, 0.2, 0.6, 1.0, 1.4) beats, lag01 = 0 / 0.5 / 1 (a beat = 0.6 s), so at high the wrist roll is 0.84 s behind the base.
5. **Posture.** The centre pose the random excursions are drawn around, linear in d. Range (base, shoulder, elbow, wrist bend, roll, deg):
   low (0, -45, 60, -70, 0), neutral (0, -60, 30, -15, 0), high (0, -80, 10, -20, 0). The study's neutral is not the rig's home pose; the wrist
   is cocked up when the arm is low so the hand stays clear of the plane.

Non-dial words (the pose sequence does not change): **long holds** = move share x 0.55; **bouncy** = zeta forced to 0.2.

## Feasibility changes made while building (before any clip was shown to anybody)

- First amplitudes (12, 18, 20 deg) and centres (low 38/55/25, neutral = rig home) put the hand on the plane at vigour high or posture low:
  amplitudes cut to 12, 16, 16, centres replaced as above, wrist cocked up.
- Stiffness low was kp_scale 0.3, zeta 0.25: the shoulder drooped 17 deg and the arm lay on the plane. Now 0.45 and 0.3 (droop at neutral
  posture 9 deg at the shoulder).
- Lag delays first 0 to 0.7 beats: moved the wrist by under 0.4 s and looked like no change in the joint CSVs; raised as listed.
  (Everything rendered with the first lag values was discarded and re-rendered.)

## Presets (Set B), final values

| preset | vigour | stiffness | roundness | lag | posture | other |
|---|---|---|---|---|---|---|
| heavy | -1 | +1 | +1 | +1 | -1 | |
| angry | +1 | +1 | -1 | -1 | +1 | |
| tense | -0.6 | +1 | -1 | -1 | +1 | long holds (share x 0.55) |
| calm | -1 | -1 | +1 | +0.5 | 0 | |
| light | +0.6 | -1 | +1 | 0 | +1 | bouncy (zeta 0.2) |

These are the starting recipes of BRAIN_SPEC 7.43.4 mapped onto the ranges above (no preset needed a feasibility change). "Together" = lag -1,
"flowing lag" = +0.5, "large lag" = +1, "angular" = roundness -1.

## STS3215 plausibility of the stiffness range (best estimate, UNVERIFIED)

The Feetech STS3215 (12 V, 30 kg.cm stall class) is a position servo with its own on-board loop: it exposes a position P gain (and I, D)
and a torque limit; velocity feedback is internal. The simulated gains reach full stall torque (2.94 N.m) at an error of 22 deg
(kp_scale 0.45), 10 deg (1.0) and 4 deg (2.5): a loose servo in that sense is within what its P setting can do, and 4 deg for stall is on the
firm side but plausible. The real doubtful part is damping: zeta 0.3 (a clearly visible overshoot) needs the on-board D term low, and a real
STS3215 is geared 1:345 with large reflected friction and backlash, which the model does not include (it has armature inertia but no friction
or backlash), so a real servo is probably better damped and stiffer-feeling than the loose end here. Nothing was measured; no servo data sheet
for loop gains was consulted (no network).
