# Night log body-t0-aioz (WO37 Builder B)

- 0b30263: loader (restricted unpickler + test), adapter (round trip max abs 6D diff 2e-7), measures, FineDance reference and `docs/T0_AIOZ_RULES.md`, pushed before any AIOZ measure.
- Check run: 1624 pkl, 6011 person-sequences, derived fps mode 30.0 (0 off-mode). Details `docs/T0_AIOZ_CHECK.md`; data `/secondary/hyst-data/body/t0/aioz_*.json`, `contact_sheet.png`.
- **HOLD aioz 2.8 %** under the literal rule (168 persons, 1.52 h of 60.79 h): joint_speed (2) drops 5836, root_jump 332, hf_power 58. The literal (2) also prunes 58 % of FineDance itself (FOR USER, see rules note).
- Calibrated variant (thresholds of (2)/(3) = max(1 %, FineDance p95 of the same share)): 1852 persons kept (30.8 %, 19.28 h), `aioz_keep_calibrated.json`. Overseer/Kosta choose; Builder A continues with FineDance alone until then.
- Contact sheet looked at (3 dropped, 3 kept): plausible poses; no rule changed.

AIOZ CHECKED
