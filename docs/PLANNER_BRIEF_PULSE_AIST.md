# Planner brief: internal pulse (WO48) and the AIST++ BAS cross-check (2026-11-17)

Answers BRAIN_SPEC 7.78 step 2.1 (the internal pulse) and the 7.78 1.1 caveat (the AIST++ cross-check). The overseer recomputed every
number below from the saved per-item values. Branch `body`, merge 80ef3d1. One arm.

## What ran

- **WO48 internal pulse.** Rules: `docs/PULSE_RULES.md`, pushed before any song was run (daf0ec3). Report: `docs/PULSE_REPORT.md`, `docs/PULSE_TABLES.md`.
  - Model: a bank of canonical nonlinear oscillators, Velasco & Large 2011 Eq. 3 with detuning 0. Parameters alpha 0, beta1 -1, beta2 -0.25,
    eps 1. The overseer checked the equation and these parameters against the published ISMIR 2011 PDF (§1.2, §2.1); they match.
    Differences from the paper: 73 oscillators over 0.5-4 Hz (24 per octave) as ruled, against the paper's 289 over 0.25-16 Hz. Unscaled time
    (w = 2 pi f). Integration RK4 at 5 ms, the B1 integrator reused unchanged.
  - Drive: running z-scores of 30-200 Hz flux x1.0, 200-400 Hz flux x0.5 and broadband onset x0.5, rectified, delayed 30 ms. Causal.
  - Selection:
    - largest amplitude x a log-Gaussian prior (centre 2 Hz, sigma 1 octave);
    - capped by the arm: a ±5° swing per period gives f_max 2.466 Hz = 147.9 BPM, with shoulder acceleration binding;
    - follows its local peak freely (±2 oscillators); a jump elsewhere needs 20 % more amplitude for 2 s.
  - Tests 6/6:
    - 120 BPM clicks;
    - a 4 s silence;
    - 60 BPM kicks under 240 BPM hats;
    - a 100→120 BPM ramp, followed with a 4-5 % lag;
    - arm limit;
    - causality.
  - Run: 1,341 songs, 0 failures.
  - Flash material prepared: 10 V4 songs × (pulse, librosa), same excerpts as V4, two questions per item.
- **AIST++ cross-check.**
  - Music: 60 tracks, one per music ID, taken from the AIST videos. Kosta agreed to the AIST terms and filled the form on 2026-11-17. Five
    pairs of the same music from different videos align at 0.0 ms, correlation ≥ 0.9995.
  - BAS: the WO47 V2 code unchanged, on keypoints3d. Rules in `docs/AIST_BAS_RULES.md` (pushed before results); report in
    `docs/AIST_BAS_REPORT.md`.
  - Sequences: 1,363 after the official ignore list. Chance level by shifted beats. Bootstrap by music ID.

## Results

### Pulse, 10 V4 songs (30 s excerpts) against Kosta's judged level

| song | pulse BPM | librosa | project grid | Kosta's level | pulse / judged |
|---|---|---|---|---|---|
| fd_018 | 87.4 | 142.9 | 139.7 | half of librosa (71.5) | 1.22 (neither level) |
| fd_053 | 134.8 | 136.4 | 129.2 | librosa | 0.99 |
| fd_183 | 110.0 | 125.0 | 110.0 | librosa | 0.88 |
| aioz_8JQ0 | 131.0 | 142.9 | 139.7 | librosa | 0.92 |
| aioz_SZhU | 112.5 | 150.0 | 89.1 | "slower than librosa" | 0.75 of librosa |
| ph_084 | 120.0 | 120.0 | 117.5 | librosa | 1.00 |
| ph_102 | 138.6 | 142.9 | 123.0 | librosa | 0.97 |
| ph_137 | 127.6 | 130.4 | 127.6 | librosa | 0.98 |
| Motorica jazz | 113.7 | 111.1 | 114.8 | not stated | 1.02 |
| Motorica street | 95.2 | 93.7 | 100.3 | librosa | 1.02 |

The pulse is within 3 % of Kosta's level on 5 of the 8 songs where he stated one.

### Pulse, all 1,341 songs

- **Regularity** (median 8-event line residual): pulse 2.1 ms, librosa 6.7 ms, project grid 72.6 ms.
- **Longest gap, as a multiple of the beat interval** (median): pulse 2.18, librosa 1.10, grid 3.71. In seconds, the pulse's longest gap is:
  median 1.20 s, q90 3.03 s, max 7.98 s. The pulse's gaps come from switches between levels, not from dropouts in the music.
- **Holds the beat through quiet passages** (580 passages): pulse 86 %, librosa 65 %, grid 83 %.
- **Holds the beat through project-grid dropouts** (7,149): pulse 93 %, librosa 97 %.
- **Level against librosa:** same 64 %, 2/3 18.6 %, 3/2 14.2 %, half 2.1 %, other 1 %. **About a third of songs lock at a 3:2 relation to
  librosa** (also to the grid). On those songs the flash can be off the beat half the time. The synthetic tests did not show this. Nothing was
  changed after seeing it.
- **Tempo:** oscillator rate q5/50/95 is 71.7 / 113.8 / 142.4 BPM; 7.9 % of songs are below 80, none above 150 (the arm cap).
  - The event-based tempo is q5/50/95 85 / 120 / 143.5, with 3.5 % below 80.
  - The difference comes mostly from 8 AIOZ clips of 3.5-10.8 s. They have 0-1 pulse events, because the bank has not locked yet, and their
    rate sits near the bottom of the bank.
- **Stability:** median 1.95 level jumps per minute; median share of frames within 6 % of the song's median rate is 0.72.

### AIST++ BAS (music-beat sum, 1,363 sequences)

| variant | BAS | chance | BAS - chance [95 % by music ID] |
|---|---|---|---|
| main (V2 constants, keypoints3d_optim) | 0.274 | 0.238 | +0.036 [+0.017, +0.055] |
| literal frame constants (smoothing 5 frames, sigma 3 frames) | 0.279 | 0.213 | +0.067 [+0.047, +0.088] |
| raw keypoints3d | 0.248 | 0.232 | +0.016 [+0.001, +0.032] |

- **Test split** (crossmodal_test, 20 sequences): BAS 0.317 (main) / 0.311 (literal).
- **Published ground truth** (Bailando, CVPR 2022, Table 1; the overseer read the PDF) is **0.2374**. **Not reproduced**; the cause was not
  checked (evaluation-code variant, their "40 pieces of 20 s", music-beat extractor).
- With 20 sequences the intervals cross zero: main +0.080 [-0.069, +0.239].
- Contrast: FineDance was at chance (WO47). AIST++ motion shows a small locking above chance, by every variant on the full set.

## Pending

- Kosta's pulse flash check is served: http://127.0.0.1:8770/. It has 20 items in blind random order (pulse vs librosa). Each item asks "Is the
  flash on the beat?" (yes / partly / no) and "Is it the right speed?" (right / too fast / too slow).
- The A retrain (WO49) is running: 3 seeds, cap 100 epochs.

## Questions

1. **The 3:2 locking (about a third of songs).**
   - Options:
     - (a) keep the pulse as ruled;
     - (b) read the pulse from summed harmonic support: each candidate's amplitude plus the amplitudes at 2f and f/2. This is Large's metrical
       readout and favours binary levels over 3:2;
     - (c) add a prior against 3:2 and 2:3 ratios to the current pulse;
     - (d) wait for Kosta's flash check.
   - **Recommendation: (d), then (b) if the flash check shows the 3:2 songs fail.** (b) is the model's own idea of meter, not a patch; (c) is a
     patch.
2. **The arm limit.** The cap uses a ±5° swing per period (f_max 147.9 BPM); the builder chose 5° so a 2 Hz pulse fits. Options: (a) keep 5°;
   (b) state the swing from A's measured shoulder amplitude at high vigour. **Recommendation: (b), when the motor-clock work order is written**:
   the cap should come from what A actually does.
3. **What the AIST++ result means for 7.78 1.1** ("dancers carry tempo, not beat phase").
   - Options:
     - (a) amend 1.1: beat-phase locking is dataset-dependent — at chance in FineDance, small but above chance in AIST++ (+0.016 to +0.067);
       tempo carrying still holds;
     - (b) chase the published 0.2374 further.
   - **Recommendation: (a).** The 7.78 design (pulse + motor clock with coupling 0.7, landings ±150 ms) does not depend on it, and (b) costs
     time for a number nobody uses.
4. **Very short clips.** Should clips under 12 s be excluded from pulse-driven use and from summaries? **Recommendation: yes; report-only for
   now.**

## Addendum (2026-11-17, after Kosta's flash check; `docs/PULSE_FLASH_RESULT.md`)

**Result.** On beat yes / partly / no: pulse 6 / 3 / 1, librosa 7 / 3 / 0. Speed right / too fast / too slow: pulse 8 / 0 / 2, librosa
7 / 3 / 0.
- The pulse's failures are songs where it runs 8-25 % slower than the beat (aioz_8JQ0 0.92, aioz_SZhU 0.75).
- On fd_018, where librosa chases the hats, the pulse at 0.61 of librosa was judged the right speed.
- Only two items are near 2:3, so the check cannot settle Q1.
- Both sources continue through beat dropouts; Kosta noted this as a miss 4 times.
- Kosta, verbatim: "the purpose isnt to find the beat, but possible end locations to match music, so it isnt just flashing on beat, but
  flashing at oportune moments e.g. beat/dropout/accent whatever right?"

**Q1, revised.** Options:
- (a) keep the pulse as ruled;
- (b) the harmonic-support readout;
- (c) a 3:2 prior;
- (d) a second flash check on 10 songs drawn from the 3:2 / 2:3 group, plus the two failures.

**Recommendation: (d), then (b) if those fail.** The pulse is usable as is: 8 / 10 judged right speed against librosa's 7 / 10.

**Q5 (new).** Kosta's purpose statement: landings at opportune moments (beat, dropout, accent), not a beat flash. Options:
- (a) the motor clock targets pulse events only, as ruled in 7.78;
- (b) the motor clock targets a candidate set: pulse events, plus dropout onsets and ends, plus strong low-band accents, all from the ear,
  causal. Landings choose among these within ±150 ms, and a dropout gives a hold.

**Recommendation: (b).** It matches the statement, uses the same ear features, and gives A2's weak pause a musical trigger (A2 brief Q1).
