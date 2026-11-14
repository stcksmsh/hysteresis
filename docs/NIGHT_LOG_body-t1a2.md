# Night log body-t1a2 (WO39, 2026-11-14)

- Step 1 (`docs/T1A2_STEP1.md`, `t1a2/step1.json`): round-1 K = 1024 variance explained, FineDance validation per joint 0.736 / 0.627 / 0.671 / 0.704 / 0.708 (base, shoulder, elbow, wrist bend, roll); AIOZ validation 0.791 / 0.741 / 0.713 / 0.540 / 0.609.
  Kept-AIOZ gesture RMS / FineDance: 0.67 / 0.78 / 0.69 / 0.46 / 0.51. Train weight share before any cap: FineDance 0.423, AIOZ 0.577.
  **Rule 7.61.3 APPLIES (4 of 5 joints below 70 %): AIOZ is capped at 50 % of total training weight in both runs.**

STEP1 DONE

- Rules `docs/T1A2_RULES.md` pushed before training (Bailando loss quoted from `models/vqvae.py` / `configs/sep_vqvae.yaml`: L1 recon + 1 x L1 velocity + 1 x L1 acceleration + 0.02 x commit; spline head, reach 24 rows; AIOZ 50 percent cap, factor 0.732). 6 tests (`test_t1a2.py`) pass.
- Run A (K = 1024, 4 threads, cores 6-13) stopped early at epoch 26 (best weighted MSE 0.397; round 1: 0.416). Run B (2 x 1024 residual, cores 14-19) stopped early at epoch 19 (best 0.182). Both by the patience-5 rule.
- Results (`docs/T1A2_REPORT.md`): variance explained on FineDance validation, minimum over joints: A 0.659 (fails 0.85), **B 0.855 (passes; 0.889 / 0.855 / 0.873 / 0.877 / 0.878)**. Usage 1.000 (both stages), ranges 0.94-1.00, gates 0.979 / 0.983 (control 1.000): pass. **Jitter fails in both**: worst ratios A 3.5 (acceleration sign changes) / 7.4 (power above 3 Hz), B 3.5 / 8.0 (round 1: 10 / 110). **Neither run passes every rule; no S1 candidate: report and hold.**
- FOR USER: gate rule applied as reconstructed pass share >= 0.95 (default); commit weight 0.02 as in Bailando (round 1 used 0.25); model selection on the round-1 weighted MSE; Run B has two code indices per chunk, which T1b would have to predict as a pair.

T1A2 READY
