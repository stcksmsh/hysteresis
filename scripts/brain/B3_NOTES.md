# B3 training and check code: notes (BRAIN_SPEC 4.1 to 4.6)

Status: code and tests only. No real training run, no result on the real corpus. The numbers below from tiny runs are smoke only
and were written to `/secondary/hyst-data/brain/b3/scratch/`, never to the results folder.

## Run

```sh
python prep_corpus.py corpus                  # feats, beats, manifest.json, stats.npz under /secondary/hyst-data/brain/corpus
python train.py --manifest M.json --stats S.npz --out CKPT_DIR --epochs N [--no-phase] [--batch 8]   # resumable; stops at 3 x 10 h
python check_b3.py --ckpt CKPT_DIR/last.pt [--ckpt-nophase ...] --manifest M.json --stats S.npz [--precheck --core2b P.npz]   # results.json
python check_b3.py --smoke --out SCRATCH ...   # smoke: marked in results.json, refuses the results folder
```

The training-side statistics of the real corpus come from the corpus builder; `prep_corpus.py` also writes a `stats.npz` (train split)
for the smoke test.

## Change to the B2 core

`core.Core(head_norm=True)` (default): a parameter-free layer norm on the layer output before the heads and before the precision read.
Without it the deep layers' stream is large, the random heads at init predict huge means, and the first training steps diverge (L4 NLL
about 5e7 before any update, gradient norm 1e10). `head_norm=False` reproduces B2 as committed in 5fe01a2 (`b2.py` pins it, so the
B2 lanes, traces and readout files are unchanged); the B2 baseline in 4.3 uses the same `head_norm` as the checkpoint. Parameter
count is unchanged (1,010,020). Two further edits: per-row frame counters in the state (so streams reset independently), and `unbind`
instead of slicing in the scan (exact same numbers, backward about 4 times faster).

## Where the spec is silent (chosen here; each is also in a docstring)

Training (`train.py`): streams of songs with state carried per stream and reset per song; 60 s chunks with 16 s of lookahead features for
targets; loss mean over features and valid frames, summed over layers; AdamW lr 1e-3, mode parameters at 0.1x and no decay, weight decay
0.01 on matrices, clip 1.0, 200 warm-up steps then cosine per epoch to 0.1x; data order seed 20261031 + epoch; checkpoints per epoch.

4.3: persistence = the last frame (not the last-window mean). Ridge AR rows every 20 bins (2 s) where every horizon's target is inside the
song; ridge alpha picked on the last 10 % of the training songs; a constant 1 column; constant per-feature variance from training
residuals (also for persistence). B2 baseline readouts: states every 2 s of the training songs, 10 leave-out groups. NLL per song = sum
over the 4 layers of the per-feature mean; MSE pooled over songs; best baseline = lowest MSE.

4.4: songs under 82 s are skipped (reported). Window positions and order seeded; H and N share F and the second S; crossfade = 50 ms
overlap, so the second S starts at 45.9 s in both versions. Grid phase is cut and joined with the audio. "Median drop >= 0.25 x SD" is
the median over songs of drop / (SD of that song's 8 s window means of the total).

4.5: cuts at seeded fixed times (no B1). Cross-song partner seeded; the within-song tail is the 10 s starting where the grid phase is
nearest the cut's. The cut is the start of the crossfade. B3 only (B2 is not asked for here).

4.6: PAC layer signal = first principal component of the layer output, band-passed; 200 circular shifts of at least 10 s. The no-phase
ablation reports 4.3's per-layer NLL for a second checkpoint. Pre-check: ridge from layer mode magnitudes pooled to 0.5 s (1,024 values),
5 folds by song, within-song r; the smoothing control is a ridge on pooled fast features with the smoother tau and lag chosen on the
training folds; core-2b predictions are read from an npz (`--core2b`, key per clip) because stage-1's caches are not rebuilt here.
Clips without a cached beat grid get phase (1, 0). MERP labels need `pyarrow` (added to the brain env).

## Measured (this machine, other jobs running, load average 8 to 12)

Training step, 8 threads, 60 s chunks, synthetic input: 22 s per audio hour at 4 streams, 24 s at 8 streams (peak RAM 3.0 and 5.4 GB).
Real-data epoch of the 20-track smoke set (loading and padding included, 8 streams): 31 s per audio hour. For 178 h that is about
1.2 h (compute only) to 1.6 h (smoke-set overhead) per epoch, plus held-out evaluation (forward only, about 5 s per audio hour).
Before the `unbind` change the same step took 92 to 97 s per audio hour.

## Launch (fixed before any real run)

`launch_b3.sh` runs, in order: (1) `prep_corpus.py corpus` on the corpus builder's `final_corpus.csv` (3,176 tracks: 2,819 train, 357 held
out; 174.7 h train, 20.1 h held out) with its features `corpus/features/<id:06d>.npy` and `corpus/feature_stats.npz` taken as they are,
checking the audio against the list's own `sha256` column (and any extra `--hashes` file), the stats npz against
`feature_stats.json`, and adding only the offline-grid beats (8 processes) and `manifest.json`; (2) the main model, with grid phase,
8 threads, 8 streams, **8 epochs**, or the cap of 30 training hours, whichever comes first; (3) `check_b3.py` on the final checkpoint into
`/secondary/hyst-data/brain/b3/results/` (`results.json`, then `precheck.json`; the pre-check is reported only and a failure of it does not
stop the run); (4) the no-phase model, same settings, inside what is left of the 30 h; (5) `ablation.json` if that run finished all 8
epochs, else `ablation_not_run.txt`.

Why 8 epochs: measured 24 to 32 s per audio hour (load average 8 to 12), so 174.7 h takes 1.2 to 1.6 h per epoch plus held-out evaluation
(about 0.03 h), at most about 1.7 h. Eight epochs are about 10 to 14 h, so the main run and the no-phase run together (at most about 27 h)
fit the 30 h cap; the cap guard stops either one first if the machine is slower. Held-out evaluation and checks are not counted in the cap
(training wall time only). The learning-rate cosine runs over the 8 epochs. Re-running the script resumes from `last.pt`.
Statistics: the SD key in the builder's npz is `sd`; `train.load_stats` accepts `sd` or `std`.

Pre-check comparison with core-2b: `core2b_adapter.py` turns stage 2b's `predictions_heldout.npz` (out-of-fold, `<clip>/core_s`, arousal = column 1, 0.5 s steps, tau 8 s as 2b chose) into the `--core2b` npz; it covers all 1,744 DEAM clips and 43 MERP songs the pre-check uses. `launch_b3.sh` runs it and passes `--core2b`. Predictions are aligned to the labels by step; a shorter series is padded with NaN.

# Round 2 (BRAIN_SPEC 4.7): what changed in the code

Status: code and tests only; the smoke run (memory and time) is reported to the overseer; no training until the overseer says go.

## The loss: β-NLL, β = 0.5

Source checked in the full text (arXiv 2203.09168v2, the ICLR 2022 paper, Seitzer, Tavakoli, Antić, Martius, "On the Pitfalls of
Heteroscedastic Uncertainty Estimation with Probabilistic Neural Networks"):
- **Eq. (7), Section 4.1, p. 5:** L_β-NLL := E[ ⌊σ̂^{2β}(X)⌋ · ( ½ log σ̂²(X) + (Y − μ̂(X))² / (2 σ̂²(X)) + const ) ], where ⌊·⌋ is the
  stop-gradient. The weight is the variance to the power β, per data point (per output dimension in the code of Appendix D.5), and it
  carries no gradient.
- **Eqs. (8), (9), p. 5:** ∇_μ̂ L = E[(μ̂ − Y) / σ̂^{2−2β}]; ∇_σ̂² L = E[(σ̂² − (Y − μ̂)²) / (2 σ̂^{4−2β})]. β = 0 is the plain NLL; β = 1
  gives the MSE gradient for the mean.
- **Recommended β:** "we find that β = 0.5 generally achieves the best trade-off between accuracy and log-likelihood" (Section 4.1, p. 5);
  "In most cases, β = 0.5 will be a good starting point" (Section 6, Conclusion, p. 9). β = 0.5 is what 4.7 fixes.
- **Appendix D.5, p. 24 (PyTorch):** `loss = 0.5 * ((target - mean) ** 2 / variance + variance.log()); loss = loss * variance.detach() ** beta`,
  then the sum over the last (feature) axis. `train.chunk_terms` does the same per feature, then takes the mean over the 44 features
  (the factor 1/44 is the round-1 convention).
- The paper also says (p. 5) the loss value "does not reflect the model's quality": monitor with the plain NLL (and RMSE). Here: the
  validation plain NLL and MSE per layer are logged each epoch and never used; surprisal and every check use the plain Gaussian NLL.

In `train.py`: `chunk_terms(out, x, nvalid, chunk, beta)` returns per-layer sums of β-NLL, plain NLL and MSE with the counts;
`chunk_nll` is the plain case. `exp(beta * logvar).detach()` is σ^{2β}; the clamp of the log-variance to [-8, 4] is as before.

## Chunks, validation, epochs, stop

- `CHUNK = 18000` (180 s), state carried across chunks and detached at the chunk edge, gradient through the whole chunk; `LOOK = 1600` stays.
- Validation: `val_split.py` draws 10 % of the training artists (72 of 722; seed 20261105, `numpy.random.default_rng(seed).choice` on the sorted artist
  ids) from `final_corpus.csv`; the artist list and the 217 track ids are committed in `val_artists.json`. The held-out side is not read.
  Artists differ in size, so the share of tracks is 7.7 %, not 10 %. The artist is the unit, as the ruling says.
- Training: up to 12 epochs (`--epochs`, the cosine learning-rate schedule runs over 12), after each epoch one validation pass: score =
  validation β-NLL summed over the 4 layers (same normalisation as the training loss). Patience 2: stop after 2 epochs without a strictly
  lower score. Every epoch is saved (`epoch_NNN.pt`); the best is also `best.pt` (an equal score keeps the earlier epoch). The log per epoch has
  train and validation β-NLL, plain NLL and MSE per layer.
- Hard stop: `--cap-hours` (default 20) of wall time, counting training and validation and carried across resumes. The training step that
  crosses it ends the run: the unfinished epoch is dropped, `last.pt` is saved, and `best.pt` gets `cut: true` (and `stopped_by_cap: true`)
  in its meta. A run that ends early has `stopped_early: true`.
- Memory options, both off by default: `--grad-checkpoint` (each layer is recomputed in the backward pass; `test_train.TestGradCheckpoint`
  checks identical loss and gradients) and `--batch` (default 8).

## Checks (`check_b3.py`)

4.3, 4.4 and 4.5 are the committed code; run them on `best.pt`. Added: `--val-artists` removes the validation tracks from the baselines'
training side (persistence and AR variances, AR weights and alpha, B2 readouts); the standardisation statistics are untouched. Evaluation
chunks stay 6,000 frames (`EVAL_CHUNK`; the state is carried, so the numbers do not depend on it). Reported only (`results.json`): `gate_4_3.mse_per_layer`;
`gate_4_4.b3.per_layer_drop`; `gate_4_5.per_layer_and_sigma_reported_only` with the per-layer splice z and the predicted-σ rise after a cut:
mean over cuts of σ (mean over the 44 features of exp(logvar / 2) of the prediction made at that time) minus its mean in the 5 s before the
cut, at 0 to 5 s in 0.1 s steps, per layer, with its peak, the time of the peak and the time to half the peak (cross-song and within-song cuts).

## Launch

`launch_b3r2.sh` (not run): train, then the checks on `best.pt`, then the pre-check. Outputs under `/secondary/hyst-data/brain/b3r2/`.
Run it inside `systemd-run --user --scope -p MemoryMax=20G -p MemorySwapMax=0`.
