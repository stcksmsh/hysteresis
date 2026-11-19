# Sync audit, agent 1 (A1 synthetic probe, A4 time-origin review): rules (WO54, BRAIN_SPEC 7.86) — written and pushed before any result

Report only. No pipeline code is changed; the probe only imports and calls it. One arm. Branch `body-syncaudit-a`; out
`/secondary/hyst-data/body/syncaudit/a/`; code `scripts/body/syncaudit_a.py` (+ `test_syncaudit_a.py`); log
`docs/NIGHT_LOG_body-syncaudit-a.md`; report `docs/SYNCAUDIT_REPORT_A.md`. Defaults are marked **(default)**.

## 1. Conventions (used everywhere)

- **Offset sign: positive = movement LATER than its music**: offset = movement event time minus music event time, in ms.
- **Finding threshold:** |offset| > 50 ms at any stage, a dataset loader whose motion and audio starts differ, or an inconsistency
  between two code paths that should agree. A latency below the threshold is still reported as a number.
- **Resolution:** arrays at 100 Hz or finer are measured to sub-sample by the centroid of the excursion (below) and, as a second
  method, by a parabola through the three samples around the excursion peak; the final video at frame resolution (30 fps, sub-frame by
  the same parabola on the per-frame trace) and the final audio at sample resolution (44.1 kHz).
- **Constant vs varying:** for each stage the per-impulse offsets are listed in the data folder; "constant" = spread (sd over impulses)
  below 5 ms **(default)** and no trend over the 30 s (slope below 1 ms per 10 s); otherwise "varies" and the pattern is stated.

## 2. Synthetic input

- **Audio:** mono, 44.1 kHz, 30 s (window 0 path) and 50 s (window 1 path, excerpt not at the sequence start), written as 16-bit PCM
  wav (the container FineDance's `music_wav` uses; checked with ffprobe on a real file before the build). Clicks (a 5 ms Hann-windowed
  1 kHz burst, peak 0.8, centre exactly on the click time) at 3.0 s and every 0.5 s to the end minus 2 s, plus 6 irregular clicks
  (e.g. 7.23, 11.61, 14.07, 19.37, 23.91, 27.45 s; for the 50 s file also 33.13, 41.77, 46.29) and nothing else. First click is at 3.0 s, never at 0.
- **Motion, FineDance format:** (T, 315) float32 at 30 fps, columns 0:3 root translation (zeros), then 52 x 6D rotations (identity
  = rows [1,0,0,0,1,0]) as `retarget.load_rotations` / `t0_lib.rot_from_array` read them. T = 900 (30 s) and 1500 (50 s). Joint 0 is
  the pelvis. Impulse = a raised-cosine bump of 0.30 s total length **(default)**, centred exactly on the click time (bump peak at the
  click; a 30 fps sample falls on the centre only when click time x 30 is an integer, otherwise the bump is sampled off-centre; both
  occur and are reported), peak rotation 70 degrees **(default)**, one rotation per impulse. Variants (one synthetic sequence each):
  - `arm`: right arm chain, shoulder 17 about z, elbow 19 about z, wrist 21 about z (drives V1 and V2 channels 1-3);
  - `torso`: joint 9 and 12 yaw about y (drives the base channel of V1 and the V2 torso angles);
  - `pelvis`: joint 0 yaw about y;
  - `mixed`: the three families on interleaved clicks (arm, torso, pelvis in turn);
  - `feet`: joints 7, 8, 10, 11 (not read by the arm pipeline; reported only in the raw-joint arrays, see 4).
- **Other datasets:** PhantomDance and Motorica enter the mismatch pipeline as stored T0 sequences (`t0_phantom/seq`,
  `t0_motorica/seq`, 100 Hz target rows from their own loaders). The probe reads their loader code (A4) and runs the same synthetic
  impulses through the shared stage code (`t0_chain.process` equivalents) with the dataset's own fps and file format where a loader can be fed a synthetic
  file without editing it; where it cannot, the dataset is reported "loader reviewed, not probed" with the reason. AIOZ only if cheap.

## 3. Stages and definitions (the real order, traced from code; corrected in the report if the probe disagrees)

Real chain of a mismatch clip: dataset motion (30 fps, window start = 20 w s of the sequence) -> `retarget.human_angles` (V1/V2) ->
`referenced` -> `to_commands` (30 fps rows) -> `lowpass_cutoff.lowpass` (zero phase, 2.5 / 5.75 Hz) -> cubic spline to 100 Hz on
[0, (T-1)/30] (`t0_chain.target`) -> `guard` -> `controls_run.sim_file`: 1.5 s pre-roll + 20 s window rows -> `guard` -> `motornet.spinal`
(3 Hz second-order layer) -> `retarget_limiter.simulate_goals` (limiter, servo, MuJoCo 5 x 2 ms substeps, warm-up trimmed, 50 Hz rows) -> `controls/q50`
(1001 rows) -> `mismatch_build.write_work` (10 s slice at `window_offset_s`, joint CSV) -> `ensemble_preview --joint-csv` (v2p body, lamp) ->
`retarget_page` -> `record_ensemble.cjs` (30 fps frames) -> ffmpeg x264 halves + concat -> mux of the composed wav (`compose_audio`) as AAC.

Per stage the measured quantity is the click-vs-impulse offset of the stage's output array, using the channel with the largest excursion.
**Impulse time of an array** = centroid of |x - median(x)| over the window click +- 0.75 s (weights below 10 % of the window's peak
zeroed); second method = parabolic peak time. Stages read (all in the data folder with per-impulse values):
1. loaded motion (the (T,315) array: bump centre by the same centroid on the rotation angle) and loaded audio (click centroid of |audio|);
2. `human_angles` output (30 fps); 3. after `referenced` / `to_commands`; 4. after low-pass; 5. after spline to 100 Hz (`target`);
6. after `guard` (window rows); 7. after the window cut (`pre-roll + rows`, row index to time as `sim_file` implies: row k of the 2001 shown rows = 20 w + k/100 s);
8. after `spinal`; 9. after the limiter/servo (`q50`, row k = k x 0.02 s of the window); 10. the lamp array (`lamp`, FK of q50) the WO47/WO52/WO53 measures read
(speed excursion) and the raw FK joint arrays of WO53 B (`beatv_raw` approximate FK, wrists, ankles, pelvis, head, from the loaded rotations);
11. the joint CSV slice (time column and rows); 12. rendered frames: lamp head pixel position per frame vs the lamp array's projection (cross-correlation lag at 30 fps, sub-frame parabola);
13. the final clip: audio decoded from the mp4 (click sample positions) against the video's impulse frame; container `start_time` of both streams (ffprobe) reported next to it;
14. shifted-foil construction: the stated shift against the foil music's click positions in the composed wav (sample exact).
Each stage reports: array or file, rate, offset mean / sd / min / max over impulses (ms), constant or varying, sign.

## 4. Time-origin review (A4)

A table `file:line | origin or offset set | what it handles | measured by A1 / A2 / reading only | doubt`, covering the dataset loaders (FineDance,
AIOZ, PhantomDance, Motorica; motion start vs audio start, trimming, fps, frame vs sample), `t0_run`/`t0_chain`/`t0_lib` windows and the 1.5 s pre-roll, the
10 s warm-up (`motornet.WARM_S`), `controls_run` window rows (WIN_ROWS 2000, PRE 150), `grammar_data`/`rhythm_events` window times, librosa beats (`beatv_raw.librosa_beats`:
frame-to-time convention and hop 441 at 22.05 kHz), `mismatch_build` excerpt and foil starts, the mux (AAC priming, concat, `-t`), `record_ensemble.cjs` capture clock, ffmpeg start times.
Mark each "checked by A1" or "reading only"; things A2 covers are marked "A2".

## FOR USER (defaults taken)

1. Impulse = 0.30 s raised-cosine bump, 70 degrees, centred on the click; times from the centroid (parabolic peak second).
2. 30 s and 50 s synthetic songs; clicks at 3.0 s, every 0.5 s, plus 6 (9) irregular ones.
3. A stage is "constant" below 5 ms sd and 1 ms / 10 s slope.
4. PhantomDance and Motorica probed only where their loader accepts a synthetic file unedited; otherwise reviewed, not probed.
