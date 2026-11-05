# Night log, builder (body-k5data), work order 8, the K5 data (2026-11-05)

## MORNING SUMMARY (in progress; lanes exporting)

- Splits (final, `scripts/body/k5_splits.json`; data copy `/secondary/hyst-data/body/k5/splits.json`): K5 train 2,602 songs / 650 artists / 162.02 h (training-side artists minus the 72 validation artists of `val_artists.json`); val 217 songs / 72 artists / 12.71 h (tuning only, extra lanes exported); check 357 songs / 73 artists / 20.07 h (held-out). No artist overlap (asserted in code and test). Ids zero-padded to 6 digits as in the corpus manifest; the three sets together equal the manifest's 3,176 songs.
- Windows (`windows.json`): 15,624 training windows (stride 30 s, 2,599 songs have at least one), 1,071 check windows (3 x 357), 362 of them clamped, 0 songs shorter than 60 s.
- Lanes: running as unit `hyst-wo8-k5data-lanes` (6 threads, 8 GB cap, swap 0, mains only, resume-safe). Free space on /secondary before the run: 414 GB.

## Rules, written before the lanes run

- Split: K5 train = corpus `split == train` and artist not in `val_artists.json`; K5 check = corpus `split == heldout`; val = the validation artists (never in training windows; for tuning). Held-out artists are read only to build the check set.
- Lanes: the toy's interface (m3d_toy.py / tm3c.brain_state), 0.5 s blocks, 8 numbers `arousal, surprisal, l3_cos, l3_sin, logpow_L1..L4`, plus `phi_end`, `omega` (the toy's phase-coupling inputs), plus 0.1 s lanes `s10` (surprisal L1..L4, total), `arousal_b7`, `power10`. Definitions in the `k5_data.py` docstring. "arousal" = one-pole (rise 1 s, fall 8 s, from 0) of the per-frame total surprisal, the toy's definition; B7's own arousal signal is stored separately. No normalisation in the files. Block b describes frames [50 b, 50 b + 50); the loop reads block b - 1 while moving in block b.
- Model: B7 epoch 6 (`braindump.CKPT`), hippocampus off as trained, whole song in 6,000-frame chunks with the state carried. A partial last block is dropped.
- Training windows: 60 s = 120 blocks, stride 30 s (60 blocks), start + 120 <= nb. Check windows: start = floor(frac x nb), frac 0.25 / 0.5 / 0.75, moved back to nb - 120 when it would run past the end (flag `clamped`); a song with nb < 120 is listed and has no window.
- Projection: M3d's measured cost per window (try 1 epoch seconds / 16) and per evaluated window, times a stated multiplier for M3e's closed loop; over 8 h means a Kaggle job is prepared, not launched. No spending.
