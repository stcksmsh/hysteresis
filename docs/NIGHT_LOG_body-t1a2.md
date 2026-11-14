# Night log body-t1a2 (WO39, 2026-11-14)

- Step 1 (`docs/T1A2_STEP1.md`, `t1a2/step1.json`): round-1 K = 1024 variance explained, FineDance validation per joint 0.736 / 0.627 / 0.671 / 0.704 / 0.708 (base, shoulder, elbow, wrist bend, roll); AIOZ validation 0.791 / 0.741 / 0.713 / 0.540 / 0.609.
  Kept-AIOZ gesture RMS / FineDance: 0.67 / 0.78 / 0.69 / 0.46 / 0.51. Train weight share before any cap: FineDance 0.423, AIOZ 0.577.
  **Rule 7.61.3 APPLIES (4 of 5 joints below 70 %): AIOZ is capped at 50 % of total training weight in both runs.**

STEP1 DONE
