# Beat-coupling verification report (WO47, BRAIN_SPEC 7.77 V1-V4)

Rules: `docs/BEATV_RULES.md` (pushed before any result; "far" fixed beforehand as outside 0.2120 +-25 %). Code `scripts/body/beatv_{lib,raw,real,v3curve,report,clicks}.py`, tests `test_beatv.py` (6) and `test_dialstudy_wo47.py` (1), all pass.
Full tables: `docs/BEATV_TABLES.md`. Per-song values: `/secondary/hyst-data/body/beatv/{raw,real,v3.json}`. Report only; no verdict. Bootstrap by song, 2,000 resamples, seed 47101.
Inputs scanned before any long run: 1,341 songs with audio, 203 raw FineDance files (315 columns, finite, wav present), 0 bad. No per-file failures in any step.

## V2 published anchor (BAS), run first

- **Source:** Bailando (Siyao et al., CVPR 2022, section 4.1), sigma 3 frames (0.1 s), kinematic beats = minima of Gaussian-smoothed (sigma 5 frames) mean joint speed, music beats from librosa. **Published ground truth for FineDance: 0.2120**, Lodge (Li et al., CVPR 2024, Table 1 and Table 4).
  The FineDance ICCV 2023 paper (Table 2, ground truth row) reports Div 6.28, Div_h 3.48, GS 0.71 and no BAS, so the order's "FineDance (ICCV 2023)" value is taken from Lodge (same authors). The released BAS code was not available: the music-beat-sum variant (my recollection of the code) is the main one, the kinematic-beat sum (paper text) next to it. **FOR USER: BAS code download needed to confirm.**
- **Deviation:** no SMPL-X skeleton exists locally; main = angular-speed proxy (mean over 22 joints of rotation angle per frame); variant = approximate FK with generic bone lengths (both marked deviations in the rules).
- **Raw FineDance ground truth, 203 files, sigma 0.1 s, music-beat sum, librosa beats:** proxy **0.227 [0.220, 0.235]**, approximate FK **0.218 [0.211, 0.226]**; with the project grid 0.224 and 0.216. All inside 0.2120 +-25 % ([0.159, 0.265]): **not "far", the pipeline was not stopped.** The kinematic-beat-sum variant gives 0.42-0.48 (that variant has no published value to compare).
- **Chance level: the same BAS with music beats shifted by a random fraction of a beat interval is 0.225 [0.220, 0.229] (proxy, librosa) and 0.214 (FK). BAS minus chance is +0.003 [-0.003, 0.009] (proxy) and +0.004 [-0.001, 0.010] (FK); +0.001 / +0.002 with the project grid; the kinematic-beat variant +0.004 / +0.005.**
  So the published ground-truth BAS 0.2120 is indistinguishable from what unrelated shifted beats give with this beat density (about 2 music beats/s, 0.9 kinematic minima/s): BAS at sigma 0.1 s does not show beat coupling in the raw FineDance ground truth either, here or (by the match with the published value) in the paper.
- **Our realised stage** (lamp speed minima, V1 and V2, four datasets): BAS 0.23-0.26 against a chance of 0.23-0.26; BAS minus chance within +-0.006 everywhere (FineDance lamp V1 0.000 [-0.004, 0.004] project / -0.001 librosa; V2 +0.003 / -0.003; AIOZ V1 -0.005 [-0.010, -0.001] project; PhantomDance +0.002 / -0.001; Motorica -0.002 / -0.006 [-0.012, 0.000]); per-joint rows in `BEATV_TABLES.md`. The retargeted motion matches the raw data in this measure (both at chance).

## V3 per-file sync (raw FineDance, whole files)

- Cross-correlation of whole-body motion energy with the onset envelope, shifts -1..+1 s in 33 ms steps. **The best offset is spread over the whole range**: quantiles 5/25/50/75/95 = -0.93 / -0.47 / +0.03 / +0.42 / +0.87 s; only 7.9 % of files have |offset| <= 33 ms (17.7 % within 100 ms).
  The mean correlation curve over files is flat (+0.023 .. +0.032 at all shifts, no peak): there is a small positive offset at every lag (slow co-variation of energy and loudness) and no sharp feature at any lag.
- Strength: median maximum correlation 0.069; z against 200 circular shifts median 1.73; 51.7 % of files exceed their own 95th percentile of shifted maxima (5 % expected). So most files show some correlation above chance, at a broad, file-specific lag.
- **Drift** (83 files of >= 150 s): best offset in the first minute minus last minute: quantiles -39 / -12 / -1 / +15 / +33 frames; 77 % of files differ by more than 2 frames. Because the best offset itself is ambiguous modulo the beat period (a ~0.5 s periodicity) this is mostly offset ambiguity, not a measured clock drift.
- Realised stage (lamp speed, summed joint speed, V1/V2, 203 FineDance songs): best offsets equally spread (within 50 ms: 2.5-3.9 % of files), max correlation median 0.035-0.042, mean curves flat.
  There is no consistent sync offset between the audio files and the motion in the raw data at a resolution of 33 ms, in either the raw or the realised motion.

## V1 local phase locking (windows of 8 beats, hop 2, events E1/E2/E4/E5 and yaw peaks E3_0)

- **Grid quality first:** the least-squares line through 8 consecutive beats leaves a median residual of **80-620 ms for the project grid** (FineDance ~80-170 ms, AIOZ 100-400 ms, PhantomDance 130-620 ms, Motorica 70-100 ms) and **6-8 ms for librosa beats** (Motorica 18 ms). The project grid is locally irregular (beat-to-beat jumps, half/double-time switches): a straight local line is not a good model of it, so V1 with the project grid is partly a test of the grid.
- **Project grid:** median excess of R over the period-scaled controls is slightly negative or zero for lamp-speed minima E1, acceleration peaks E2 and onsets E5 in all datasets and both variants (e.g. FineDance V1 E1 -0.008 [-0.014, -0.001], E2 -0.012 [-0.020, -0.006]; AIOZ V1 E1 -0.001, E5 +0.001; PhantomDance -0.005 / -0.007 / 0.000; Motorica -0.007 / -0.008 / -0.004); yaw peaks FineDance V1 +0.024 [0.003, 0.038], others -0.013 .. +0.038 with intervals including 0.
- **Librosa beats (regular local lines):** E1 and E2 FineDance, PhantomDance, Motorica: -0.007 .. +0.009, intervals include 0 (FineDance V1 E1 -0.007 [-0.016, 0.003]); **AIOZ E1 +0.022 [0.015, 0.029] and E2 +0.021 [0.012, 0.032] (V1), +0.021 / +0.021 (V2)**; onsets E5: AIOZ V1 +0.055 [0.035, 0.079], V2 +0.096 [0.065, 0.134], Motorica +0.020 / +0.022, FineDance -0.042 .. +0.002, PhantomDance +0.027 / +0.007 (intervals include 0).
  **Yaw velocity peaks lock to librosa's local lines: median excess FineDance V1 +0.150 [0.101, 0.227] (91 songs), V2 +0.050 [0.019, 0.120]; AIOZ V1 +0.482 [0.350, 0.555] (77 songs), V2 +0.248 [0.216, 0.311]; PhantomDance V1 +0.107 [0.033, 0.199], V2 +0.077 [0.032, 0.134]; Motorica V1 +0.158 [0.073, 0.230], V2 +0.127 [0.071, 0.173].**
  Mean R real 0.44-0.69 against control 0.31-0.37, 60-79 % of windows above control. Caveats: a window needs >= 6 events in 3.5 s, so yaw (the sparsest event) is evaluated only in windows with fast regular base rotation (fewest windows: 52-120 songs per cell, `BEATV_TABLES.md` columns "songs" and "windows"); the control destroys a lock to the period, not to the phase (a periodic yaw movement at the beat tempo with any offset scores high); **the preferred phase differs between songs** (pooled phase 0.77-0.98, spread of per-song phases R 0.10-0.28), so this is a period (tempo) lock with a song-specific phase offset, not a common beat-relative phase.
- Permuted-interval control: excess ~0 everywhere (permuting 7 intervals and refitting a line barely changes the line); it is not informative and is reported for completeness.
- **Raw FineDance mocap** (kinematic-speed minima, 203 songs): project grid -0.007 [-0.011, -0.003]; librosa **+0.012 [0.003, 0.019]**; mean R 0.31 against control 0.28 (librosa), 52.5 % of windows above control; whole-song R 0.067 (project) / 0.099 (librosa) (the overseer's check: 0.079 against 0.060 shifted). Realised FineDance V1 E1 against librosa: -0.007 [-0.016, 0.003]: the retargeted motion and the raw mocap agree (both near 0).
- Whole-song R (project grid, WO46 style) for the same sequences: 0.05-0.20 (same as WO46).

## V4 click material (prepared, not served)

`/secondary/hyst-data/body/beatv/clicks/`: 10 songs of `metric/spotcheck/manifest.json`, one 30 s excerpt each (start seeded, not in the first or last 10 s, mean RMS >= the song's median), 5 ms 1.5 kHz Hann clicks at 0.3 of the excerpt peak at the project grid (items `S00a`..`S09a`) and a separate item at librosa's beats (`S00b`..`S09b`) = 20 singles,
`manifest.json` (labels yes / partly / no, question "Are the clicks on the beat?") for `dialstudy_session.py` (which gained a per-item `question` for singles, test added), `key.json` (grid per item). Median distance between the two grids' beats in the excerpts' songs: FineDance 54-121 ms, AIOZ 62-97, PhantomDance 77-137, Motorica 77-180 ms (`key.json`).
The session shuffles items. Motorica items (4 of 20) stay local.

## Coverage

- V1/V2 realised steps analysed 4,594 of 4,778 sequences; **184 skipped, all AIOZ** (0.40 of 38.5 AIOZ hours, 1.0 %): train 170 sequences / 0.38 h, test 14 / 0.02 h, validation 0. The cause is a grid with fewer than 12 beats (the V1 window needs 12 for at least 3 windows): project grid 182 of them, librosa 82 (WO46's 78 used < 8 beats). FineDance, PhantomDance, Motorica: none skipped.
- Raw V2/V3: 203 of 203 FineDance files.

## What the numbers say (no verdict)

1. The published ground-truth BAS for FineDance (0.2120) is reproduced on the raw data (0.22), and it equals the chance value of shifted beats; the standard score therefore does not itself show beat coupling in this dataset, and our realised motion is at the same level.
2. No consistent audio/motion sync offset exists per file (V3), at a 33 ms step; per-file correlation above chance is broad (|best offset| spread over +-1 s), the mean curve has no peak.
3. Locally, with a regular grid (librosa), yaw peaks lock to the beat period in all four datasets (and onsets in AIOZ, weakly elsewhere), with song-specific phase; lamp speed minima and acceleration peaks do not (except AIOZ, +0.02). With the project grid nothing locks, but that grid is irregular within 8 beats (residual 80-620 ms).
4. The planner's reading (a measurement cause) is therefore supported in one respect (grid regularity matters: the lock appears with the regular grid and only for the yaw events and AIOZ), and not in another (the BAS anchor itself sits at chance and the raw mocap lamp-like minima gain only +0.012 with librosa).

## FOR USER

BAS variant (music-beat sum main, code unavailable); proxy and approximate-FK deviations; librosa parameters (hop 441, defaults); V1 window 8 beats, hop 2, >= 6 events, >= 12 beats per song; controls period x1.13 / x0.87 (permuted-interval control uninformative); the published ground truth is quoted from Lodge (CVPR 2024), not the ICCV paper.
