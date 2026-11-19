# Planner brief: end-to-end sync audit result (BRAIN_SPEC 7.86 Q2), 2026-11-19

TO: planner. FROM: overseer (via Kosta). Reports `docs/SYNCAUDIT_REPORT_A.md` (A1 synthetic probe, A4 code review), night log
`docs/NIGHT_LOG_body-syncaudit-b.md` (A2 AIST++, A3 lag diagnostic); data `/secondary/hyst-data/body/syncaudit/{a,b}/`. Both merged into
`body` (15ad08b, 13 tests pass). Report only; no pipeline code was changed. Sign: positive = movement later than its music.

## Result against the 7.86 outcome rule: FINDING (offset > 50 ms), a latency of the simulated body, not a loader error

Two independent audits agree. The retarget path to the realised arm adds a delay; every array cut from `controls/q50` carries it.

| stage | A1 synthetic probe (sine 0.5-2 Hz, 70 deg pulses) | A2 AIST++ (60 seqs, stage vs previous stage) |
|---|---|---|
| loading, retarget angles, to_commands, low-pass (zero phase), spline to 100 Hz, guard, window cut | 0.0 ms (-0.6 .. +0.0) | 0.000 s (<= 0.004) |
| spinal layer (3 Hz, zeta 0.7) | **+80 / +81 / +86 ms** (sd 0 on pulses +84.5) | **+84 ms** (V1 and V2) |
| limiter + servo (v2p body) = `controls/q50` | **+100 .. +200 ms beyond spinal; total +177 .. +291 ms**, varies with joint (base yaw +191..+284), frequency and amplitude (limiter saturates) | +44 .. +114 ms (V1 +69 limiter, +114 servo; V2 +44, +70) |
| lamp FK, joint CSV, 60 fps table, rendered frames (P04), x264, concat, AAC mux, container start, shifted-foil construction | 0 (CSV time column exact; frame track -2.3 ms; audio clicks 0.000-0.003 ms; foil shift 0.0 samples) | lamp +8 / +27 ms |
| **cumulative retarget to realised lamp** | **+180 .. +290 ms** | **+275 ms V1, +224 ms V2** |

- A3 (overseer recomputed from `a3_results.json`): lamp speed vs raw human joint speed of the same windows, pooled lag with 95 % CI by
  song: FineDance V1 +0.312 [0.275, 0.355], V2 +0.299 [0.287, 0.312]; AIOZ +0.333 / +0.247; PhantomDance +0.386 / +0.269; Motorica
  +0.351 / +0.301 (V1 / V2). Four-dataset means: V1 +0.346 s, V2 +0.279 s.
- The raw-joint arrays carry 0 ms (WO47 raw, WO53 part B): they are on the music's clock; the lamp arrays are 0.2-0.3 s late.
- The spinal layer's analytic low-frequency group delay (2 zeta / omega_n at 3 Hz, zeta 0.7) is 74 ms, consistent with the measured +80..86 ms.
- **Movement against music directly cannot resolve a lag**: per-song peak lags against the onset (ear col 40) and energy envelopes are flat
  over +-1.5 s (share within +-100 ms 0.03-0.11; peak heights equal the chance heights, e.g. FineDance lamp V1 0.038 vs chance 0.034 / 0.036), for
  raw and lamp alike. On raw AIST++ keypoints too (pooled CI about +-1 s). The lag is therefore measured movement-to-movement, plus the
  probe; it is not a measured movement-to-music lag in real songs. AIST++ raw BAS is +0.057 over chance [0.011, 0.103]; V1 lamp -0.023,
  V2 lamp +0.000.
- A4 code review: no dataset loader adds or detects an offset (motion frame 0 = audio sample 0 everywhere; decimation from frame 0); the
  warm-up in this path is a 1.5 s pre-roll, trimmed exactly. Librosa/ear conventions add up to about one hop (20-33 ms), below threshold,
  not measured. The mismatch page also draws a 1.5 s look-ahead hint of the hand path and a 4 s trail (drawing features, the arm itself
  is exact at t).

## Does it explain the shifted-foil preference (8/8)? Not by itself

- The lag (0.2-0.3 s) is far smaller than the 2-6 s shifts.
- A3's table for the 13 shifted clips (lamp speed against each half's music envelope): foil minus real correlation at zero lag is +0.011
  (ear col 40, foil higher in 5/10 pairs) and -0.064 (energy, foil higher in 3/10); all |c| < 0.2. No preference for the foil is visible in
  the signal; the audit does not explain the picks.
- A movement that trails its own music by 0.3 s would, at a 2-6 s shift, still leave a mismatch; so this lag removes one confound but does
  not predict a foil preference. The foil preference stays unexplained.

## Earlier results touched (overseer reading; none rerun)

- WO47 lamp BAS and V3 offsets, WO52 hold/change/burst-vs-music-event lags and the music-lag part of rhythm, the "retargeted lamp" columns
  of WO53 B: the lamp is late by 0.2-0.3 s. Period-ratio (shift-invariant) results, and all raw-joint results, are unaffected.
- BAS at sigma 0.1 s with a 0.3 s lag lands at chance by construction; but raw FineDance BAS is also at chance with 0 ms (7.77), so the lag
  does not explain that.
- The 7.75/7.77/7.78 "fits the music" viewings, the pulse flash checks and the mismatch clips used `controls/q50`-based movement with the
  undelayed music.
- A2/A3-trained models: A's controls are measured on the realised lamp (`controls/q50`) and paired with music features by token index;
  whether the 0.2-0.3 s matters for A, and for B's later music-to-control training, is not assessed. To check before A3.
- Cortex events and pulse (music only): not touched.

## Questions

**Q1. Fix route.** R1 already allows an audio delay to compensate servo travel.
- (a) Re-time at read time: for measures, shift every `controls/q50`-derived array earlier by a constant L per variant (V1 0.35 s, V2 0.28 s,
  the four-dataset means); for viewing clips, advance the movement by cutting the joint CSV from `window_offset + L` (equivalently delay the
  music by L). No re-simulation. Residual error across joints and amplitudes about +-50 ms (the A1 spread). **[recommended]**
- (b) Lead-compensate the body path: advance the commands fed to spinal + limiter + servo and re-simulate all windows (hours of CPU); the
  residual would still depend on joint and amplitude.
- (c) Leave arrays as they are; report the lag in every result that uses the lamp.

**Q2. Constant L per variant, or per dataset?** The per-dataset V1 values are 0.31-0.39 and V2 0.25-0.30 (CIs overlap across datasets).
- (a) One constant per variant. **[recommended]** (b) Per dataset and variant.

**Q3. Rerun order after the fix (7.86 outcome rule).** Cheap analyses first, viewing last:
1. WO47 lamp BAS / V3 and WO52 event locks and WO53 B lamp column on re-timed arrays (report only);
2. then mismatch round 2 on re-timed clips (instruction page explaining shifted pairs, offsets 4-6 s, foils from another dataset when
   tempo allows, fresh excerpts, 5 repeats). **[recommended]**
- Alternative: run round 2 immediately on re-timed clips and the analyses in parallel.

**Q4. A and B.** Should A3's data rebuild shift controls vs music by L (token alignment) before the next A training? **[recommended: yes,
as part of the "A3 controls and B senses" ruling; the overseer measures the token-level effect first (report only)]**

Standing rules unchanged.
