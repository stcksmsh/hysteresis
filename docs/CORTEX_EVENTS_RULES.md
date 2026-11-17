# Cortex as event detector: rules (BRAIN_SPEC 7.79 Step 2) — written and pushed before any result

Report only. No verdict, no training, no change to the cortex, A or B. Code `scripts/body/cortexev.py` (one file), test
`scripts/body/test_cortexev.py` (synthetic signals only). Out: `/secondary/hyst-data/body/cortexev/`. When these rules were pushed,
no code had been written and no song had been passed through any detector below.

## 0. Data (all precomputed, nothing recomputed)

- **Cortex surprisal:** the T0 lanes (`/secondary/hyst-data/body/t0/lanes`, `t0_phantom/lanes`, `t0_motorica/lanes`), field `s10`
  (n10, 5) = surprisal of layers L1..L4 and the total, frozen cortex B7 epoch 6, `braindump.surprisal` (Gaussian NLL, mean over the 44
  channels), at 10 Hz on stamps t_k = (10k + 9) / 100 s. These are the same values as the 100 Hz T1b precompute
  (`t1b/cortex/*.npy`, FineDance only; `t1b/cortex/repro.json` checks the equality), so the T0 lanes are used for every dataset.
- **Ear features:** field `ear` of the same lanes: the 44 standardised, clipped (±10) fast features at 100 Hz
  (`scripts/brain/fast_features.py`). Raw values are recovered as `ear * std + mean` with the B3 corpus statistics (`braindump.stats()`);
  the ±10 clip is the only loss.
- **Timing of the cortex surprisal (structural, stated before results):** layer i's surprisal at t scores the mean of the features over
  the last h_i frames (h = 0.1, 0.5, 2, 8 s) against a prediction made 2h_i earlier. An event at time e therefore enters L3's surprisal
  over [e, e + 2 s] and L4's over [e, e + 8 s]; a ±0.5 s window is narrow for the slow layers by construction. The ±1 s window and an
  event-locked lag profile (section 5) are reported so this is visible; the windows are not changed per layer.

## 1. Event reference = the ear-feature event detectors (the baseline)

All on a 10 Hz grid at the cortex stamps; each 10 Hz value is the mean of the 10 frames at 100 Hz ending at the stamp (causal).
Signals: **L** = low-band power = mean over the log-mel bands whose centre is below 200 Hz (librosa Slaney mel centres, 32 bands
30-16000 Hz, as in `controls_stats.acoustic`) of 10^(dB/10); **O** = onset strength (column 40), causal mean over the last 0.5 s;
**F** = low-band flux (column 32, 30-200 Hz). "Running median" = median over the 10 s before the stamp (100 stamps, current excluded).

- **Dropout (causal).** Condition c(t) = L(t) < 0.25 × base_L and O(t) < 0.5 × base_O, where base_L, base_O are the running medians at
  t; while a dropout is open the bases stay frozen at their values at its first stamp. A dropout is a run of c lasting at least 0.4 s
  (4 stamps). It ends at the first stamp from which c is false for at least 0.3 s (3 stamps). **Dropout onset** event = first stamp of
  the run; **dropout end** event = first stamp of that 0.3 s recovery. (Detection is known 0.4 s / 0.3 s after the timestamp.)
- **Drop (causal).** At stamp t: the mean of L over the 1 s before t is < 0.5 × the running median of L taken at t − 1 s (the
  "reduced" second), and F(t) > 3 × the running median of F at t, and L(t) ≥ 0.5 × that same baseline (the low band is back).
  Event = first stamp meeting all three; refractory 4 s.
- **Section change (NOT causal; it is a reference).** 0.5 s tokens (means of 50 frames of the 44 standardised ear features, token time
  = its centre), each column z-scored over the song; cosine self-similarity, Gaussian-tapered checkerboard kernel, half-width 16 tokens
  (8 s), sigma 8 tokens (`controls_stats.novelty`); peaks = local maxima ≥ the song's novelty mean + 1 SD, minimum spacing 8 s
  (`controls_stats.peaks`). Uses 8 s of future audio.
- **any** = union of the four types above.
- **manifest** (the 10 V4 songs only): the boundaries in `/secondary/hyst-data/body/metric/spotcheck/manifest.json` (WO46, fixed
  before this work; top 6 peaks of an 8 s novelty on 0.5 s tokens of 44 ear + 32 cortex mode-amplitude columns).

No threshold above was tried on any song.

## 2. Detectors scored

- **Cortex, per layer:** L1, L2, L3, L4 and total (`s10` columns 0-4). Smoothing: causal mean over the last 3 stamps (0.3 s), NaN
  stamps skipped. Peak: a stamp that is the maximum of the smoothed lane within ±1 s (±10 stamps) and ≥ the song's 90th percentile of
  the smoothed lane over the scoring span. Timestamp = the peak stamp (confirmation needs 1 s of future; stated, not hidden).
- **Simple ear peak detectors (same smoothing and peak rule as the cortex, so the two differ only in the signal):**
  E-onset (column 40, raw), E-lowflux (column 32, raw), E-change (Euclidean distance between the mean standardised 44-feature vector
  over the last 1 s and over the 1 s before that).
- **The ear event detectors themselves** (drop, dropout onset, dropout end, section) as predictors of the OTHER types (section 4).

## 3. Alignment measure

- Scoring span per song: from 16.0 s (the first stamp where L4 surprisal is defined; also gives the 10 s running medians history) to
  the end. Predicted peaks and reference events outside the span are dropped.
- Hit windows ±0.5 s (primary) and ±1 s. A predicted peak is a hit if a reference event lies within the window; a reference event is
  recalled if a predicted peak lies within the window (not one-to-one).
- Precision = hit peaks / peaks, recall = recalled events / events, F1 = 2PR / (P + R), pooled over songs (sums of the four counts).
  Per detector × reference type × window.
- **Chance:** each song's predicted times circularly shifted by a uniform random offset within its span (wrapped inside the span), 200
  shifts, seed 79201, an independent offset per song per shift. Chance F1 = mean over shifts of the pooled F1; p = (1 + #shifts with
  F1 ≥ observed) / 201.
- **Intervals:** bootstrap over songs, 2,000 resamples, seed 79202: 95 % percentile interval of F1 and of excess = F1 − chance F1
  (chance from each song's mean shifted counts, resampled with the song).

## 4. The fair comparison and its circularity

The reference events are built from ear features, and the cortex's only input is the same ear features (plus grid phase). The
yardstick is therefore ear-made, which favours ear detectors that read the defining column (E-lowflux vs drop: column 32 is in the drop
rule). It is limited by:
1. **Cross-scoring:** each ear event detector is scored only against the other types (dropout onset vs drop, section, ...; "any" for an
   ear event detector excludes its own type). The diagonal is not reported.
2. **Same peak rule:** the simple ear peak detectors use exactly the cortex's peak rule, so a cortex advantage cannot come from the
   peak picker.
3. **manifest:** fixed before this work by a different pipeline; it is still ear-made and also uses cortex mode amplitudes, so it is
   circular in the cortex's favour. Reported for the 10 V4 songs only, with the small-n caveat.
4. **The only held-out reference** is Kosta's ear: `v4_events.md` (section 6) is prepared for a later check; no ear verdict exists now.
   The V4 / pulse-flash notes give no timestamps, so they cannot be scored.

## 5. Also reported (no claim)

Event-locked lag profile: per layer, mean of the per-song z-scored smoothed surprisal at lags −4 to +12 s around each reference type,
with the lag of its maximum, so the slow layers' structural delay (section 0) is visible.

## 6. Song set

- The 10 V4 songs (`metric/spotcheck/manifest.json`), plus a seeded sample (seed 79203) of 200 others: 50 per dataset (FineDance,
  AIOZ, PhantomDance, Motorica; Motorica has 72 eligible), drawn from the songs with T0 lanes, excluding the V4 songs.
- Excluded: songs under 12 s (the 7.79 Q4 rule), and, because the scoring span starts at 16 s, songs whose span would be under 12 s
  (duration < 28 s). The second rule is applied before sampling. AIOZ: at most one clip per YouTube id (clips of one video share
  music). Motorica takes may share music; not deduplicated (no music id in the data).
- Motorica is local only; nothing leaves the laptop.

## 7. Outputs

`/secondary/hyst-data/body/cortexev/`: `songs.json` (song list), `per_song.json` (per song: events, peaks, counts), `results.json`
(tables), `v4_events.md` (ear-check sheet: for the 10 V4 songs every reference event and every cortex-layer peak not within ±1 s of
one, mm:ss.s; not served, no page). Report: `docs/CORTEX_EVENTS_REPORT.md`.
