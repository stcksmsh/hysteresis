# Builder prompt: work order 41, T1b E1 baseline (listener + planner), lookups, then T2 (2026-11-15)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.63-7.68** (including every overseer note in 7.64.10, 7.65.6, 7.67 and 7.68.11), then 7.59-7.62 where these do
not change them. Wording per 7.66.7. No verdict. One arm. **Report T2 and STOP before T3.** You do not run Kosta's labelling session: the
overseer serves it. This work order is order steps 1-3 of 7.67 only (E1 with 3 seeds): no ablations, no variants (E3-E5), no pitch augmentation, no teacher
stage.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-t1b origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo41-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, `python -u`; read logs 1 min after start. Run on battery. Commit
and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env
`/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t1a,t1a2}/` (frozen vocabulary `t1a2/runB/best.pt`), the B7
checkpoint `epoch_006.pt` (load as T0 did: `k5_video_lanes.load_model`, chunks with carried state as `k5_data.song_lanes`), FineDance
`music_wav`. Out: `/secondary/hyst-data/body/t1b/`. Training resumable per epoch (the laptop can stop at any time). Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.59, 7.61-7.67; `docs/T0_RULES.md` (note its per-column `token_lookahead_s`), `docs/T1A2_RULES.md`,
`docs/T1A2_REPORT.md`, `docs/S1_REPORT.md`; the T0 and T1a2 code under `scripts/body/` (ear features, token features, gates, body
pipeline, realised-stage jitter measure); `scripts/body/dialstudy_session.py`.

## The work

1. **Causality list first (7.68.1):** for each of the 44 ear features and every cortex input, the window it uses relative to the frame
   time, and any offline whole-song fact it rests on (beat grid). LIST them; do NOT change any input. The planner must see music only up
   to decision time (test it). Night log "CAUSAL <list>".
2. **Storage + precompute:** per-frame width of the full cortex state (7.64.1, each part's count), bytes per song and total at float16 and
   float32; then precompute at 100 Hz for all FineDance songs to `t1b/cortex/`; reproduce one song's T0 values (< 1e-5). Night log "STORAGE <numbers>".
3. **Rules note `docs/T1B_RULES.md`** (push before training), everything fixed in it:
   - listener (rhythm 192 / affect 64, time constants and init, cross-connections), planner (how the 2-stage residual code is predicted,
     attention, embeddings), parameter counts per part (7.66.2c), size no larger than specified (7.63.5);
   - vigour bins and posture vocabulary per 7.63.8, fitted on the training split before training (posture variance explained: STOP if
     < 0.9); loss and nucleus sampling per 7.63.8; input-noise rule; 60 s TBPTT with carried listener state; decision-time indexing;
     early stopping and epoch cap; train/validation gap per epoch;
   - FineDance only, 4 copies (7.63.3); grouping by performance in evaluation (7.67.5 note);
   - 3 seeds (7.68.9), seeds named; mean and spread reported for every T2 number;
   - retrieval control (7.64.8, transition weight) and random-human-chunk control (same transition cost, no music);
   - swapped-music rule and STOP threshold per 7.68.5 (3 partners within 5 %, seeded, tempo from the offline beat grid; fill from
     validation, then half/double tempo; bootstrap by song, seed fixed);
   - held-out 60 s windows (7.65.6); every T2 measure with its exact formula (list in step 6), the event-detection rule, the 2 s history
     truncation, the affect probe and passage test (classifier, folds, shuffled-label control, seeds).
   Tests: causality (no music after decision time), carried state, mirror copies sharing music, bin/vocabulary round-trip, one tiny
   overfit run.
4. **Timing run + estimate** for 3 E1 seeds in parallel (cores 6-9 / 10-13 / 14-17, 4 threads each), and a Kaggle package per 7.68.11
   (derived features + script, private dataset, NOT uploaded) in `t1b/kaggle/`. Night log "T1B ESTIMATE <hours, peak memory>". If the 3
   seeds finish in <= 24 h, start them without waiting; otherwise STOP and wait (Kosta decides on Kaggle).
5. **While E1 trains (cores 18-19, nothing here changes E1):**
   - Lookups for the reviewers (7.66.2 a-d) and the 7.67.2 sync check per FineDance sequence, plus the two feature forms of 7.67.3 as a
     report: `docs/T1B_FACTS.md`. Night log "FACTS DONE".
   - Kosta's label clips (7.68.6, 7.68.11): all 39 test + validation song groups (one sequence per group, seeded), three 15 s passages
     per song (seeded starts), still frame + audio, h264 + aac; one manifest of singles for `dialstudy_session.py` with labels calm / sad / tense / energetic / light
     (add a label-set option; change nothing else). To `t1b/labels/`, night log "LABEL CLIPS READY". Do not open any answers file; the
     overseer passes you the labels after Kosta's session.
6. **T2** after training, FineDance held-out songs as the main result, AIOZ held-out report-only and separate (7.63.3). Every measure:
   7.59.4.3 as amended by 7.65.6; 7.64.6 (swapped-music STOP with 3 songs, event response, 2 s memory); 7.65.1 (identical-shape STOP,
   triples per minute); 7.63.8 (diversity, 8 samples per song); 7.66.3 (both controls, self-similarity at 2/8/30 s, endpoint jerk and
   direction changes, approximate repetition, all aesthetic numbers on realised trajectories with commanded vs realised, AIOZ-only code
   share); train songs per genre (7.63.5); gates at 1.25 through the full body pipeline. Kosta's labels must reach you before T2 is computed
   (7.68.6): if they have not arrived when training ends, STOP and wait. Save every per-song value used, for recomputation.
7. **Done when:** `docs/T1B_REPORT.md` (every STOP with its value and threshold, all reports, train/validation curves) and "T1B READY
   <commit>" in `docs/NIGHT_LOG_body-t1b.md`, pushed. Then STOP. No clips of generated dance, no viewing, no T3.
