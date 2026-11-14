# Builder prompt: work order 38, T1a motor vocabulary: rules note, timing run, estimate (2026-11-14)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting.

**Binding:** `docs/BRAIN_SPEC.md` **§7.59** (3.1, 4.1, 5) and **§7.60** (4: per-source reporting). **This work order stops at the estimate:
no full training.** No verdict. One arm.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-t1a origin/body`; absolute paths; no new worktrees.
Cores 6-13, 8 threads. Jobs > 2 min as detached units `hyst-wo38-<fresh>`, `MemoryMax=16G`, `MemorySwapMax=0`; `python -u`; read the log
1 min after start. Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs,
downloads or uploads (no Kaggle). Env `/secondary/hyst-env/brain` (torch CPU). Data in: `/secondary/hyst-data/body/t0/` (read-only). Out:
`/secondary/hyst-data/body/t1a/`. Keep messages short (usage is tight).

## Read first

`docs/BRAIN_SPEC.md` 7.59, 7.60; `docs/T0_RULES.md`, `docs/T0_REPORT.md`; npz layout in `t0/seq/*/*.npz` (`gesture`, `targets`,
`win_pass`, `win_start_tok`, `weight`, `split`).

## The work

1. **Rules note `docs/T1A_RULES.md`, pushed before any training.** It fixes, per 7.59.3.1:
   - chunks: 0.5 s gesture chunks (50 steps x 5 joints, 100 Hz) on the token grid, only inside kept windows (`win_pass`), all 4 copies;
     train / validation / test from the npz `split`; sample weights = npz `weight`;
   - vigour = chunk amplitude (state the norm, e.g. RMS over the 50 x 5 values after per-joint scaling by the train-split sd of gesture);
     chunk normalised by it; a floor for near-still chunks (stated);
   - the VQ autoencoder: encoder, codebook dim, EMA decay, dead-code reset rule, commitment weight; convolutional decoder seeing
     neighbouring tokens, causal with at most 0.25 s lookahead (state exactly which neighbours); loss;
   - optimiser, batch, learning-rate schedule, epochs cap, early stopping on validation reconstruction error;
   - the codebook-size rule: train 128, 256, 512, 1024; choose the smallest whose validation reconstruction error is within 5 % of the next
     larger one;
   - the 4.1 stop-rule measures (codes in use on validation >= 60 %; reconstruction on held-out songs: jitter measures <= 1.1x the
     input's, joint ranges within 10 %; gates at 1.25 through the full body pipeline, the T0 gate code), and per-source (FineDance / AIOZ)
     reporting (7.60.4);
   - all seeds.
2. **Tests:** chunking only inside kept windows, vigour normalisation round trip, decoder causality (perturbing a token > 0.25 s ahead does
   not change the output), codebook EMA update and dead-code reset on a toy case.
3. **Timing run:** each codebook size for a fixed small number of steps on the real train set; seconds per epoch; memory peak (anon).
4. **Estimate:** projected wall time for all four sizes to the epoch cap; T1b is not estimated here.
5. **Done when:** "T1A ESTIMATE <commit>" in `docs/NIGHT_LOG_body-t1a.md` with the estimate, chunk counts per split and source, and FOR
   USER items, pushed. Then STOP. Full training starts only on the overseer's go.
