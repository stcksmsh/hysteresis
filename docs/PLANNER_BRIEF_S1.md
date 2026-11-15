# Planner brief: S1 rebuild check results (BRAIN_SPEC 7.62), 2026-11-15

TO: planner. FROM: overseer, for Kosta. Report `docs/S1_REPORT.md` (branch body), with the verbatim notes and the overseer's measures.

## Results

- 6 pairs, original vs Run B rebuild: **same 4, original 2, rebuild 0.** The two "original" answers carry "Idk" / "Unsure, they are both
  decent". Expected per 7.59.4.2: "same".
- **Jitter note:** S02 "Second seems less flicky" (second = original). Measured on the rendered joint data, the S02 rebuild has no more
  acceleration sign changes than the original (1.8-3.0 vs 2.2-3.2 per s) and similar peak accelerations. Per 7.62.3 the wiggle fix is
  conditional on jitter in the notes; the measure does not show it.
- **Rebuild shrink:** the rebuild is up to about 10-20 % slower on the wrist joints in several pairs (e.g. S01 wrist roll 110.7 vs 123.4
  deg/s mean speed; S06 wrist bend 20.6 vs 25.7).
- **AIOZ notes (both versions, both AIOZ pairs):** "wait too much", "periods where they do nothing", "don't match the music", "too slow /
  small", "there is literally a DROP in this section". These are about the retargeted human data itself, not the vocabulary. The AIOZ
  originals move more slowly than the FineDance ones on shoulder and wrists (S05/S06 shoulder 10.5 / 6.9 deg/s vs FineDance 11.4-22.4).
  Step 1 of 7.61 had found kept-AIOZ gesture RMS 0.46-0.78 of FineDance's.

## Questions

1. **Does the vocabulary pass S1?** (a) Yes: no pair favours the rebuild against the original clearly, 4 of 6 "same"; T1b may start on
   Kosta's go **[recommended]** / (b) No: rerun S1 after a fix.
2. **Wiggle fix (7.62.3):** (a) not needed: the "flicky" note is not borne out by the measure **[recommended]** / (b) fix anyway.
3. **AIOZ in T1b (the sequencer learns which move when, how strong, to the music):** Kosta's notes say the AIOZ dancing itself does not
   follow the music and is small.
   - (a) T1b trains on FineDance only (the vocabulary keeps the AIOZ shapes); AIOZ windows stay out of T1b train/validation; T2 reports on
     FineDance held-out songs and, separately, AIOZ **[recommended: the sequencer should learn music-to-movement timing and vigour from the
     data Kosta judged on-music]**. Cost: FineDance train is 41,520 tokens per copy (166,080 with the 4 copies).
   - (b) keep the 50 % AIOZ cap in T1b;
   - (c) drop AIOZ everywhere, including retraining the vocabulary.
4. **Rebuild shrink:** report-only for now; T2's joint-range and vigour checks cover it **[recommended]** / or act now.
5. Record as 7.63.
