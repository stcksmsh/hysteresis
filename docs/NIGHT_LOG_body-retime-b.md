# Night log: body-retime-b (WO55 part B, arm-only re-timed mismatch round 2 material)

- 2026-11-19 17:05 branch `body-retime-b` from `origin/body` e5d2b29. Rules note `docs/MISMATCH2_RULES.md` written and pushed before any clip.
- 17:20 `retime.py` appeared on `origin/body-retime-a` (1158ddf) and was copied unchanged. Builder, arm-only patch, proof script, session `intro` option and tests (28 pass) pushed (f40efe4).
- 17:25 plan (unit hyst-wo55b-plan1): 25 items. Different-song foils: 9 AIOZ, 1 PhantomDance (P10, Motorica movement), none same-dataset. Shifted offsets 4.0-6.0 s, none outside Q3.
- next: render 20 movements, arm-only page (unit hyst-wo55b-render1).
- 17:50 render: 20 of 20 movements rendered arm-only (P04 proof: 415 strokes with hint+trail vs 273 arm-only, hint 22 -> 0, trail 120 -> 0). Assemble: 25 clips, manifest with `intro`. Session built (seed 53201), not served.
- next: checks, order checks, synthetic scorer (unit hyst-wo55b-chk1).
- 17:55 first checks: clips 25/25, retime 25/25, order checks pass, but repeat sides 4 first / 1 second (MISMATCH_RULES section 3 states 2-3 / 3-2; round 1's code does not enforce it, round 1 happened to get 3/2). Added `balance_repeats` (redraws only the repeat choice) + test; first build moved to `retime/b/superseded_build1/` (its session was never served, answers empty).
- 18:10 rebuild (unit hyst-wo55b-redo1): the 20 pairs identical to build 1 (same seed stream), renders reused; repeats R01-R05 = P06, P09, P17, P11, P10 (3 different-song, 2 shifted), reversed sides 2 first / 3 second. Session `/secondary/hyst-data/body/mismatch2/session_2026-11-19` (seed 53201, intro.json), not served.
- Checks: clip checks 25/25 (645 frames, 21.5 s, gap silence 0 and black < 2/255, real half sample-exact, AAC lag 0 corr > 0.999, RMS ratio 1.00, frame-identical halves, limits <= 1.25); retime 25/25 (max error 5e-7 deg, all 501 rows); arm-only string check 20/20 pages; overlap with round 1: 0 songs in every dataset; order checks pass (10/10, 5/5 per kind, Spearman rho 0.00, longest run 5, code parity 12/25, size diff 1.8 %, no leaks).
- Scorer unchanged on synthetic answers in a temporary key copy: all real -> met; all foil and 5 random -> not met.
- Spot check by eye (P01, P02, P13): frames 0, 5, 10, 11, 12, 21 s and waveforms; arm only, no trail or hint, gap black and silent.
