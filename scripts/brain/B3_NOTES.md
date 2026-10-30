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
