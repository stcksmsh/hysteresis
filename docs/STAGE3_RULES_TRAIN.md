# Stage 3 trainer: rules (work order 26B, BRAIN_SPEC 7.39.4 + 7.40), written before the timed round

One arm (permanent rule). Code: `scripts/body/s3_train.py` (+ `s3_data.py`, `s3_obs.py`, `s3_loss.py`). Existing modules are imported, never edited.
Amendments only as dated entries at the end. Items marked **FOR USER** are choices where the spec left a detail open; the nearest default was taken.

## 1. Body, policy, brain streams

- **Body:** exactly `k5p2_train.CFG` (v2f, raised plane 0.053 m, contact tc 0.006, end stops, smooth-u c = 0.5, hard clip), generator caps at their defaults, basal ganglia
  (program softmax, dopamine critic and rate multiplier, program switch cost `W_SWITCH = 0.01 x tv`) as built in `m3f`.
- **Windows:** the K5 splits, 60 s windows (120 blocks of 0.5 s, `k5/windows.json`), block b of a window is block `start + b` of the song's lanes.
- **Fast stream (4 columns):** `k5/lanes` `y[:, 0:4]` = arousal, surprisal, l3_cos, l3_sin, after `m3d.transform_state` (arcsinh on arousal and surprisal), then a causal 30 s
  z-score: block b standardised by the mean and sd of blocks `max(0, b-59)..b` of the window, 0 where fewer than 8 blocks (as `m3e.running_z`), with the sd floored at
  `0.1 x` the corpus sd of that column (corpus sd = sd over all blocks of the train windows after `transform_state`, `corpus_sd.json` in the run directory), clipped to +-5.
- **Slow stream (13 columns):** 26A's `slow/<split>/<id>.npz` `slow` (nb, 13), the same block indexing as `k5/lanes`, corpus-normalised once (train mean/sd), **no within-song normalisation**;
  clipped to +-8 only as a safety. Columns: 8 L4 PCs, 8 s surprisal integral, logpow_L1..L4.
- **Decoding target** `tgt` (E, 120, 17) = [fast 4 | slow 13].
- **Policy input** per block b: `x_b = [prev-z (8), delta (8), slow_{b-1} (13)]` (the pass2 path of `m3e.ToyE.inputs` for the first 16, then the previous block's slow
  columns, zero for b = 0) followed by the cerebellum feedback `feat` (25). The cortex's first weight matrix has 13 zero rows inserted after row 16, so at initialisation the
  policy is the pass2 initial policy. The critic input has 54 columns. The pass2 input `yz` (8 causal-z numbers, 60-block window) is **unchanged** as an input and as the K5 validation target.

## 2. Objective (computed per chunk of 8 blocks = 4 s, one Adam step per chunk, as pass2)

Blocks b >= `VALID_FROM` = 8 of the window are scored (as pass2). `valid` = that mask. All means are over scored blocks and the windows of the group.

1. **Decoding, both streams, external and internal observer.** Observer = MLP `n_in -> 64 -> 64 -> 17`, tanh hidden, every weight matrix W replaced by `W / max(1, sigma_max(W))`
   (exact SVD, recomputed at every call, differentiable), biases free, output times the fixed gain `G = 4`. So the observer is `G`-Lipschitz (tests measure it) in its input units:
   **external** input = the pass2 standardised joint-trajectory descriptors of the visible arm (23 numbers, `m3f_jax.n_desc`; standardised by the calibration sd, so one unit is one
   calibration-sd of a descriptor of the 10 Hz low-passed joint trajectories in degrees, not metres) and **internal** input = its internal descriptors (27 numbers, the same
   standardisation). **FOR USER:** the spec words "metres of hand/joint position" for the external observer; the pass2 observer reads descriptors of joint angles, not positions in metres. To keep
   bar (a) and the pass2 machinery comparable the descriptors were kept; the Lipschitz statement is in standardised descriptor units.
   Per observer: `mse_fast` = mean over blocks, windows and the 4 fast outputs of the squared error to `tgt[..., :4]`, `mse_slow` likewise over the 13 slow outputs.
   `dec_obs = (1 + mu_f) * mse_fast + (1 + mu_s) * mse_slow`; the loss term is `dec_ext + dec_int`. `mu_f`, `mu_s` are the D multipliers (point 3) and enter as constants.
   The observers are not trained by this loss (stop-gradient, as pass2): two groups A and B, each observer fitted on the **other** group's rollouts (cross-fit), Adam lr 1e-3,
   wd 1e-3, clip 10, batch 256, 400 steps at calibration and 200 per round on the last 4 rollouts of the other group (`m3f.Trainer._refresh` schedule), through the Lipschitz apply.
2. **InfoNCE music<->motion.** A group of the round (8 windows) is one batch: the anchor window plus one window of each of the **7 nearest train songs** to the anchor's song by
   `d = sqrt(((bpm_i - bpm_j)/10)^2 + ((logrms_i - logrms_j)/0.3)^2)` from 26A's `tempo_rms.json` (the anchor's song excluded; ties by song id; the window of a neighbour song is
   drawn with `default_rng([SEED, round, group, rank])` among that song's `windows.json` windows). For each chunk (a 4 s window, 8 blocks): motion input = the hand position
   (`J.hand_points` of the 100 Hz joint trajectory `q`, metres) at 10 Hz (every 10th sample, 5 per block, 40 points x 3 = 120 numbers); music input = the mean and the sd over the
   8 blocks of the chunk of `tgt` (17 + 17 = 34 numbers, the matched brain-state window). Encoders: motion `120 -> 64 -> 32`, music `34 -> 32 -> 32`, tanh, L2-normalised;
   symmetric InfoNCE, temperature 0.1, weight 0.5, positives on the diagonal; the gradient reaches the policy through the motion encoder (`q` and the hand position are differentiable).
   Chunks of blocks 0..7 are not scored (as the decoding); chunks c0 >= 8.
3. **D hinge per stream.** Once per round, after the round's 16 windows and the observer refresh: roll out 16 fixed validation windows (the first 16 of `k5_train.val_windows`, argmax,
   start poses seed 4242), predict with the group-A and group-B external observers, and compute per stream the toy's shifted-gap definition `D = 1 - L_matched / L_shifted`
   (blocks >= 8; `L_matched` = mean squared error of the stream's outputs; `L_shifted` = same against `tgt` rolled circularly in time by a shift drawn uniformly in 16..104 blocks
   (>= 8 s), 20 shifts per window from `default_rng(0)`; ratio of the means over the 16 windows), averaged over the A and B observers. These windows are never trained on and are not the
   357 held-out songs. `D_fast`, `D_slow` -> `mu_s <- max(0, mu_s + 0.16 * max(0, 0.7 - D_s))`, both start at 0, rising only (BRAIN_SPEC 7.40.1, 7.40.4). The new multipliers act from the next round.
   D >= 0.7 is a training safeguard, not a bar.
4. **Limit hinges with dual multipliers.** Seven constraints, each the chunk mean over scored blocks of a violation that is zero inside the envelope:
   `g = [energy, jerk, hand_v, jolt, acc, floor, lim]` with
   `g_energy = relu(E_b / E_thr - 1)`, `g_jerk = relu(J_b / J_thr - 1)` (`E_b` = `m3f_jax` block output `energy`, J; `J_b` = block output `jerk`; thresholds from 26A's `thresholds.json`),
   `g_hand_v = hand_v / 1.2` (m/s over 1.2), `g_jolt = jolt / 9` (m/s^2 over 9), `g_acc = acc / 4.8` (m/s^2 over 4.8), `g_floor = floor / 0.05` (m below the floor margin over 0.05),
   `g_lim = lim` (already normalised by 10 deg beyond 100 deg), the block outputs of `m3f_jax.penalties`. (Spec text for the jolt unit "m/s^2" is followed: the change rate of the 50 Hz hand speed.)
   Loss term `sum_k mu_k g_k`; after every optimiser step `mu_k <- max(0, mu_k + 0.02 g_k)`, `mu_k = 1` at start, rising only, one multiplier set shared by the two groups.
   These replace pass2's LAM-weighted soft costs in the Stage 3 path (no `lam x (energy + penalties)` term). The switch cost `0.01 x mean(tv)` and the jerk-free interiors are as stated here only.
5. **Total loss per chunk:** `dec_ext + dec_int + 0.5 * InfoNCE + sum_k mu_k g_k + 0.01 * mean(tv)`. Optimiser: pass2's (Adam lr 1e-3, global gradient clip 1.0, dopamine rate multiplier on
   the program-logit path); the encoders are optimised in the same Adam step.

## 3. Round, order, resume, compute

- One **round** = two groups (A, B) of 8 windows = 16 windows, as pass2. The anchors are the pass2 seeded order (`k5_train.train_order`): round r takes `order[16r]` for group A and `order[16r + 1]`
  for group B; the other 14 windows are the matched neighbours of point 2.5. R = ceil(15,624 / 16) = 977 rounds, `tau_r = 0.2^(r/(R-1))`. **FOR USER:** pass2 saw every window once; Stage 3 sees 1,954 anchors and
  13,664 neighbour windows per pass (a window can repeat), because a batch must be one anchor plus its matched songs.
- Validation every 200 rounds and at the end, best.pkl, early stop (two validations in a row not beating the best): pass2's, on the 217 validation songs, **best = highest mean external
  (a) gap** of `k5p2_train.score_modes` (fresh unconstrained observers on the 8-column `yz`, 7.27/pass2 procedure). `best.pkl` carries `P` (policy with the 13 extra input rows), `stats`, `round`, `val`, `cfg`,
  and `s3 = {enc, slow_inputs: true}`.
- Resume: `ckpt.pkl` after every round (policy, encoders, observers, critic, Adam states, multipliers, key, history); the round's batches depend only on (SEED, round), so a resumed run equals
  an uninterrupted one (test, 2 rounds). Compute box 30 h on the pause-aware clock, mains only, SIGTERM stops after the round (all as `k5_train`).
- Threads: the timed round and the Stage 3 run use exactly 6 threads, `taskset -c 6-11`, stated in the log (BRAIN_SPEC 7.38.4). Tests and builds: cores 12-17.

## 4. Inputs from work order 26A (fixed interface)

`<s3>/slow/{train,val,check}/<id>.npz` (`slow` (nb, 13)), `<s3>/tempo_rms.json` (`{id: {bpm, log_rms}}`), `<s3>/thresholds.json` (`{energy, jerk, method}`), default `<s3>` = `/secondary/hyst-data/body/s3`.
Tests use a stub written to a temporary directory. Until 26A's files exist the trainer refuses to start (explicit error).

## 5. Dated notes
