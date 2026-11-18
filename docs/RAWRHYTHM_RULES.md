# Raw-joint movement rhythm vs beat: rules (WO53 part B, BRAIN_SPEC 7.84 item 3) — written and pushed before any result

Report only. No change to A or B, nothing trained, no verdict. One arm. Code `scripts/body/rawrhythm.py` (one file), tests
`scripts/body/test_rawrhythm.py` (synthetic only). Out: `/secondary/hyst-data/body/rawrhythm/`. When these rules were pushed no raw-joint
rhythm value had been computed on human data. Defaults are marked **(default)** and listed under FOR USER.

## 0. What is reused unchanged from WO52 (`docs/RHYTHM_EVENTS_RULES.md` section 1-2)

Everything in WO52's rhythm part except the signal: analysis windows W = 3 s (main) and 4 s (variant), hop 1 s, inside A's kept 20 s
windows; linear detrend; biased autocorrelation; highest local maximum in lags 0.2-2.5 s with parabolic refinement; rhythm strength;
"none" below strength 0.2 (narrow variant 0.3) or with no peak; librosa local beat period (median IOI within the window ±1.5 s, >= 3
intervals) and pulse v2 period (median `period` in the window); ratio r = movement period / beat period; bins 1/2 [0.4, 0.6], 1 [0.8, 1.25],
2 [1.6, 2.5], other (narrow variant [0.45, 0.55], [0.9, 1.11], [1.8, 2.22]); cluster share; circular concentration C of log2 r; chance 1
(similar-tempo song of the same dataset, ±10 %, 20 draws, seed 52103) and chance 2 (shuffled periods within the dataset, 20 permutations,
seed 52104). The functions are imported from `scripts/body/rhythm_events.py`, not copied.

**Same windows:** the analysis rows are exactly WO52's rows (`rhythm/windows_<ds>.npz`: every V1 and V2 copy of every kept window, W = 3
and 4). The raw motion of a performance is the same for its V1 and V2 copies, so each raw value is attached to both copy rows (as the lamp
side has one row per copy). Because the rows, beat periods, songs and groups are identical, the chance draws (same seeds, same order) are
identical for the raw signals and for the lamp: only the movement period and strength differ. The lamp numbers are recomputed in the same
run and must equal WO52's point estimates (checked and reported).

**Bootstrap:** by song group (WO52's unit), 2,000 resamples, **seed 53201**, 95 % percentile intervals, for raw and lamp alike.

## 1. The signal: raw human joints before retargeting

- **Joints (6):** left wrist, right wrist, left foot, right foot, pelvis, head. "Foot" = the ankle joint **(default)** (SMPL L_Ankle 7 /
  R_Ankle 8; Motorica BVH `LeftFoot` / `RightFoot`): the one foot joint present in every skeleton; SMPL's toe-side "foot" joints 10/11
  are frozen in FineDance. Wrist = SMPL 20 / 21, BVH `LeftHand` / `RightHand`; pelvis = SMPL 0, BVH `Hips`; head = SMPL 15, BVH `Head`.
- **Positions per dataset** (all at 30 Hz, frame j at song time j / 30 s, the T0 time base: T0 window w = frames 600 w .. 600 (w + 1)):
  - **FineDance** `datasets/finedance/data/finedance/motion/NNN.npy` (30 fps): local rotations (6D, `beatv_lib.local_rots`), root
    translation as stored, **approximate FK with generic bone lengths** (`beatv_lib.fk`, WO47's skeleton): **deviation, marked** (no SMPL-X
    model locally).
  - **AIOZ** `datasets/aioz/data/motions_smpl/<clip>.pkl` (30 fps; opened only by `t0_aioz.load_pkl`, the restricted unpickler), person
    `p` of the key: axis-angle -> local rotations (`t0_aioz.aa_to_mats`), `root_trans`, the same generic FK: **deviation, marked**.
  - **PhantomDance** raw json (`/secondary/hyst-data/phantomdance/raw/PhantomDanceDatav1.1/motion/NNN.json`, path from
    `t0_phantom/catalogue.json`, 30 fps): world quaternions with the x flip and frame-truncation rule of `t0_phantom.phantom_rot`,
    root positions as stored, the same generic FK from the world rotations (P_j = P_parent + G_parent offset_j): **deviation, marked**
    (the json has no bone offsets).
  - **Motorica** raw BVH (`/secondary/hyst-data/motorica/raw/motion/motorica_dance_dataset/bvh/<name>.bvh`, path from
    `t0_motorica/catalogue.json`, 120 fps), decimated to every 4th frame exactly as `t0_phantom.motorica_rot` (the T0 time base), FK with
    **the file's own skeleton offsets** (cm -> m; Euler channels in the listed order, intrinsic, as `motorica_rot`; position channels used at
    the root only, non-root position channels checked constant in the scan). Not approximate.
  - The raw sources of PhantomDance and Motorica live outside `/secondary/hyst-data/datasets/` (their T0 catalogues point there); read-only.
  - AIST++ is local but has no WO52 windows (not in A): not analysed.
- **Speed:** each joint's 30 Hz position (m) is interpolated to the 50 Hz grid t = n / 50 by a cubic spline (`scipy.interpolate.CubicSpline`,
  not-a-knot) **(default)**, then speed = |np.gradient(position) x 50| (m/s), as the lamp speed in WO52.
  - **world** = position in the dataset's world frame including root translation (main);
  - **pelvis-relative** = position minus the pelvis position (world axes, not rotated with the body) (variant). Pelvis-relative pelvis is
    identically zero and is "none" by the variance rule (reported as such);
  - **mean of the six** = mean of the six joint speeds at each sample (world; and pelvis-relative, where the pelvis contributes 0).
- Window slice: song time [20 w + s, 20 w + s + W) = samples [50 (20 w + s), 50 (20 w + s + W)) of the whole-sequence 50 Hz speed.

Signals: `lamp` (WO52, recomputed), raw `lwr, rwr, lft, rft, pel, head, mean` (world) and `lwr_rel, ..., mean_rel` (pelvis-relative):
15 in all. Variants narrow and W = 4 for `lamp`, `mean`, `mean_rel` only **(default)**; all signals in the main variant.

## 2. Outputs per dataset (and pooled), per signal, per beat source (librosa, pulse v2)

As WO52 section 2: bin shares (of all windows and of rhythmic windows), cluster share, chance 1 and 2 cluster share, **excess 1 and 2**
(cluster share minus chance) with song-group bootstrap interval, C and its excess over both chances with interval.
Also:
- **period distributions:** quantiles 5/25/50/75/95 of the movement period (s) and of r over rhythmic windows, raw vs lamp;
- **paired per-window comparison** (W = 3, main): per row with a beat period of the source, the bin of the raw signal vs the bin of the lamp
  (5 bins incl. none): share of rows in the same bin; the same share expected if the two bins were independent (sum over bins of the product
  of the two marginal shares); and the same two numbers over rows where both are rhythmic (4 bins);
- histograms of log2 r (as WO52, counts in `results.json`).

## 3. The 7.84 item 3 condition, as numbers (no verdict)

Stated per beat source and per chance model, main variant, pooled and per dataset:
- "raw joints cluster at 1/2, 1, 2" = the cluster-share excess of at least one raw joint signal or the mean (world or pelvis-relative) has a
  95 % lower bound > 0;
- "the arm does not" = the lamp's excess interval includes 0.
The number of raw signals examined (13 non-degenerate x 2 sources x 2 chances) is stated next to it; no multiple-comparison correction is
applied **(default)**.

## 4. Files

`/secondary/hyst-data/body/rawrhythm/`: `scan.json`; `windows_<ds>.npz` (row-aligned to `rhythm/windows_<ds>.npz`: key, W, win, start,
lib, pul, group, song, and per_<sig>, str_<sig> for every raw signal); `songs_<ds>.npz` (per song group counts: rhythmic, in-cluster,
complex sum, bin counts, chance expectations, per source / signal / variant); `results.json`; `tables.md`. Report
`docs/RAWRHYTHM_REPORT.md`, full tables `docs/RAWRHYTHM_TABLES.md`. Motorica appears in git only as dataset aggregates.

## 5. Tests (`test_rawrhythm.py`, synthetic joints through the raw pipeline: 30 Hz positions -> spline -> speed -> rhythm -> bin)

A joint going round a circle with its speed pulsing at the beat period gives r = 1; a joint swinging back and forth with period 2 beats
gives r = 1 (speed pulses twice per swing); a joint whose speed pulses at twice the beat period gives r = 2; a joint with white-noise
position gives "none"; pelvis-relative removes a common translation; the BVH reader and FK place a two-bone synthetic chain correctly.

## FOR USER (defaults taken)

1. Generic-bone approximate FK for FineDance, AIOZ and PhantomDance (no SMPL model locally; PhantomDance json has no offsets); Motorica
   uses its BVH offsets.
2. Foot = ankle joint.
3. Raw sources of PhantomDance and Motorica read from `/secondary/hyst-data/{phantomdance,motorica}/raw/` (outside `datasets/`).
4. 30 Hz -> 50 Hz by cubic spline of positions.
5. Raw value duplicated on V1 and V2 rows so the window set and chance draws equal WO52's.
6. Narrow and W = 4 variants only for lamp and the two means; no multiple-comparison correction.
