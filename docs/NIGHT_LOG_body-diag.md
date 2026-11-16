# Night log, body-diag (WO46)

- Part 1 rules pushed first (`docs/DIAG_RULES.md`). Swaps of posture entries vs gesture codes on WO44 material, A1 blocks, realised stage; 37 songs in ~8 min on cores 14-19 (unit hyst-wo46-diag-161506), no errors. 4 tests pass (HJ rebuild matches WO44 stored rows within 2e-5 deg; float noise, tolerance 1e-3).
- Result: human posture removes most of the lamp excess (retrieval 3.65 -> 1.46, random 4.47 -> 1.99, model 4.43 -> 1.71); human gestures with the control's posture keep 2.3-2.9. See `docs/DIAG_REPORT.md`.

DIAG READY
- GRIDS 1138 new grids (AIOZ 804, PhantomDance 260, Motorica 74) via analyze_mix; FineDance uses the stored 203. Check on 10 seeded FineDance songs: same beat counts, max abs beat-time difference 0.0 s (analyze_mix is deterministic). Bar level provisional (no downbeat source).
- SPOTCHECK READY (material prepared in /secondary/hyst-data/body/metric/spotcheck, 10 songs, manifest.json; not served). Whole-sequence sims (V1,V2) and per-sequence analysis still running; report follows.
