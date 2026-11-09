# Night log body-s3 (WO26A section)

## MORNING SUMMARY (WO26A, updated 2026-11-09 ~19:30)

- Rules file `docs/STAGE3_RULES_DATA_EVAL.md` committed and pushed (609afc6) before any long run; two dated amendments (Burger flux = audio low-band flux; thresholds obtained).
- **Done:** `s3/thresholds.json` (method v47-v2f): energy 0.3747, jerk 4.748e6 (1.25 x mean 3.799e6); 1,784 blocks, arm 0 of ic/fy/pr 100 Hz exports replayed on v2f with the pass2 CFG.
  Per-song mean jerk differs a lot (ic 7.1e6, fy 1.3e6, pr 2.2e6): the pooled mean is dominated by Instant Crush.
- **Done, code:** `s3_slow.py`, `s3_tempo_rms.py`, `s3_thresholds.py`, `s3_eval.py`, `test_s3_data.py` (4 tests pass; 3 data tests skip until the slow lanes exist).
- **Pending, blocked on mains power** (`/sys/class/power_supply/ADP1/online` = 0 since the start): unit `hyst-wo26a-data1` (raw L4 pass 57 min-ish, PCA fit, slow lanes, tempo/RMS) and unit `hyst-wo26a-eval1`
  (waits for the data unit, then the data tests and the pass2 reference run of `s3_eval.py`). Both poll and start by themselves.

## WO26A log

- 19:05 branch body-s3d from origin/body; rules written and pushed.
- Thresholds run: 6 threads (cores 6-11), JAX CPU, ~10 min. Smoke test of `l4_blocks` on song 022840: (136, 512), block count equals k5/lanes.
- `s3_eval.py` smoke test (25 check songs, pass2 rollouts): runs; numbers meaningless at that size.
