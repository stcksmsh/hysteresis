# Night log: WO53 part B raw-joint rhythm rerun (branch body-rawrhythm), 2026-11-18

- Rules `docs/RAWRHYTHM_RULES.md` written and pushed before any raw-joint value was computed.
- Code `scripts/body/rawrhythm.py`, tests `test_rawrhythm.py` (6, synthetic, pass). Smoke run on one performance per dataset (load, speeds, 20 windows) only; it found Motorica non-root position channels varying by 0.017 cm, so the rules were amended ("< 1 cm") before any result.
