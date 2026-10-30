# scripts/brain: B1 pulse (docs/BRAIN_SPEC.md sections 1.1, 2)

Environment: `/secondary/hyst-env/brain` (uv; numpy, scipy, soundfile, librosa 1.0.0, mir_eval 0.8.2, pytest, plus numba and llvmlite from librosa).
Data and outputs stay outside git: `/secondary/hyst-data/brain/` (test sets in `testsets/`, check outputs in `b1/`, B2 readouts and lanes in `b2/`). torch (CPU) is installed in the env for B2.

| File | What |
|---|---|
| `fast_features.py` | the 44 fast features at 100 Hz; STFT, mel range, band groups and onset formula fixed in its docstring |
| `grfnn.py`, `GRFNN_PARAMS.md` | Hopf bank, beat readout with the 20 % / 2 s hysteresis rule; every value with its source |
| `gaps.py` | gate 2 gaps (silence, shaped noise), seed 20261029, and the gap verification by permutation test |
| `scoring.py` | gates 1 to 3 (pass rules in its docstring), bootstrap and permutation seeds |
| `testsets.py`, `testsets/*.sha256`, `testsets/AUDIT.md` | Ballroom and GTZAN loaders, hash lists of every file used, audit |
| `check_b1.py` | one script for all gates; `results.json` and `check_b1.log` go to `/secondary/hyst-data/brain/b1/` |
| `synthetic_input_sweep.py`, `sd_reference.py`, `synthetic_exclusion.py` | the synthetic sweep that fixed the input gain; the SD reference of the z-score floor; exclusion rates of the gap verification on synthetic audio |
| `core.py` | B2 core (BRAIN_SPEC 4.1, untrained): 4 LRU layers, heads, precision coupling, state carry, mode clamp; init rules in its docstring |
| `b2.py` | B2 readouts (ridge on the frozen state), lanes (band power, surprisal, neuromod, grid phase) at 10 Hz, JSON export, static HTML traces; `b2.py fit`, `b2.py run`; fixed choices in its docstring |
| `train.py` | B3 training loop (60 s chunks, state carried, AdamW, clamp, 3 x 10 h wall-clock cap, resumable checkpoints); choices in its docstring; CLI `train.py --manifest --stats --out --epochs [--no-phase]` |
| `prep_corpus.py` | raw fast features and offline-grid beats per track, `manifest.json`, `stats.npz` (`corpus` or `mp3dir` mode) |
| `check_b3.py`, `precheck_data.py` | all B3 checks (4.3 baselines and gate, 4.4 habituation, 4.5 splice, 4.6 reported) from a checkpoint, writes `results.json`; `--smoke` never writes to the results folder; choices in its docstring |
| `test_*.py` | unittest, synthetic data only |

PLL baseline: `crates/hyst-audio/examples/beat_pll.rs` (`cargo build --release -p hyst-audio --example beat_pll`).

Tests: `cd scripts/brain && /secondary/hyst-env/brain/bin/python -m unittest discover -s . -p "test_*.py"` (the last one, `test_check_b1`, builds the PLL example if missing and takes about 35 s).

`check_b1.py` has never been run on a test set.
