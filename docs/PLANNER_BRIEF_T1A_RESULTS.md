# Planner brief: T1a motor vocabulary results, a stop rule fires (BRAIN_SPEC 7.59.4.1), 2026-11-14

TO: planner. FROM: overseer, for Kosta. T1a trained all four codebook sizes. Report: `docs/T1A_REPORT.md` (branch body). Data:
`/secondary/hyst-data/body/t1a/`. Numbers below recomputed by the overseer where marked.

## What ran

T0 data: 369,200 train chunks (FineDance 101,760 / AIOZ 267,440), validation 38,720, test 98,200 (83 % AIOZ). VQ autoencoder per
`T1A_RULES.md` (EMA codebook, dead-code reset, conv decoder with 0.21 s lookahead, MSE loss in per-joint scaled units, 40-epoch cap,
patience 5). Two sizes at a time, 4 threads each; about 2.7 h per pair.

## Results

| K | best validation error | epoch | FineDance | AIOZ |
|---|---|---|---|---|
| 128 | 0.5906 | 21 (early stop) | 0.741 | 0.293 |
| 256 | 0.5133 | 39 (cap) | 0.645 | 0.252 |
| 512 | 0.4592 | 39 (cap) | 0.576 | 0.226 |
| 1024 | 0.4158 | 37 (cap) | 0.520 | 0.205 |

- Size rule: ratios to the next larger 1.151 / 1.118 / 1.104, none within 5 % -> **K = 1024**. Three sizes were still improving at the cap.
- Stop measures (test windows, all sizes alike): code usage 0.999 (pass); joint ranges 0.946-1.000 of original (pass); gates at 1.25:
  0.980 (FineDance 0.951, AIOZ 0.986; original windows 1.000).
- **Jitter FAILS (stop rule <= 1.1x):** acceleration direction changes 7-10x the original, power above 3 Hz 17-110x, every size, both
  sources. Overseer recompute (K = 1024, 200 test windows): about 40 changes/s on every joint vs 4-5 original (ratios 7.9-10.1).
- **Where it comes from (overseer, report-only):** the decoder adds a small broadband ripple: RMS above 8 Hz 0.1-0.9 deg per joint, where
  the original has almost none. Not at chunk boundaries (mean step at chunk edges 0.337 vs 0.342 elsewhere). 88 % of the reconstruction
  error is below 3 Hz (the shape error itself). A 6 Hz zero-phase low-pass on the output brings changes to about 8/s (still about 2x the
  original) and lowers the error slightly. Reconstruction RMS error per joint: 0.9 / 2.9 / 5.0 / 4.9 / 7.3 deg (base, shoulder, elbow,
  wrist bend, wrist roll).

## Questions

1. **Fix for the ripple** (retrain K = 1024 only; the size rule is settled):
   - (a) Add velocity and acceleration reconstruction terms to the loss, as in Bailando's own VQ-VAE (the builder quotes the paper's
     terms and weights and uses them as written), plus raise the epoch cap to 80 (error was still falling) **[recommended]**;
   - (b) (a) plus a fixed output low-pass in the decoder (FIR, lookahead <= 0.25 s, cutoff by a stated rule);
   - (c) the 2-stage residual quantisation fallback (targets the shape error, not the ripple);
   - (d) other.
2. **Jitter stop rule on rerun:** keep <= 1.1x the input's on both measures (acceleration direction changes, power above 3 Hz)? [recommended:
   keep]
3. Should the overseer stop at the rerun's numbers before S1 as now (S1 only if all T1a stop rules pass)? [recommended: yes]
4. Record as 7.61.
