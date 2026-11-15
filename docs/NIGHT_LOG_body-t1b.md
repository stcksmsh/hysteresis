# Night log, body-t1b (WO41, T1b E1 baseline)

Branch `body-t1b` (from origin/body 9f410d9). Env `/secondary/hyst-env/brain`. Cores 6-17 mine; WO42 on 18-19.

## CAUSAL (2026-11-15)

Full list: `docs/T1B_CAUSAL.md`. Summary:
- 44 ear features: one centred STFT (2048, hop 441), lookahead 23.2 ms for every column; global normalisation, no per-song statistic.
- Cortex input = 44 ear + 2 beat-grid phase. The beat-grid phase is an offline whole-song fact (online PLL run over the whole file, then interpolated between beats, so the
  phase at t uses the next beat, up to one beat interval ahead). Cortex layers, hippocampus, surprisal and arousal are causal given their input.
- Ear energy (1.0 s lookahead) is NOT an E1 input.
- Planner for chunk k reads listener step 25k-13 (last 50 Hz step at or before chunk start - 0.25 s); k = 0 reads the zero state.
- No input changed.

## STOP posture vocabulary (2026-11-15)

256-entry posture-change k-means explains 0.847 of variance on train (0.838 validation), below the 0.9 STOP of 7.63.8. Checked 200 iterations, 2 seeds; deltas heavy-tailed,
joints nearly uncorrelated; 1024 entries would give 0.914. No training until the overseer rules. Cortex precompute (running) and other independent steps continue.
Cortex reproduction (fd_001 vs T0 lanes): ear 0, arousal 0, s10 0, h_abs 2.9e-6; float16 round trip of h: max abs 0.0625.
Code: scripts/body/t1b_cortex.py, t1b_tokens.py (tokens encoded with runB, 812 files in t1b/tokens/).

## LABEL CLIPS READY (2026-11-15)

39 test+validation FineDance groups (19 test, 20 validation; one seeded sequence per group), 3 seeded 15 s passages each = 117 clips (still frame + audio, h264 + aac), in
`/secondary/hyst-data/body/t1b/labels/` (`clips/`, `manifest.json` with labels calm / sad / tense / energetic / light, `passages.json` with group, sequence, start, split). Seed 36401.
`dialstudy_session.py`: a manifest object may carry `"labels"` (the only change). Session build checked in a temp dir (117 items); no answers file touched. Overseer serves the session.
Code: scripts/body/t1b_labelclips.py.

## FACTS DONE (2026-11-15)

`docs/T1B_FACTS.md`: 44-feature definitions (global normalisation), alignment checks, parameter counts (1,820,192; residual posture 1,926,944), genres per split, the two feature forms.
Finding: 5 sequences have audio shorter than motion by > 0.5 s, two by 18-20 s (fd_043 validation, fd_059 train); E1 drops tokens past the audio end. Onset/movement lag: no systematic offset or drift, but per-sequence correlation is only about 0.05, so sub-0.1 s alignment per sequence is not confirmed.

## STORAGE (2026-11-15)

Per-frame width 2105: modes 2048 (4 layers x re/im x 256), surprisal 4, surprisal-valid 4, log-precision 4, arousal 1, ear 44. 100 Hz, 203 FineDance sequences, 7.656 h = 2,756,221 frames.
- float16: 421 kB/s, 57.2 MB per song, **11.6 GB** total (on disk 11 G). float32: 23.2 GB. (50 Hz averaged form would be half.) Disk free 258 GB.
- Reproduction of fd_001 against T0 lanes: ear 0, arousal 0, s10 0, h_abs 2.9e-6 (< 1e-5). float16 round trip of h: max abs 0.0625 (relative about 5e-4).
- Beat-grid fact (all 203 songs): median inter-beat interval 0.51 s; mean time from a frame to the next beat 0.76 s (inflated by tracker gaps); longest gap 71 s (a beat-less passage), so the beat-phase input can look far ahead there.
- Files: t1b/cortex/<fd_NNN>.npy, t1b/cortex/beats/<fd_NNN>.json, t1b/cortex_norm.npz (train mean/sd).

## T1B ESTIMATE (2026-11-15)

Timing run, 3 trainers in parallel (cores 6-9 / 10-13 / 14-17, 4 threads each, 4 slots x 4 copies): about 8.4-9.2 s per 60 s window step (includes first-read of the data); peak memory 1.23 GB per run (limit 8 G).
One epoch = about 115 window steps (154 train sequences, 4 slots) = about 17 min + validation and train-subset evaluation about 3 min = **about 20 min per epoch**.
Early stopping typically 15-30 epochs = **5-10 h**; the epoch cap of 60 = **20 h**. Three seeds in parallel: **<= 24 h in every case, so they run locally** (Kaggle package ready in t1b/kaggle/, not uploaded).
Not started: waiting for the posture ruling (7.70).

## T2 code ready (2026-11-15)

scripts/body/t1b_t2*.py: generation (nucleus 0.9, 8 samples), swapped-music + 2 s truncation likelihoods, retrieval and random-chunk controls (cached train database), realised simulation with gates on 3 x 20 s windows, all per-dance measures, affect probe and passage test, diversity, seed aggregation with STOP checks.
Smoke-tested end to end on a throwaway 1-epoch model (deleted). Findings: 17 of 23 test songs give a 60 s dance from 10 s (audio >= 70 s); the human reference keeps all rows regardless of the T0 gate (most human windows fail some gate); likelihood is masked by ok.
Not done: AIOZ held-out (needs cortex states for 41 test clips + token encoding of AIOZ dancers), AIOZ-only code share. Waiting for the posture ruling (7.70) before training.

## 7.71 applied (2026-11-15)

Label session cancelled: affect probe and matched-passage test removed from T1B_RULES and the code (t1b_t2c.py deleted); added report-only vigour-vs-ear-energy and posture-height-vs-ear-energy correlations (model vs human). T2 no longer waits for labels. Label clips stay on disk unused. Training still waits for 7.70.

## E1 TRAINING STARTED (2026-11-15)

Units hyst-wo41-e1-s1, -s2, -s3 (seeds 41101, 41102, 41103; cores 6-9 / 10-13 / 14-17, 4 threads, MemoryMax 8G, swap 0). Script scripts/body/t1b_run.sh IDX (resumable per epoch: rerun it after a stop). Logs t1b/logs/e1_seed<seed>.log, output t1b/e1/seed<seed>/ (ckpt.pt, best.pt, log.json, done.json).
Posture head residual 2 x 256 (7.70); loss = five equal cross-entropies, per-head train and validation loss in every epoch record. Estimate 20 min per epoch, 5-10 h typical, 20 h at the 60-epoch cap.

## fd_192 and E1 RESTARTED (2026-11-16)

Seed 41102 crashed in load_tokens: fd_192 ("cheers_part2", 520 motion frames = 17 s) is shorter than one 20 s T0 window, so T0 kept 0 windows (n_win 0) and the token files have 0 tokens. It is the only song affected (scan of all 812 token files: exactly fd_192 x 4 copies; none with fewer than 10 tokens besides). It is a train song; 153 train, 26 validation, 23 test songs remain.
Fix: song_index skips zero-token songs and prints their names. All three units stopped, old e1/ output and logs deleted, restarted from scratch so all seeds see identical data.

## E1 RESTARTED

Units hyst-wo41-e1b-s1, -s2, -s3 (seeds 41101-41103, cores 6-9 / 10-13 / 14-17), reason: fd_192 zero-token crash. Old units hyst-wo41-e1-s* stopped.
