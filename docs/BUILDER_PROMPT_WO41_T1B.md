# Builder prompt: work order 41, T1b listener + planner training, then T2 (2026-11-15)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.64 and §7.65** (including overseer notes 7.64.10 and 7.65.6), then 7.59-7.63 where these do not
change them. No verdict. One arm. **Report T2 and STOP before T3.** You do not run Kosta's labelling session: the overseer serves it.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-t1b origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo41-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, `python -u`; read logs 1 min after start. Run on battery. Commit
and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env
`/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t1a,t1a2}/` (Run B vocabulary `t1a2/runB/best.pt`), the B7
checkpoint `epoch_006.pt` (load as T0 did: `k5_video_lanes.load_model`, chunks with carried state as `k5_data.song_lanes`), FineDance
`music_wav`. Out: `/secondary/hyst-data/body/t1b/`. Training resumable per epoch (the laptop can stop at any time). Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.59, 7.61-7.65; `docs/T0_RULES.md`, `docs/T1A2_RULES.md`, `docs/T1A2_REPORT.md`, `docs/S1_REPORT.md`; the T0 and
T1a2 code under `scripts/body/` (token features, gates, body pipeline, realised-stage jitter measure); `scripts/body/dialstudy_session.py`.

## The work

1. **Storage check (before anything big):** per-frame width of the full cortex state as 7.64.1 lists it (state each part's count),
   bytes per FineDance song and in total at float16 and float32. Precompute at 100 Hz for all FineDance songs (T0 split, FineDance only)
   to `t1b/cortex/`; reproduce one song's T0 ear/lane values from it (< 1e-5) as a check. Night log "STORAGE <numbers>".
2. **Rules note `docs/T1B_RULES.md`** (push before training): listener (rhythm 192 / affect 64, time-constant parametrisation and init,
   cross-connections), planner (how the 2-stage residual code is predicted, attention, embeddings), vigour bins and posture vocabulary
   (7.65.6), input-noise rule for teacher forcing, 60 s TBPTT with carried listener state, decision-time indexing (7.64.10), early-stopping
   rule and epoch cap, run-time sampling (7.65.6); the ear-only ablation model (same rules); retrieval control (7.64.8, transition weight);
   swapped-music pairing rule (seeded, tempo from the offline beat grid); held-out 60 s windows (7.65.6); every T2 measure with its exact
   formula, including the two repetition STOPs, the event-response detection rule, the 2 s history truncation, the affect probe (classifier,
   cross-validation folds, shuffled-label control, seeds). Tests for: causality (no music after decision time), carried state, mirror
   copies sharing music, bin/vocabulary round-trip, one tiny overfit run.
3. **Timing run + estimate** for the full model and the ablation (2 units in parallel: cores 6-13 / 14-19, 4 threads each). Night log
   "T1B ESTIMATE <hours, peak memory>". If each run is estimated at <= 24 h, start both training runs at once without waiting; otherwise
   STOP and wait.
4. **Kosta's music labels (prepare only, during training):** 20 songs per 7.65.6 (seeded), one 30 s clip each (still frame + audio, h264
   + aac), manifest of singles for `dialstudy_session.py` with the label set calm / sad / tense / energetic / light (add a label-set option;
   change nothing else). Write to `t1b/labels/`, night log "LABEL CLIPS READY". Do not open any answers file; the overseer passes the labels
   to you after Kosta's session.
5. **T2** after training, on the FineDance held-out songs, every measure in the rules note: the 7.59.4.3 list as amended in 7.65.6, the
   7.64.6 swapped-music STOP and reports, the 7.65.1 STOP and report, retrieval control beside the model, the ablation model beside the
   full model, gates at 1.25 through the full body pipeline, jitter at the realised stage. The affect probe runs once the overseer has passed
   you Kosta's labels; if they have not arrived, report everything else and mark the probe pending. Save every per-song value used, for
   recomputation.
6. **Done when:** `docs/T1B_REPORT.md` (every STOP with its value and threshold, all reports, train/validation curves) and "T1B READY
   <commit>" in `docs/NIGHT_LOG_body-t1b.md`, pushed. Then STOP. No clips, no viewing, no T3.
