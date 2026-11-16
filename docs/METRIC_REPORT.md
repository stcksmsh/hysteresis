# Metric report: beat-phase / metrical analysis of human motion (WO46 part 2, BRAIN_SPEC 7.76 point 1 / 7.74 Q4)

Rules: `docs/METRIC_RULES.md` (pushed before any result; one amendment to the structure null, section "Structure" below, made before anything was reported). Code `scripts/body/metric_{grids,sim,lib,run,report,spotcheck,check_sim}.py`,
tests `test_metric.py` (15 pass). Full tables (every dataset, V1/V2, ALL/PASS, every lag, every delay, side table): `docs/METRIC_TABLES.md`. Per-sequence values: `/secondary/hyst-data/body/metric/results/` (Motorica never in git beyond aggregates).
Report only; no verdict. All statistics: resampling by song group, 2,000 resamples, seed 46101, 95 % percentile intervals. Provisional: half-time and bar levels (no downbeat source: 4/4 assumed, bar phase by onset strength).

## Material and coverage

- Beat grids: FineDance stored (203), AIOZ 804, PhantomDance 260, Motorica 74 new via `analyze_mix`. Check on 10 seeded FineDance songs: identical beat counts, max beat-time difference 0.0 s (deterministic).
  **Tempo caveat:** grid tempi cluster (median 117.5 BPM, 81 % of FineDance and 86 % of the other songs between 100 and 140 BPM); the tracker may favour that range, and none of the grids was checked by ear. Tempo-dependence results have little range to work with.
- Whole realised sequences (one pass through the WO43 chain, V1 and V2 copies, mirrors excluded): 4,778 sequences, 0 simulation failures. Checked against WO43's windowed q50 on 8 sequences: shoulder/elbow/wrist bend within 0.5 deg, yaw/roll differ by the per-window re-reference offset only, lamp z <= 2 mm, lamp speed <= 6 mm/s.
  (A first run was invalid: my sim script omitted `patch_gates()` -> 10 s warm-up dropped the first 8.5 s of every sequence and failed on short AIOZ clips; deleted and redone, see the night log.)
- **Analysed 4,700 of 4,778; 78 sequences skipped for fewer than 8 beats in the grid, all AIOZ** (0.14 h of 38.5 h of AIOZ motion: train 70 sequences 0.13 h, test 8 sequences 0.01 h, validation 0).
- **Sequences too short for one whole 20 s window** (no PASS set, no structure result): AIOZ 464 (train 350 / 0.96 h, validation 6 / 0.02 h, test 108 / 0.34 h; 3.4 % of AIOZ hours), FineDance 2, PhantomDance 4. Groups analysed per dataset (V1): FineDance 172, AIOZ 227, PhantomDance 260, Motorica 74.
- Event counts (per minute, V1): lamp-speed minima E1 92-113, acceleration peaks E2 70-88, reversals E4 60-76, onsets E5 40-56, joint-velocity peaks E3 36-101 (yaw lowest, wrist bend highest).

## 1. Phase concentration (rules section 4)

Headline (ALL, excess of R over the time-shuffled-IBI control, V1 and V2 side by side; full table with the other control, other levels, PASS and per-joint rows in `METRIC_TABLES.md` A0/A). Retarget low-pass cutoffs: **V1 2.50 Hz, V2 5.75 Hz**; at the mean tempo of
about 118 BPM the beat rate is **1.97 Hz** and the half-beat rate **3.93 Hz**, so V1 is filtered below the half-beat rate (and near the beat rate), V2 above both.

| dataset (BPM) | event | beat V1 | beat V2 | half-beat V1 | half-beat V2 |
|---|---|---|---|---|---|
| FineDance (118) | E1 speed minima | -0.001 [-0.006, 0.004] | 0.003 [-0.002, 0.009] | -0.001 [-0.006, 0.004] | 0.000 [-0.005, 0.005] |
| | E2 acceleration peaks | 0.003 [-0.003, 0.008] | 0.008 [0.001, 0.015] | -0.001 [-0.007, 0.005] | -0.003 [-0.009, 0.003] |
| | E5 onsets | 0.006 [-0.002, 0.014] | 0.011 [0.002, 0.020] | 0.006 [-0.002, 0.014] | 0.005 [-0.003, 0.014] |
| | E3 yaw peaks | 0.037 [0.022, 0.052] | 0.035 [0.021, 0.050] | 0.012 [0.003, 0.021] | 0.004 [-0.006, 0.014] |
| | E3 elbow peaks | 0.002 [-0.004, 0.008] | 0.010 [0.002, 0.018] | 0.002 [-0.003, 0.009] | -0.001 [-0.007, 0.005] |
| AIOZ (117) | E1 | 0.000 [-0.005, 0.006] | 0.005 [0.000, 0.010] | 0.003 [-0.002, 0.009] | 0.007 [0.002, 0.013] |
| | E2 | 0.006 [0.000, 0.011] | 0.013 [0.006, 0.020] | 0.005 [-0.002, 0.013] | 0.011 [0.003, 0.019] |
| | E5 | 0.005 [-0.003, 0.013] | 0.012 [0.004, 0.020] | 0.008 [0.001, 0.014] | 0.008 [0.000, 0.017] |
| | E3 yaw | 0.032 [0.017, 0.047] | 0.028 [0.014, 0.042] | 0.008 [-0.005, 0.021] | 0.010 [-0.003, 0.023] |
| | E3 elbow | 0.010 [0.004, 0.017] | 0.022 [0.013, 0.033] | 0.004 [-0.001, 0.010] | 0.007 [-0.002, 0.016] |
| PhantomDance (116) | E1 | 0.001 [-0.003, 0.006] | 0.006 [0.001, 0.010] | 0.001 [-0.004, 0.005] | 0.002 [-0.003, 0.006] |
| | E2 | 0.000 [-0.004, 0.006] | 0.003 [-0.003, 0.009] | 0.002 [-0.004, 0.008] | 0.002 [-0.004, 0.007] |
| | E5 | 0.001 [-0.005, 0.008] | 0.008 [0.001, 0.015] | 0.002 [-0.004, 0.009] | 0.000 [-0.006, 0.006] |
| | E3 yaw | 0.009 [-0.000, 0.017] | 0.010 [0.001, 0.018] | 0.006 [-0.002, 0.014] | 0.008 [0.000, 0.015] |
| | E3 elbow | 0.001 [-0.004, 0.006] | 0.002 [-0.004, 0.008] | 0.004 [-0.002, 0.009] | -0.001 [-0.007, 0.005] |
| Motorica (120) | E1 | 0.003 [-0.003, 0.010] | 0.003 [-0.004, 0.009] | 0.003 [-0.004, 0.010] | -0.004 [-0.010, 0.002] |
| | E2 | 0.006 [-0.002, 0.014] | 0.001 [-0.006, 0.009] | -0.000 [-0.008, 0.008] | 0.006 [-0.002, 0.015] |
| | E5 | 0.001 [-0.008, 0.010] | 0.002 [-0.009, 0.013] | -0.002 [-0.011, 0.007] | 0.001 [-0.008, 0.012] |
| | E3 yaw | 0.028 [0.012, 0.046] | 0.030 [0.012, 0.048] | 0.006 [-0.004, 0.017] | 0.001 [-0.010, 0.012] |
| | E3 elbow | -0.000 [-0.008, 0.006] | 0.014 [0.002, 0.026] | 0.008 [0.000, 0.017] | 0.000 [-0.008, 0.009] |

Findings (numbers in the table and in `METRIC_TABLES.md`):
1. **Beat-phase concentration of the human motion events is at chance level.** Real R equals the shuffled-grid and other-song-grid R within +-0.01 for lamp speed minima, acceleration peaks, direction reversals and movement onsets, at beat and half-beat level, in every dataset, for V1 and V2 (real R 0.05-0.14, chance ~1/sqrt(n) 0.06-0.15).
   Excess over the other-song tempo-matched grids is the same (`METRIC_TABLES.md`). V2 shows slightly larger excess (up to +0.013 for E2 in AIOZ, +0.022 for AIOZ elbow peaks) than V1; every excess is below 0.025 except the yaw row.
2. **The one consistent signal is the yaw (base rotation) velocity peaks:** excess about +0.03 at beat level in FineDance (0.037 / 0.035), AIOZ (0.032 / 0.028) and Motorica (0.028 / 0.030) for both V1 and V2, +0.009 in PhantomDance (V2 interval just above 0); about +0.01 at half-beat level (FineDance V1, interval above 0). Yaw V1 vs V2 are the same, so the low-pass does not explain it. Still small (R 0.11-0.20).
3. **Preferred phases are not consistent.** Pooled preferred phase differs between event types and datasets, and the spread of per-song preferred phases is R 0.03-0.2 (per song the phases are close to uniform). No beat-relative offset can be quoted. Half-time and bar levels (provisional) show nothing beyond chance either (`METRIC_TABLES.md` A).
4. **Lead/lag scan** (hit rate within +-50 ms of the beat shifted by L, -250..+250 ms in 25 ms steps, all lags in `METRIC_TABLES.md` B): hit rates are 0.16-0.18 (chance for a 100 ms window at ~0.5 s beats is 0.2 minus edge effects) with excess over shuffled grids within +-0.01 at every lag; no lag stands out (the lag-scan test recovers an injected shift).
5. **ALL vs PASS:** the same pattern (FineDance PASS: all lamp events within +-0.003, yaw peaks +0.035; AIOZ PASS slightly larger excess +0.014..+0.016 for E2/E4/E5, below 0.025).
6. The filter: V1 (2.5 Hz) removes motion at and above the half-beat rate by construction, so absence at half-beat level for V1 is partly expected; V2 (5.75 Hz) passes both rates and shows the same absence at the lamp level, with small positive excess for V2 in AIOZ and for FineDance E2/E5/elbow at beat level.

## 2. Tempo, density, pauses (rules section 5; V1, Spearman across song groups, `METRIC_TABLES.md` C)

- Motion-event rates against tempo: rho -0.11 .. +0.09, all intervals include 0 (E1/E2, four datasets). Against onset density: FineDance -0.27 [-0.40, -0.12] (E1 and E2), other datasets -0.07 .. +0.05, intervals include 0.
- Pause occupancy (pauses >= 0.25 s): FineDance 4.9 %, AIOZ 3.2 %, PhantomDance 8.7 %, Motorica 2.8 %; pauses of 2-8 s: 1.8 %, 0.5 %, 4.0 %, 0.6 % of the time (0.32, 0.09, 0.64, 0.11 per minute, mean duration 3.0-3.8 s); pauses > 8 s: <= 1.8 %.
- Against rhythmic density (onset density) and pulse clarity (P1 autocorrelation peak, P2 onset strength at beats / mean): pause occupancy vs P1 rho -0.24 [-0.39, -0.09] (FineDance) and -0.28 [-0.41, -0.15] (AIOZ), nothing in PhantomDance and Motorica; every other pair has an interval containing 0 (|rho| <= 0.17). 2-8 s pause occupancy: no relation (|rho| <= 0.13, intervals include 0).

## 3. Whole-song structure (rules section 6; `METRIC_TABLES.md` D)

Change points of the motion control vector (and of 4-token motif blocks) against music novelty (ear features; cortex also for FineDance), delays -2..+2 s (music after motion), excess over 200 rotations of the music inside the valid interval (tokens 16..n-16).
**Amendment before reporting:** a first version rotated the music over the whole song including the novelty kernel's NaN edge region; short AIOZ clips then gave an inflated excess (artefact). The null now rotates inside the trimmed interval and a test (unrelated streams, 75 tokens) shows excess ~0.
- Delay 0, 2 s scale, control vector vs ear-feature boundaries (ALL, V1): hit-share excess FineDance +0.034 [0.017, 0.051], AIOZ +0.042, PhantomDance +0.008 [-0.005, 0.019], Motorica +0.030 [0.013, 0.049]; novelty-curve correlation excess +0.04 (FineDance, PhantomDance, Motorica) and +0.08 (AIOZ).
  8 s scale: hit-share excess +0.057 [0.029, 0.086] FineDance, +0.033 PhantomDance, +0.040 Motorica; correlation excess +0.10 (FineDance, Motorica), +0.13 (PhantomDance). Cortex features (FineDance) give similar values to ear features (2 s scale hit excess +0.025 [0.010, 0.041] vs +0.034; 8 s scale +0.049 [0.024, 0.075] vs +0.057; correlation excess +0.042 / +0.106 vs +0.040 / +0.104): the cortex adds nothing measurable over the ear features here.
  The excess is largest at delay 0 or +-0.5 s and falls towards +-2 s; it is small in absolute terms (hit share 0.2-0.3 against 0.2 chance).
- Repetition-curve correlation (2 s scale): FineDance +0.015 [-0.005, 0.035], Motorica +0.030, PhantomDance +0.078 [0.054, 0.102], AIOZ +0.053. Motif blocks behave like the control vector.
- PASS (kept windows only) gives the same sign with wider intervals (FineDance 2 s hit excess +0.023 [-0.003, 0.049]).
- **AIOZ 8 s scale (corr excess +0.30, hit excess +0.11) is not trustworthy:** median clip 36 s leaves about 30-40 tokens after trimming, with a smoothing kernel of 16 tokens, so each song has very few independent values; the null still shares less structure than the real pair. Quote FineDance, PhantomDance and Motorica for the 8 s scale.
- Side table (control vs acoustics on whole songs, rules E, V1, ALL, lags -2..+2 tokens): within-song Spearman median |rho| 0.03-0.06 over all 320 control x measure x lag cells per dataset; largest FineDance 0.25 (pause probability vs high-band energy, lag 0), PhantomDance 0.27 (pause probability vs RMS), AIOZ 0.13, Motorica 0.15 (vigour vs RMS). Per-song medians at most 0.31 in absolute value.
  Consistent with 7.74's token-scale finding (|rho| <= 0.19 within song): the whole-song numbers are of the same size.

## Summary of what the numbers say (no verdict)

- Timing: none of the five motion-event definitions is locked to the detected beat grid at beat, half-beat, half-time or bar level beyond chance, in any of the four datasets and for both retarget variants; the exception is a weak beat-level lock of yaw-velocity peaks (R excess ~0.03).
- Character/structure: slow structure of the music (ear/cortex novelty) and of the motion controls co-vary only weakly (excess 0.03-0.06 in boundary hit share at delay 0, correlation 0.04-0.13); pauses are rare (3-9 % of time) and barely related to rhythmic density or pulse clarity.
- Open for the overseer: the result concerns these grids (not checked by ear, tempo-clustered), the retargeted realised stage (V1 low-passed at 2.5 Hz), and 8 s / 2 s control-vector boundaries (not gesture-code motifs; FOR USER).

## FOR USER (defaults taken)

V1 main and ALL main with PASS alongside; mirrors excluded; 30-event minimum per cell; 50 ms hit window, 25 ms lag step; bar/half-time provisional; motif = 4-token control block (gesture-code n-grams only exist for FineDance, not done); zero motion/audio offset (lag scan reports all offsets); whole sequences are one simulation pass, the tail beyond the last full 20 s window counts as not passing; structure results trimmed 16 tokens each end (amendment); AIOZ 8 s-scale structure flagged unreliable.

## Spot check

Prepared, not served: `/secondary/hyst-data/body/metric/spotcheck/` (`manifest.json`, 10 songs: FineDance 3, AIOZ 2, PhantomDance 3, Motorica 2; +-8 s excerpts around the 8 s-scale ear-feature novelty boundaries, at most 6 per song; Motorica excerpts stay on this laptop). The boundaries were computed before the structure amendment and are music-side only (the amendment changed only the null), so they stand.
