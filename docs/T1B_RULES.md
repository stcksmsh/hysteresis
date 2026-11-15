# T1b rules: E1 baseline (work order 41; BRAIN_SPEC 7.63-7.68)

Written before any training. E1 = FineDance only, pooled V1/V2/mirrored copies, ear + cortex listener (rhythm 192 / affect 64), planner over the frozen 2 x 1024 vocabulary.
No variants, no ablations, no pitch augmentation, no teacher stage, no verdict. One arm. Code: `scripts/body/t1b_*.py`. Data and models: `/secondary/hyst-data/body/t1b/` (outside git).
Items marked **(default)** are listed under FOR USER; **[PENDING]** waits for a ruling.

## 1. Input and causality

- Input per 100 Hz frame: width 2105 = 2048 mode states (4 layers x [real, imag] x 256) + 4 surprisal + 4 surprisal-valid bits + 4 log-precision + 1 arousal + 44 ear
  (`t1b_cortex.py` header). Log-precision = minus the mean logvar over the 44 channels (a bounded stand-in for precision; **default**).
- Causality list and decision-time rule: `docs/T1B_CAUSAL.md` (ear 23.2 ms; beat-grid phase = offline whole-song fact; token k reads listener step 25 k - 13; only token 0 has none and reads zeros).
- Standardisation: per-column mean and sd over every 10th train frame (`cortex_norm.npz`), clip +-5. Stored float16 (round-trip error of h up to 0.0625 absolute, about 5e-4 relative; reported).
- The planner never sees a frame after the decision step's frame (+ the listed lookahead). Tested in `test_t1b.py` (listener causal, planner rows causal, carried state).

## 2. Targets, vocabulary, bins

- Tokens: the T0 0.5 s grid from motion frame 0; token k = rows [50 k, 50 k + 50) of the 100 Hz target; only the n_win x 40 tokens of T0's 20 s windows; `ok` = its window passed the T0 gate. Loss only on `ok` tokens.
  Code pair (stage 1, stage 2) and vigour a_n from the frozen run-B encoder (`t1a2/runB/best.pt`), chunk scaling as T1a.
- Vigour: 32 log-spaced bins between the train p0.5 and p99.5 of a_n (0.0500 to 3.45); outside values go to the end bins. The floor value 0.05 is the lowest bin's edge (0.83 % of tokens sit on the floor).
- Posture change of token k = posture[50 (k+1)] - posture[50 k] (100 Hz posture target, raw units), standardised per joint with the train sd.
  **[PENDING, 7.70]** Single 256-entry k-means explains 0.847 train / 0.838 validation = STOP of 7.63.8. Recommended alternative (planner brief): residual 2 x 256 (stage 2 = k-means of the stage-1 residual), 0.971 / 0.967;
  the planner predicts the two stages like the two code stages (stage 2 given stage 1, the stage-1 embedding fed to the stage-2 head). Loss stays the sum of one cross-entropy per head, equal weights
  (code 1, code 2, vigour, posture 1, posture 2); the code in `t1b_model.py` groups them as code (1 + 2), vigour, posture (1 + 2) for reporting. Posture vocabulary fitted on the train split only, seed 36001.
- Mirror copies share the unmirrored music (the same cortex file). V1, V2, V1m, V2m of one performance are one song unit in splits and in every evaluation (grouping by performance, 7.67.5).

## 3. Model (size fixed: nothing larger than 7.63.5 / 7.64 specify)

- **Listener** (7.64.2, 7.65.2): linear 2105 -> 128, dropout 0.2, then 256 leaky-tanh units at 50 Hz: h <- (1 - a) h + a tanh(W h + U p), a = 1 - exp(-0.02 / tau), tau learned per unit
  (log-parametrised). Units 0-191 (rhythm) tau init log-uniform 0.1-1 s; units 192-255 (affect) log-uniform 2-30 s. W is a full 256 x 256 matrix (both parts feed each other),
  orthogonal init gain 0.9, U shared input for both parts. State starts at zero at song start and is carried detached across 60 s windows (7.64.10). The 50 Hz input is the mean of frame pairs.
- **Planner** (7.64.3): GRUCell 256, one step per token. Input: listener state read at the decision step (256, both parts) + embeddings of the previous token (code 1: 32, code 2: 32, vigour bin: 16, posture entry/entries: 32 each).
  Single-head attention over the last 32 GRU states of the song (keys/values/query: Linear 256, output Linear 256, residual + LayerNorm); no positional encoding (**default**).
  Heads: code 1 (1024), code 2 given code 1 (1024), vigour (32), posture stage 1 (256) [and stage 2 given stage 1].
- Parameter counts (printed by `Model.counts()`, single-posture variant): listener projection 269,568; input U 33,024; recurrent W + tau 65,792; planner embeddings 74,240; GRU 480,768;
  attention + LayerNorm 263,680; heads: code 1 263,168, code 2 295,936, vigour 8,224, posture 65,792. **Total 1,820,192** (about 1.82 M; the residual posture head adds 0.1 M).
- Generation (T2): nucleus p = 0.9 on every head (7.63.8, fixed), sampled in head order code 1, code 2, vigour, posture; the previous sampled token is fed back; posture accumulates by the entry's centre (start posture = the song's human posture at token 0, same for the 4 copies).

## 4. Training

- Loss: sum of the head cross-entropies, equal weights (7.63.8), per token weighted by the copy's T0 weight, masked by `ok`; normalised by the weight sum of the window step.
- Input-noise rule (fixed): every fed-back component of the previous token (each code, vigour bin, each posture entry) is replaced by a uniformly random index with probability 0.10, independently, in training only;
  listener dropout 0.2 in training only.
- Truncated backprop through 60 s windows (6000 frames = 3000 listener steps = 120 tokens); one optimiser step per window step; listener state, planner state, attention memory and the previous token are carried (detached) between windows of the same song.
  Four songs advance in lockstep ("slots", batch of 4 songs x 4 copies); a finished slot starts its next song at zero state. Song order reshuffled each epoch (seeded).
- AdamW lr 1e-3, weight decay 0.01, gradient clip 1.0; lr halved after 2 epochs without validation improvement; early stopping on validation total cross-entropy, patience 5, epoch cap 60.
- Reported per epoch: noisy training loss, loss of the model in evaluation mode on a fixed 16-song train subset, validation loss, and the gap (validation minus train subset) per head.
- Splits: T0 split (train / validation / test by song group, seed 33001). FineDance only. Train songs per FineDance genre reported (7.63.5).
- Seeds (7.68.9): 41101, 41102, 41103 (initialisation, shuffle and noise streams all derived from the seed). Three runs in parallel (cores 6-9 / 10-13 / 14-17, 4 threads each).

## 5. Controls (7.64.8, 7.66.3)

- **Retrieval:** for each token of a held-out song, nearest training token (cosine) on the cortex+ear state averaged over the 0.5 s token window ending at the token's decision step (listener-free); the picked training chunk brings its posture, gesture and vigour.
  Transition cost = joint-space jump at the boundary (standardised joints, weight 1.0 relative to 1 - cosine), Viterbi over the song; same body pipeline and gates. Train split only.
- **Random human chunks:** the same Viterbi with the same transition cost but music distance zero (no music). Both run for the T2 held-out songs, seed 36101.

## 6. T2 protocol (run after training; Kosta's labels first)

- Held-out songs = test split. 60 s window per song from the song's first full 60 s after 10 s (start = 10 s), one per song, fixed. Human reference = the T0 targets of the same song and window, the 4 copies averaged where a measure allows.
  AIOZ held-out: report-only, separate, same measures.
- Everything on **realised** trajectories (spinal layer, limiter, servo, v2p) with the commanded-vs-realised difference reported; jitter at the realised stage (7.62).
- Swapped-music STOP (7.64.6, 7.68.5): per held-out song, log-likelihood (sum of the head cross-entropies, teacher forced, the 60 s window) with the true music minus the mean over 3 other songs whose tempo (offline beat grid median) is within 5 %.
  Partner choice seeded (seed 36201): first from validation songs, then allow half / double tempo; report how many songs needed the fallback and how many had no partner. STOP if the bootstrap 95 % interval of the mean difference over songs (resampled by song,
  2000 resamples, seed 36202) includes 0.
- Event response (report): events = onsets (ear-feature column 40 above its song-wise 95th percentile, local maximum within +-0.1 s), energy jumps (RMS column 41 3 s mean rises > 6 dB within 1 s), cortex slow-state changes (cosine distance
  between the layer-4 mode state mean over 1 s and the previous 1 s above its 95th percentile). Movement change = mean hand speed in [0, 1 s] minus [-1 s, 0] around the event; model vs human on the same events.
- 2 s history truncation (report): likelihood with the listener state reset to zero 2 s before each token (listener run on the preceding 2 s only) vs full.
- Identical-shape repetition STOP (7.65.1): share of tokens in a generated 60 s dance whose (code 1, code 2) pair occurred earlier in the same dance; STOP if the model's mean over songs exceeds the human data's mean on the same songs by more than 2x.
  Triples (shape pair, vigour bin, posture entry) distinct per minute, model vs human. Approximate repetition: for each token the nearest-neighbour distance of its decoded gesture to earlier gestures of the same dance (scaled units, RMS), median per song.
- Diversity (7.63.8): 8 samples per held-out song: share nearest to V1 / V2 / mirrored; mean pairwise distance between samples vs between the human copies.
- Self-similarity (7.59.4.3, 7.66.3): music self-similarity (cosine of 0.5 s-averaged ear+cortex states) vs movement self-similarity (cosine of 0.5 s-averaged joint targets), correlation of the two matrices (upper triangle, lag >= 1 s), at windows 2 s, 8 s, 30 s; STOP of 7.59.4.3: below half the human value at the 8 s window.
- Beat alignment: hand-speed minima within +-0.1 s of beats of the offline grid (share of beats), model vs human (Bailando's style score). Vigour vs ear-energy correlation (ear-energy lane of `ear_energy.py`, 0.5 s means) model vs human.
- Posture range and posture-change rate; STOP joint range p5-p95 per joint < 50 % of the human data's (any joint); STOP jitter (acceleration sign changes per s and power above 3 Hz at the realised stage) > 1.5x the training data's; STOP frozen pose: hand speed < 0.05 m/s for > 3 s.
- Endpoint (lamp) jerk and direction changes per s; V1/V2 nearest-style share and style switches per minute; joint-limit hits; limiter saturation share; AIOZ-only code share (codes seen only in AIOZ chunks); gates at 1.25 through the full body pipeline.
- Affect probe (7.65.2, 7.68.6, report-only): Kosta's labels of 39 test+validation songs (3 passages of 15 s each, majority = song label, ties reported). Features = mean listener affect state (units 192-255) over the passage; 5-fold cross-validated
  multinomial logistic regression (C = 1, standardised), accuracy vs a shuffled-label control (100 shuffles, seed 36301); folds grouped by song. Passage test (7.66.3): passage pairs matched on tempo (5 %) and RMS (10 %) with different labels:
  fraction of pairs whose affect states are farther apart than the matched same-label pairs; shuffled-label control; no conclusion below 10 matched pairs.
- Mean and spread (min, max, sd) over the 3 seeds for every T2 number; per-song values saved to `t1b/t2/`.

## FOR USER (defaults taken)

- Log-precision as minus mean logvar; surprisal NaN -> 0 with valid bits.
- No positional encoding in the attention; attention memory = last 32 GRU states.
- Event-detection thresholds and the 2 s truncation implementation as stated in section 6.
- Posture head: single vs residual awaiting 7.70.
