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

## Full training and stop measures (2026-11-14)

- Trained K = 1024, 512 (then 256, 128), 4 threads per unit, units `hyst-wo38-k<K>`; 1024, 512, 256 reached the 40-epoch cap (error still falling at the cap), 128 stopped early at epoch 27. Size rule: K = 1024 (ratios 1.104 / 1.118 / 1.151, none within 5 percent; checked in `t1a_eval.pick_size`, tested).
- Stop measures on the 2,455 test windows (`docs/T1A_REPORT.md`): code usage 0.999 (>= 0.60 holds); joint ranges 0.946-1.000 of the original (within 10 percent holds); gate pass share 0.980 (control, the original windows: 1.000; FineDance 0.951, AIOZ 0.986); **jitter ratios far above 1.1: acceleration sign changes 7-10 x, power above 3 Hz 17-110 x the original (all four sizes, both sources)**. The numbers are in the report; no verdict here.
- FOR USER: the jitter excess comes from the reconstruction (the originals are low-passed to 2.5 / 5.75 Hz); the gates still pass 98 percent because the spinal layer and limiter smooth the commands. Pre-roll rows of the gate use the original targets; yaw and roll are re-referenced to the window start (approximation of the T0 gate, control 1.000).

T1A READY
