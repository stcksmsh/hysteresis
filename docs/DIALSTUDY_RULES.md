# Dial study rules (work order 28A, 2026-11-12)

Binding: `docs/BRAIN_SPEC.md` 7.43. Disposable study: no learning, no pass bars, no verdict by the builder. These rules are written before
any clip is rendered. Numbers marked (initial) may be changed for feasibility only; every change is logged in `docs/NIGHT_LOG_body-dial.md`
and in `docs/DIALSTUDY_DIALS.md`.

## (a) Body and stepping

- Body: the v2f model, rebuilt from the repo's own text: `make_arm_v2.xml_v2(kv, condim=1, table_z=RAISED_PLANE_Z)` (arm of `make_arm.py`,
  table plane at z = 0.053 m, self-collision of links, base column and ball sphere), every collision geom `solref = [0.006, 1]`
  (contact time constant, as pass2's CFG). Mirror-ball mass and inertia stay for all clips (shapes in Set C are visual only).
- Stepping: **plain MuJoCo on CPU** (`mujoco` python in `/secondary/hyst-env/body`, default solver iterations, no MJX), one process per
  clip, six processes at a time, `taskset -c 6-11`, 6 threads in all. Same loop as `m3f_jax.arm_step` with `clip=True`: 100 Hz control,
  5 physics substeps of 2 ms; the commanded target goes through the braking-aware limiter of `arm_sim.ArmSim.limit_target` (speed and
  acceleration of `make_arm.LIMITS`), ranged targets are clipped 0.5 deg inside the range, and after every substep the ranged joint
  positions are clipped to the range (hard stop, outward speed zeroed).
- Servo gains per clip: `kp = KP * kp_scale`, `kv = 2 zeta sqrt(kp I)` with `I` the mass-matrix diagonal of `make_arm.tune_kv` (straight-out
  pose); set in the actuator `gainprm` / `biasprm`. Stall force range unchanged.
- Each clip starts with 1.5 s of pre-roll holding the first pose (so droop and settling are not in the shown clip); 12.0 s are recorded.
- The 50 Hz joint CSV is the realised joint angles of the physics (every second control step, t = 0 at the clip start), in the
  `arm_sim.csv_text` format.

## (b) Underlying movement

- Seed `28011`; a fixed `numpy.random.default_rng(28011)` draws, once, `Z`: 12 x 5 values uniform in [-1, 1]. Row k is pose k in
  normalised excursion units. Pose k in degrees = `centre(posture) + Z[k] * amp * vigour_scale`. The sequence `Z` is the same in every clip;
  clips differ only by dial settings. Not v47, no v47 data read.
- Grid: 100 BPM, beat 0.6 s. One move per **two beats** (interval 1.2 s), 10 moves in 12 s; pose 0 is held at the start.
  Move k leaves pose k-1 at `k * 1.2 s`; it ends at `k * 1.2 + share * 1.2 s` (share is set by vigour, see (c)).
- Neutral amplitudes (deg): base yaw 30, shoulder 12, elbow 16, wrist bend 16, wrist roll 45.

## (c) Dials (value d in [-1, +1]: -1 low, 0 neutral, +1 high; presets may use values between)

1. **Vigour**: excursion scale `0.35 -> 1.0 -> 1.7` (d = -1, 0, +1, piecewise linear) and move time share of the interval
   `0.95 -> 0.70 -> 0.45`. Peak speed and acceleration are held by the limiter inside `LIMITS`.
2. **Stiffness**: `kp_scale 0.45 -> 1.0 -> 2.5`, `zeta 0.3 -> 1.5 -> 1.0` (log-linear in d for kp, linear for zeta).
   Loose: overshoots and settles; rigid: stops dead.
3. **Roundness**: blend `rho = (d + 1) / 2` between two joint-space paths through the same poses: (angular) joint-linear segments with a
   short ease (trapezoid, 15 % each end), stopping at every pose; (round) a C1 Catmull-Rom spline through the same poses at their
   arrival times, flowing without stopping.
4. **Lead/lag**: per-joint start offsets `lag01 * [0, 0.20, 0.60, 1.00, 1.40]` beats for (base, shoulder, elbow, wrist bend, wrist roll),
   with `lag01 = (d + 1) / 2`: low = all together, high = base and shoulder lead, wrist roll follows 0.84 s late (raised from the first 0.10-0.70 beats: a first look at the CSVs showed under 0.4 s and almost no change from neutral).
5. **Posture**: centre pose `(base, shoulder, elbow, wrist bend, roll)` `low = (0, -45, 60, -70, 0)`, `neutral = (0, -60, 30, -15, 0)`,
   `high = (0, -80, 10, -20, 0)` deg, linear in d; low = drooped, low, folded; high = lifted, tall, open (the study's neutral is not the rig's home pose; the wrist
   is cocked up in low and neutral so the hand clears the plane; revised from the first numbers for feasibility: with the first amplitudes
   and centres the hand sat on the plane at vigour high / posture low / stiffness low; kp and zeta of low stiffness raised because at
   kp 0.3 the shoulder droops 17 deg and the arm lies on the plane).
- Non-dial words (do not change the pose sequence): **long holds** (tense) = share multiplied by 0.55; **bouncy** (light) = zeta forced to
  0.2 at any kp_scale.

## (d) Glitch gates (clip rejection, not pass bars; evaluated on the 50 Hz realised CSV and on every physics substep)

A clip is shown to nobody unless all hold:
1. **Clearance**: at every CSV sample, `m3f_report` rule: FK points 1-4 at least `FLOOR_M = 0.05` m above z = 0 and the hand point
   at least `FLOOR_M + DISC_M = 0.11` m above it (check-csv).
2. **No contact**: no MuJoCo contact (table, base column, link-link, ball) at any physics substep of the 12 s (pre-roll included).
3. **End stops**: no ranged joint (shoulder, elbow, wrist bend) within 3 deg of its `RANGE_DEG` limit for more than 0.1 s (6 or more
   consecutive 50 Hz samples).
4. **Jitter**: (i) share of joint-velocity power above 8 Hz (Welch, 4 s windows, joints 0-3 summed, 50 Hz data) at most
   `max(3 x all-neutral value, 0.01)`; (ii) velocity sign reversals per second (1 deg/s dead band) per joint at most
   `max(3 x the all-neutral maximum over joints, 6)`. Thresholds are computed from the all-neutral clip and written to the manifest.
   Settling overshoot of a loose servo is allowed; buzzing is not.
5. **Limits**: joint speed and acceleration of the CSV inside `LIMITS` (5 % tolerance for finite-difference noise), no NaN.

Plus a human check by the builder: 3 frames per clip and a fast-forward contact sheet looked at before a clip is listed as passed.
A failing clip is regenerated inside its dial or preset intent (ranges adjusted for feasibility only, logged). Never shown while failing.
