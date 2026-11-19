# WO54 sync audit, agent 2 (A2 AIST++ known-aligned reference, A3 per-song lag diagnostic): rules (written and pushed before any result)

Report only. No pipeline code is changed, nothing is fixed, no verdict beyond the numbers and the 7.86 outcome rule. Branch
`body-syncaudit-b`, cores 14-19, out `/secondary/hyst-data/body/syncaudit/b/`. Kosta's mismatch `answers.csv` is never opened.

## Definitions (used everywhere)

- **Offset / lag sign:** positive = movement LATER than its music (movement event time minus music event time). For a cross-correlation
  of motion signal `m(t)` against music envelope `e(t)`: `c(L) = corr_t( m(t), e(t - L) )`; a peak at `L = +0.2 s` means the motion
  follows the music by 0.2 s.
- **Finding threshold:** |offset| > 50 ms at any stage, any dataset loader whose motion and audio starts differ, any inconsistency between two
  code paths that should agree. For A2, a stage that moves the peak lag by more than 20 ms relative to the raw keypoints is reported.
- **Resolution:** all arrays at 50 Hz (q50, lamp, raw speeds) or 100 Hz (ear envelope) or finer; the lag grid is the 50 Hz sample grid
  (20 ms), sub-sample by parabolic interpolation of the peak (three points). Reported lags are rounded to 1 ms but their resolution is
  about 5 ms; differences below 10 ms are not claimed.
- **Time conventions taken as the existing measures use them (not verified here, that is A4):** window `w` of a song starts at song time
  `20 w` s; sample `i` of a 50 Hz window array is at `20 w + i/50` s; raw joint arrays (50 Hz, from `rawrhythm.speeds50`) start at song
  time 0; ear / `rms` columns (100 Hz) frame `j` is at `j/100` s. If one of these is off by more than a frame, A3 shows it as a lag,
  which is the point.

## A3: per-song lag diagnostic

Datasets: finedance, aioz, phantom, motorica (WO52/WO53 windows; V1 and V2 versions reported separately, mirror copies not used).

- **Motion signals:** lamp speed (`controls/q50/<ds>/<key>.npz` `lamp`, 50 Hz, norm of the gradient, as `rhythm_events.speeds`);
  raw joint speeds of WO53 B (`rawrhythm.speeds50`, world frame: lwr, rwr, lft, rft, pel, head and `mean`; the `mean` is the main raw signal).
  Per-joint results are given for the pooled lag only.
- **Music signals:** onset envelope = `ear[:, 40]` (the WO52 column, the stored z-scored value de-normalised exactly as
  `rhythm_events.music_events` does, then 100 Hz -> 50 Hz by block mean of 2): **main**; librosa onset strength (`hop 441`, sr 22050,
  half-wave rectified spectral flux as `librosa.onset.onset_strength`) is the secondary and is run only if the source audio is local and
  readable for at least 80 % of songs (else FOR USER). Energy envelope = `rms` of `pulse2/songs/<song>.npz` (100 Hz), low-passed by a
  0.5 s moving mean, then 50 Hz. Main motion signal for headlines: lamp (retargeted) and raw `mean`; main music signal: ear col 40.
- **Per-song curve:** for each kept 20 s window of the song and version, remove a 2 s moving mean from motion (window) and envelope (whole
  song, before slicing); motion core `t` in [3, 17] s of the window; `c(L)` for `L` in [-3, +3] s every 20 ms, Pearson over the core
  samples; the song's curve is the mean over its windows (equal weight per window). Windows with a constant core are dropped.
- **Peak:** the maximum of the song's curve within |L| <= 1.5 s, parabolic sub-sample; height = curve value there.
- **Chance (20 draws per song, seed 54203):** (i) the same motion windows against the envelope of another song of similar tempo (librosa
  tempo within 5 %, any dataset, same absolute time range, song long enough; fewer than 20 candidates: all, with replacement drawn by
  seed), (ii) the song's own envelope circularly shifted by a random 2-6 s (uniform, sign random). Per draw the same peak lag and
  height are taken.
- **Reported per dataset, signal, version:** quantiles (5, 25, 50, 75, 95) of the peak lag, a histogram table (0.2 s bins, -1.5..1.5),
  share of songs with |peak lag| <= 100 ms, median peak height versus the median height of each chance family, and the lag of the pooled
  (mean over songs) curve with its bootstrap by song (2,000, seed 54204; 95 % percentile interval). Chance families' lag distributions
  are shown next to the real one so that a peak "lag" that also appears at chance is visible.
- **Also (consistency check not in the work order, cheap):** the same cross-correlation between the lamp speed and the raw `mean` speed
  of the same windows (no music involved). A lag there is a pipeline offset by itself.
- **Shifted-foil reading:** for the 13 shifted clips of `mismatch/material_key.json` (10 pairs and 3 repeats): the movement's own lamp
  speed (its window, version) over the excerpt `[excerpt_start_s, +10)` against (a) the real half's music envelope and (b) the foil half's
  envelope (foil start = `foil.excerpt_start_s`, foil offset = `foil.offset_s`), `c(0)` for each, plus `c(L)` with `L` swept -6..+6 s
  every 20 ms, the lag of the best peak within |L| <= 1.5 s for the real half. Reported: `c_real(0)`, `c_foil(0)`, and the value of the
  real-music curve at `L = foil.offset_s` (the same quantity as `c_foil(0)`, shown as a check). Kosta's answers are not opened. The
  excerpt uses the 10 s core of the movement as the clip did; the 2 s mean removal is applied to the whole-song envelope before cutting.

## A2: AIST++ known-aligned reference

- **Sequences:** the WO47 set if the file list is recoverable from `aist/bas/per_sequence.csv`; else 60 drawn by seed 54201, spread over the 10 genres
  (6 per genre where available). `ignore_list` sequences excluded.
- **Raw keypoints** (`keypoints3d_optim` main, `keypoints3d` raw as a second source), 60 fps, music `aist/music/<mID>.wav`
  (mono 22050). Motion signal: mean joint speed (as `aist_bas.speed`); music signal: librosa onset strength at hop 441 (50 Hz) and a
  low-passed RMS. Cross-correlation as in A3 (2 s mean removal, +-3 s, 20 ms grid, motion core is the whole sequence minus 3 s each side,
  peak within +-1.5 s). Chance: music of another sequence of the same genre (20 draws, seed 54203), same peak statistics.
- **BAS** at sigma 0.1 s (WO47 main) and 0.05 s, motion beats from the kinematic minima as `beatv_lib.kin_beats` (the WO47 recipe), music beats
  from librosa as `aist_bas.music_beats`, chance as `beatv_lib.bas_chance`.
- **Stages:** raw keypoints, then each of our stages that accepts AIST++ keypoints with the unchanged code: first an inventory by reading
  `retarget*.py`, `controls_*.py` and the servo / v2p code. A stage that cannot take AIST++ input (format or joint-set limit) is named in the
  report with the reason and the closest stage that can be run is used; no stage code is edited, and an adapter written for the audit (new
  file `scripts/body/syncaudit_b.py`) only converts the array format, never retimes. If no pipeline stage can be run, the report says so and
  A2 is limited to the raw-keypoint measures plus the stages we can reproduce by their definition (stated per stage: the 50 Hz spline,
  a low-pass of the same cut-off); those are marked "re-implemented, not pipeline code".
- **Report:** per stage, lag distribution (quantiles, share |lag| <= 100 ms), BAS, with a bootstrap by sequence (2,000, seed 54202), and the
  list of stages whose median peak lag differs from the raw keypoints by more than 20 ms.

## Tests

`scripts/body/test_syncaudit_b.py`: a known lag is recovered on synthetic signals within 20 ms (both signs; sign convention as above),
2 s mean removal does not move the peak, chance shifting changes the lag but not the sign convention, the foil reading finds the stated
offset on a synthetic song.

## FOR USER (defaults taken so far)

1. Main music signal is ear col 40, main motion signals lamp and raw `mean`.
2. Per-song curve is the mean over windows with a [3, 17] s core; the peak search is +-1.5 s.
3. The time conventions above are taken from the existing measures, not checked (A4 does that).
