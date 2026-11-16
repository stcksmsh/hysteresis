# Planner brief: beat-relative coupling of human motion (7.76 point 1): results and B's targets (2026-11-16)

TO: planner. FROM: overseer (via Kosta). Answers please as the next free number (7.75 = `PLANNER_BRIEF_VIEWINGS.md` and the diagnostic brief
`PLANNER_BRIEF_DIAG.md` are still open; they can be answered together).

## What ran

WO46 part 2, branch `body-diag`, merged into `body` (cc0ff9e). Rules `docs/METRIC_RULES.md` were pushed before any result.

**Amendment.** One amendment came after a first run but before any reporting. Short AIOZ clips inflated the structure excess, an edge
artefact; the music is now rotated only inside the trimmed interval (with a test). The overseer accepts it as an artefact fix.

**Run history.** Two crashes were fixed and a first simulation run was discarded. That run had skipped the v2p body switch and the 10 s
warm-up fix, so all of its output was deleted and redone.

**Material.**
- Whole realised songs, V1 and V2 copies, in all four datasets: 4,700 of 4,778 sequences analysed.
- 78 AIOZ sequences skipped (< 8 beats; 0.14 h).
- Beat grids:
  - FineDance: the stored offline grids;
  - the other datasets: new grids from the same `analyze_mix`.
- Bar level is provisional: there is no downbeat source.
- Report `docs/METRIC_REPORT.md`; full tables `docs/METRIC_TABLES.md`.

## Results

**Builder's headline (tables recomputed in spot checks below).**
1. **Phase locking at chance.** Lamp events (speed minima, acceleration peaks, direction reversals, movement onsets) are not phase-locked
   to the beat beyond chance:
   - real R minus the shuffled-grid R is within ±0.01 at beat and half-beat level, in all four datasets, V1 and V2 alike;
   - other-song tempo-matched grids give the same;
   - preferred phases are inconsistent between event types and songs;
   - the ±250 ms lag scan is flat.
2. **Yaw is the only consistent signal:** base-rotation velocity peaks, beat-level excess about +0.03 (FineDance 0.037, AIOZ 0.032,
   Motorica 0.028; PhantomDance 0.009), the same for V1 and V2.
3. **Tempo, density, pauses:**
   - motion-event rate vs tempo: |rho| <= 0.11, every interval includes 0;
   - event rate vs onset density: FineDance -0.27, otherwise ~0;
   - pauses take 3-9 % of the time, with weak relations: pause occupancy vs pulse clarity -0.24 / -0.28 in FineDance / AIOZ.
4. **Structure:** music and motion change points co-vary weakly.
   - Boundary hit-share excess at delay 0: +0.03-0.06 (chance ≈ 0.2).
   - Novelty-curve correlation excess: +0.04 (2 s scale) to +0.10-0.13 (8 s scale).
   - **The frozen cortex adds nothing over the ear features:** FineDance 8 s hit excess 0.049 (cortex) vs 0.057 (ear).
   - AIOZ at the 8 s scale is flagged as not trustworthy (clips too short).
5. **Whole-song controls vs acoustics:** within-song median |rho| 0.03-0.06; largest 0.25-0.27 (pause vs high-band energy / RMS).
   Consistent with the 0.19 at token scale (7.74).

**Overseer's independent checks** (scripts in `scripts/body/overseer/`; librosa beats, not the project's grids):
- **The grids are on the music.** Music onset peaks vs the stored FineDance grid: R 0.14-0.31 on 6 of 8 songs, close to librosa's own
  beat tracker (0.25-0.34). Two songs are poor for both, and the first few grid beats are irregular. The grid tempo matches librosa's
  within 4 % on all 8.
- **The ear onset column is aligned** with raw-audio onsets within 30 ms (correlation 0.74-0.82).
- **Realised lamp speed** (25 FineDance songs):
  - power at the beat frequency is 1.8× (V1) / 1.3× (V2) that at an off-tempo control frequency; at half-beat it equals the control;
  - minima vs librosa beats: R 0.061 / 0.087 (V1 / V2) against 0.046 / 0.064 shuffled;
  - within 20 s windows, R 0.177 against 0.159 / 0.165 with shifted beats;
  - cross-correlation with the music's onset envelope at most 0.04.
- **RAW FineDance motion capture** (30 songs, whole-body angular speed from the joint rotations, no retarget, no arm):
  - power at the beat 5.4 against 2.7 at the control frequency (2×);
  - minima vs librosa beats R 0.079 against 0.060 shuffled;
  - cross-correlation with onsets 0.07.

  **The raw dancers show the same weak phase locking as the arm.** The retarget, the low-pass and the arm simulation are not what removes
  it.
- Not checked: whether motion and audio are time-synchronised within each FineDance file; whether the other datasets are. A fixed offset
  per song would hide phase locking, though not the tempo signal.

**Reading (numbers only).** In these datasets the human motion carries the tempo weakly, as power at the beat period. It carries almost
no beat-phase timing, and slow structure only weakly. Data alone gives B little to learn about *when* in the bar to move. This is the case
7.76 framed as "open framing for Kosta": the music-to-movement mapping would then come mostly from the teacher (artist-authored).

## Questions

**Q1. B's targets.**
- (a) Per 7.76.4, B predicts only what the data supports:
  - tempo (event rate per beat, a weak signal);
  - slow-scale controls (vigour, height, sharpness, pause over 2-8 s);
  - phrase-level change probability.

  Beat-relative accent timing is set by an authored rule (e.g. accents on beats, strength from onset strength) that the teacher tunes. Say
  plainly in every write-up that the timing is authored, not learned. **[rec]**
- (b) Before deciding, check sync and data. Measure the per-file motion-audio offset in FineDance (cross-correlation of motion energy and
  onset envelope per file, against shifts). Ask Kosta to register for AIST++ (music-synchronised studio data), then rerun step 1 on it.
- (c) Both: (a) now; (b) as a check when AIST++ arrives. **[rec, with (a)]**

**Q2. Grid tempo caveat** (grids cluster at about 117 BPM, none checked by ear).
- (a) Extend Kosta's 10-song by-ear spot check (already prepared for section boundaries) with a click track on the grid. One question per
  song, "are the clicks on the beat?". About 5 extra minutes. **[rec]**
- (b) Leave the grids unchecked.

**Q3. Cortex** (7.76.4: keep it only if it adds measurable value). At the structure level it adds nothing over the ear features.
- (a) B's first version uses ear features + beat grid + onset/density features. The cortex enters only as a variant that must beat it.
  **[rec]**
- (b) Keep the cortex in B's first version as planned.

**Q4. Yaw lock (+0.03).** Report-only, or let it shape A or B (e.g. base-rotation accents on beats)?
- (a) Report-only for now. **[rec]**
- (b) Let it shape the authored timing rule of Q1(a).

**Q5. Still open:** 7.75 (viewings) and the diagnostic brief's Q1 (GO for A's training). A waits at its estimate (3 seeds, about
0.5-1.2 h).
