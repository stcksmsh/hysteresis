# Night log, body-t1b (WO41, T1b E1 baseline)

Branch `body-t1b` (from origin/body 9f410d9). Env `/secondary/hyst-env/brain`. Cores 6-17 mine; WO42 on 18-19.

## CAUSAL (2026-11-15)

Full list: `docs/T1B_CAUSAL.md`. Summary:
- 44 ear features: one centred STFT (2048, hop 441), lookahead 23.2 ms for every column; global normalisation, no per-song statistic.
- Cortex input = 44 ear + 2 beat-grid phase. The beat-grid phase is an offline whole-song fact (online PLL run over the whole file, then interpolated between beats, so the
  phase at t uses the next beat, up to one beat interval ahead). Cortex layers, hippocampus, surprisal and arousal are causal given their input.
- Ear energy (1.0 s lookahead) is NOT an E1 input.
- Planner for chunk k reads listener step 25k-13 (last 50 Hz step at or before chunk start - 0.25 s); k = 0, 1 read the zero state.
- No input changed.

## STOP posture vocabulary (2026-11-15)

256-entry posture-change k-means explains 0.847 of variance on train (0.838 validation), below the 0.9 STOP of 7.63.8. Checked 200 iterations, 2 seeds; deltas heavy-tailed,
joints nearly uncorrelated; 1024 entries would give 0.914. No training until the overseer rules. Cortex precompute (running) and other independent steps continue.
Cortex reproduction (fd_001 vs T0 lanes): ear 0, arousal 0, s10 0, h_abs 2.9e-6; float16 round trip of h: max abs 0.0625.
Code: scripts/body/t1b_cortex.py, t1b_tokens.py (tokens encoded with runB, 812 files in t1b/tokens/).
