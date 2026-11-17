# Night log: WO48 internal pulse (branch body-pulse), 2026-11-17

- Rules `docs/PULSE_RULES.md` pushed before any song was run. Model reuses B1's GrFNN integrator (`scripts/brain/grfnn.py`) unchanged.
  Before the push only synthetic signals were run (tests, a timing run on noise). Tests `test_pulse.py` 5/5 pass.
- Scan 1,341 songs, 0 bad. Run unit hyst-wo48-run1 (cores 14-19, 6 processes): 1,341 songs, 0 failures. Report tables `docs/PULSE_TABLES.md`, report `docs/PULSE_REPORT.md`.
- Headline: pulse most regular (median 8-event residual 2.1 ms vs librosa 6.7, grid 72.6); keeps 86 % of quiet passages (librosa 65 %);
  at Kosta's level on 5 of 8 V4 songs, fd_018 at 87 BPM (judged 71.5); about a third of all songs at 2/3 or 3/2 of both trackers; level jumps give long gaps.
- PULSE READY (commit: see next line of git log, "WO48 PULSE READY").
- Flash material unit hyst-wo48-flash1: 20 items Q00..Q19 in `/secondary/hyst-data/body/pulse/flash/` (manifest, key), two questions per item. Not served.
- PULSE FLASH READY. Stopped.
