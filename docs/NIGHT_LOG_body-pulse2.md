# Night log: WO51 pulse v2 (branch body-pulse2), 2026-11-17

- Rules `docs/PULSE2_RULES.md` written; only synthetic signals run before the push. Tests `test_pulse2.py` (13), `test_pulse2_score.py` (1), `test_pulse.py` (6), `test_dialstudy_wo48.py` (1) pass.
- Run unit hyst-wo51-run1 (cores 14-19, 6 processes): 1,341 songs, 0 failures; 1,270 songs of at least 12 s in the summaries. Report
  `docs/PULSE2_REPORT.md`, tables `docs/PULSE2_TABLES.md`.
- Headline: level switches per minute median 1.87 -> 1.25; 3:2 share vs librosa 0.327 -> 0.257; confidence median beat 0.38, silence 0.13,
  beatless 0.18, dropout 0.17; per-song median confidence 0.20 (drive term limits).
- PULSE2 READY (commit: see next line of git log, "WO51 PULSE2 READY").
