# Night log: WO53 part B raw-joint rhythm rerun (branch body-rawrhythm), 2026-11-18

- Rules `docs/RAWRHYTHM_RULES.md` written and pushed before any raw-joint value was computed.
- Code `scripts/body/rawrhythm.py`, tests `test_rawrhythm.py` (6, synthetic, pass). Smoke run on one performance per dataset (load, speeds, 20 windows) only; it found Motorica non-root position channels varying by 0.017 cm, so the rules were amended ("< 1 cm") before any result.
- Unit hyst-wo53b-run1 failed at start (log directory missing); rerun as hyst-wo53b-run2 (scan, extract, assemble, analyse, tables; cores 17-19).
- hyst-wo53b-run2: scan 0 bad (2,128 performances), extract 0 failures, all 310,065 WO52 rows with raw values; lamp recomputed equals WO52 point estimates exactly (max diff 0.0).
- Headline (pooled, mean of six vs lamp, cluster-share excess): chance 1 librosa -0.004 [-0.007, -0.001] vs +0.001; pulse v2 +0.008 [+0.002, +0.014] vs +0.000; chance 2 +0.084 / +0.070 vs +0.018 / +0.015. Condition of 7.84 item 3 as numbers per cell in the report. Report `docs/RAWRHYTHM_REPORT.md`, tables `docs/RAWRHYTHM_TABLES.md`. Stopped.
