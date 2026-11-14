# T0 rules: training data for the motor vocabulary and sequencer (work order 37, BRAIN_SPEC 7.59)

Written before any full run, for overseer review. Binding: `BRAIN_SPEC.md` 7.59 (points 2, 8), 7.56.8 and 7.56.10 where 7.59.8 keeps them, 7.55,
`RETARGET_RULES.md` (a)-(n), `EAR_ENERGY_RULES.md`. T0 only: no model, no training, no clips, no uploads, no verdict. One arm.
Code: `scripts/body/t0_*.py`. Output: `/secondary/hyst-data/body/t0/` (outside git). Audio stays outside git.
Where this note picks a detail the spec leaves open, it is marked **(default)** and listed under FOR USER at the end.

## 1. Sources, grouping, split (7.59.2.5, 7.59.8 split)

- Dancers: FineDance (203 sequences, 30 fps, 6D rotations) and AIOZ-GDANCE person-sequences kept by section 2 (each person of a clip is one dancer).
- Song unit: FineDance = stripped lower-case `name` from `label_json` + audio hash; AIOZ = the YouTube id (first name field). Two units with the same
  stripped name, or the same audio hash (sha256 of the wav bytes), are merged into one group (union-find) before the split. One group is never in two splits.
- The 5 check songs (blue-lagoon, schizoid-man, epitaph, breathe, one-of-these-days) and the 3 danced songs (instant-crush, five-years, presence):
  no group may match any of them by stripped name or audio hash (their wavs: `motornet_toy/work3/wav`, `body/k5/danced`). A match is dropped from T0 and counted
  (FOR USER if any).
- Split: `numpy.random.default_rng(33001).permutation` of the sorted group keys; n groups: test = round(0.15 n), validation = round(0.10 n), rest train.
  Lists in `t0/split.json` (group key, members, dataset, split). Groups are the unit, so all dancers and all four copies of a group go together.

## 2. AIOZ intake (7.56.10, 7.59.2.4)

- **Restricted unpickler** (`t0_aioz.py`, Builder B): `pickle.Unpickler.find_class` allows only `numpy.core.multiarray._reconstruct`, `numpy.core.multiarray.scalar`,
  `numpy.ndarray`, `numpy.dtype` (and numpy 2 `numpy._core.*` equivalents), `collections.OrderedDict`, builtins `list/dict/tuple/set/frozenset`; everything else raises.
  Test: a crafted pickle (an `os.system` reduce) is refused.
- **Adapter:** `smpl_poses` (persons x frames x 72) = SMPL 24 joints x 3 axis-angle; the first 22 joints are FineDance's body joints (same order). Axis-angle ->
  rotation matrices (`scipy Rotation.from_rotvec`) -> the dict {joint: (T,3,3)} that `retarget.human_angles` takes (it needs joints 0,3,6,9,12,14,15,17,19,21).
  Test: one FineDance sequence (6D -> matrix -> axis-angle -> matrix) round-trips; max abs angle difference reported.
- **Frame rate:** per sequence = frames / wav duration; the distribution is reported; a sequence more than 2 % off the mode is dropped and counted;
  the mode (rounded to the nearest of 24, 25, 30, 50, 60 if within 2 %) is the dataset's fps, resampled to 30 fps by cubic interpolation of the rotation
  vectors' unwrapped matrices via slerp if it is not 30 **(default; builder reports what the mode is)**.
- **Validity measures** (per person-sequence, before the low-pass; FineDance is the reference): (1) human end-point power above 3 Hz, both end points (the
  Step A measure of `v3_lib`); (2) share of frames where any body joint's angular speed exceeds FineDance's p99.9 of that joint; (3) share of frames with
  root speed above FineDance's p99.9; (4) share of frames with all joints still (< 1 deg/s). Also reported: per-person mean height and vertical drift.
- **Prune:** drop a person-sequence if (1) exceeds FineDance's p95 for either end point, or (2) or (3) exceeds 1 % of frames, or (4) exceeds 20 %.
  The FineDance reference percentiles are written to `docs/T0_AIOZ_RULES.md` and pushed before any AIOZ measure is computed.
  If fewer than 30 % of AIOZ person-sequences survive, "HOLD aioz <share>" and T0 continues with FineDance alone. Report: `docs/T0_AIOZ_CHECK.md`.
- Surviving AIOZ then runs through exactly the same chain as FineDance. FineDance cutoffs reused (not recomputed).

## 3. Mirror (7.59.2.3, 7.59.8)

- Lateral axis: local x (the retarget code's right-arm bone axis is -x, `retarget.XM`; checked on the data in the mirror test below).
  M = diag(-1, 1, 1). Mirrored motion: swap left/right joints (SMPL pairs 1-2, 4-5, 7-8, 10-11, 13-14, 16-17, 18-19, 20-21 of the 22 body joints; spine, neck,
  head and pelvis map to themselves), every local rotation R' = M R M, root lateral translation negated (root x). The retarget code is then run unchanged on
  the mirrored motion: its right arm is the original's left arm (V1 uses the left arm when mirrored), base yaw sign flips by construction.
- Tests: mirror twice = identity (max abs difference reported); with a synthetic skeleton (right arm offsets along -x, left along +x, fixed offsets), the mirrored
  motion's right wrist position = M x (original left wrist position), and the original right wrist = M x mirrored left wrist.
- Four copies per dancer: V1, V2, V1m, V2m; counted separately; they share their dancer's weight.

## 4. Targets (7.59.2.2, 7.59.8)

- Stage: the human angles of the whole sequence referenced at frame 0 (`RT.referenced(v, 0)`), `RT.to_commands` per variant, 2nd-order Butterworth filtfilt at
  30 fps (V1 2.50 Hz, V2 5.75 Hz, `lowpass_cutoff.lowpass`), `RT.to_100hz`, `make_arm_v2p.guard`. **Target = the guard output, before H1 (`motornet.spinal`).**
  Rate 100 Hz; row r is at time r / 100 s; motion frame k is at k / 30 s; music time 0 = motion frame 0 (audio offset 0). T100 = floor((T30 - 1) / 30 * 100) + 1.
- Guard share per window is part of the gate (<= 0.10). The guard is run on the whole sequence for the stored targets (`guard_share_seq` stored); each window's gate
  runs its own guard on the re-referenced window (section 6), so the stored target can differ from the gated rows only by the guard's held values.
- Posture / gesture (7.59.2.9): base yaw and wrist roll are unwrapped in the stage-1 angles already; posture = 2nd-order Butterworth filtfilt at 0.5 Hz of the 100 Hz
  target, per whole dancer sequence; gesture = target - posture. Both stored.

## 5. Music features, tokens (7.59.2.8, 7.59.8)

- Lanes per song (brain env, `t0_lanes.py`): the toy-round recipe: `ff.fast_features(load_mono(wav))` (100 Hz, 44 columns), `analyze_mix` beats, `b2.build_inputs`,
  the B7 checkpoint `epoch_006.pt` (`k5_video_lanes.load_model`), 6000-frame chunks with carried state (`k5_data.song_lanes`, `motornet2_lanes.l4_lanes`).
  Stored per song: 44 standardised fast features (100 Hz, the `bd.stats()` mean/std, as `b2.build_inputs` uses), `y` (0.5 s block lane; cols 2, 3 = l3_cos, l3_sin),
  `s10` per-layer surprisal L1..L4 (10 Hz, NaN where undefined), `arousal_b7` (10 Hz, frames 9::10), `h_abs` (10 Hz, 4 layers x 8 groups: |h| of the 256 complex modes,
  modes split into 8 contiguous groups of 32 in index order, mean over the group), raw 44-feature array for ear energy, ear energy lane (10 Hz, `ear_energy.lane`).
  Surprisal source **(default)**: `bd.surprisal` per layer as in `song_lanes` (`s10`, the stored-lane recipe), not `b2.surprisal_lanes` (which needs the b2 readout model,
  not the B7 checkpoint).
- Tokens: fixed 0.5 s grid from motion frame 0; token k covers [0.5 k, 0.5 (k + 1)) s. n_tok = floor(T30 / 15).
  Columns (F = 86): 44 ear features (mean of the standardised 44 over the token's 50 frames); 32 mode amplitudes (mean of `h_abs` over the token's 5 stamps, 10 Hz stamps
  at frames 9, 19, ...; stamp j of token k is stamp 5k + j); 4 surprisal (mean of the token's stamps, NaN excluded; none -> 0); `arousal_b7` and ear energy (mean of the
  token's stamps; ear energy raw lane); 4 beat phase (cos, sin of l3 at the token's start frame and middle frame, from `y` linearly interpolated at stamps (i + 0.5) * 0.5 s).
  Mask bit per token: 1 where surprisal had no stamp (all four layers NaN); stored as `token_mask` (n_tok,) uint8.
- Standardisation: train-split mean and sd per column over all train tokens (masked tokens excluded for surprisal columns), clip +-3, constants in
  `t0/token_norm.json`; the mode amplitudes, surprisal, arousal_b7, ear energy and beat phase columns only (the 44 ear columns are already standardised by `bd.stats`
  and are clipped +-3 only). No frame after the token's end is used, except that the beat-phase and ear-energy lanes carry the existing lanes' own smoothing windows
  (ear energy's 1 s centred loudness mean and 2 s onset-density window reach up to 1 s past the token) **(default; flagged, the existing lane recipe is kept as recorded)**.

## 6. Weighting, windows, gating (7.59.2.6-7, 7.59.8)

- Weight: per group, w_song = hours of its longest dancer (human motion, before the four copies); each dancer weight = w_song / (sum of its group's dancers' hours)
  if that sum exceeds w_song, else 1. Same rule for FineDance. Written per npz as `weight`.
- Windows: non-overlapping 20 s windows from the sequence start; a tail under 20 s is dropped and counted. A window is 40 tokens, 2000 target steps (rows k0 .. k0 + 2000).
- Gate per window and per copy: the window's stage-1 commands are re-referenced to the window start (exact: yaw and roll columns are shifted by their value at the window's first
  frame, which commutes with the linear filter and the spline, so the look test's rule (h) is kept), then `to_100hz` with a 1.5 s pre-roll (clamped at the sequence start,
  first row repeated), guard, `motornet.spinal` (H1), `FX.limiter_out`, `FX.simulate_goals` (servo, v2p), `RR.gates_v2p` at 1.25 (all parts: motion, limits, end stop, contact,
  clearance, guard). A failing window is dropped, counted per failed part; no state is carried across windows. Stored: `win_pass`, `win_part_names`, `win_parts` (n_win x n_parts bool).
- Windows are training segments only where `win_pass` is true; tokens of failed windows stay in the file.

## 7. Files in `t0/`

- `split.json`, `token_norm.json`, `aioz_keep.json` (Builder B), `lanes/<song>.npz`, `numbers.json`.
- `seq/<dataset>/<dancer id>__<copy>.npz`, copy in V1, V2, V1m, V2m: `targets` (T100, 5) float32, `posture`, `gesture`, `tokens` (n_tok, 86) float32 standardised,
  `token_cols` (str), `token_mask` (n_tok,), `weight` (scalar), `fps`, `win_start_tok` (n_win,), `win_pass`, `win_part_names`, `win_parts`, `guard_share_seq`, `split`, `group`.
- Resumable: an npz that exists and loads with matching keys is skipped; each npz is written to a temp name and renamed.

## 8. Run plan

1. Lanes (brain env, 8 threads): every FineDance song and every kept AIOZ clip. Time: measured on one song in step 4.
2. Split, token norm (after lanes). 3. Targets and gating per dancer and copy (body env, MuJoCo sim 20 s windows, parallel processes on cores 6-13).
4. Report: `docs/T0_REPORT.md` and `t0/numbers.json`. Total projected time is logged from one long FineDance sequence; above 10 h -> "HOLD time <hours>".

## FOR USER (defaults taken)

- Surprisal from `bd.surprisal` (`s10`), not `b2.surprisal_lanes`.
- AIOZ non-30 fps resampled to 30 by slerp; mode reported.
- Ear-energy and beat-phase lanes keep their recorded smoothing, so a token's feature can reach up to 1 s past its end (the 7.59.8 "frames up to the token's end" holds for all other columns).
- Stored targets are referenced at sequence frame 0; windows are re-referenced only for the gate.
