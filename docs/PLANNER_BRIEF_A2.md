# Planner brief: A retrained to convergence (WO49, 7.78 A retrain) (2026-11-17)

Report `docs/A2_REPORT.md`; merged into `body` (e098cc3), 11 tests pass. The overseer recomputed the intervention diagonal with a song
bootstrap from the saved per-start values (`grammar2/checks/seed*_values.npz`, 178 starts, 105 songs). It matches the report within
0.01 sd. One arm.

## What ran

- The A retrain as ruled in 7.78: cap 100 epochs; pause up-weighting per A_RULES addendum 3 (factors 1.471 / 1.268 / 1.000 / 1.935); seeds
  49101-49103.
- The WO45B checks unchanged.
- The S-B candidates: 6 excerpts, V1 vs V2, prepared and not served (`grammar2/look/manifest.json`, 12 entries, with room for the motor-clock
  pairs).

## Results

- **Converged.** All seeds stopped by early stopping (patience 5) before the cap: epochs 78 / 80 / 74, best epochs 73 / 75 / 69.
  - Best validation total 18.315 / 18.277 / 18.295, against A1's 18.417 / 18.469 / 18.446 when it stopped at the 40-epoch cap.
  - Train-to-validation gap 2.75-2.83.
  - Without controls, validation is higher by 3.30-3.44 nats.
- **Following its controls** (own-measure effect, sd; mean of 3 seeds, A1 → A2):
  - vigour 2.54 → 2.59;
  - height 4.51 → 4.48;
  - sharpness 0.67 → 0.67;
  - direction 0.30 → 0.30;
  - accent 0.08 → 0.06;
  - **pause 0.04 → 0.10** (per-seed intervals [0.087, 0.149], [0.055, 0.113], [0.050, 0.120]).
  - Pause now moves its own measure above zero, but stays small next to vigour and height.
  - Raising pause also raises sharpness (+0.43 to +0.57 sd) and lowers base speed (-0.54 to -0.83).
- **Cross-talk** is the same as in A1: vigour → base speed +1.42 to +1.48 and direction changes +1.35 to +1.37; sharpness → direction
  changes +0.51 to +0.61.
- **Smoothness** stays at human level: lamp power above 3 Hz relative to the re-decoded human is 1.04-1.06, and frozen windows are about 0.
- **Coherence** (A / human): control cosine 0.97-1.02; gesture-family repeat at 2 s 0.79-0.94, at 4 s 0.93-1.05.
- **Substitution:** realised output against its own request 0.40, against another sequence's request 0.82.
- **The S-B pairs are now matched on realised sharpness**: V1/V2 differ by at most 0.0003 (requested 0.029-0.073).
- **The p99 pause condition** is identical to the 0 / 1 condition, because train pause p99 = 1.0.

## Questions

1. **Pause is still weak (0.08-0.12 sd).**
   - Options:
     - (a) accept A2 as the motor grammar and make stillness a motor-clock decision: a hold when the pulse's confidence drops or the music is
       quiet;
     - (b) another A retrain with a larger pause weight;
     - (c) a separate stillness head.
   - **Recommendation: (a).** 5.4 % of training tokens carry any pause, and up-weighting moved the effect from 0.04 to 0.10. A further
     retrain is unlikely to make pause a usable knob, and 7.78 already gives timing to the motor clock.
2. **When to hold the S-B viewing.** Options: (a) now, V1 vs V2 only; (b) after the motor clock, so one session also carries the clock pairs
   (7.78 Q7 order). **Recommendation: (b).**
3. **The next work order is the motor clock (7.78 2.2/2.3) on A2.** It needs:
   - the pulse readout decision (brief PULSE_AIST Q1, after Kosta's flash check);
   - the arm-limit source (PULSE_AIST Q2).
   - **Recommendation:** write it once those are ruled; default to seed 49102 (lowest validation total).
