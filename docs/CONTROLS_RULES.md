# Controls rules: the control representation (work order 43, BRAIN_SPEC 7.73 Steps 0a, 0b, 0c, clip candidates for 0b')

Written and pushed before any control value is computed. Binding: `BRAIN_SPEC.md` 7.73 (with its overseer notes), then 7.59, 7.61-7.63, 7.69-7.71 where 7.73 does not change them.
Measures and reports only: no training of A or B, no grammar, no listener, no k-means control vocabulary. One arm. Code: `scripts/body/controls_*.py`.
Out: `/secondary/hyst-data/body/controls/` (outside git). **Motorica and anything derived from it stay on this laptop; no per-file Motorica numbers in git (aggregates only).**
Defaults taken where the spec is open are marked **(default)** and listed under FOR USER in the night log.

## 1. Source trajectory (7.73 Step 0a "realised or target")

**Realised** (default), for every dataset. Why: it is what the arm actually does (servo, limiter, hard stops, v2p body), it is the stage T1a2 measured jitter on, and a control
that A is asked to reproduce is only meaningful at that stage. Target (stored `targets`) would carry guard and spinal-layer artefacts that never reach the lamp.
Recipe = `t1a_eval.gate_one` / `t1a2_realised.sim_one` exactly, for every **kept** window (`win_pass` true) of every copy (V1, V2, V1m, V2m) of every dancer of FineDance, AIOZ (calibrated
keep list), PhantomDance and Motorica (the existing `t0*/seq/*.npz`): rows = `targets[a:a+2001]` (a = 2000 x window index), pre-roll = `targets[a-150:a]` (first row repeated for window 0),
yaw and roll re-referenced to the window start, `guard`, `motornet.spinal` (H1), `FX.simulate_goals` -> `q50` (1001 rows, 50 Hz, deg, 5 joints), the same rows the gate judged.
Lamp = point 5 of `m3f_report.fk_points(q50)` (m, rig frame: base at the origin, z up, yaw as realised). All derivatives are taken on these 50 Hz rows.

## 2. Token grid, derivatives, filters

- Token k (k = 0..39 of a window) = samples 25k .. 25k+24 of `q50` (0.5 s, t = j/50 s); sample 1000 is unused. This is the T0 token grid (window w, token k = global token 40w + k).
- Joint angular velocity w_j = np.gradient(q50_j) x 50 (deg/s). Lamp velocity v = np.gradient(p) x 50 (m/s), acceleration a = np.gradient(v) x 50, jerk = np.gradient(a) x 50.
  `np.gradient` = central difference inside, one-sided at the window's two ends. Support past a token: 1 sample for v, 2 for a, 3 for jerk.
- Every per-token value below uses only samples inside the token **plus** the stated filter support: derivative support (<= 3 samples = 0.06 s), accent smoothing (2 samples), the sharpness
  high-pass (zero-phase Butterworth, effectively +-0.3 s, whole window), and the pause run test (a run may cross the token edge). These are measures of human motion, not model inputs.

## 3. The six controls (7.73 Step 0a)

Constants fitted on **FineDance train split, kept windows, all four copies** only (token rows of split "train"); written to `controls/norm.json` and reused unchanged for every dataset.

1. **Vigour.** `vj` = sqrt(mean over the token's 25 samples and 5 joints of w_j^2) (deg/s); `vl` = sqrt(mean over the 25 samples of |v|^2) (m/s); kept separately, plus the five per-joint RMS.
   Normalisation: `l = log(x + eps)`, eps = 0.01 (deg/s for `vj`, m/s for `vl`), right-skewed quantities; `z = (l - median) / (1.4826 MAD)` with median and MAD from FineDance train tokens.
   **Combined vigour** = first principal component of (z_vj, z_vl) (covariance of the train tokens), sign fixed so both loadings are positive, scaled to unit variance on train. Loadings stored.
2. **Height.** `z_mean` = mean lamp z over the token. Usable workspace: **z in [0.11, 0.77] m**. Lower bound 0.11 = 0.05 (link clearance) + 0.06 (hand disc radius), the floor clearance the gates enforce
   (`m3f_report.FLOOR_M + DISC_M`). Upper bound 0.77 = maximum lamp z over a 45^3 grid of the three bending joints across their limits (+-110 deg, `make_arm.RANGE_DEG`; yaw and roll do not change z;
   the straight-up value is 0.08 + 0.28 + 0.22 + 0.08 + 0.11 = 0.77 m from `make_arm.LINKS`). `height = clip((z_mean - 0.11) / 0.66, 0, 1)`.
3. **Accent pattern.** Per sample `u = |a| / A + |jerk| / J`, with A and J the FineDance-train p95 of |a| and |jerk| over all samples of kept tokens; smoothed with a centred 5-sample box
   (0.1 s), edge samples reflected; aggregated to **8 sub-slots of 62.5 ms = 3.125 samples** by exact area-weighted mean (cumulative sum interpolated linearly at the fractional slot edges).
   The scalar `accent_mean` = mean of the 8 slots (accent density / strength, used for the look pairs); `accent_peak` = max slot / mean of the slots (peakiness; reported only).
4. **Sharpness.** Share of high-frequency acceleration energy in total movement energy, dimensionless: a_hp = zero-phase Butterworth high-pass (order 2, `filtfilt`, cutoff **3 Hz**, applied to the
   whole 20 s window, the 3-D lamp acceleration per axis); `sharp = sum |a_hp|^2 / sum |a|^2` over the token's samples. Band edges 3 Hz .. 25 Hz (Nyquist); the 3 Hz edge is the one the jitter measure
   (`pos_measures`/`p_gt3`) uses. Defined only where the token's lamp acceleration RMS >= 0.05 m/s^2 (else NaN, counted and reported). Scaling the whole trajectory by a constant leaves `sharp` unchanged
   (linear filter); tested on a synthetic signal.
5. **Direction.** `d = mean(v)` over the token's samples (m/s, rig frame); direction = d / |d| (unit 3-D vector) if |d| >= 0.02 m/s, else the zero vector with flag `dir_ok = 0`. `dir_z` and
   the elevation angle (asin dir_z) are the scalar summaries. **Mirror copies (V1m, V2m) enter with the direction as realised** (the arm's own frame; no un-mirroring): the mirror flips the sign of x/y
   components by construction, so in per-dataset statistics the x and y components are summarised by their absolute value, `dir_z` as is.
6. **Continuity.** Lamp speed `|v|` per sample; a **pause** is a run of consecutive samples (over the whole window) with `|v| < 0.05 m/s` lasting **>= 13 samples** (> 0.25 s). `pause_prob` = share of the token's
   samples inside pause runs; `activity` = share of the token's samples with `|v| >= 0.05 m/s`. The continuity control used for the look pairs is `pause_prob` (low = continuous).

## 4. Measured only (not controls)

- **Movement lead (proximal vs distal onset order).** Onset of joint j = an upward crossing of |w_j| through `0.25 x p90_j` (p90_j = FineDance-train p90 of |w_j|) after |w_j| stayed below `0.125 x p90_j` for at least 0.2 s.
  Proximal = base yaw, shoulder; distal = wrist bend, wrist roll. Each distal onset is paired with the nearest proximal onset within +-0.5 s; lead = t_distal - t_proximal (positive = distal later, the
  expected order). Token value = mean lead of the pairs whose proximal onset lies in the token (NaN if none). Reported: distribution, share positive, coverage.
- **Slow structure on the motion side.** Per window, the 40 tokens' control vectors (combined vigour, height, sharp (NaN -> 0), pause_prob, accent_mean), z-scored with train constants: cosine
  self-similarity matrix S; novelty = checkerboard kernel of half-width 4 tokens (2 s) with a Gaussian taper (sigma 2 tokens) correlated along the diagonal (valid for tokens 4..35); phrase boundaries =
  local maxima of novelty at least mean + 1 sd high and at least 4 tokens apart; **repetition** of token k = max cosine similarity of the 4-token block starting at k to any block starting >= 8 tokens away
  (inside the window); **contrast** = novelty value. Windows are 20 s, so phrases longer than ~10 s cannot appear: stated limit.

## 5. Copies, splits

- All four copies enter each statistic as separate token rows (mirrors included; direction as in 3.5). The bootstrap resamples **songs** (the T0 split group: FineDance song group, AIOZ YouTube id,
  PhantomDance/Motorica group) with all their dancers, copies and windows, so copies and co-dancers of one song never count as independent. Splits stay as T0 made them (`split` stored per token); the
  normalisation is fitted on FineDance train only; Step 0b/0c statistics are descriptive and use **all kept windows of the dataset** (split-wise FineDance tables for the correlation matrix are added as a check).
- Per-song statistics use the kept tokens of a group, pooled over its dancers and copies.

## 6. Step 0b (numeric validation), per dataset (PhantomDance and Motorica reported separately, marked "look check pending")

Scalar controls: vigour (combined), vj, vl, height, accent_mean, sharp, pause_prob, activity, dir_z (+ |dir_x|, |dir_y| for completeness).
- Distributions: quantiles 1, 5, 25, 50, 75, 95, 99; a 20-bin histogram (fixed bin edges from the pooled FineDance train 0.5 / 99.5 percentiles, same for all datasets); NaN share.
- Pairwise Pearson and Spearman (Spearman = Pearson of the ranks, ranks computed once per dataset; bootstrap resamples the ranked rows), pairwise-complete; every pair with |r| > 0.7 in either is flagged "redundant".
- Within-song vs between-song variance share per control: between = sum_g n_g (m_g - m)^2 / sum (x - m)^2, within = 1 - between (group = song group).
- Bootstrap by song for every interval: 200 resamples, seed 4301, 95 % percentile intervals (quantiles: median; correlations; variance share).

## 7. Step 0c (report-only, human data)

Acoustic measures per token, from the T0 lanes (`t0*/lanes/<song>.npz`, the 44 fast features at 100 Hz un-standardised with `braindump.stats()`; 50 frames per token, frame t centred at t/100 s):
**RMS** (mean of `20 log10 max(rms, 1e-4)` over the token's frames, dB; col 41), **spectral flux** (mean of the 8 band-flux columns 32..39, then over frames), **onset strength** (col 40, mean over frames), **low-band
energy** (mean of the log-mel dB columns whose Slaney band centre < 200 Hz), **high-band energy** (same for centre >= 3200 Hz; centres from `librosa.mel_frequencies(34, 30, 16000)[1:-1]`),
**spectral centroid** (col 42, mean), **local dynamic range** (p95 - p5 of the 100 Hz RMS dB over the 4 s window centred on the token, clipped at the song ends), **beat strength** (FineDance only: max over the
beats of `t1b/cortex/beats/<key>.json` that fall inside the token of the maximum onset-strength frame within +-50 ms of the beat; NaN where no beat falls inside; the other datasets have no stored beat grid and
are not given this measure: stated, not faked).
Controls related to these: combined vigour, vj, vl, height, sharp, pause_prob, accent_mean, dir_z.
Relation of each control to each measure: Pearson and Spearman, **global** (all tokens), **within-song** (the song group's mean removed from control and measure), **per song** (Spearman per group with >= 60 tokens:
median, quartiles, share of songs with a positive value), and **over lags -1..+1 s** = -2..+2 tokens (control of token k against measure of token k + L; L > 0 = the music after the motion). Bootstrap by
song (same scheme, seed 4301) for the global and within-song values at every lag.
Musical structure layer (report-only, no source separation, no instrument labels): beat = the existing offline grid (FineDance); onsets = the onset-strength measure; **phrase boundaries and repetition**
by the section-4 novelty/repetition routine applied to (a) the token music features (44 ear columns + the 32 mode amplitudes, standardised as T0: all datasets) and (b) for FineDance the frozen
cortex (`t1b/cortex/<key>.npy`, token mean of the 2048 h components, float16 read, FineDance only). The music routine runs on the whole song, then is cut to the windows. **Alignment of the motion-side
boundaries with the music-side boundaries**: share of motion boundaries with a music boundary within +-1 token, against 200 circular shifts (seeded, >= 10 tokens) of the music boundaries inside the window; bootstrap by song.

## 8. Clip candidates for Step 0b' (rendered here, not served; no answers file is opened)

- Pool: FineDance **validation and test** songs only, copies **V1 and V2 (not mirrored)**, kept windows. A candidate clip = 16 consecutive tokens (**8 s**) starting at a token multiple of 4 inside one kept window.
  Clip control value = mean of the per-token control over its 16 tokens (NaN tokens skipped; clips with > 25 % NaN dropped).
- Controls and their value: vigour (combined), height, sharpness (`sharp`), continuity (`pause_prob`), accent density (`accent_mean`). For each, **3 pairs** = a "low" clip (value <= pool p10 of that control)
  and a "high" clip (value >= p90), **both of the same variant (V1 or V2)**, different songs.
- Matching rule: the other four controls matched where possible: residual `r = sum over the other controls of |value_low - value_high| / pool sd`; among all (low, high) pairs the 20 smallest `r` form the
  shortlist; pair i takes shortlist entry `default_rng(4302 + 10 c + i).integers(20)` (c = control index), skipping a shortlist entry that reuses a song already used by that control or a clip already used by any
  control. Residual differences (per other control, in pool sd units) and the pair's own control values are reported in `CONTROLS_REPORT.md`.
- Render: the same retarget clip chain as `t0_phantom_look.py` (pre-roll 1.5 s, guard, limiter, servo, v2p), through `retarget_render.sh` with `RETARGET_ROOT=/secondary/hyst-data/body/controls/look`, lamp head,
  1280x720, the song's own audio excerpt (offset 0). The window-aligned 8 s excerpt reproduces the realised q50 of section 1, so the reported control values are those of the rendered motion.
- Manifest: `look/manifest.json`, kind "pair", 15 items, each with `question` per control: vigour "Which looks bigger / faster?", height "Which looks higher?", sharpness "Which looks sharper?",
  continuity "Which looks more continuous?", accent density "Which looks more accented?", answers first / second / same. The order inside a pair is drawn from a seeded RNG (the key keeps `control`, `high_first`). If
  `dialstudy_session.py` cannot carry a per-item question, the smallest option that does is added (a manifest field `question`), with a test. Nothing else of the tool changes.

## 9. Tests (synthetic, known answer)

Constant lamp speed -> vigour constants as computed by hand; a pure tone at a known frequency -> sharpness near 0 at 1 Hz and near 1 at 10 Hz; sharpness unchanged under a uniform amplitude scale; a pause of a
known length -> `pause_prob` exact (runs of 12 samples do not count, 13 do); a straight line in a known direction -> the direction vector; the 8 sub-slots of a ramp sum to the token's mean exactly; a token's
control values change only if an input sample inside token + stated support changes (perturb one sample far outside -> identical).

## FOR USER (defaults taken)

1. Realised stage (not target) is the source; target would be one switch away.
2. Workspace z bounds 0.11 .. 0.77 m (floor clearance gate and the straight-up reach).
3. Log transform before the robust normalisation of vigour parts; eps 0.01.
4. Sharpness cutoff 3 Hz (the jitter measure's edge), undefined below 0.05 m/s^2 acceleration RMS.
5. Pause threshold 0.05 m/s, run >= 13 samples; direction zero below 0.02 m/s.
6. 8 s clips, 3 pairs per control, shortlist of 20; V1/V2 only, no mirrors in the look pairs.
7. Beat strength FineDance only (no stored beat grid elsewhere); cortex-based structure FineDance only.

## Addendum 1 (2026-11-16, after the FineDance controls were computed once, before any statistic was read)

The movement-lead onset rule of section 4 ("|w_j| stayed below 0.125 p90 for at least 0.2 s before the crossing") never fired on the realised dance trajectories (lead was NaN for all 101,760 FineDance tokens
of V1, a rest of 0.2 s is practically absent in dance). Changed, for the lead only and nothing else: an onset of joint j is an upward crossing of |w_j| through 0.25 x p90_j **after |w_j| dipped below
0.125 x p90_j at some sample within the preceding 0.2 s** (10 samples). Pairing (+-0.5 s), proximal/distal sets and token assignment unchanged. On a 1/6 sample of FineDance V1 windows the new rule gives about 4,600 proximal and
7,200 distal onsets, 6,853 pairs. The five controls and every other measure are untouched; the FineDance controls files were recomputed with the new lead rule.

## Addendum 2 (2026-11-16, fix 1, pushed before recomputing)

Height bounds come from the v2p body the realised stage simulates (`make_arm_v2p.py`: column top z = 0.053 m, floor 1.0 m below it at z = -0.947 m, link margin 0.05 m, hand margin 0.11 m), not from the old table body.
Usable workspace = the lamp z range over joint poses with `make_arm_v2p.margins(q) >= 0`, computed on a grid: yaw 0..345 deg step 15, shoulder / elbow / wrist bend -110..110 deg step 5 (roll does not move the lamp point),
2,187,000 poses, 1,523,956 clear. Result **z_lo = -0.569 m, z_hi = 0.770 m** (grid resolution 5 deg; z_lo is the lowest clear lamp point). `height = clip((z_mean - z_lo) / (z_hi - z_lo), 0, 1)`.
Report-only: FineDance-train p1 / p99 of z_mean next to these bounds. Nothing else in the rules changes (section 3.2's 0.11 m is superseded; Z_LO in `controls_lib.py` = -0.569).
