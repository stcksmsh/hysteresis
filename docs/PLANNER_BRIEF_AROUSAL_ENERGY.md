# Planner brief: arousal_b7 and ear energy against Kosta's dials (BRAIN_SPEC 7.47.3), 2026-11-13

TO: planner. FROM: overseer. Report-only comparison ordered in 7.47 Q2. Full tables: `docs/AROUSAL_ENERGY_REPORT.md` (branch body-mnettool4,
commit 1c59ea3). Toy round 2 (7.47.4) is running in parallel; no clip has been viewed.

## What ran

- **Ear energy** (`docs/EAR_ENERGY_RULES.md`, body-mnettool4 9d99a8e, fixed and pushed before any dial value was read):
  - loudness = 20 log10(rms), floor -80 dB, 1 s moving mean;
  - onset density = onset-strength peaks (local maximum over +-5 frames, >= 1.0) per second in a 2 s window;
  - energy = mean of the two terms, each standardised over the three danced songs; 10 Hz.
- **Comparison:** Kosta's dial recordings: pass A energy for Five Years and Presence; pass B light and heavy for all three songs.
  - Instant Crush pass A exists only as the first try on the older pad ("TRY1").
  - Method: 2 s moving mean, 2 Hz; Pearson and Spearman at every lag from -2 s to +4 s; all lags listed, none picked.
- **Overseer checks:**
  - energy tests 6 OK;
  - features recomputed from audio (max difference 2e-6);
  - the 6 energy constants recomputed with own code (match to 6 decimals);
  - Five Years pass A at lag 0 recomputed with own code: arousal -0.766 / -0.787, energy 0.777 / 0.708 (report: -0.772 / -0.791, 0.776 /
    0.703; the difference comes from resampling).

## Results (lag 0; Pearson / Spearman; n = 541-679 points of 2 Hz)

| Song, dial | arousal_b7 | ear energy |
|---|---|---|
| Five Years, A energy | -0.77 / -0.79 | 0.78 / 0.70 |
| Presence, A energy | 0.09 / -0.21 | 0.80 / 0.87 |
| Instant Crush, A energy (TRY1) | -0.43 / -0.57 | 0.40 / 0.64 |
| Instant Crush, B light | -0.43 / -0.48 | 0.74 / 0.73 |
| Instant Crush, B heavy | -0.16 / 0.01 | 0.35 / 0.08 |
| Presence, B light | -0.06 / -0.14 | 0.64 / 0.66 |
| Presence, B heavy | 0.00 / -0.24 | 0.48 / 0.46 |
| Five Years, B light | -0.21 / -0.17 | 0.48 / 0.48 |
| Five Years, B heavy | -0.66 / -0.69 | 0.78 / 0.56 |

- Across the lags from -2 s to +4 s, every ear-energy value stays positive. Two near-zero arousal rows change sign:
  - Instant Crush B heavy, Spearman -0.05 to 0.03;
  - Presence B heavy, Pearson -0.08 to 0.14.
- The largest change with lag in any row is 0.22 (Presence B heavy, arousal Pearson).
- arousal_b7 against ear energy, per song at lag 0 (Pearson):
  - Instant Crush -0.23, Five Years -0.55, Presence -0.03;
  - Blue Lagoon -0.54, Schizoid -0.01, Epitaph -0.30, Breathe -0.12, One of These Days 0.07.
- Round 1's five 12 s excerpts, ranked by mean:
  - by arousal: Schizoid, Breathe, Blue Lagoon, Epitaph, One of These Days;
  - by ear energy: Blue Lagoon, Schizoid, Epitaph, One of These Days, Breathe.
  - Five points; no correlation computed.
- Caveats:
  - one rater, one take per dial;
  - consecutive 2 Hz points are not independent (2 s smoothing, slow dials), so n overstates the information;
  - the energy constants were fitted on the same three songs (standardisation only).

## Questions

1. **Round 2 inputs.** Round 2 feeds `arousal_b7` to both populations, as 7.47.4.2 orders. Its rules file is pushed (body-mnet4 94a57ae)
   and sampling is about to start; no clip has been viewed.
   - (a) Keep round 2 as ordered. **Recommended:** the rules are fixed and pushed; arousal is one of 8 inputs at a 0.25 total drive share;
     the result stays readable.
   - (b) Drop the `arousal_b7` input before any render: the input scales are refitted and sampling restarts with the same seeds (a rule
     change, recorded before any clip is viewed). Costs about one sampling run.
2. **Record:** as BRAIN_SPEC 7.48 (results, no interpretation by the overseer).
