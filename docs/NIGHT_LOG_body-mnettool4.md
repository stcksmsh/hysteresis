# Night log: body-mnettool4 (work order 30A)

## MORNING SUMMARY

- Step 1 done: ENERGY READY 9d99a8e (formula pushed before any dial value was read).
- Step 2 done: COMPARISON READY (below). Tool follows.

## Step 1

Formula `docs/EAR_ENERGY_RULES.md`, code `scripts/body/ear_energy.py`, constants `scripts/body/ear_energy_norm.json` (fitted once on the three
danced songs' features; no dial value read, no correlation computed). Tests `scripts/body/test_ear_energy.py` 6 OK. Use
`ear_energy.network_input(feats)` for the network.

ENERGY READY 9d99a8e

## Step 2

`scripts/body/arousal_energy.py` (brain env, cores 12-17, 6 threads) -> `/secondary/hyst-data/body/arousal_energy/` (numbers.json, lags.csv,
excerpts.csv, arousal_vs_ear.csv, feature arrays) and `docs/AROUSAL_ENERGY_REPORT.md`. Check: the excerpt `arousal_b7` raw and standardised
values reproduce 29C's manifest values (0.485 / -0.227, 1.405 / 0.659, ...). Instant Crush pass A comes from `dial-ic-try1.json` (arousal
axis, column 2; take stopped at about 329 s), marked TRY1 everywhere. Check songs: features from the full mp3, lanes from round 1's `work3`.
Taps: not correlated (none recorded in dial2). No verdict.

COMPARISON READY
