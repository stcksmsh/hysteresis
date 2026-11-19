# Sync audit A (A1 synthetic probe, A4 time-origin review): report (WO54, BRAIN_SPEC 7.86) — 2026-11-19

Report only: no pipeline code was changed (the probe imports and calls it). Rules: `docs/SYNCAUDIT_RULES_A.md`. Code: `scripts/body/syncaudit_{lib,a,lamppix}.py`,
`test_syncaudit_a.py` (7 tests, synthetic). Data: `/secondary/hyst-data/body/syncaudit/a/` (`chain.json`, `sine.json`, `final.json`, `lamppix.json`, `syn/`,
`render_root/`, `clips_src/`). **Offset sign: positive = movement LATER than its music.** Threshold 50 ms.

## Headline

Stages from the loaded file to the 30 Hz window rows add **0 ms**. **The spinal layer adds +80 to +86 ms and the limiter + servo another +100 to +200 ms, so the
realised arm (`controls/q50`, and everything cut from it: lamp array, joint CSV, rendered video) trails the music by about +180 to +290 ms, depending on joint and amplitude.**
The raw-joint arrays (WO47 raw, WO53 B) carry 0 ms. Audio, mux, container, frame clock and the shifted-foil construction are exact. This is a latency of the simulated body, not a loader error.

## A1: offset per stage (synthetic click / impulse probe through the real code)

Method: clicks (5 ms burst, sample-exact) at 3.0 s, every 0.5 s to 8.0 s (dense block, matched-filter lag), then isolated clicks 1.7-2.4 s apart (per-impulse centroids);
motion = FineDance-format (T,315) at 30 fps with a 0.30 s raised-cosine, 70 deg impulse on each click (families arm / torso / pelvis / feet / mixed), plus a 20 deg sinusoid at
0.5, 1, 2 Hz (linear-regime delay by demodulation). 30 s songs (window 0) and a 50 s song (window 1). Real functions: `t0_lib.load_rot`, `t0_chain.stage1/target`, `controls_run.sim_file`
(the replication of its internal arrays is asserted equal to its q50, max 1e-3 deg), `mismatch_build.write_work/cmd_assemble`, `retarget_render.sh`, `ffmpeg`. V1 = arm-as-arm, V2 = arm-as-whole-body
(V2 does not read the arm joints: the `arm` family gives no V2 response, expected).

| # | stage (array / file) | rate | offset ms (sign +, later) | constant? | evidence |
|---|---|---|---|---|---|
| 1a | loaded audio (ffmpeg decode of the wav) | 44.1 kHz | 0.000 (sd 0.000, n 20-30) | yes | `chain.json` |
| 1b | loaded motion (family joints' angle, 30 fps pulses) | 30 Hz | -0.4 (sd 1.2) | yes | 30 fps sampling of a centred bump |
| 2-3 | `human_angles`, `referenced`, `to_commands` (V1 arm, torso, pelvis; V2 torso, pelvis) | 30 Hz | 0.0 to -0.6 (sd <= 1.4) | yes | |
| 4 | low-pass (`lowpass_cutoff.lowpass`, zero phase 2.5 / 5.75 Hz) | 30 Hz | 0.0 (train lag -1.2..+1.5, sd <= 1) | yes | filtfilt |
| 5 | cubic spline to 100 Hz + guard (`t0_chain.target`) | 100 Hz | 0.0 | yes | |
| 6 | window rows + 1.5 s pre-roll, guard (`controls_run.sim_file`) | 100 Hz | 0.0 | yes | row i = 20 w + (i-150)/100 s |
| 7 | spinal layer `motornet.spinal` (3 Hz, zeta 0.7) | 100 Hz | **+80 (0.5 Hz), +81 (1 Hz), +86 (2 Hz)** sine; pulses +84.5 (sd 0.0) | yes (linear delay) | `sine.json`, `chain.json` |
| 8 | limiter + servo = `controls/q50` row k = 20 w + 0.02 k | 50 Hz | **V1 arm: +177 (0.5 Hz), +186 (1 Hz), ~+291 (2 Hz, amplitude 56 %); V1 base yaw: +284, +240, +191; V2 tilt: ~+236, ~+248, 2 Hz attenuated to 20 %**; 70 deg pulses: matched-filter +222 to +382, per-impulse centroids +137 to +283 | varies with joint, frequency, amplitude (limiter saturates) | `sine.json`, `chain.json` |
| 9 | lamp point = row-wise FK of q50 (`m3f_report.fk_points`) | 50 Hz | 0 added by construction (same rows, same times); a sinusoid's fundamental through the FK is distorted, the measured values in `sine.json` for this stage are not delays | by code | code reading |
| 10 | raw FK joint speeds of the loaded rotations (`beatv_lib.fk`; wrists, feet, ankles, head, pelvis) | 30 Hz | +0.3 (sd 0.6-0.7) | yes | no pipeline stage in between |
| 11 | joint CSV (`write_work`) | 50 Hz | 0: time column = k/50 exactly (max err 0.0 s), rows = q50 slice (max err 5e-7 deg) | yes | `final.json` |
| 12 | rendered frames (`ensemble_preview` 60 fps table, `record_ensemble.cjs` frame i = score time i/30, x264) | 30 fps | lamp disc pixel track vs FK lamp, P04: **-2.3 ms** (rms 2.1 px, 300 of 300 frames). P01-P03: inconclusive (disc detected in 54 / 47 / 0 % of frames) | yes (code: `draw(t)` linear interpolation, no delay, `ensemble.html:85-96`, `ensemble_preview.rs:606-620`, `record_ensemble.cjs:42`) | `lamppix.json` |
| 13 | final clip, audio track (AAC, decoded) | 44.1 kHz | click centroids vs expected: 0.000 to 0.003 ms (sd <= 0.003 ms) both halves, 5 items; pre-encode wav 0.000 | yes | `final.json` |
| 13 | final clip container | - | video and audio `start_time` 0.000000, 645 frames, 21.5 s both; AAC priming already compensated | yes | ffprobe |
| 14 | shifted foil (+3, -3, +4, -4 s) | sample | measured shift minus stated = 0.0 samples (3 matched clicks per item) | yes | `final.json` |
| 14 | different-song foil start | - | foil clicks at the stated start (5 of 5, P05) | yes | |

**Delay constant or varying:** stages 1-6, 9 (by code), 10-14 constant 0. Stage 7 constant (a linear delay of a second-order low-pass, +80 to +86 ms at 0.5-2 Hz). Stage 8 varies with
joint (base yaw +191 to +284, shoulder +177 to +291), with frequency and with amplitude (the rate limiter flattens large fast pulses). Sign everywhere: movement later.

## Findings

FINDING 1: stage 7 spinal layer / `scripts/body/motornet.py:101-112` (SPINAL_F 3 Hz, zeta 0.7; called at `controls_run.py:55` and `t0_chain.py` `gate_window`) / **+80 to +86 ms** / positive (movement later) / sine and pulse probe, sd 0 across impulses. Above the 50 ms threshold on its own.

FINDING 2: stage 8 limiter + servo / `retarget_limiter.simulate_goals` (`retarget_limiter.py:45-70`, step 19-32) with the v2p MuJoCo body / total q50 delay vs the input **about +180 to +290 ms** (+100 to +200 ms beyond the spinal layer) / positive / sine probe at 0.5, 1, 2 Hz and 70 deg pulses; varies with joint and amplitude. Every array cut from `controls/q50` (lamp, `lamp` speed of WO52, CSV, rendered video, the mismatch clips' movement) carries it.

FINDING 3: inconsistency between two code paths that should agree / raw-joint measures (`beatv_raw.py`, `rawrhythm.py`: 0 ms) vs lamp measures (`rhythm_events.py` on `controls/q50`: +180 to +290 ms) / difference about 0.2-0.3 s / the two sets of timing results (beat phase, V3 offsets, event timing) are not on the same clock. Period-ratio results (shift-invariant) are not affected by a constant delay; phase, offset, lag and event-timing results are.

FINDING 4: mismatch clips / `mismatch_build.write_work` (csv from q50) / in every clip the real half's movement trails its own music by about +0.2-0.3 s (stages 7-8 above; mux, container and foil construction add 0) / positive. The 2-6 s shifts are much larger than this lag; whether it matters for the preference is for the overseer (no verdict here).

FINDING 5 (note, not an offset): `crates/hyst-previz/src/ensemble.html:282-290` draws a faint hint of the hand path **1.5 s ahead** and a 4 s trail (`:258-262`) in every clip; both are drawing features, the arm itself is drawn exactly at t.

No finding: stages 1-6 (loading, retarget, referenced, low-pass, spline, guard, window cut), 9 (by construction), 10-14 (CSV, page and capture clock, x264 halves, concat, AAC mux, container start times, foil construction). The mux needs no priming compensation by hand: ffmpeg writes the offset, the decoded click lands at 0 ms.

## A4: time origins (file:line), who measured

| where | origin or offset set / assumed | handles | measured | doubt |
|---|---|---|---|---|
| `t0_run.py` `cmd_catalogue` (t30 = motion frames), `one` (`n = min(n_tokens(t30), lane frames // 50)`) | motion frame 0 = audio sample 0; no offset field in any dataset loader; the shorter of motion and music decides the length | none | A1 (FineDance format, synthetic, aligned by construction); real alignment A2/A3 | the loader cannot detect a motion/audio offset; Motorica readme warns of "audio/motion synchronisation issues" |
| `t0_aioz.py`, `t0_phantom.py` (BVH 120 -> 30 fps, `motorica_rot`: every (fps_in/30)-th frame from frame 0), `t0_phantom_run.py` | same assumption; decimation starts at frame 0 so no sub-frame shift is added | none | reading only (not probed: loader takes the original pkl / BVH files) | AIOZ clip audio cut from video segments, PhantomDance music file start: not verifiable here; A2/A3 |
| `t0_lib.py:11,57-70` (FPS 30, WIN_S 20, PRE_S 1.5, `n_windows`, `n_tokens`, `t100`) | window w = frames 600 w..600 (w+1), song time 20 w; 100 Hz rows `t100 = (T-1)/30 x 100 + 1` | exact | checked by A1 (stage 5-6: 0 ms) | none |
| `t0_chain.py:17-33` (`CUT`, `stage1`, `target`) | cubic spline on [0, (T-1)/30], row k = k/100 s; zero-phase low-pass | exact, no delay | checked by A1 | none |
| `t0_chain.py:35-45` `window_rows`, `MARGIN` | 1.5 s pre-roll, margin slice, yaw/roll shifted to the window start | exact | checked by A1 (gate path; `sim_file` path replicated) | `window_rows` and `sim_file` are two code paths for the same window; the same time convention, only gating uses `window_rows` |
| `controls_run.py:21,49-55` (`PRE 150`, `WIN_ROWS 2000`, `a = w x 2000`, pre-roll, shift) | window row a = song time 20 w; first window repeats row 0 as pre-roll | exact | checked by A1 (replication equal to stored q50) | none |
| `retarget_run.py:57` `patch_gates`: `M.WARM_S = 1.5` | the "10 s warm-up" (`motornet.py:17`) is **1.5 s** in this path; `retarget_run.py:242` sets 10.0 for the old reference path | warm-up trimmed by `nw`, q50 row 0 = window start | checked by A1 (q50 row k = 20 w + 0.02 k) | other paths using 10 s default would differ; not used for the mismatch clips |
| `motornet.py:101-112` spinal; `retarget_limiter.py:19-70`; `make_arm_v2p.py:28-35` servo | physical latency of the simulated body | **+80 to +290 ms** | checked by A1 | FINDINGS 1-2 |
| `beatv_raw.py:20-31` (librosa, SR 22050, hop 441; `beat_track units=time`), `:98` (hop 735 at 30 Hz) | frame i = i x hop / sr, `onset_strength` centre=True; the onset difference adds at most one hop | no offset added | reading only | up to about one hop (20-33 ms) of onset-envelope lag is conventional, below threshold; not measured |
| `rhythm_events.py` / `RHYTHM_EVENTS_RULES.md` section 0 | window w = song time [20 w, 20 w + 20) s, ear frame t centred at t/100 s | exact | reading only | ear 2048-sample window looks 23 ms ahead (stated in `t0_lib.TOKEN_LOOKAHEAD_S`) |
| `mismatch_build.py:241-247` `write_work` (slice `a = window_offset x 50`, 501 rows; m4a `-ss excerpt_start -t 10`) | movement excerpt and music excerpt share the same start in the song | exact | checked by A1 (items P01-P05: csv rows = q50 slice, clicks 0 ms) | none |
| `mismatch_build.py` `compose_audio` / `cmd_assemble` (halves, black 1.5 s, concat copy, AAC) | audio sample 0 = video frame 0; second half at 11.5 s | exact | checked by A1 (container starts 0, clicks 0 ms, 645 frames) | none |
| `crates/hyst-previz/examples/ensemble_preview.rs:605-620` | duration = (rows-1)/hz, 60 fps table, linear interpolation | no delay | checked by A1 (P04 -2.3 ms) and code | P01-P03 pixel tracks inconclusive |
| `scripts/author/record_ensemble.cjs:35-42` | frame i drawn at score time `start + i / 30`, mux audio `-ss start -t duration` (start 0) | exact | checked by A1 (clip start 0) | none |
| `crates/hyst-previz/src/ensemble.html:84-96,258-290` | `scoreTime = audio - delay` (delay 0 in the recorder), trail 4 s back, hint 1.5 s ahead | none | reading only | FINDING 5 |
| `retarget_render.sh` | `HYST_FAST=1`, 1280x720; page patch `retarget_page.py` only moves the floor/pillar | none | checked by A1 | none |

## Corrected stage list (real order)

dataset motion -> `human_angles` (V1/V2, un-referenced) -> `referenced` at frame 0 -> `to_commands` (30 fps) -> low-pass (zero phase) -> cubic spline to 100 Hz on the whole sequence -> `guard` (whole
sequence, `target`) -> **at window time (`controls_run.sim_file`)** per window: pre-roll 150 rows + 2001 rows, yaw/roll shift to the window start, `guard`, **spinal layer, then limiter/servo** (`simulate_goals`, warm-up
trimmed, 50 Hz) -> `controls/q50` (1001 rows) -> `write_work`: 10 s slice (501 rows) -> `arm_sim.csv_text` -> `ensemble_preview --joint-csv` (60 fps table, linear) -> `retarget_page` -> `record_ensemble.cjs` (30 fps frames, x264 + the m4a)
-> `mismatch_build.cmd_assemble`: x264 half re-encode, black gap, concat copy, composed wav as AAC. Differences from the work order's list: low-pass comes before the spline; there is no separate 10 s warm-up trim (it is 1.5 s
pre-roll); the spinal layer runs before the limiter, not as a separate "when used" option; the joint-CSV step is a 10 s slice of q50, not the whole window.

## Not measured, and why (FOR USER)

1. PhantomDance, Motorica and AIOZ loaders were reviewed (A4) but not probed: their real inputs are pkl / BVH files read by `t0_phantom.py` / `t0_aioz.py` and building a faithful synthetic file would mean new loader code; A2/A3 cover their real alignment.
2. Pixel-track delay is clean only for P04 (pelvis, V2); the disc-colour mask lost the disc on P01-P03. The frame-difference-energy cross-correlation of the first pass (+4 to +68 ms, unstable between halves, the first half contaminated by the black transition) was discarded as a measure of different quantities.
3. The mixed variant is measured per family but the cross-family overlap (clicks 0.5 s apart) makes the non-arm families noisy; single-family runs are the reference.
4. The lamp stage is reported "0 by construction"; a direct sinusoid measurement through the nonlinear FK is not a delay measure.
5. Whether a pure +0.2-0.3 s lag can explain the 8 of 8 shifted-foil picks is not tested here.
