# Retarget look test rules (work order 32B, 2026-11-13)

Binding: `docs/BRAIN_SPEC.md` 7.49.5, 7.50 (incl. 7.50.8). Disposable look test: **no training, no learning, no hand-picking of clips, no shaping by
eye, no verdict by the builder.** One arm. Written and pushed before any clip is rendered or viewed; once pushed, no mapping, scale or pick rule is
changed. Numbers that depend on the data (pooled percentiles) are computed once by `scripts/body/retarget_scale.py` from joint angles only (no clip
is rendered or viewed), written to `docs/RETARGET_SCALE.json`, and committed before any render. Code: `scripts/body/retarget.py` (angles, scaling),
`retarget_run.py` (picks, sim, gates, manifest), `retarget_render.sh`.

## (a) Source

FineDance public part, `/secondary/hyst-data/datasets/finedance/` (motion, music_wav, label_json), used locally only (7.50.3: no upload, music
credited in the manifest). If `docs/NIGHT_LOG_body-data.md` on `origin/body-data` says "FINEDANCE BLOCKED" instead of "FINEDANCE READY", Motorica
Dance (BVH, single dancer, music included) is used and the switch is reported in the night log and here; the mapping below then reads the BVH local
rotations with the same canonical directions. **Switch status: none (FineDance), updated if that changes.**

Motion file `motion/NNN.npy`: `T x 159`, columns 0-2 root translation (unused), columns 3-158 = 52 joints x 3 axis-angle **local** rotations of the
SMPL-H skeleton, 30 fps (to be confirmed on the unpacked files; a different layout is logged and fixed before this file's scale step). Only the first 22 joints are used:
0 pelvis, 3 spine1, 6 spine2, 9 spine3, 12 neck, 14 R collar, 15 head, 17 R shoulder, 19 R elbow, 21 R wrist.

**No SMPL / SMPL-H model file.** Everything below uses local rotations and canonical T-pose bone directions only (right arm along -x, left +x, spine,
neck, head along +y, body forward +z; +x is the subject's left). If an angle below cannot be built that way, STOP and log FOR USER.

## (b) Angles from local rotations

Forward kinematics of rotations only: `G_j = G_parent(j) * R_j` (Rodrigues of the axis-angle, pelvis parent = identity), over the chain
pelvis, spine1, spine2, spine3, [neck, head] / [R collar, R shoulder, R elbow, R wrist]. A bone's world direction is `G_j * d_rest`, with `d_rest` the
canonical direction of the bone leaving joint j: spine/neck/head chain (0, 1, 0), right arm chain (-1, 0, 0). The **torso frame** is `G_9`
(spine3); the **pelvis frame** is `G_0`. All angles in degrees, sampled at the dataset's 30 fps.

Notation: `u` = upper-arm direction (`G_17 (-1,0,0)`), `f` = forearm direction (`G_19 (-1,0,0)`), `h` = hand direction (`G_21 (-1,0,0)`), each
expressed in the torso frame (`G_9^T` applied). Yaw of a frame `G` = `atan2(F_x, F_z)`, `F = G (0,0,1)`, unwrapped over the sequence (continuous; positive
= a turn to the subject's left = counter-clockwise from above). Swing-twist of a local rotation about its bone axis x: twist angle = `2 atan2(q_x, q_w)`
of the quaternion, wrapped to (-180, 180] and unwrapped over the sequence.

**V1, "arm as arm" (the human's right arm drives the robot):**

| Robot joint | Human angle | Sign |
|---|---|---|
| base yaw | yaw of the torso frame `G_9` (pelvis + three spine joints), relative to its value at the reference frame (below) | + |
| shoulder | upper-arm elevation `e = asin(u_y)` in the torso frame (0 = horizontal T-pose arm, +90 up) | robot shoulder angle = `-e_r`, `e_r` the scaled elevation (robot link elevation above horizontal = -shoulder, checked with FK) |
| elbow | elbow flexion `acos(u . f)` (0 = straight, 0 to 180) | + (robot elbow + = forearm bends down) |
| wrist bend | wrist flexion: rotation of the local wrist rotation `R_21` about the local z axis after removing its twist about x (swing part, z component of its rotation vector) | + (robot wrist + = hand bends down, toward the palm side) |
| wrist roll | forearm/hand twist: twist about x of `R_19` plus twist about x of `R_21`, summed | + (right-hand rule about the distal bone direction) |

**V2, "arm as whole body" (PROPOSAL in 7.49):**

| Robot joint | Human angle | Sign |
|---|---|---|
| base yaw | yaw of the **pelvis** frame `G_0` (hip yaw), relative to the reference frame | + |
| shoulder | torso lean forward/back: pitch of the torso up vector `G_9 (0,1,0)` in the yaw-removed pelvis frame, `atan2(up_z, up_y)` (+ = leaning forward) | robot shoulder = `-e_r` with `e_r` the scaled lean, so leaning forward raises the upper link |
| elbow | upper-body bend: lateral bend of the same torso up vector, `atan2(up_x, up_y)` (+ = leaning to the subject's left), same frame. Neck was the alternative named in 7.49; the torso bend is used because the lean already takes the sagittal torso angle | + |
| wrist bend | head nod: pitch of the head up vector `G_15 (0,1,0)` in the neck frame `G_12` (`atan2(up_z, up_y)`, + = chin down) | + |
| wrist roll | head tilt: lateral angle of the same head up vector in the neck frame (`atan2(up_x, up_y)`, + = ear to the subject's left), unwrapped | + |

(The torso lean uses the pelvis frame with its yaw removed, so turning the hips does not read as a lean.) Linear in all of the above except the
unwrapping; no filtering except the cubic interpolation in (d).

**Reference frame for yaws and twists:** the frame at 5.0 s of the sequence (the earliest allowed window start, (e)). Yaw and twist angles are measured relative to
their value there (unwrapped from frame 0 so the relative value is continuous); non-yaw angles are absolute.

## (c) Scaling: one rule per variant, computed once

Pool every FineDance sequence (all files, all frames from 5 s on). For each variant and joint, the human angle `x` has pooled `p2`, `p98`; define
`mid = (p2 + p98) / 2`, `half = (p98 - p2) / 2`. The scaled value is
`y = centre_j + s_j * sign * (x - mid)`, `s_j = target_half_j / half`, so the pooled p2-p98 fills `centre_j +- target_half_j` (`sign` as in the tables; for the shoulder the sign is
applied after scaling: `shoulder = centre_shoulder - e_r`, with `e_r = (-centre_shoulder) + s (x - mid)`, i.e. the human mid maps to the round-1 centre, rising x raises the link).

Centre: round 1's calibration centre (`MOTORNET_PARAMS`): **(base 0, shoulder -60, elbow 30, wrist bend -15, wrist roll 0) deg**.
Target half-span: **80 % of the distance from the centre to the nearer joint limit** for the three ranged joints (limits +-110; `make_arm.RANGE_DEG`):
shoulder `0.8 x 50 = 40`, elbow `0.8 x 80 = 64`, wrist bend `0.8 x 95 = 76` deg. The continuous joints have no limit: **base yaw +-180 deg, wrist roll +-150 deg**
(target half-spans, pooled p2-p98).

The base yaw and the twist are measured relative to the reference frame, so each sequence's own 5 s frame maps to the centre plus the pooled-mid offset
(`mid` is computed over the same relative values). The scales and `mid` per variant and joint go to `docs/RETARGET_SCALE.json` (once, from joint angles, before any render); the
commanded values are never clipped by the scale (the command limiter and the 0.5 deg margin handle the ranges).

## (d) Body path (7.50.8)

Scaled angles at 30 fps -> **cubic (Catmull-Rom/`scipy.interpolate.CubicSpline` on the unwrapped values) interpolation to 100 Hz** -> the round-1 command limiter
and servo (`motornet.simulate_goals`, i.e. `dialstudy` limiter, 0.5 deg inside the range, hard end stops, 5 x 2 ms substeps, v2f model, `kp = make_arm.KP`, zeta 1.5) -> realised angles at 50 Hz.
**No spinal spring-damper.** The sim starts at rest on the first goal; a **1.5 s pre-roll** of the sequence before the window start is simulated, and contacts
are counted from the pre-roll (as round 1's 1.5 s). The shown 20 s are the CSV (1001 rows, `arm_sim.csv_text`) and the video. Lamp head, round 1's camera,
framing and recorder (`motornet_part3_render.sh` path: `ensemble_preview --joint-csv`, `scripts/author/record_ensemble.cjs`, `HYST_FAST=1`).
Reported per joint in `numbers.json`: the limiter's share, `limiter-output p5-p95 / target p5-p95`, and the share of the command cut (1 - that) as round 1.

## (e) Clips and picks

- **10 clips of 20 s.** Genres from `label_json` (the fine-grained genre); genre order = the sorted list of genres permuted by `default_rng(32011)`;
  clip k takes genre k of the order (cycling if fewer than 10 genres); sequence = `default_rng(32011 + 100 + k)` choice among that genre's sequences at least 26.5 s long
  (5 s before the window + 1.5 s pre-roll slack not needed beyond the 5 s; window end must lie inside the sequence); window start = uniform in `[5.0, len - 20.0]` from the same generator.
- **Replacement:** a clip failing a gate in either variant is replaced by the next seeded pick: the picks continue as a stream (genre k+1, k+2, ... of the order, cycling,
  each with `default_rng(32011 + 100 + k)` for k beyond the first 10) until 10 clips pass both variants. Every failure is logged (clip, variant, which gate, values).
- **Gates** (7.44; round 1's code): `dialstudy.gate_values` / `judge` with hf share <= 0.01, reversals <= 6 /s, floor and base clearance (FK points 1-4 >= 0.05 m, hand >= 0.11 m above z = 0),
  no contact, no end-stop dwell (3 deg, 6 consecutive 50 Hz samples), speed and acceleration within `LIMITS` (5 % tolerance), finite; **plus** minimum motion: hand p5-p95 extent >= 0.10 m
  on one axis, and no 3 s stretch below 0.01 m/s mean hand speed (`motornet.motion_values`; over the 20 s). The gates are clip-rejection, not pass bars.
- **Reference R1_S03:** round-1 S03 (`/secondary/hyst-data/body/motornet_toy/clips/settings.json`, network, input scale, calibration, spinal layer 3 Hz, unchanged) run on the
  FineDance music of **2 of the 10 clips** (`default_rng(32021).choice(10, 2, replace=False)` over clip index 0-9), the same 20 s window, cortex lanes computed from that music as the round-1 music path does
  (`motornet_music.py`; warm-up on the 10 s before the window as far as the song provides, silence before 0). Same gates; a failing reference is logged and not replaced.
- **Pairs:** 5 of the 10 clips (`default_rng(32031).choice(10, 5, replace=False)`) are also shown as V1-vs-V2 pairs. V1 plays first in exactly 2 or 3 of the 5:
  `rng = default_rng(32041)`, `n = 2 + integers(2)`, the V1-first pairs are `rng.choice(5, n, replace=False)` (pair order = sorted clip index). Pairs reuse the same single files.
- **Music:** the dataset's own `music_wav` for the sequence, the window's 20 s cut with `ffmpeg`, muxed aac into every single (V1, V2 and reference of the same clip carry the same audio).
  Credit line per clip (song title from `label_json` if given, dataset, "FineDance, ICCV 2023") in the manifest.

## (f) Outputs

Root `/secondary/hyst-data/body/retarget_look/`: `clips/<id>.mp4` (1280x720 h264 + aac, 20 s), `work/<id>.csv`, `numbers.json` (per clip and variant: limiter share per joint,
every gate value, joint p5-p95, mean hand speed), `manifest.json`. Ids: clips `C01..C10`, singles `C01_V1`, `C01_V2`, references `C03_R1S03` (clip index in id),
pairs `PAIR_C03`. Manifest, as 32A's tool reads it: singles
`{id, kind: "single", file, variant: "V1"|"V2"|"R1_S03", clip, genre, source_seq, window_start_s, csv, music_credit}`;
pairs `{id, kind: "pair", files: [first, second], variants: [..], clip, genre}`. Three frames per clip are looked at after rendering, never to select or reshape.
Clips are not shown to the user; the overseer checks them first.

## (g) Choices made where the work order left a default

- V2 elbow = lateral upper-body bend (not neck), see the V2 table. **FOR USER** (logged).
- Base yaw span +-180, wrist roll span +-150, ranged-joint share 80 %: builder's defaults, fixed here.
- Window start and the 5 s reference frame: yaw and twist are relative to the 5 s frame of each sequence.

## (h) Dated note 2026-11-13: motion layout, 6D convention, joint order, genre spelling (before any scale step)

Overseer-accepted rules above are unchanged (mapping, scale rule). This note replaces only the layout statement in (a) ("159 columns, axis-angle"); it was a guess from the readme.

- **Actual layout** (`INVENTORY.md`, checked on the unpacked files): `motion/NNN.npy` is float32 `T x 315` at 30 fps: columns 0-2 root translation (unused), columns 3-314 = 52 joints x **6D rotation**.
  203 sequences (lengths 521 to 11781 frames).
- **6D convention** (read online, no download): FineDance `data/code/pre_motion.py` (`motion_feats_extract`) reshapes the 312 values to `(T, 52, 6)` and calls `ax_from_6v` from
  `dataset/quaternion.py`, which is `matrix_to_axis_angle(rotation_6d_to_matrix(q))` with both helpers from `pytorch3d.transforms` (`rotation_conversions.py`).
  `matrix_to_rotation_6d` returns `matrix[..., :2, :]` flattened: **the 6D holds the first two ROWS of the 3x3 rotation matrix** (row 0 then row 1). `rotation_6d_to_matrix`:
  `a1, a2 = d6[:3], d6[3:]; b1 = normalize(a1); b2 = normalize(a2 - (b1.a2) b1); b3 = b1 x b2; R = stack((b1, b2, b3), dim=-2)`, i.e. b1, b2, b3 are the **rows** of R.
  Implemented that way in `retarget.py` (numpy), no torch/pytorch3d. The resulting `R_local` replaces the Rodrigues step in (b); everything downstream (forward kinematics, swing-twist via quaternion of R) is unchanged.
- **Joint order:** the same `pre_motion.py` slices the 156-dim axis-angle as `global_orient = [:, :3]` (joint 0), `body_pose = [:, 3:66]` (21 body joints, 1-21), `left_hand_pose = [:, 66:111]`, `right_hand_pose = [:, 111:]`:
  SMPL-X/SMPL-H body order, which is the order used in (a): 0 pelvis, 3 spine1, 6 spine2, 9 spine3, 12 neck, 14 R collar, 15 head, 17 R shoulder, 19 R elbow, 21 R wrist. The code also uses SMPL-X feet (7, 8, 10, 11) consistent with that order.
  Sanity check made in `retarget_scale.py` before the scale step: all matrices orthonormal (|det - 1| < 1e-3), and the pooled R elbow flexion lies in 0-180 deg with median well below 180 (a wrong order would not).
- **Genre spelling:** `style2` has 17 spellings; compared **case-insensitively** (jazz = Jazz), **16 genres**, sorted lowercase names, permuted by `default_rng(32011)`. The genre shown in the manifest is the lowercase name.
- **Sequence length filter** (clarifies (e)): a sequence is eligible if at least 25.0 s long (a 5.0 s lead-in plus the 20 s window); the "26.5 s" in (e) is withdrawn. The window start is uniform in `[5.0, len - 20.0]`.
- **Data root:** `/secondary/hyst-data/datasets/finedance/data/finedance/` (`motion`, `music_wav`, `label_json`).

## (i) Dated note 2026-11-13: reference frame of yaw and twist is the window start (changed before the scale step)

Found while computing the scale, from joint angles only (nothing rendered or viewed). With the 5 s-of-sequence reference of (b), the pooled yaw of the dataset is the dancers' accumulated
spin: sequences reach 1,000 to 10,000 deg unwrapped (real turning, not a flip: the torso forward vector stays horizontal, root up vector is +y), so the pooled p2-p98 of (c) became a half-span of
4,356 deg and a scale of 0.04, a robot that barely turns. Change: **base yaw and wrist roll (twist) are measured relative to the frame at the start of the clip window** (for the scale pooling:
relative to the start of every 20 s window, window starts every 5 s from 5 s on, 4,603 windows in 203 sequences, all frames of each window). Everything else in (b) and (c) is unchanged (mapping, centre, target half-spans, 80 %, +-180, +-150, `mid`, `s`).
The sign, the unwrapping over the sequence and the pre-roll are unchanged; the pre-roll rows have negative window-relative time. Result in `docs/RETARGET_SCALE.json`: base yaw half-span of the pooled windows 776 deg (V1) and 774 deg (V2), so the base scale is 0.23: the robot turns a quarter
as far as the dancer (heavy-tailed; a window with several spins is compressed). Accepted as the stated rule; reported, not tuned. Section (b)'s "reference frame" paragraph reads "window start" from here on.

## (j) Dated note 2026-11-13: pillar mount v2p (work order 32C, BRAIN_SPEC 7.51); written and pushed before any render

Everything in (a)-(i) is unchanged: V1/V2 mappings, 80 % share, round 1's centre, `RETARGET_SCALE.json`, seeds 32011 (stream **restarted from candidate 1**), 32021, 32031, 32041, FineDance music, lamp head, manifest format, 20 s clips, genre order. Only the body (and with it the clearance gates) changes.

- **Body v2p** (`scripts/body/make_arm_v2p.py`, new; `make_arm_v2.py`, `make_arm.py`, `dialstudy.py`, `motornet.py` are not edited, so v2f stays byte-identical). v2f's model with the raised plane (z = 0.053 m, `RAISED_PLANE_Z`) removed and replaced by:
  - a **square column**, the arm's base footprint plus 2 cm per side: the base's own box is 0.10 m x 0.10 m (`make_arm.py`, half-sizes 0.05 0.05), so the column is **0.14 m x 0.14 m**, x, y in [-0.07, 0.07], axis along the base yaw axis, **top at z = 0.053 m (the old table plane)**, running down to the floor;
  - a **floor plane at z = 0.053 - 1.0 = -0.947 m** (1.0 m below the column top).
  The base stays where it was (origin, z = 0). Both new geoms use the table's collision bits (contype 1, conaffinity 0), so every arm part collides with them except the arm's own first capsule (the base column of the arm), exactly as the table was; condim 1, `solref [0.006, 1]`, as v2f. Servos, limits, end stops, self-collision unchanged. **Contact with the column or the floor counts as contact** (any contact substep, from the 1.5 s pre-roll on, as (d)). The arm's capsule radius is 0.01 m.
- **Clearance gates on v2p** (replace the old "points >= 0.05 m and hand >= 0.11 m above z = 0"), from the realised 50 Hz joint angles, on the rig's forward-kinematics points p2, p3, p4 (elbow, wrist-bend and wrist-roll joints, the points the old gate used, minus the shoulder p1) and the hand p5 (the mirror ball, radius `DISC_M` = 0.06 m, as in the old gate):
  - distance from each of p2, p3, p4 to the column (the solid box x, y in +-0.07, z <= 0.053) **>= 0.05 m**;
  - the hand: distance of its centre to the column **>= 0.05 m + 0.06 m = 0.11 m** (the ball's surface 0.05 m from the column: the analogue of the old 0.11 m);
  - all of p2..p5 **>= 0.05 m above the floor** (the hand centre >= 0.11 m); this never binds in practice (the floor is 1 m down);
  - **p1** (the shoulder) is fixed 0.027 m above the column top by construction and is exempt; the arm's capsules are covered by the contact gate instead (a link capsule of radius 0.01 touching the column or floor is contact). Sampling the link segments against the 0.05 m margin was not used: the shoulder is 0.027 m above the column top, so a 0.05 m margin on the segments would forbid every upper-arm elevation below about 35 degrees by construction. **FOR USER** (logged).
  The gate value `floor_m` of `dialstudy.gate_values` is replaced by the smallest margin over these tests (>= 0 passes); every other gate as 7.44 (contact, end stop within 3 deg for 6 samples, >8 Hz share <= 0.01, reversals <= 6 /s, speed and acceleration within `LIMITS` + 5 %, finite, minimum motion over the 20 s).
- **Backstop guard** (7.51 C): applied per 100 Hz command frame, to the scaled and cubic-interpolated command row `G[i]` (before the limiter), using the same margin tests as the gate on the forward kinematics **of the commanded angles** (clipped inside the joint ranges as the sim does). If frame i breaks any margin, **`G[i]` is replaced by the last safe command `G[i-1]`** (a held command stays held until a safe frame comes). Frames before the first safe frame take the first safe command (counted as held). **Engagement = held frames / all command frames** (the 1.5 s pre-roll and the 20 s, 2,151 frames). Logged per clip and variant (`guard_share` in `numbers.json`). **A clip whose guard share is > 0.10 fails the gate.** The guard is never relied upon to pass: the gate then checks the realised motion with the same margins, and the contact gate counts the real collisions.
- **Gating and counts:** both variants of each seeded 20 s window; the first 10 candidates (stream from candidate 1) that pass in both. Pass counts, discards per gate and guard shares per variant are reported in the night log and `numbers.json`. **If fewer than 10 pass in both within 200 candidates: "HOLD <counts>" in the night log, push, stop** (no share ladder or other change without Kosta).
- **Reference R1_S03:** round 1's S03 (network, input scale, calibration, spinal layer, inputs unchanged) re-simulated on v2p and gated with the same v2p gates (no guard for the reference: it is a network output, not a retargeted command; the margins are gate-only); a failing reference is logged, not replaced.
- **Camera:** round 1's framing unchanged (target [0, 0, 0.3], yaw -0.6, pitch 0.35, distance 2.1, 1800 px focal, 1280x720): **no camera change.** At that framing the column top sits at z = 0.053 m, the same place as round 1's table surface, and the lower part of the column runs out of the bottom of the frame (the 1 m column cannot fit at this distance). The page is post-processed (a copy, not the template `ensemble.html`) by `scripts/body/retarget_page.py`: the floor stage and its light pool move to z = -0.947, the pedestal becomes a 0.14 m square dark column from z = 0.053 down to the floor (top face with the three base-yaw spokes), the projector's patch and the arm's shadow land on the new floor, and the plumb line from the hand to the floor is dropped (it would run a metre down). The arm, lamp, implement, trail and everything else are drawn as in round 1.
- **Order of work:** note (j) pushed -> overseer review -> code, gating, render. No v2p gate number has been computed or looked at before this push.

## (k) Dated note 2026-11-13: limiter fix (work order 32D step A, BRAIN_SPEC 7.52.2 and 7.52.8)

**Finding: a bug** (wind-up and missing range braking at the joint-range clamp). Measured as the gate measures realised acceleration (limiter output rows at 50 Hz, second difference x 2500 / limit), over the 145 candidates x 2 variants of the WO32C stream: the round-1 limiter output exceeds 1.05 x the acceleration limit on **35 of 290** (shoulder 35: V1 8, V2 27; elbow 21, wrist bend 29, wrist roll 0, base yaw 0): only the **ranged** joints (+-110 deg), never the continuous ones.
- **Code:** `scripts/body/motornet.py` `limiter_out` lines 25-37 (and the same lines inline in `simulate_goals`, lines 132-136; also `dialstudy.simulate` line 143, `arm_sim.limit_target` lines 98-108): the speed profile is `sqrt(2 A |goal - target|)` (it knows the goal, not the range edge), then `tgt = clip(tgt + tv*DT, lo_t, hi_t)` clamps the position and leaves the velocity state `tv` unchanged. When the goal turns round while the held target is still moving fast (a retargeted dancer does this constantly), the target runs past the goal into the clamp, **stops dead in one frame (a velocity step of up to LIM_V = 5.8 x the acceleration limit at the 100 Hz frame, 3.2 x by the gate's 50 Hz measure)**, then sits at the edge with a stale `tv` for several frames (wind-up).
- **Worst candidate** (candidate 30, V2; the 5.5 x of the planner brief was the 100 Hz-frame figure of a nearby case): by the gate measure **3.20 x before, 1.000 x after**; the frame dump (rows 1890-1902): out -107.98 (goal -103.7) moving -0.36 deg/frame, reaching -109.5 at row 1896, a step of 0.00 at row 1897 (5.83 x). After the fix the output brakes before the edge.
- **Fix** (new `scripts/body/retarget_limiter.py`; `motornet.py`, `dialstudy.py`, `arm_sim.py`, round 1 and v2f are **not** edited): (1) the desired speed toward each range edge is capped to the speed from which acceleration A can still stop before it (discrete stopping distance `v^2/(2A) + v DT/2` <= 0.9 x the distance left; the plain bound left a 1.06 x residue); (2) after the position clamp the velocity state is the step actually taken (no wind-up). A copy of `simulate_goals` with the fixed limiter is in the same module; `retarget_run.py` swaps it in for every clip of this look test (V1, V2 and the round-1 S03 reference, so all three share one body).
- **Test** (`scripts/body/test_retarget_limiter.py`, 4 tests, `python -m unittest test_retarget_limiter` in the body env): the round-1 limiter on a goal that runs to -108 deg at 120 deg/s, waits 0.2 s and turns round reads **> 2 x** (fails the limit; 2.7 x measured); the fixed limiter stays <= 1.0 x on it and on 20 random goal walks (before the 0.9 distance factor the random walks read up to 1.06 x), speed <= 1.0 x, range respected, and it equals the round-1 limiter away from the range edges.
- **After, over the whole stream:** the fixed limiter output is <= 1.000 x the acceleration limit on every joint of all 290 candidate/variant pairs (shoulder 0 above 1.0).

## (l) Dated note 2026-11-13: look-test tolerance and pick rule (work order 32D step B, BRAIN_SPEC 7.52 Q1 a and Q2); written and pushed before any render

- **Tolerance:** the speed and acceleration gate ("limits") is **1.25 x the limit** (was 1.05), **for this look test only**: a simulation exception, **not a hardware margin**. It applies to the realised 50 Hz rows exactly as `gate_values` computes them (speed = diff x 50 / limit, acceleration = second difference x 2500 / limit, per joint, worst joint decides). Every other gate is unchanged (contact, clearance, end stops, guard > 10 %, > 8 Hz share, reversals, minimum motion, finite). It applies to V1, V2 and the round-1 S03 reference.
- **Pick rule:** the same seeded stream (seed 32011, restarted from candidate 1, genre order unchanged). A candidate is taken when it passes both variants **and** (a) its FineDance sequence has not been taken yet and (b) fewer than two clips of its genre (16, case-insensitive) are taken; otherwise it is skipped and counted as skipped by the pick rule. The 10 first taken fill the clips in order; **fewer than 10 within 200 candidates: "HOLD <counts>"**, push, stop. Seeds 32021 (references), 32031 (pairs), 32041 (pair order) unchanged.
- **Re-gate** with the fix of (k), on v2p, from candidate 1. The WO32C outputs (gating, logs, clips, work files, numbers, manifest) are kept in `/secondary/hyst-data/body/retarget_look/v2p_1.05/`, not overwritten.
- **Numbers per clip and variant** (`numbers.json`, in addition to WO32C's): commanded shoulder acceleration (the retargeted command at 50 Hz rows, second difference x 2500 / limit) and realised shoulder acceleration, each as p50, p95 and max of the absolute value, in multiples of the limit; the limiter's share (share of 100 Hz frames in which the limiter output differs from the commanded shoulder by more than 1e-6 deg); the shoulder RMS of (command - limiter output) in degrees (shown 20 s, 100 Hz frames).


## (m) Dated note 2026-11-13: space retarget V3 (work order 35, BRAIN_SPEC 7.54.5 and 7.54.8); written and pushed before any V3 run

V1, V2, the shown clips, `RETARGET_SCALE.json`'s old keys, rules (a)-(l), the seeds and the 10 windows are untouched. V3 is a new, separate path (`scripts/body/v3_*.py`). **Report only: no video, no blind session.**

- **Variants.** **V3a**: the lamp follows the human **right wrist** (FineDance joint 21) relative to the **right shoulder** (17); **V3b**: the lamp follows the **head** (15) relative to the **pelvis** (0). Positions from forward kinematics with the canonical T-pose offsets of the WO34 viewing figure (no SMPL model file; `v3_lib.fk`), at the dataset's 30 fps.
- **Frame.** The relative vector is taken in the dancer's **heading frame**: the world rotated about the vertical by minus the pelvis yaw (yaw = atan2(F_x, F_z), F = pelvis rotation applied to (0,0,1)), so the human's own forward axis is +z. Human axes (x left, y up, z forward) map to the robot's (X forward, Y left, Z up) by `robot = (z, x, y)`: the human forward axis is the robot's base-0 forward.
- **Scale (uniform, one per variant).** The reach = the 98th percentile of the end point's distance from its origin, pooled over all frames of the 4,603 eligible 20 s windows of `RETARGET_SCALE.json` (every 20 s window, starts every 5 s from 5 s): **V3a 0.510 m, V3b 0.620 m**. The arm's reach = the distance from the shoulder joint p1 to the lamp centre (point p5) at full extension = **0.69 m**. Scale `s = 0.8 x 0.69 / reach`: **V3a 1.0824, V3b 0.8909**. New keys `V3a`, `V3b` in `RETARGET_SCALE.json` (old keys unchanged; also stored there: the reach from the median and the scale that would give, for the record).
- **Offset (centre).** The workspace centre c0 = the lamp position at round 1's centre pose (base 0, shoulder -60, elbow 30, wrist bend -15, roll 0) = **(0.4649, 0, 0.5668) m** in the robot frame. Lamp target = c0 + s x A (rel - r_med), with r_med the pooled **median** of the relative vector in the heading frame (human axes): **V3a (-0.0706, -0.1733, 0.1283), V3b (-0.0023, 0.6041, 0.0354)**, also in `RETARGET_SCALE.json`. **FOR USER (departure from the literal text of 7.54.8, decide before the run):** 7.54.8 adds "the scaled human end-point offset" (the vector from its origin) at c0. For V3b that vector is the head 0.60 m above the pelvis at all times, which would put the lamp target at z = 1.1-1.2 m, out of reach for the whole clip; for V3a it is the arm hanging at the dancer's side. Centring on the pooled median keeps the direction and the scale of the motion and puts the dancer's usual pose at the workspace centre. Overseer: reject this in review and the run uses the literal offset (target = c0 + s x A rel; code switch `--literal-offset` is not built, ask and it is a one-line change).
- **Reachability note (FOR USER).** c0 is **0.673 m from p1, the arm reaches 0.69 m**: the round-1 centre pose is almost fully extended, so the part of the scaled motion that points away from the shoulder by more than 1.7 cm is unreachable. The IK then ends at the nearest reachable pose (the arm straight) and the frame counts as residual > 2 cm. These counts are reported per clip; nothing is tuned to reduce them.
- **Orientation.** The tool frame (x = stem toward the lamp, y = the wrist-bend axis, z) is aligned with the end joint's frame: **V3a** `tool = A Ry(-yaw) G21 M_a`, tool x = the hand's distal direction (-x_local), tool y = the flexion axis (z_local), tool z = y_local, `M_a = [[-1,0,0],[0,0,1],[0,1,0]]` (columns = tool axes in the joint's local axes); **V3b** `tool = A Ry(-yaw) G15 M_b`, tool x = the face direction (z_local), tool y = x_local (the nod axis), tool z = y_local (up), `M_b = [[0,1,0],[0,0,1],[1,0,0]]`. The orientation target is the rotation matrix per frame (quaternion cubic spline `RotationSpline` from 30 fps to 100 Hz). **Projection onto the wrist's two axes:** the orientation residual is the x and y components of `vee(R_cur^T R_target)` in the current tool frame (x = roll, y = bend); the z component is dropped.
- **IK** (`v3_ik.py`; the numbers by `v3_derive.py`, written to `v3/ik_params.json`; none tuned by eye or on a gate outcome). Per 100 Hz frame, on the v2p arm (same FK as the body, `make_arm.AXES/LINKS`), warm-started from the previous frame (the first frame from round 1's centre pose with 50 iterations), on the cubic-spline-resampled (30 -> 100 Hz, as V1/V2) target path. Residual rows: position (3, metres), orientation (2, radians x `w_o`), column clearance (4, metres of violation x `w_c`). Each iteration solves `(J^T J + (lam^2 + mu) I) dq = -J^T f - mu (q - q_prev)` (J by forward differences), then clamps the bend joints to +-109.5 deg (base yaw and wrist roll are continuous).
  - **Damping** `d = lam^2 + mu = sigma_c^2 / 9 = 3.604e-4`, with `sigma_c = 0.05695` the smallest singular value of the 3 x 5 position Jacobian at the centre pose (0.807, 0.465, 0.057): a 1 cm target step moves the joints by at least 90 % of the exact (undamped) solution in the weakest direction there (measured on 1,000 random steps: minimum 90.0 %, median 90.1 %).
  - **lam** = 1 % of the arm's reach = 0.0069 (`lam^2 = 4.761e-5`, the DLS damping against singular poses). **mu**, the per-frame joint-change penalty, = `d - lam^2` = **3.128e-4**: a stationary target, whose previous solution is already the minimiser, gives zero motion (unit test).
  - **Orientation weight** `w_o` = **0.05 m/rad** (a 1 rad orientation error costs as much as a 5 cm position error: position first). **Column weight** `w_c` = **1** (a violation of d metres costs as a d metre position error), rows for p2, p3, p4 (margin 0.05 m) and the hand p5 (0.11 m) on the signed distance to the column (negative inside, so a point inside has a gradient).
  - **Step cap** (trust region) = 2 x (1 cm / sigma_c) = **0.351 rad** per iteration (never binds on a 1 cm step in the weakest direction).
  - **Iterations per frame N = 3**: the smallest count for which, on 1,000 random 1 cm target steps and the 378 of 1,000 random 5 cm steps (the largest per-frame end-point step expected: a hand at 5 m/s at 100 Hz) whose target is inside the arm's reach, from the centre pose, the end point after N iterations is within 1 mm of the end point after 50 iterations (1 cm: max 0.9 microns at N = 3; 5 cm: max 0.06 mm at N = 3, but 2.4 mm at N = 2). The 1 cm probe alone gave N = 1; the 5 cm probe was added before any clip was run.
  - **Column**: the penalty rows above plus a **projection** after the solve (up to 10 Newton steps on the smallest signed margin, returns the best pose seen, never worse than the solve's result), then the **7.51 guard** (`make_arm_v2p.guard`: hold the last safe command) on the IK output as backstop; the guard share is reported.
  - **Residual**: the end-point error after the solve; frames with error > 2 cm are counted per clip, over the shown 20 s and over all 21.5 s (with the 1.5 s pre-roll).
- **Then the existing pipeline:** IK joint angles at 100 Hz -> guard -> round-1 `motornet.spinal` (3 Hz, zeta 0.7, unchanged, H1) -> the fixed limiter (k) -> servo -> v2p body -> gates at 1.25 (l) (every other gate as run), 1.5 s pre-roll as the look test. The same 10 seeded windows (C01-C10) for V3a and V3b; no re-pick; pass/fail and failed parts reported per clip, nothing selected on it.
- **Report** (`docs/V3_REPORT.md` section B, `v3/numbers.json`, realised CSVs in `v3/work/`): jitter measures per stage as `JITTER_DIAGNOSIS.md` (end point, IK output, spinal, limiter, realised), the IK residual count, the shoulder numbers of 7.52.5, medians next to V1/V2 baseline and H1 and the S03 references. **No video.**
- **Tests:** `test_v3_lib.py` (position measures on known signals, T-pose FK), `test_v3_ik.py` (stationary target gives zero motion; the 90 % step response; a reachable target converges to 2 mm; joint limits hold; the step cap bounds an unreachable target's motion; projection never worsens a margin and clears at least 85 % of small violations, FK equals the rig's `fk_points`).
