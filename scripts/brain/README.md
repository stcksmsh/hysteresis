# scripts/brain: B1 pulse (docs/BRAIN_SPEC.md sections 1.1, 2)

Environment: `/secondary/hyst-env/brain` (uv; numpy, scipy, soundfile, librosa 1.0.0, mir_eval 0.8.2, pytest, plus numba and llvmlite from librosa).
Data and outputs stay outside git: `/secondary/hyst-data/brain/` (test sets in `testsets/`, check outputs in `b1/`).

| File | What |
|---|---|
| `fast_features.py` | the 44 fast features at 100 Hz; STFT, mel range, band groups and onset formula fixed in its docstring |
| `grfnn.py`, `GRFNN_PARAMS.md` | Hopf bank, beat readout with the 20 % / 2 s hysteresis rule; every value with its source |
| `gaps.py` | gate 2 gaps (silence, shaped noise), seed 20261029, and the gap verification by permutation test |
| `scoring.py` | gates 1 to 3 (pass rules in its docstring), bootstrap and permutation seeds |
| `testsets.py`, `testsets/*.sha256`, `testsets/AUDIT.md` | Ballroom and GTZAN loaders, hash lists of every file used, audit |
| `check_b1.py` | one script for all gates; `results.json` and `check_b1.log` go to `/secondary/hyst-data/brain/b1/` |
| `synthetic_input_sweep.py`, `sd_reference.py`, `synthetic_exclusion.py` | the synthetic sweep that fixed the input gain; the SD reference of the z-score floor; exclusion rates of the gap verification on synthetic audio |
| `test_*.py` | unittest, synthetic data only |

PLL baseline: `crates/hyst-audio/examples/beat_pll.rs` (`cargo build --release -p hyst-audio --example beat_pll`).

Tests: `cd scripts/brain && /secondary/hyst-env/brain/bin/python -m unittest discover -s . -p "test_*.py"` (the last one, `test_check_b1`, builds the PLL example if missing and takes about 35 s).

`check_b1.py` has never been run on a test set.
