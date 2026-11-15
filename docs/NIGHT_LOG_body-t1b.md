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
