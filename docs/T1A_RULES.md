# T1a rules: motor vocabulary (VQ autoencoder over 0.5 s gesture chunks) (work order 38, BRAIN_SPEC 7.59.3.1, 7.59.4.1, 7.60.4)

Written before any training. T1a only; this work order stops at the timing estimate (no full training, no verdict). One arm.
Code: `scripts/body/t1a_*.py`. Data in `/secondary/hyst-data/body/t0/` (read-only); out `/secondary/hyst-data/body/t1a/`. Env `/secondary/hyst-env/brain` (torch CPU, 8 threads, cores 6-13).
Open details are marked **(default)** and listed under FOR USER in the night log.

## 1. Chunks and data

- Source: every T0 npz (`t0/seq/<dataset>/<dancer>__<copy>.npz`, all 4 copies V1, V2, V1m, V2m, both datasets). Split = the npz `split`; sample weight = the npz `weight`.
- Window i of a dancer = gesture rows `2000 i .. 2000 i + 1999` (100 Hz), only where `win_pass[i]` is true. A chunk is 0.5 s = 50 rows x 5 joints on the token grid: chunk j of the window = rows `50 j .. 50 j + 49`, j = 0..39. Chunks exist only inside kept windows (a dropped window gives none; no chunk crosses a window edge).
- Cache `t1a/windows_<split>.npz` (built by `t1a_data.py`): `g` (N, 2000, 5) float32 gesture in degrees, `w` (N,) weight, `src` (N,) 0 FineDance / 1 AIOZ, `copy` (N,) 0..3, `dancer` (N,) index into `dancers`, `win` (N,) window index, `dancers` (str).
- Per-joint scale s_j = sd of the train-split gesture rows over all kept train windows (unweighted); `t1a/scale.json`. All model input and loss are in scaled units x / s_j (so a joint with a large range does not dominate).

## 2. Vigour

- Chunk x (50, 5) scaled. Vigour a = sqrt(mean(x^2)) (RMS over the 250 values). Floor F = 0.05 (scaled units; chunks below it are "still"). Used amplitude a_n = max(a, F).
- Normalised chunk u = x / a_n (so a still chunk is not blown up: its u has RMS a / F < 1). Reconstruction of a chunk = a_n x decoded shape; round trip: decode(encode-free) u x a_n = x exactly (tested).
- The token's vigour scalar handed on to T1b is log a_n. The share of train chunks under the floor is reported.

## 3. Model

- **Encoder** (per chunk, input u as (5 channels, 50 steps)): Conv1d(5, 64, k5, pad 2) GELU; Conv1d(64, 128, k5, stride 2, pad 2) GELU (25 steps); Conv1d(128, 128, k5, stride 2, pad 2) GELU (13 steps); flatten (1664); Linear(1664, 64). One 64-dimensional vector per chunk.
- **Quantiser**: codebook K x 64 (K in 128, 256, 512, 1024), nearest code by L2. EMA updates (decay 0.99, eps 1e-5, Laplace-smoothed counts); the codebook receives no gradient. Straight-through estimator. Commitment weight 0.25 on ||z_e - sg(e)||^2. Codebook initialised from random encoder outputs of the first batch.
- **Dead-code reset**: every 100 steps a code whose EMA count is below 0.05 x (chunks per batch / K) is replaced by a random encoder output of the current batch (plus N(0, 0.01) noise); its EMA count is set to the uniform value (chunks per batch / K) and EMA sum to count x vector.
- **Decoder** (works on a whole 40-chunk window at once, so joins are smooth): token vector e_t -> Linear(64, 64); each token repeated 50 times (2000 steps); three convolutions with explicit zero padding (left, right): Conv1d(64, 128, k11, (5, 5)) GELU; Conv1d(128, 128, k11, (5, 5)) GELU; Conv1d(128, 5, k9, (4, 4)) = decoded shape. The amplitude series a_n (piecewise constant per chunk, 2000 steps) is smoothed by a fixed box filter of +-7 steps (zero padded) and multiplies the decoded shape: output = amp_smooth x shape.
  **Causality**: the right reach is 5 + 5 + 4 + 7 = 21 steps = 0.21 s <= 0.25 s. Output row r depends on tokens whose chunk starts at row <= r + 21 only, i.e. a sample sees its own chunk, all earlier chunks inside the left reach (21 steps) and, in the last 21 rows of a chunk, the next chunk's code and vigour. A token whose chunk starts more than 25 rows (0.25 s) after r cannot change row r (tested). At a window's edges the missing neighbours are zeros (training windows are isolated; at run time neighbours exist).
- **Loss** (per window, weight w): mean over the window of the squared error of the full reconstruction in scaled units, plus 0.25 x the mean commitment loss; weighted mean over the batch. Validation reconstruction error = the same squared error, weighted by w (also reported unweighted and per source).

## 4. Optimiser and schedule

- Adam (betas 0.9, 0.99), lr 2e-3 with a cosine decay to 1e-4 over the epoch cap, no warm-up; gradient clip 1.0; no weight decay; batch 16 windows (640 chunks); sampling = a seeded shuffle of the train windows each epoch (weights act in the loss, not in the sampling).
- Epoch cap 40; early stopping on validation reconstruction error (patience 5 epochs, best checkpoint kept); the validation pass runs after every epoch.
- Seeds: data shuffle 34001, torch init 34002, reset noise 34003 (one `torch.Generator` each).

## 5. Codebook-size rule and the 4.1 stop measures

- Train K = 128, 256, 512, 1024 (same seeds, same data). Choose the smallest K whose best validation reconstruction error is within 5 % (<= 1.05 x) of the next larger K's. Report error and code usage for all four.
- Stop measures (7.59.4.1), on the chosen K (reported for all four): (a) codes in use on validation >= 60 % (a code is in use if it is the nearest code of at least one validation chunk); (b) reconstruction on held-out songs (the test split): per joint and window the jitter measures of `jitter_diag.all_joints` (acceleration sign changes per second, power above 3 Hz) of posture + reconstructed gesture <= 1.1 x those of the original target, medians over windows; joint ranges (p5-p95) within 10 % of the original's; (c) gates at 1.25 through the full body pipeline (guard, `motornet.spinal`, limiter, servo, v2p, `RR.gates_v2p`), the T0 gate code on the window rows (posture + reconstructed gesture, with yaw and roll re-referenced to the window start as in T0) with the original windows as the control; pass share per source.
- Per-source reporting (7.60.4): FineDance and AIOZ validation chunks separately for reconstruction error, jitter, code usage and gate share.
- No verdict; the overseer and Kosta read the numbers.

## 6. Timing run (this work order)

Each K for a fixed 40 training steps on the real train cache (batch 16), seconds per step -> seconds per epoch (steps per epoch = ceil(train windows / 16)) plus one validation pass; peak memory (anon, `RssAnon`, and `ru_maxrss`); projected wall time for all four sizes to the epoch cap of 40 (upper bound; early stopping shortens it). T1b is not estimated.
