# T1a2 rules: retrain with Bailando's loss, spline decoder, residual run (work order 39, BRAIN_SPEC 7.61)

Written before any training. Builds on `T1A_RULES.md` (chunks, vigour, encoder, EMA quantiser, evaluation); only what changes is stated here. Stops before S1. No verdict. One arm.
Code: `scripts/body/t1a2_*.py`. Out: `/secondary/hyst-data/body/t1a2/`. Env `/secondary/hyst-env/brain`, 4 threads per run: Run A on cores 6-13, Run B on cores 14-19, detached units `hyst-wo39-<name>`, MemoryMax 8G.
Defaults are marked **(default)** and listed under FOR USER in the night log.

## 1. Data and weights (7.61.3, Step 1 result)

- Same windows, chunks, scaling and splits as T1a. Step 1 (`T1A2_STEP1.md`): kept-AIOZ gesture RMS is below 70 % of FineDance's on 4 of 5 joints, so **the rule applies: AIOZ is capped at 50 % of the total training weight in both runs.**
- Cap: weight of every AIOZ window = npz weight x f, with f chosen on the train split so that sum(AIOZ weight x chunks) = sum(FineDance weight x chunks) (7.61.7). f is computed once from the train windows, written to `t1a2/weights.json`, and applied unchanged to the validation windows' weights (so the weighted validation error and early stopping use the capped weights **(default)**).

## 2. Loss (Bailando, used as written)

Source: Bailando's official repository (`github.com/lisiyao21/Bailando`), `models/vqvae.py` (function computing the VQ-VAE loss) and `configs/sep_vqvae.yaml` (the paper, arXiv 2203.13055, was not fetched separately; the code is taken as the statement of the loss). Quoted:

```
_loss_fn(x_pred, x_target) = t.mean(t.abs(x_pred - x_target))                       # L1
velocity_loss     += _loss_fn(x_out[:, 1:] - x_out[:, :-1], x_target[:, 1:] - x_target[:, :-1])
acceleration_loss += _loss_fn(x_out[:, 2:] + x_out[:, :-2] - 2 * x_out[:, 1:-1], x_target[:, 2:] + x_target[:, :-2] - 2 * x_target[:, 1:-1])
loss = recons_loss + commit_loss * self.commit + self.reg * regularization + self.vel * velocity_loss + self.acc * acceleration_loss
config: commit 0.02, vel 1, acc 1 (reg 0 unless set; not set)
```

Used here: recons = L1 of the decoded gesture against the target (scaled units, 100 Hz rows), velocity and acceleration = the same L1 on first and second differences along time of the 100 Hz decoded gesture (joint angles; Bailando uses joint positions), commit weight 0.02, vel 1, acc 1, reg 0. The L1 terms are means over the window and joints; the per-window loss is weighted by the (capped) window weight and averaged. The commitment term is the T1a one (||z_e - sg(e)||^2 summed over the quantiser's stages in Run B). Model selection and early stopping use the **round-1 metric** (weighted mean squared reconstruction error in scaled units) so the runs are comparable with T1a **(default)**.

## 3. Decoder with a B-spline head (7.61.7)

- The decoder works at 25 Hz: control point j sits at row 4 j (every 40 ms), j = -1 .. 501 for a 2000-row window (503 points). Control point j takes the token vector of token clamp(floor(4 j / 50), 0, 39) (Linear 64 -> 64), then three convolutions at 25 Hz with explicit zero padding (left, right): Conv1d(64, 128, k5, (2, 2)) GELU; Conv1d(128, 128, k5, (2, 2)) GELU; Conv1d(128, 5, k3, (2, 0)); the 5 channels are the control values.
- Fixed uniform cubic B-spline to 100 Hz: row r = 4 i + p (p = 0..3, t = p / 4) = sum over m in -1..2 of B_m(t) c_(i + m) with B_-1 = (1 - t)^3 / 6, B_0 = (3 t^3 - 6 t^2 + 4) / 6, B_1 = (-3 t^3 + 3 t^2 + 3 t + 1) / 6, B_2 = t^3 / 6. The amplitude series (vigour per chunk, box-smoothed +-7 rows as in T1a) multiplies the splined shape.
- **Right reach**: the convolutions look 2 + 2 + 0 = 4 control points ahead (16 rows), the spline 2 control points (8 rows) -> a row depends on tokens whose chunk starts at most 24 rows (0.24 s) after it (<= 0.25 s; tested: a token starting 25 or more rows later changes nothing). The amplitude path reaches 7 rows. Edge neighbours are zeros in training, as in T1a.

## 4. Runs

- **Run A**: K = 1024 single EMA codebook (T1a quantiser, dead-code reset as T1a), the loss of section 2, the spline decoder.
- **Run B**: as Run A with a 2-stage residual quantiser (2 x 1024). Stage 1 quantises z_e as in Run A (EMA, dead-code reset, own codebook); stage 2 quantises the residual r = z_e - sg(e1) with its own EMA codebook and dead-code reset (same rules, thresholds relative to chunks per batch / 1024). The decoder receives e1 + e2 (straight-through from z_e); the encoder, decoder and both codebooks train together end to end; the commitment loss is ||z_e - sg(e1)||^2 + ||r - sg(e2)||^2 with weight 0.02.
- Optimiser and schedule as T1a (Adam 0.9 / 0.99, lr 2e-3 cosine to 1e-4 over the cap, clip 1.0, batch 16 windows) except **epoch cap 80**; early stopping patience 5 epochs on the weighted validation error; checkpoint every epoch (`ckpt.pt`, atomic), resumable; `done.json` at the end.
- Seeds as T1a: shuffle 34001, init 34002, reset 34003 (same for both runs).

## 5. Evaluation (each run)

- All T1a stop measures on the test windows (`T1A_RULES.md` 5): code usage on validation (Run B: stage 1 and stage 2 separately) >= 0.60; jitter ratios <= 1.1 (acceleration sign changes, power above 3 Hz, medians over windows per joint); joint ranges within 10 %; gates at 1.25 on the reconstructed windows (T0 gate code, control = original windows); per source (FineDance / AIOZ).
- New (7.61.5): **variance explained >= 0.85 on every joint on FineDance validation chunks** (1 - var(recon - gesture) / var(gesture), pooled, degrees, unweighted; also reported for test and per source).
- Report which run passes everything. S1 candidate = the smaller passing model (A before B). If neither passes: report and hold. Stop before S1.
