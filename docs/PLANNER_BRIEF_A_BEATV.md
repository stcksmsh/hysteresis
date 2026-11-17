# Planner brief: beat verification V1-V4 (7.77) and the first motor grammar A (7.73/7.75/7.76): results and next steps (2026-11-17)

TO: planner. FROM: overseer (via Kosta). Answers please as BRAIN_SPEC 7.78.

## What ran

- **WO47 (beat verification)**, branch `body-beatv`, merged into `body`.
  - Rules `docs/BEATV_RULES.md` pushed before any result. Report `docs/BEATV_REPORT.md`, tables `docs/BEATV_TABLES.md`.
  - Order: V2 (published anchor) and V3 (sync) first, then V1 (local locking), then V4 material.
- **WO45 / WO45B (A)**, branch `body-grammar`, merged into `body` (f76624e). Rules `docs/A_RULES.md` with addenda 1 (7.75) and 2 (overseer
  fixes), each pushed before the run it governs. Report `docs/A_REPORT.md`.
  - Data: FineDance + AIOZ + PhantomDance + Motorica, all copies.
  - Model: 1.33 M parameters, 3 seeds.
  - Checks on 200 held-out starts (2 samples each), realised stage.
- **Overseer fix 1 of A's checks.** Four defects were found and fixed before this brief:
  - the pause intervention never ran (train p10 = p90 = 0);
  - the V1/V2 match used requested, not realised, sharpness;
  - a coherence ratio was computed as a mean of per-song ratios;
  - per-start values were not saved.

## Results: beat verification (overseer recomputed where stated)

1. **V2 published anchor.**
   - BAS on raw FineDance: 0.227 (angular-speed proxy) / 0.218 (approximate forward kinematics; no SMPL-X offsets locally).
   - Published ground truth: 0.2120. The overseer fetched it from Lodge, CVPR 2024, Table 1, which follows the AIST++ definition. Inside
     the ±25 % band, so the pipeline is not suspect.
   - **But the shifted-beat chance level of the same score is 0.225 / 0.214.** BAS minus chance = +0.003 [-0.003, 0.009] on raw data. On
     the realised arm it is ±0.006.
   - **The published ground-truth value itself is at chance.** The papers do not compare it with a chance level.
   - Code variant (sum over music beats vs kinematic beats) not confirmed: the evaluation code was not reachable; the music-beat sum is used.
2. **V3 sync.** Per FineDance file, the best motion-energy vs onset-envelope offset is spread over ±1 s:
   - only 8 % of files are within 33 ms;
   - the mean cross-correlation curve is flat;
   - no consistent per-file sync offset.
3. **V1 local locking (8-beat windows, tempo and phase re-fitted per window).**
   - **The project grid is locally irregular:** median 8-beat line residual 79 ms, against 8.4 ms for librosa (overseer recompute,
     40 songs).
   - With the project grid nothing locks.
   - With librosa's local lines:
     - **yaw (base-rotation) velocity peaks lock to the beat period** in all four datasets (excess +0.05 to +0.48). But they are evaluated
       only in windows with fast regular base rotation (>= 6 peaks in 3.5 s), the phase differs per song, and the control removes period
       locking, not phase. So this is tempo locking of periodic rotation, not beat-phase timing. The overseer's own 19-song recompute of
       yaw was not significant.
     - Lamp speed minima and acceleration peaks do not lock (AIOZ +0.02).
     - Raw-mocap minima: +0.012 [0.003, 0.019].
4. **V4, Kosta's flash check: done** (`docs/BEATV_V4_RESULT.md`).
   - Setup: 10 songs × 2 grids, blind, 30 s excerpts at or above median loudness. A white disc flashes at each beat (Kosta found audio
     clicks hard to hear over the music).
   - **librosa: 8 yes, 2 partly, 0 no. Project grid: 3 yes, 6 partly, 1 no.**
   - Kosta on librosa: "Perfect 4/4 basically", "finds the 4/4", "on the kick pattern when it exists, when it doesnt it catches the percs".
   - Kosta on the project grid: "entire sections without anything", "dropouts", and on one song "tries to follow the vocals as a beat,
     becomes WAY too fast". Overseer check: the longest project-grid gap is 8.8 s on fd_183.
   - **librosa's flaw is the metrical level.** On a slow song with hats (fd_018), Kosta: "we follow the FASTEST element (hats are always
     fast) ... the rim is 1/4 the hats and is perhaps a better thing to track". On an AIOZ song: "tries to hit every hit of fast percs ...
     too fast?". Also: "misses the drop doubling of kicks, but thats ok, cant hit that speed anyway on servos".
   - Overseer check: librosa puts fd_018 at 143 BPM. Over all 1,341 songs, librosa tempo is never below 80 BPM and above 150 BPM for 7 %.
     Its default tempo prior (`start_bpm` 120) pulls slow songs to double time.

**Reading (numbers only).** The measurement worry is real for the project grid (locally irregular), but not for the conclusion. With a
regular grid, and on raw data scored by the published metric, the dancers' movement timing is at chance relative to the beat. The motion
carries the tempo (period power, periodic base rotation), not beat-phase accents.

## Results: A

1. **Training.**
   - Validation 18.42 / 18.47 / 18.45; without controls 21.7-21.8 (controls are worth about 3.3 nats).
   - Gesture code-1 head 4.85 against chance 6.93.
   - **All three seeds ran to the 40-epoch cap while still improving** (about -0.01 per epoch at the end; learning rate never halved).
   - Train/validation gap 2.2-2.3 nats in total.
2. **Smoothness: E1's problem is gone.**
   - Lamp power above 3 Hz against re-joined human A1: 1.05-1.10 (mean of per-song ratios), 0.92-0.96 (ratio of means, overseer
     recompute).
   - Frozen share about 0 (human 0.003).
   - Direction changes 1.44-1.46 /s (human 1.45).
   - Posture / gesture split: A's posture with human gestures 0.93-0.95; human posture with A's gestures 1.12-1.16.
3. **Control following.**
   - Substitution: A's output matches its own request (error 0.41) far better than another performance's request (0.80); correlation with
     the request 0.55, against 0.31 for shuffled requests.
   - Intervention (in sd of human window means; overseer recompute agrees in direction and size):
     - vigour -> vigour 2.5-2.7;
     - height -> height 4.5;
     - sharpness -> sharpness 0.6-0.7;
     - direction -> vertical direction 0.3;
     - accent pattern -> accent centre 0.05-0.13 (weak).
   - Cross-talk:
     - vigour also raises direction changes (+1.3) and base-rotation speed (+1.6), and lowers pause (-0.4) and accent centre (-0.6);
     - height lowers sharpness (-0.2).
   - **Pause is not followed.** A full pause request (0 -> 1 over 18 s) moves realised pause by only +0.02-0.07 sd, and *raises* vigour
     (+0.24 to +0.77) and sharpness (+0.44 to +0.55 in the report's units). Pauses exist in only 4-8 % of training tokens.
4. **Coherence (ratio of means, after fix 1):**
   - control cosine A / human 1.01-1.03 (2 s) and 0.99-1.02 (4 s);
   - gesture-family repeat 0.84-0.86 (2 s) and 1.01-1.08 (4 s);
   - with the motif state turned off, 4 s repeat drops to 0.84-0.95 and 2 s to 0.70-0.86.
5. **Residual gesture stage:**
   - all 1,024 codes used;
   - mutual information with stage 1: 1.10 nats;
   - the decoded stage-2 gesture is about 17 % of the gesture RMS.
6. **S-B clips ready, not served:** 6 FineDance excerpts × 7 clips: human; A with own / other / shuffled / constant controls; V1 vs V2
   matched on realised sharpness (|diff| ≤ 0.0003).

## Questions

**Q1. Beat-relative accent timing (the decision 7.77 deferred to after V1-V4).**
- (a) **Authored rule**, tuned by the teacher and stated as authored in every write-up. B's first version predicts tempo, slow controls and
  phrase change (7.77 Q1). Beat times come from librosa (regular), (Q2, Q2b). **[rec]**
- (b) Wait for AIST++ (Kosta's registration) and V4 before deciding.
- (c) Learn timing from the yaw period-locking only.

**Q2. Beat grid for B and for any authored timing.** V4 favours librosa (8/2/0 against 3/6/1).
- (a) librosa beats replace the project grid everywhere new (B, authored timing, viewings). The project grid stays only where earlier
  results used it (reproducibility). **[rec]**
- (b) Keep the project grid.

**Q2b. Metrical level** (librosa doubles slow songs; Kosta: track the kick/rim, not the hats; the servos cannot follow very fast pulses).
- (a) Choose the pulse level per song: compute both the librosa beat and its half-time. Pick the level whose beats carry more low-band
  (kick/rim) onset strength. Cap the pulse the arm is asked to accent at a stated rate (e.g. ≤ 2.5 Hz; state the servo basis). Validate
  on the same 10 songs by a second short flash check. **[rec]**
- (b) Lower librosa's tempo prior (e.g. `start_bpm` 90) and keep one level.
- (c) Leave as is; the teacher handles it.

**Q3. A's training length.** All seeds stopped at the cap while improving.
- (a) Retrain A to convergence: early stopping as ruled, cap raised to 100. Then rerun the checks. Cost about 1.5-2.5 h for 3 seeds on
  this laptop. **[rec, with Q4 (a)]**
- (b) Keep the current A.

**Q4. Pause is not followed.**
- (a) In the retrain (Q3), up-weight windows containing pauses (state the factor), and give the pause request at least the same corruption
  and dropout treatment as the others. Report the pause intervention again. **[rec]**
- (b) Drop pause as an A control: pauses come from an authored rule (e.g. hold the pose) placed by B / the teacher.
- (c) Keep A as is and report.

**Q5. Cross-talk** (vigour also drives direction changes and base speed; vigour lowers the accent centre).
- (a) Report-only. Human data has the same couplings (vigour x accent Spearman 0.8); judge by eye in S-B. **[rec]**
- (b) Reweight the auxiliary control loss.

**Q6. Residual gesture stage.**
- (a) Keep it (MI 1.10 nats, about 17 % of gesture RMS). **[rec]**
- (b) Drop it.

**Q7. S-B viewing (Kosta, ~10 min).**
- (a) After the retrain (Q3/Q4), on the new A. **[rec]**
- (b) Now, on the current A.
