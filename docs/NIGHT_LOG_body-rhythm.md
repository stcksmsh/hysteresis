# Night log: WO52 movement rhythm vs beat and event responses (branch body-rhythm), 2026-11-18

- Rules `docs/RHYTHM_EVENTS_RULES.md` written; code `scripts/body/rhythm_events.py`, tests `test_rhythm_events.py` (8, synthetic, pass).
  Before the push only the synthetic tests and an input presence check (4,056 non-mirror sequences: q50 windows match A's windows; every
  song has librosa beats, a pulse v2 file and T0 lanes) were run. No human rhythm, response or event value computed.
- Unit hyst-wo52-ext1 killed by the OOM killer in the scan (window file re-read per row); fixed (b547070), rerun as hyst-wo52-ext2:
  scan 0 bad, extract 0 failures (4,056 sequences, 310,065 analysis windows of 3 and 4 s, 1,215 songs with music events).
- Unit hyst-wo52-ana1: results.json written; then failed on the histogram PNG (no matplotlib, no installs). PNG dropped (FOR USER),
  histograms as tables; `rhythm_events.py tables` writes `rhythm/tables.md` = `docs/RHYTHM_EVENTS_TABLES.md`.
- Headline: cluster share excess over similar-tempo chance +0.001 [-0.001, +0.003] (librosa), +0.000 [-0.003, +0.004] (pulse v2); over
  shuffled +0.018 / +0.015 (mainly AIOZ). Event lock: holds 1.3-1.8 x chance before novelty / dropout / onset events; bursts 1.4-1.5 x at
  dropout ends; family change fires at ~every token. Report `docs/RHYTHM_EVENTS_REPORT.md`. Stopped.
