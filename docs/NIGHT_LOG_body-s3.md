# Night log body-s3 (WO26A section)

## MORNING SUMMARY (WO26A, 2026-11-09 ~21:00): DONE

- Rules `docs/STAGE3_RULES_DATA_EVAL.md` (609afc6, before the long runs) + two dated amendments. Branch `body-s3d`.
- Slow lanes: `/secondary/hyst-data/body/s3/slow/{train,val,check}/<id>.npz` (nb, 13) + `slow/norm.json`. 3,176 songs, 1,168,320 train blocks. PCA top-8 explained variance
  0.3752 0.1113 0.0897 0.0678 0.0393 0.0316 0.0289 0.0235, cumulative 0.767. Raw L4 block means kept in `s3/raw_l4/`.
- `s3/tempo_rms.json`: 3,176 songs (check bpm reused from s0/tempo.json after the 5-song check), median bpm 117.5.
- `s3/thresholds.json`: v47-v2f, energy 0.3747, jerk 4.748e6.
- `scripts/body/s3_eval.py` + `test_s3_data.py` (8 tests OK). Reference run on pass2: `s3/eval_pass2/bars.json`.
- Pass2 reference bars (357 songs): (a) PASS ext a 0.943 [0.911, 0.977], paired vs untrained 0.922 [0.891, 0.953]; (b) interleaved 2AFC 0.468 [0.407, 0.528], 54 pairs, shuffled 0.491; (c) JS between/within 0.484 (0.321/0.663);
  (d) median occupied 5 cm cells in 120 s = 385 (285 songs; the pass2 reference for bar (d)); (e) shoulder sd >= 8 deg in 0 % of songs (median 3.76 deg); (f) check-csv accepted on all three, e'1 2.1 vs limits 5.2-7.5, e'2 0.0 vs limits 0.007-0.014.
  Programs: ONE program used (program 1, all 144,095 blocks). Burger: shoulder sd vs B7 pulse proxy rho -0.03; wrist bend sd vs audio low-band flux rho 0.07.
- Held-out limit report: shoulder speed max 24.8 deg/s (0.28 of limit), acc max 177 deg/s^2 (0.59); no flags raised in this pooled summary.
- JS ratio 0.48 vs the spec's "about 0.69": the 0.69 was Stage 0's half-vs-half definition; the rules use odd-vs-even interleaved clips (BRAIN_SPEC 7.36.3), whose within-song JS (0.66) is larger. Not tuned. 2AFC (0.47) and shoulder sd (3.8 deg) match expectation.

## WO26A log

- 19:05 branch body-s3d from origin/body; rules written and pushed.
- Thresholds run: 6 threads (cores 6-11), JAX CPU, ~10 min. Smoke test of `l4_blocks` on song 022840: (136, 512), block count equals k5/lanes.
- `s3_eval.py` smoke test (25 check songs, pass2 rollouts): runs; numbers meaningless at that size.
