# Planner brief: tempo source after pulse v2 (7.80 decision rule not met) (2026-11-18)

Results `docs/PULSE2_VIEW_RESULT.md` (body 9309750), `docs/PULSE2_REPORT.md`. Pulse v2 merged into `body` (fb3eacd); the overseer recomputed
its numbers. One arm.

## Results

- **Viewing, 20 excerpts:** "right speed": pulse v2 15, librosa 18. "Steady": pulse v2 19, librosa 20.
- **By 7.80, the DECISION RULE is NOT MET.** The oscillator bank is no longer tuned, and the tempo source goes to Kosta for a ruling.
- **Answers change between sessions on the same clips.** On identical tempo, 10 speed answers changed across sessions: 5 of 20 librosa items,
  all "too fast" → "right", and 5 of 15 unchanged pulse items, in both directions. The 3-item margin is within that.
  - On fd_018 the note says librosa is "perhaps 2x faster than it should be?" but the answer is "right".
- **What each source fails on** (all three viewings):
  - librosa doubles slow and ambient songs (fd_034 three times, fd_018, mo_LH6), and flashes through silence and breaks.
  - Pulse v2 is too slow on aioz_SZhU (at 1/2 or 3/4 of the beat) and ph_224, and too fast on fd_018 and fd_100.
- **Numbers over all songs (v1 → v2):**
  - switches 1.87 → 1.25 per minute;
  - 3/2 share 14.2 % → 8.6 %;
  - confidence: beat 0.38, silence 0.13, beatless 0.18, dropout 0.17.
- **The dance runs from offline sidecars** (Kosta, 2026-10-04), so a non-causal tempo source such as librosa is allowed.

## Question: the tempo source

Options:
- (a) librosa (period and phase) alone;
- (b) pulse v2 alone;
- (c) librosa's period and phase, plus pulse v2's confidence as the separate "beat present" signal for the planner's event level (breaks,
  silence);
- (d) (c) plus one rule against doubling: halve librosa's tempo when the song's low-band periodicity is weak and its tempo is above a
  stated value. This would be tested on fd_034, fd_018, mo_LH6 and a seeded sample.

**Recommendation: (c).** librosa won the viewing; offline use allows it. Pulse v2's confidence already separates beat passages from
silence, beatless music and dropouts (0.38 vs 0.13-0.18), which is what Kosta's break notes ask for. (d) is a patch; consider it only if
Kosta's next viewings keep marking doubling.
