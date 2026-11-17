# Night log body-grammar2 (WO49)

- 2026-11-17: branch body-grammar2 from origin/body, worktree wo37b-aioz, cores 6-13. Rules addendum 3 pushed (docs/A_RULES.md) before training; 11 tests pass.
- A2 ESTIMATE: 3 seeds parallel, 2 threads each: 54 / 82 / 68 s per epoch (206 steps, 13,179 train / 1,397 val windows), peak 0.65 GB. Cap 100 epochs = 2.3 h worst case (<= 12 h): training starts without waiting. Pause factors 1.471 / 1.268 / 1.000 (floored) / 1.935 (finedance / aioz / phantom / motorica).
- FOR USER: pause factor floored at 1 (Phantom); validation / early stopping unweighted by pause.
- A2 TRAIN DONE: seeds 49101/49102/49103 early-stopped at epochs 78/80/74 (best val total 18.315 / 18.277 / 18.295; A1 18.42-18.47).
- A2 CHECKS DONE (all A_RULES section 6 + addenda 1-2, per-start values saved) and S-B CLIPS: 6 excerpts x 7 clips rendered (42), manifest grammar2/look/manifest.json (not served; no motor-clock pairs yet).
- A2 READY f12e8fd (report docs/A2_REPORT.md)
