# Planner brief: cortex surprisal as an event detector (7.79 Step 2) (2026-11-17)

Rules `docs/CORTEX_EVENTS_RULES.md`, pushed before any result. Report `docs/CORTEX_EVENTS_REPORT.md`. Merged into `body` (1cca7ba), 3 tests pass.
The overseer recomputed the pooled F1 and the circular-shift chance from `cortexev/per_song.json`. All values match to ±0.002. One arm.

## What ran

- **Cortex surprisal:** the existing per-layer values (L1-L4 + total, 10 Hz), already stored in the T0 lanes for all datasets. Nothing was
  recomputed or trained.
- **Songs:** 210, the 10 V4 songs plus 200 seeded others, 52-53 per dataset; 6.35 h in all.
  - Scored from 16 s to each song's end, because L4 has no value earlier.
  - Songs under 28 s excluded.
- **Reference events,** from causal ear-feature rules (section changes from checkerboard novelty): 292 drops, 76 dropout onsets, 37 dropout
  ends, 817 section changes.
- **Comparison detectors:** the same peak rule applied to three ear signals (E-onset, E-lowflux, E-change), so that only the signal differs.
- **Chance:** circular shifts of the peaks within each song. Intervals: bootstrap over songs.

## Results (F1 against all event types; excess over shift chance [95 %])

| detector | ±0.5 s excess | ±1 s excess |
|---|---|---|
| L1 | +0.051 [+0.039, +0.064] | +0.044 [+0.031, +0.056] |
| L2 | +0.074 [+0.058, +0.090] | +0.145 [+0.125, +0.164] |
| L3 | +0.010 [-0.003, +0.024] | +0.025 [+0.008, +0.042] |
| L4 | +0.025 [+0.009, +0.040] | +0.031 [+0.014, +0.049] |
| total | +0.069 [+0.051, +0.087] | +0.109 [+0.086, +0.133] |
| E-onset | +0.014 [+0.005, +0.024] | +0.013 [+0.002, +0.024] |
| E-lowflux | +0.040 [+0.026, +0.057] | +0.021 [+0.007, +0.035] |
| E-change | +0.031 [+0.015, +0.047] | +0.175 [+0.156, +0.194] |

- **By type at ±0.5 s:**
  - Section changes: L2 +0.050 [+0.038, +0.062]; every ear detector between -0.010 and +0.006.
  - Drops: E-lowflux +0.044 and E-change +0.042; L1-L3 about +0.02; total +0.036.
- **Lags:** L3 peaks 2-4 s after events and L4 2-8 s after, so ±1 s windows miss them.
- **Limits:**
  - **The reference is circular.** It comes from the same ear features the cortex reads, and there is no human reference yet.
  - The dropout rule (low band AND onset energy both fall) finds few dropouts (76 onsets), and misses beat dropouts where hats or vocals
    continue (fd_053: 1 found).
  - Kosta's V4 and flash notes carry no timestamps, so they are not scored.
- **Kosta ear-check sheet prepared, not served:** `/secondary/hyst-data/body/cortexev/v4_events.md`. It lists every reference event and
  every unmatched cortex peak on the 10 V4 songs, in mm:ss.

## Questions

1. **Event source for the lookahead scoring (7.79: "if the cortex detects events better, it becomes the planner's event source").**
   - Options:
     - (a) the cortex (L2 + total) for all events;
     - (b) a mix: cortex L2 for section changes and structure, the ear's low-band flux for drops and dropouts;
     - (c) decide only after Kosta's ear check of `v4_events.md`.
   - **Recommendation: (c), with (b) as the default meanwhile.** Neither wins everywhere: the cortex wins on section changes at ±0.5 s, the
     ear on drops, and E-change at ±1 s. The yardstick is circular until a human reference exists.
2. **Dropout rule.** Options:
   - (a) keep it;
   - (b) define a dropout by low-band (kick) energy alone, whatever hats or vocals do. This matches Kosta's "beat dropout" notes.

   **Recommendation: (b).** The overseer has already written it into the WO50 factorial work order (not yet sent) as the default.
3. **Kosta's ear check.** Should it be a page (mark each listed time as real event / not / unsure), rather than reading a sheet? Options:
   (a) the sheet; (b) a page built with the existing dialstudy tool, one item per candidate time with 6 s of audio around it.
   **Recommendation: (b).** His answers become the first human event reference, for both this question and Q1.

## Pending

- WO50 (factorial viewing material): prompt written, not yet sent.
- Second pulse flash check: material being prepared, not served.
- The A2 brief, with the planner.
