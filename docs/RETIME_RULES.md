# Re-timing rules (WO55 part A, BRAIN_SPEC 7.87) — written and pushed before any re-timed result

Report only. No pipeline code that produces `controls/q50` or `metric/q50` is changed, nothing is re-simulated, nothing is trained, A's
data are not rebuilt. One arm. Helper `scripts/body/retime.py` (tested in `test_retime.py`); analysis wrapper `scripts/body/retime_a.py`
(tests in `test_retime_a.py`). Out: `/secondary/hyst-data/body/retime/a/` (original result files are never overwritten). Defaults are
marked **(default)** and listed under FOR USER.

## 1. Constants and sign

- **L(V1) = 0.35 s, L(V2) = 0.28 s**, one constant per variant (7.87 Q1, Q2). The variant is read from the key suffix (`__V1`, `__V2`;
  mirror copies `__V1m` / `__V2m` take their variant's L).
- **Sign:** positive L = the movement is LATER than its music. The realised arm trails its music by L, so every array cut from the
  realised arm is **read L later**: sample i of the re-timed array is sample i + round(L x rate) of the original, placed at the original
  sample i's music time. In event-time terms, a movement event at music time t on the original clock is at t - L on the re-timed clock.
- At 50 Hz: round(17.5) = 18 samples (0.36 s) for V1, 14 samples (0.28 s) for V2 (Python rounding; the residual 0.01 s is inside the
  +-50 ms residual that 7.87 records and does not remove).
- Residual +-50 ms (lag varies with joint, frequency and amplitude, `SYNCAUDIT_REPORT_A.md`) is recorded, not removed.

## 2. Which arrays are shifted and which are not

- **Shifted (every array cut from the realised arm):** the lamp position and lamp speed, the realised joint angles `q50` and their
  speeds (`controls/q50` windows and the WO46 whole-sequence `metric/q50`, which is the same simulation chain **(default: the same L)**),
  and everything derived from them: kinematic beats (lamp-speed minima), the WO52 response times (hold, change, burst), the per-token
  controls of A (vigour, height, sharpness, pause).
- **Not shifted:** raw human joint arrays (before retargeting: `beatv_raw.py`, `rawrhythm.py` raw signals, 0 ms in the audit), music
  features (onset envelope, ear lanes, low-band energy), librosa beats and the project grid, pulse v2, cortex surprisal, music events.

## 3. Window handling

- A re-timed array is `x[round(L x rate):]`: its first sample is at the original window start, it covers [start, end - L) of music time,
  and **the last L seconds of a 20 s window (or of a whole sequence) are dropped, never padded**.
- Analysis windows that would reach into the dropped tail are left out, and the original side of each comparison is recomputed on the
  same reduced set (so original vs re-timed compare the same rows):
  - WO52/53 rhythm rows: the 3 s window starting at 17 s and the 4 s window starting at 16 s of each 20 s window (one row of 18 / 17).
  - WO47 BAS: music beats after the shortened duration are not scored (the code's own `music < duration` rule).
- **Token-level responses and controls are not re-cut (default):** a token keeps its 0.5 s of movement and its controls; only its
  music time moves by -L. Re-cutting tokens on a shifted grid would need A's data rebuilt (not allowed here). WO52 segment spans move
  with the tokens: span (a, b) -> (a - L, b - L).

## 4. Period-ratio results

A constant time shift does not change the period of a signal, so period-ratio results (WO52/53 rhythm bins, cluster shares, C) are
unchanged by it in expectation. They are not identical row by row: each 3 s or 4 s analysis window now contains the movement of
[s + L, s + L + W) of the original window, so per-window periods and strengths change somewhat while the beat period of the row stays.
Checked in step 2c: original vs re-timed on the same reduced row set; any difference is reported.

## 5. Analyses (each = the original code path with the lamp side shifted by L; same seeds)

- **(a) WO47** (`beatv_real.py`, `beatv_v3curve.py`, `BEATV_RULES.md` sections 1-2): BAS of the re-timed lamp-speed minima against
  librosa beats and the project grid, music-beat sum (main) and kinematic-beat sum, shifted-beat chance with the same per-file seed
  (47104 + crc32) and draw order, mean over song groups, bootstrap by song group (2,000, seed 47101); V1 and V2, per dataset.
  V3 realised table (FineDance, lamp speed and summed |joint velocity|, V1/V2, against the 50 Hz onset envelope, +-50 samples, 200
  circular shifts, the per-file seed 47103 + n consumed in the original order, raw scan first): best offset quantiles, share within
  50 ms, max correlation, z; plus a bootstrap by song (2,000, seed 47101) of the median best offset **(added; the original reports no
  interval)**. Expected: the best offset moves by about +L (k > 0 = music after motion).
- **(b) WO52 event locks** (`rhythm_events.py` analysis B on the stored `tokens_<ds>.npz` with `t` and `hold_t` moved by -L per copy;
  `events.json` unchanged): every response x event, peak excess, its lag, its interval, max-statistic p, mean excess over +-0.3 s; same
  circular shifts (seed 52102, same per-sequence streams), bootstrap by song group (2,000, seed 52101); same thresholds D and vigour sd
  (they do not depend on time).
- **(c) WO53 B lamp column** (`rawrhythm.py` analyse on the WO52 rows with the lamp's period and strength recomputed from the re-timed
  lamp speed; the reduced row set of section 3 for both the original and the re-timed run): lamp bin shares, cluster share and excess
  over both chances with intervals (seed 53201), C; raw vs lamp same-bin share per window.
- **Headline per analysis (no verdict):** re-timed point value, original point value with its 95 % interval, and the distance by which
  the re-timed value lies outside that interval (0 when inside).

## 6. Token-level effect (7.87 Q4, report only)

- Token length 0.5 s; **L in tokens = 0.70 (V1), 0.56 (V2)**; nearest whole token = 1 for both (residual -0.15 s V1, -0.22 s V2).
- Data: A's windows (`grammar/win_<ds>.npz`, V1 and V2 copies, mirrors left out as WO52 **(default)**), segments of consecutive kept
  windows as WO52; token k of window w covers movement [20 w + 0.5 k, + 0.5) s.
- Controls: vigour (ctl 0), height (ctl 1), sharpness (ctl 10, only where `sharp_ok` = 1), pause onset (ctl 14 >= 0.2 and the previous
  token < 0.2, WO52's hold rule on the token grid; binary).
- Alignments: **original** (token at its own time), **re-timed** (token placed at its time - L), and, for information, **whole-token**
  (time - 0.5 s).
- **Event-locked control at lag 0:** for each WO52 music event e (onset, dropout_on, dropout_end, novelty, cortex_L2, cortex_total)
  inside a segment's span (+-1.1 s margin as WO52), the control of the token whose (aligned) interval covers e; mean over events
  (pause onset: rate per token); chance = the same with event times shifted circularly within the span, 200 shifts, seed 52102; excess =
  observed - chance; bootstrap by song group (2,000, seed 52101).
- **Correlation with ear energy features:** low-band energy (as WO52's dropout L: mean power of mel bands below 200 Hz, 10 Hz) and
  onset strength (ear column 40, raw, 10 Hz); per token the feature's mean over the token's aligned interval shifted by lag lambda,
  lambda = -1.0 .. +1.0 s in 0.1 s steps (lambda > 0 = music after the token); both series demeaned per sequence copy **(default:
  within-sequence correlation)**; pooled Pearson r from per-group sums, bootstrap by song group (2,000, seed 52101); peak lag = lag of
  max |r|. Reported: r at every lag, peak lag and its interval, original vs re-timed, and whether the peak lag moves by L. By construction
  r_retimed(lambda) = r_original(lambda - L) up to the token-interval sampling, so a move of about +L is expected (stated before running).

## FOR USER (defaults taken)

1. `metric/q50` (WO47 whole sequences) re-timed with the same L as `controls/q50` (same simulation chain; L was measured on the dataset
   windows).
2. Rhythm rows reaching into the dropped tail are left out of both sides; no continuation from a neighbouring window.
3. Tokens are not re-cut; responses and controls move by -L in time.
4. Mirrors left out of the token-level effect (as WO52); within-sequence demeaning for the correlations; peak = max |r|.
5. V3 median best offset bootstrap added (original has no interval).
