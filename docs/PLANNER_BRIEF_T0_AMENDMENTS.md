# Planner brief: Kosta's amendments to the imitation-training plan (BRAIN_SPEC 7.56.9-11), 2026-11-14

TO: planner. FROM: overseer, for Kosta. Two DEFAULTs of 7.56 changed by Kosta. T0 has not started.

**1. Data: FineDance + AIOZ-GDANCE (strikes "FineDance only").**
- AIOZ: 16.7 h, 1,624 group-dance clips; its licence wording ("non-commercial artistic projects") matches FineDance's. FineDance public
  part is 7.7 h (203 sequences, 181 distinct songs).
- AIOZ motion is reconstructed from internet video, so it is likely noisier. It is checked and pruned before use, by a rule fixed before
  any AIOZ number is seen: drop a dancer if wrist/head path power above 3 Hz is above FineDance's p95, or > 1 % of frames have joint or
  root speeds above FineDance's p99.9, or > 20 % of frames are frozen. If < 30 % survive, AIOZ is dropped. Same low-pass cutoffs and 1.25
  gates as FineDance; hours always reported per dataset.
- Split unit: song (FineDance) / YouTube id (AIOZ), one seeded split over both.

**2. Variant: V1 and V2 pooled, no label (replaces "one model, one variant").**
- Every clip gives two training examples: the arm as the dancer's arm (V1) and the arm as the dancer's whole body (V2). Same music, two
  very different valid movements.
- Kosta: "a dance isn't one solution, it's freedom." The model should treat both as valid answers to the same music; the
  mixture-density head's sampling is that freedom. No 0/1 variant input; one style at run time.
- Overseer's concern, for discussion: the same joint means different body parts in V1 and V2 (shoulder = arm raise vs torso lean). With
  two conflicting targets per input, the risks are (a) averaging into small, mean-pose motion, (b) incoherent mid-phrase switching. The
  mixture head and the autoregressive input should prevent (a) and mostly (b); this is untested.
- Safeguards: T2's existing stop rules (joint range < 50 % of the data's, frozen pose) catch (a). Added, report-only: per output window
  on held-out songs, distance to the nearest V1 and nearest V2 target window of the same song (shows uses both / switches / averages).

**Questions**
1. Any objection to pooling V1 + V2 without a label, given the safeguards? Should T1 size the mixture head for it (e.g. more than 5
   components)?
2. Is the AIOZ prune rule acceptable, or should the low-pass cutoff be recomputed on AIOZ instead of reused?
3. Record as 7.57 (or as amendments to 7.56).
