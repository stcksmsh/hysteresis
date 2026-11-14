# Night log body-t1a (WO38, 2026-11-14)

- Rules `docs/T1A_RULES.md` pushed before any training (ec6bbe5). Code: `scripts/body/t1a_{data,model,train}.py`, tests `test_t1a.py` (5 pass: chunking only in kept windows, vigour round trip and floor, decoder causality / 21-step right reach, EMA update and dead-code reset on a toy case, shapes and straight-through gradient).
- Timing run (40 steps per size on the real train set, batch 16 windows, 8 threads, cores 6-13; `t1a/timing.json`):

| K | s / step | s / epoch (train + validation pass) | hours to the 40-epoch cap | RssAnon MB |
|---|---|---|---|---|
| 128 | 0.250 | 149 | 1.65 | 785 |
| 256 | 0.272 | 162 | 1.80 | 715 |
| 512 | 0.283 | 168 | 1.87 | 778 |
| 1024 | 0.289 | 171 | 1.90 | 880 |

- **Estimate:** all four sizes to the epoch cap of 40, one after the other: **7.2 h** (upper bound; early stopping with patience 5 shortens it; sizes can also run two at a time if cores allow). Peak memory about 1.1 GB (ru_maxrss), under 0.9 GB anon. 577 steps per epoch.
- Chunks (kept windows x 40): train 369,200 (FineDance 101,760 / AIOZ 267,440); validation 38,720 (17,840 / 20,880); test 98,200 (16,240 / 81,960). Windows 9,230 / 968 / 2,455.
- Per-joint scale (train gesture sd, deg): base yaw 2.0, shoulder 5.1, elbow 9.8, wrist bend 8.6, wrist roll 13.2.

FOR USER: vigour floor 0.05 and decoder smoothing box +-7 steps are my defaults (no data behind them yet); the decoder sees zero neighbours at window edges in training; the stop-measure evaluation code (jitter, ranges, gates on reconstructed windows, section 5 of the rules) is specified but not yet written, to be added before the full run; losses are on scaled gesture units, weighted by the T0 dancer weight (AIOZ clips are 72 % of train chunks before weighting).

T1A ESTIMATE
