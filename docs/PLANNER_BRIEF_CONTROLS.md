# Planner brief: control representation (7.73 Step 0) and chunk joining: results and questions (2026-11-16)

TO: planner. FROM: overseer (via Kosta). Answers please as BRAIN_SPEC 7.74.

## What ran

- **WO43 (controls)**, branch `body-controls`, merged into `body` (892fd18). Rules `docs/CONTROLS_RULES.md` pushed before any value was
  computed. Two addenda:
  1. The movement-lead onset rule never fired and was relaxed. Lead is measured only, and the change came before any statistic was read.
  2. Overseer fix: the height bounds had been taken from the old table body. The realised stage simulates the v2p body (on a pillar,
     floor 1.0 m below the column top). The bounds are now z in [-0.569, 0.770] m: every lamp height the v2p body reaches with clearance
     >= 0. Everything was recomputed.
- Source: the realised 50 Hz trajectory of every kept 20 s window of every copy (V1, V2 and their mirrors).
  - FineDance 135,840 tokens / 168 songs.
  - AIOZ 370,280 tokens.
  - PhantomDance 138,840 tokens and Motorica 69,560 tokens (both "look check pending": Kosta's 12-clip check is not done).
- Normalisation fitted on the FineDance training split only. Bootstrap by song, 200 resamples.
- Report `docs/CONTROLS_REPORT.md`.
- **WO44 (chunk joining)**, branch `body-join`, merged (ecd95fb). Rules `docs/JOIN_RULES.md` pushed before the run. Report
  `docs/JOIN_REPORT.md`. Material: 37 FineDance validation and test songs, 60 s dances, realised stage. Methods:
  - A0 raw chunks (as E1's controls);
  - A1 decoder in 40-token blocks (as E1);
  - B whole-sequence overlap decoding with a Hann crossfade;
  - C raw chunks with the position jump at each join ramped out over 0.5 s.

## Results (overseer recomputed)

**Overseer checks.**
- Controls recomputed with independent code from the saved trajectories:
  - vigour parts, height, pause and sharpness are identical on 3 files / 800 tokens;
  - height bounds identical from an independent pose grid;
  - FineDance between-song shares and the vigour x accent Spearman match the report.
- Join ratios recomputed from the per-song values; all match.
- Tests pass: controls 8/8, joining 5/5.
- Not recomputed: the Step 0c lag tables and the structure-layer bootstrap.

**Controls, Step 0b.**
1. **Redundant pairs (|r| > 0.7) in all four datasets:**
   - vigour x joint speed and vigour x lamp speed. Expected: vigour is their first principal component, which carries 0.898 of their
     variance.
   - vigour x accent strength: Spearman 0.83 FineDance, 0.80 AIOZ, 0.86 PhantomDance, 0.81 Motorica.
   - pause probability x activity: true by construction.
   - PhantomDance also has vigour x pause.
   - Height is nearly independent of the others (|r| <= 0.06 against vigour, accent, sharpness and pause on FineDance).
2. **Between-song share of variance is small:** FineDance vigour 0.16, accent 0.18, pause 0.11, sharpness 0.07, height 0.05; AIOZ all
   <= 0.08. Most control variance is within a song.
3. **Pauses are rare:** pause probability (lamp below 0.05 m/s for > 0.25 s) is 0 in 92-96 % of tokens.
4. **Sharpness** (share of lamp acceleration energy above 3 Hz) is undefined (near-zero acceleration) in 0.0-2.0 % of tokens. Its FineDance
   median is 0.023, p95 0.108.

**Controls, Step 0c (human data, report-only).**

5. Strongest within-song lag-0 Spearman between a control and an acoustic measure:
   - FineDance: vigour x high-band energy 0.19, accent x high band 0.19, vigour x RMS 0.18;
   - AIOZ: pause x RMS -0.16;
   - PhantomDance: pause x RMS -0.17;
   - Motorica: vigour x RMS 0.14.
6. Structure: motion boundaries within ±1 token of a music boundary, minus chance:
   - FineDance +0.024 [0.014, 0.032] (cortex-based music boundaries +0.021);
   - AIOZ +0.060;
   - PhantomDance +0.031;
   - Motorica +0.019.

   Windows are 20 s, so phrases longer than about 10 s cannot appear.

**Clip pairs for Kosta's Step 0b' viewing.** 15 pairs, 8 s each, FineDance validation and test, rendered, not served. The other controls
are matched, with these residual differences (sum over the other four, in sd units):
- height 0.18-0.20, sharpness 0.21-0.31, continuity 0.52-0.68;
- vigour 1.93-3.20: the low/high vigour clips also differ in accent by 1.50-1.60 sd;
- accent 1.68-2.55: the low/high accent clips also differ in vigour by 1.33-1.99 sd.

The vigour and accent pairs therefore cannot separate the two controls.

**Chunk joining (lamp power above 3 Hz, ratio to continuous human, mean over songs [95 % bootstrap by song]).**

7. **Human chunks re-joined through the decoder are at human level:**
   - A1 0.88 [0.81, 0.97];
   - B 0.86 [0.79, 0.94];
   - both inside the target interval (P10-P90 of per-song human values, 0.0008-0.0035).

   The decoder and the vocabulary add no high-frequency power of their own.
8. Raw controls as in E1 (A0): retrieval 2.51, random 3.50. The jump ramp C brings them to 1.43 and 1.91, inside the interval.
9. Decoded controls and the model stay high whatever the joining:
   - decoded retrieval: A1 3.65, B 2.88;
   - decoded random chunks: A1 4.47, B 4.44;
   - E1 model (seed 41101, 17 test songs): A1 4.43, B 4.35. Ratio of means 2.50 / 2.44 at the lamp, against 1.37 per joint.
10. Frozen-pose share: 0.17-0.25 for the decoded controls and the model, 0.095 for human.
11. **Reading (numbers only):** the excess is in token sequences that do not form one human movement (decoded gesture plus posture-knot
    sequences), not in the joins. Overlap decoding equals blocks on human and model. Not separated: how much comes from posture knots and
    how much from gesture codes.
12. Cost of joining: about 0.01 s per 60 s of dance for either decoder method.

## Questions

**Q1. Vigour and accent strength overlap (Spearman 0.80-0.86).**
- (a) Keep accent as a *pattern* only: the 8 sub-slots divided by their token mean (shape, not level). Vigour carries the level. Accent
  density leaves the 0b' viewing. **[rec]**
- (b) Residualise accent strength on vigour (within dataset) and keep it as a second level control.
- (c) Keep both as defined; A's intervention matrix shows whether they act separately.

Recommendation (a): vigour already carries the level. The shape (where in the half-second the accents fall) is the part vigour cannot
say.

**Q2. Pause / activity.** The two are redundant by construction, and pause is 0 in 92-96 % of tokens.
- (a) Keep pause probability only, as the continuity control (rare events are real). Drop activity. **[rec]**
- (b) Replace both with a continuous measure: the token's p10 lamp speed / token mean speed.
- (c) Keep both.

**Q3. Kosta's 0b' viewing (~15 min).**
- (a) Serve 12 pairs now: vigour, height, sharpness, continuity; drop the 3 accent pairs per Q1(a). The vigour pairs carry an accent
  difference of 1.5-1.6 sd: say so in the report, and count a "seen" vigour as vigour+accent level. **[rec]**
- (b) Rebuild the vigour and accent pairs with accent residualised first (needs Q1(b)), then serve all 15.
- (c) Serve all 15 as built.

**Q4. Chunk joining.** The 7.73 target ("re-joined human chunks reach human-level high-frequency power") is met by the existing decoder
(A1) and by overlap (B). The excess at the model is not caused by joining.
- (a) Close the parallel task. Keep A1 for speed parity with E1, or B: equal on human, negligible cost. Use re-joined human A1 as the
  jitter reference in S-B. Add a small report-only diagnostic before A: posture-knot vs gesture contribution to lamp power above 3 Hz and
  to the frozen share (decoded retrieval with human posture knots, and vice versa). **[rec]**
- (b) Close it without the diagnostic.
- (c) Try a posture-knot smoothing method (untrained) before A.

**Q5. Music relation on human data is weak** (within-song |rho| <= 0.19; boundary alignment +0.02 to +0.06 over chance). This is the
ceiling a listener can learn from these datasets at the token scale.
- (a) Proceed to A as 7.73 orders. Report B's S-A numbers against these human values, not against an absolute bar. **[rec]**
- (b) Before A, run Step 0c on longer windows (whole songs, not 20 s), to see phrase-scale relations the 20 s windows cut off.
- (c) Both: (b) runs in parallel with A on separate cores.

**Q6. 7.72.** The answer to `PLANNER_BRIEF_E1_RESULTS.md` (Q2-Q5: jitter reference, posture drift, no T3, AIOZ held-out) never reached
the overseer. Please resend its text, or confirm that 7.73 supersedes it.

**Q7.** Record as 7.74.
