# Planner brief: second pulse flash check (7.79 Q1 (d)) (2026-11-17)

Result `docs/PULSE_FLASH2_RESULT.md` (body 955e42f); material `docs/PULSE_FLASH2_MATERIAL.md`. Scored by the overseer from Kosta's answers.
One arm.

## What ran

20 blind items, each with two questions ("on the beat?", "right speed?"):
- 8 songs where the whole-song pulse sits at 2/3 or 3/2 of librosa, 4 each;
- the 2 first-check failures on new excerpts (these overlap the first excerpts by 16-20 s);
- each song shown with the pulse and with librosa.

## Results

| | pulse | librosa |
|---|---|---|
| on beat yes / partly / no | 1 / 8 / 1 | 6 / 3 / 1 |
| right speed | 6 / 10 | 6 / 10 |
| 3/2 group (pulse faster), right speed | 1 / 4 (3 too fast) | 4 / 4 |
| 2/3 group (pulse slower), right speed | 3 / 4 | 1 / 4 (3 too fast) |

- **The 3/2 group fails**, which is the 7.79 Q1 condition for (b), the harmonic-support readout.
- **The 2/3 group** favours the pulse's slower level, as fd_018 did in the first check. The one miss, fd_034, is a beatless ambient piece
  where both fail.
- **Level switching inside a 30 s excerpt** (5 notes): "double flashing", "speeds up before it should", "switches up without reason", "too
  fast, then slows back down".
- **Flashing through silence, beatless music and breaks** (4 notes, both sources).
- **Kosta, verbatim:** "more beat than accent signal (the accent/moment stuff should have a limit sortof? It should catch the distinct stuff
  or smth?)".

## Questions

1. **Pulse v2 scope.**
   - (b) as ruled: the harmonic-support readout, with each candidate scored by its own amplitude plus those at 2f and f/2. This favours
     binary levels: against 3/2, keeping 2/3-type slower levels where the slower level has support.
   - Add (s), stability: a level change needs sustained evidence, for example a longer hold and a higher margin than the current 2 s and
     20 %, and only at a phrase boundary or a large novelty.
   - Add (g), a beat-presence gate: no pulse events while low-band periodic drive is absent (silence, beatless music, dropouts). The pulse's
     state keeps running underneath, so the beat resumes in phase.
   - **Recommendation: (b) + (s) + (g) in one work order.** Rerun the numeric check, then show Kosta the same 20 items plus the first check's
     20, scored per item against his earlier answers. (g) also supplies the "dropout → hold" signal that 7.79's event level needs.
2. **"Catch the distinct stuff".** Kosta's notes ask for selective moments, not a uniform clock. Under 7.79 that is the EVENTS level of the
   lookahead scoring, not the pulse. Options:
   - (a) leave the pulse as the tempo source only, with events from the event detector (cortex/ear, PLANNER_BRIEF_CORTEX_EVENTS);
   - (b) also make the flash viewing show the event detector's events instead of a clock.

   **Recommendation: (a)**, plus an event-only flash check once the event source is ruled.
