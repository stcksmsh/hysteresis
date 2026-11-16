# Beat-coupling verification rules (WO47, BRAIN_SPEC 7.77 V1-V4) — written before any result

Report only; no training, no verdict. One arm. Code `scripts/body/beatv_*.py`; out `/secondary/hyst-data/body/beatv/` (Motorica stays on this laptop; aggregates only in git).
Order: V2 and V3 first (they can invalidate the rest), then V1, then V4 material. Defaults are marked **(default)** and listed under FOR USER in the night log.

## 0. Shared definitions

- Raw FineDance: `/secondary/hyst-data/datasets/finedance/data/finedance/{motion,music_wav}/NNN.{npy,wav}` (203 files, 30 fps, 315 columns = root position 3 + 52 joints x 6D). Key `fd_NNN`.
  6D -> rotation: Gram-Schmidt of the two 3-vectors, third = cross product (as `overseer/rawbeat.py`). The angle between consecutive rotations is invariant to the row/column convention.
- **Whole-body motion energy (raw)** = sum over the 22 body joints (SMPL-X order 0-21) of the angle between consecutive local rotations x 30 (rad/s). **Kinematic speed** for BAS = the same quantity divided by 22 (mean over joints).
- **Librosa beats (the second grid):** `librosa.beat.beat_track(onset_envelope=librosa.onset.onset_strength(y, sr=22050, hop_length=441), sr=22050, hop_length=441, units='time')` (defaults: start_bpm 120, tightness 100, trim True), on each song's audio mixdown (as `overseer/motionbeat.py`). Computed for every song of the four datasets: `beatv/librosa/<key>.json`.
- **Project grid** = `metric/beats` / FineDance stored grids (WO46, `analyze_mix`).
- **Onset envelope** = `librosa.onset.onset_strength(y, sr=22050, hop_length=735)` (30 Hz) for raw FineDance, hop 441 (50 Hz) against the realised stage.
- Realised motion = `metric/q50` (WO46 whole-sequence realised V1 and V2, all four datasets; mirrors excluded), lamp point and joints. Events E1 (lamp-speed minima), E2, E4, E5, E3 yaw exactly as `docs/METRIC_RULES.md` section 3 (`metric_lib.events`).
- Bootstrap by song group, 2,000 resamples, seed 47101, 95 % percentile intervals.

## 1. V2 published anchor: beat-alignment score (BAS)

**Source and definition.** BAS comes from Bailando (Siyao et al., CVPR 2022, section 4.1 "Beat Align Score", after AIST++/FACT, Li et al. ICCV 2021): with kinematic beats B^x (frames) and music beats B^y,
`BAS = (1/|B^y|) sum_{b in B^y} exp( - min_{t in B^x} (t - b)^2 / (2 sigma^2) )`, **sigma = 3 frames at 30 fps (0.1 s)**. The paper text sums over kinematic beats; the released evaluation code, as I remember it
(`for bb in music_beats: ba += exp(-min((motion_beats - bb)^2) / 2 / 9)`, divided by `len(music_beats)`), sums over music beats. **Both are computed, the music-beat sum is the main one**; the exact code was not available
(no download): **FOR USER: BAS code download needed to confirm the variant**. **Kinematic beats** (Bailando `get_mb` / AIST++): velocity magnitude = mean over joints of the 3-D position speed; smoothed with a Gaussian (sigma 5 frames);
local minima (`scipy.signal.argrelextrema(np.less)`). **Music beats**: librosa beat tracking (the project's second grid above; the paper does not state parameters).
**Published ground truth for FineDance:** BAS **0.2120**, Lodge (Li et al., CVPR 2024, arXiv 2403.10518), Table 1 ("Compare with SOTAs on the FineDance dataset", Ground Truth row; also Table 4). The FineDance ICCV 2023 paper's Table 2 (Ground Truth row)
reports Div 6.28, Div_h 3.48, GS 0.71 and **no BAS**; the value is therefore quoted from Lodge (same authors, same data). For scale: Bailando reports ground truth AIST++ BAS 0.2374.
**"Far" is defined here before computing: raw-data BAS (main variant below) outside 0.2120 +-25 %, i.e. outside [0.159, 0.265], is "far": the other steps then stop and the cause is looked for.**

**Raw FineDance.** All 203 files, whole sequence. Positions need forward kinematics with SMPL-X bone offsets; **no SMPL-X skeleton or model file exists locally** (verified), so:
- **main (deviation, marked): angular-speed proxy** = mean over the 22 body joints of the rotation angle per frame (Gaussian sigma 5 frames, argrelextrema minima), no positions.
- **variant: approximate FK** with a generic adult skeleton (bone lengths from standard proportions, T-pose offsets rounded: spine 0.11/0.13/0.05 m, neck 0.12, head 0.10, collar 0.08, upper arm 0.28, forearm 0.26, hand 0.08,
  hip offset 0.09, thigh 0.40, shank 0.40, foot 0.10; stated as approximate, not the SMPL values), 22 joints, positions + root translation as stored, then the Bailando recipe. A second deviation, marked.
- Music beats: librosa (above) for both; BAS also with the project grid. Controls for scale: the same kinematic beats against the music beats shifted by a uniform random offset in [0.25, 1] x the median beat interval (20 draws per song, seed 47102) = the BAS chance level of the song.

**Our realised motion** (V1 and V2, all four datasets): kinematic beats = local minima of (a) the lamp speed (50 Hz, Gaussian sigma 5 frames at 30 fps = 0.167 s = 8.3 samples), (b) each joint's |angular velocity|, as the Bailando recipe in seconds
(sigma_BAS 0.1 s); music beats = librosa and the project grid; same shifted-beat controls. Per-song values saved; dataset values = mean over songs, bootstrap by song.

## 2. V3 per-file sync (raw FineDance, and the realised stage as a second table)

Per file: demeaned whole-body motion energy a[t] (30 Hz) against demeaned onset envelope e[t] (30 Hz); c(k) = Pearson(a[t], e[t + k]) for k = -30..+30 frames (**step 1 frame = 33.3 ms**), k > 0 = the music envelope after the motion
(motion leads), every lag kept. **Best offset** = argmax_k c(k); strength = c at the best offset, compared with the same maximum over **200 circular shifts** of e by >= 5 s (seed 47103): z = (max c - mean of shifted maxima)/sd and the share of
files whose max c exceeds the 95th percentile of its own shifted maxima. **Drift** = best offset in the first 60 s minus best offset in the last 60 s (files >= 150 s; each with its own ±1 s scan). Reported: distribution (quantiles) of best offset, of strength, of drift,
share of files with |offset| <= 1 frame, and with |drift| > 2 frames. Second table: lamp speed and sum of joint |w| of the realised V1 and V2 (50 Hz, onset envelope hop 441, +-50 samples).

## 3. V1 local phase locking

Per song and per grid (project grid, librosa beats): sliding windows of **8 consecutive beats** (7 intervals), **hop 2 beats**. In each window: the beat times t_k (k = 0..7) are fitted by least squares `t_k = t0 + T k` (local period T, phase t0); the residual RMS of the fit (ms) is saved.
Events (E1, E2, E4, E5, E3 yaw of the realised V1 and V2, all four datasets; and, FineDance only, raw-mocap kinematic-speed minima (Gaussian sigma 3 frames at 30 fps, `find_peaks` of -speed, distance 6 frames, prominence 0.2 sd, as `overseer/rawbeat.py`)) that fall in [t_0, t_7) give phase
phi = ((t - t0)/T) mod 1; window R = |mean exp(2 pi i phi)|; windows with < 6 events are skipped (counted). **Controls inside the same window and events:** the line with the period scaled by 1.13 (phi' = ((t - t0)/(1.13 T)) mod 1) and by 0.87;
control R = mean of the two (a 13 % tempo error: the planner's incommensurate case); plus **beat intervals permuted within the window** (refit line to the permuted beat times, 20 permutations per window, seed 47104). Excess = R real - control R (both controls reported).
Chance R for n events ~ sqrt(pi)/(2 sqrt(n)) is reported next to the means. Per song = median over windows of the excess; dataset value = median over songs, **bootstrap by song** (CI of the median); also mean R real and R control, share of windows with R real > R control, the median fit residual, and the preferred phase (circular mean of the window mean-resultant vectors).
Also, as the overseer's notes request, the whole-song R (WO46 style, project grid) next to V1 numbers for the same songs.

## 4. Tests (`scripts/body/test_beatv.py`, synthetic)

Events locked to phase 0.3 on a beat grid whose tempo drifts by 4 % over the song: V1 local windows give R near 1 and phase 0.3 (whole-song single-line R clearly lower); uniform random events give the chance level;
a known offset of +7 frames between motion energy and onset envelope is recovered by V3 (and drift of a piecewise offset); BAS of motion whose speed minima sit exactly on the music beats is >= 0.95 (maximum 1), BAS of unrelated beats is near its shifted-beat chance level; the FK function maps a zero-rotation skeleton to a T-pose of the stated lengths.

## 5. V4 material (prepared, not served)

For the 10 songs of `metric/spotcheck/manifest.json`: one 30 s excerpt each, start chosen (seeded, 47105) among 30 s windows that are not in the first or last 10 s and whose mean RMS is at or above the song's own median RMS (7.75 Q3); short clicks (5 ms, 1.5 kHz, Hann-shaped, level 0.3 of the excerpt's peak) mixed at the project grid's beat times; second version with clicks at librosa's beats;
the two versions of a song are separate items in a random order (the key keeps which). One manifest of singles for `dialstudy_session.py`, question "Are the clicks on the beat?", answers yes / partly / no; folder `beatv/clicks/`. Motorica items stay local.

## FOR USER (defaults taken)

BAS variant (music-beat sum main; code not available); proxy BAS on angular speed instead of positions, approximate-FK variant with generic bones; far = outside +-25 % of 0.2120; librosa parameters as in section 0; V1 window 8 beats, hop 2, min 6 events; controls period x1.13 / x0.87 and permuted intervals.
