# T0 for PhantomDance and Motorica: format mapping and rules (work order 42, BRAIN_SPEC 7.69)

Written and pushed before any retarget run. Binding: `BRAIN_SPEC.md` 7.69 (with its overseer notes), `T0_RULES.md` (everything not changed here is as written there),
`RETARGET_RULES.md`, `LOWPASS_REPORT.md` (cutoffs V1 2.50 Hz, V2 5.75 Hz, reused). T0 only: no training, no verdict. One arm.
Data and everything derived stay outside git: `/secondary/hyst-data/{phantomdance,motorica}/` (raw, licence, `PROVENANCE.md`) and `/secondary/hyst-data/body/{t0_phantom,t0_motorica}/`.
**Motorica and anything derived from it stay on this laptop** (licence: no redistribution; no Kaggle). Code: `scripts/body/t0_phantom.py` (adapters), `t0_phantom_run.py` (driver).
What the T0 chain takes from FineDance: `rot` = dict joint -> (T,3,3) **local** rotations of SMPL joints 0,3,6,9,12,13..21 in the SMPL-H frame (right-handed, y up, subject faces +z,
subject's left = +x, rest = T-pose with the right arm along -x), plus root translation (T,3), at 30 fps. Both adapters produce exactly that; the chain is not changed.

## 1. PhantomDance (v1.2 zip, folder v1.1; 260 pairs, 9.502 h)

| Item | Source format | Mapping |
|---|---|---|
| Skeleton | 24 bones, names and order = SMPL (`Pelvis, L_Hip, R_Hip, Spine1 ... R_Hand`), checked by assertion | indices 0-21 are FineDance's joints; the chain's joints 0,3,6,9,12,14,15,17,19,21 (and 13,16,18,20 for the mirror) map 1:1 |
| Rotation | `rotations` (T x 24 x 4), quaternion (x, y, z, w), **world** (README) | local = parent_world^T x world (SMPL parent table); pelvis local = world |
| Axes | Unity: left-handed, x right, y up, z forward | negate x: R' = F R F, F = diag(-1, 1, 1) (quaternion (x, -y, -z, w)). Gives the SMPL frame (right arm at -x, subject faces +z) |
| Units / root | `root_positions` metres, x negated with the axes | translation only enters through the mirror (lateral sign flip) |
| Frame rate | 30 fps (README) | none needed; 259 files: rotation frames / 30 = audio duration within 0.94 s, median 0 |
| Audio | README: 16 kHz wav | **measured: 239 float32 mono 16 kHz, 18 PCM16 mono 16 kHz, 3 PCM16 44.1 kHz stereo.** `t0_lanes.mono_wav` (ffmpeg) resamples every file to 44.1 kHz mono as for FineDance |
| Genre | none in the data | genres "unlabelled" (FOR USER) |

Checks done before this note (angles only, no clip viewed): right-elbow local rotation is about +y (flexion, as in SMPL) after the x flip, about -y without it; percentiles (5 / 50 / 95)
of V1 elevation, elbow flexion and wrist bend over 20 sequences against 20 FineDance sequences are of the same size (elevation median -36 against -26 deg, flexion 55 against 48,
wrist bend 0 against 2); no constant rest-pose offset of the A-pose size is seen. Rest-pose offsets (A-pose bind) would show as a constant shift in elevation; none of 40 deg.
**Anomaly (file 000):** its rotation list ends with one malformed frame (12 entries) and its `root_positions` has 6408 rows against 4105 valid rotation frames. Rule: the sequence ends at
the first frame whose list is not 24 entries long; root positions are cut to the same length; logged in the report. Audio of 000 is 136.4 s against 136.8 s of motion.
Song names or dancer identity are not in the data: the split unit is one pair, merged with any other pair by identical audio hash (union-find, as `T0_RULES.md` 1).
FineDance-overlap by name cannot be tested; by audio hash it cannot either (sample rates differ), so the list is empty by construction and said so in the report (FOR USER).

## 2. Motorica Dance Dataset (74 paired sequences, 3.558 h)

| Item | Source format | Mapping |
|---|---|---|
| Skeleton | BVH, 51 joints: Hips, Spine, Spine1, Neck, Head, Left/RightShoulder, Arm, ForeArm, Hand, fingers, legs | Hips -> 0, Spine -> 3, **(spine2, joint 6: no joint, identity)**, Spine1 -> 9, Neck -> 12, Head -> 15, RightShoulder -> 14, RightArm -> 17, RightForeArm -> 19, RightHand -> 21, left analogues -> 13, 16, 18, 20 |
| Rotation | local Euler, channel order Zrotation Xrotation Yrotation, degrees | matrix = Rz Rx Ry (scipy intrinsic "ZXY", listed order). Files differ: some give 6 channels at every joint (positions constant); the rotation channels are taken by name |
| Axes / rest | right-handed, y up; rest offsets: left arm +x, right arm -x, spine +y, T-pose | same frame as SMPL-H with the subject facing +z; no conversion. The rest bones are axis-aligned, so local identity = T-pose as in SMPL |
| Units / root | cm; root = Hips position | metres; translation only enters through the mirror |
| Frame rate | 120 fps (Frame Time 0.0083333) in all 74 | every 4th frame (30 fps); no filter before the decimation (the T0 low-pass cutoffs, 2.5 and 5.75 Hz, are far below 15 Hz) |
| Audio | 48 kHz mono wav, stems identical to the BVH stems | ffmpeg to 44.1 kHz mono as for FineDance. 47 further BVH have no music: not used (no lanes possible) |
| Genre | from the file name: kthjazz (gCH, gJZ, gTP), kthstreet (gLH, gKR, gPO, gLO), kthmisc (gCA) | family = jazz / street / misc; the second token (gCH...) is kept as the style code |
| Mirror | the dataset's own `_mirrored` copies are in the features zip only, not in the bvh folder | T0's own V1m / V2m copies as for FineDance |

**Design choice (default, FOR USER):** the one missing spine joint (SMPL spine2) is the identity, so the torso frame G_9 is Spine then Spine1; the torso yaw and lean of V1/V2 read the same
quantities, but the pelvis-to-torso bend is carried by two joints instead of three. Pre-check (angles only): V1/V2 percentiles over 16 sequences are of FineDance's size
(elevation median -40 against -26 deg, flexion 54 against 48, wrist bend -16 against 2, torso lean +14 against +6). The wrist-bend median of -16 deg is a real offset; it is not corrected.
Motorica song unit: the file stem (title and take number); merged by identical audio hash. Name match against FineDance: stripped lower-case stem contains or equals a FineDance stripped name (list in the report).

## 3. What runs, per source (T0 as FineDance, `T0_RULES.md` 1-7)

- Lanes per song (brain env, `t0_lanes.song`, torch threads 2). Split: `numpy.random.default_rng(seed).permutation` of the sorted group keys, shares 75 / 10 / 15,
  **seeds: PhantomDance 42001, Motorica 42002** (FineDance 33001). The 5 check songs and 3 danced songs are matched by name and hash as in `T0_RULES.md` 1 (Motorica by name; PhantomDance by hash only: none can match, 16 kHz).
- Four copies V1, V2, V1m, V2m; targets, posture/gesture, windows of 20 s, gates at 1.25, H1, tokens (86 columns): code reused (`t0_chain.process`, `t0_lib`, `t0_run.song_tokens`), nothing changed in it.
- **Token standardisation: with the FineDance `t0/token_norm.json` (the E1 constants), so every source lands in the same units; the unstandardised tokens are stored too (`tokens_raw`).**
  A source-own norm is a one-line rerun on request (FOR USER).
- Output `seq/<dancer>__<copy>.npz` as FineDance plus `tokens_raw`, `source`, `style`.
- Weight: one dancer per sequence in both sources, weight 1 (per group the 7.59.8 rule is kept: identical-audio pairs share their group's cap).

## 4. Look clips (7.69.3), 6 per source, never selected by eye

- Slots k = 0 ... 5 draw from `default_rng(SEED + 100 + k)` (Motorica SEED 42002, PhantomDance 42001). Strata: Motorica = jazz, street, misc, jazz, street, misc (so two each);
  PhantomDance = six equal parts of the sorted pair ids (no genre labels; FOR USER). Within a stratum one sequence of at least 25 s, one window start uniform in [5 s, length - 20 s].
  Slot variant: V1 for slots 0, 2, 4 and V2 for 1, 3, 5 (not mirrored). The retarget clip chain of `retarget_run.sim_variant` (pre-roll 1.5 s, guard, limiter, servo, v2p gates at 1.25); a candidate that fails a gate or repeats
  a sequence is dropped and the next candidate k is drawn (at most 200); nothing is hand-picked.
- Render: `retarget_render.sh` with the output root set by `RETARGET_ROOT` (default unchanged): lamp head, 1280x720, h264 + aac, the song's own audio excerpt (offset 0).
  Three frames per clip are looked at for a render check only. Manifest of singles (`kind` "single", `labels` "follow") for `dialstudy_session.py`:
  question "Does the dancer follow the music?", answers yes / partly / no + note (new label-set option; the default look set is unchanged). To `t0_phantom/look/`, `t0_motorica/look/`.

## FOR USER (defaults taken)

1. PhantomDance has no genre labels: look-clip strata are id sixths; the report's genre table is "unlabelled".
2. Motorica spine2 = identity (above).
3. Source-specific seeds 42001 / 42002; PhantomDance name-overlap with FineDance cannot be tested.
4. Tokens standardised with the FineDance constants (raw stored too).
5. File 000 of PhantomDance is cut at its malformed frame.
6. Look clips alternate V1 / V2 by slot.
