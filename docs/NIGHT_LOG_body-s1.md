# Night log, builder (body-s1), work order 20, Stage 1 toy (2026-11-09)

## MORNING SUMMARY

Toy built, NOT run. Rules `docs/STAGE1_RULES.md` (committed first, amended once, section 10). `scripts/body/s1_toy.py` + `test_s1_toy.py` (13 tests pass: InfoNCE picks the correct pair, observer Lipschitz <= G=4 measured,
log det K rises with spread, hinges 0 inside the envelope, causal z-score is causal, 1-epoch smoke per arm). Smoke: 0.37 / 0.39 / 0.54 / 0.53 s per epoch (arms i-iv, 3 threads); 10 runs x 1000 epochs is about 1.5 h serial.
Waiting for "run Stage 1". FOR USER: none.

## Log

- Environment has no optax, sklearn, torch, pytest: own Adam, own L2 logistic regression (scipy L-BFGS), unittest.
- One run: `python s1_toy.py --arm iv --seed 0 --epochs 1000 --lam 0.5 --out /secondary/hyst-data/body/s1/run_iv_0.5_s0`; result.json holds val and held-out measures.
- Smoke outputs are in `/secondary/hyst-data/body/s1/smoke_*` (2 epochs, not results).
