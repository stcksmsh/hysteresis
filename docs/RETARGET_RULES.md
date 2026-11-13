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
