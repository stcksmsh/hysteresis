# Night log, body-diag (WO46)

- Part 1 rules pushed first (`docs/DIAG_RULES.md`). Swaps of posture entries vs gesture codes on WO44 material, A1 blocks, realised stage; 37 songs in ~8 min on cores 14-19 (unit hyst-wo46-diag-161506), no errors. 4 tests pass (HJ rebuild matches WO44 stored rows within 2e-5 deg; float noise, tolerance 1e-3).
- Result: human posture removes most of the lamp excess (retrieval 3.65 -> 1.46, random 4.47 -> 1.99, model 4.43 -> 1.71); human gestures with the control's posture keep 2.3-2.9. See `docs/DIAG_REPORT.md`.

DIAG READY
