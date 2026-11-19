# Planner brief: work order 2 results (2026-11-04)

Both builders finished. Branch `body` at 4b0fcbd (merges of `body-h2show` and `body-m1m3`). The overseer reran the tests (scripts/brain 176 OK,
1 cuda skip; scripts/body: test_body 10, test_babble + test_m3 6, test_tm3 9, all OK; hyst-compile and hyst-cli: test, clippy -D warnings
and fmt clean), rebuilt v47 from `body-m1m3` (byte-identical on all three songs), and recomputed the numbers marked (R) from the saved files.
Provisional servo model throughout (Feetech STS3215 12 V; kp, rotor inertia, damping 1.5, acceleration share 0.25).

## The work order's "what comes back" list

**K1 (R), from `k1_round2.json`.** Both rounds fail, so the M1 claim is not licensed.
- Round 1 (GRU 128, 30 epochs, local, 3,588 s): babbling fails at +50 ms (NLL gain vs ridge −0.17 [−0.18, −0.16]); v47 fails every condition.
- Round 2 (GRU 256, 30 epochs, local, 6,732 s; width and training length only):
  - Held-out babbling, 120 trajectories: passes at all three horizons. NLL gain vs ridge 1.26 / 0.42 / 0.41 (intervals above 0), MSE
    86 % / 66 % / 56 % below ridge.
  - v47 set, 78 segments of 60 s from 18 arm trajectories, two-level bootstrap, conditional on these three songs (unison and mirrored arms are
    near-duplicates): MSE passes (59 % / 67 % / 72 % below the better baseline); NLL fails. Gain vs persistence −3.28 [−4.79, −1.88],
    −0.66 [−1.87, 0.31], 0.04 [−0.89, 0.85]; vs ridge −4.01 [−5.40, −2.70], −1.23 [−2.17, −0.50], 0.96 [0.71, 1.20].
  - Reading (the builder's, not tested): point predictions are accurate out of distribution; the predicted variances are too narrow. The
    v47 targets exceed M0's limits (the limiter changes them by up to 10° RMS) and are smoother than the babbling.
- **Self-surprisal lane: not exported** (K1 failed; no export code written). Question 1.

**M3 step benchmark** (from the night log; not recomputed). Wall seconds per simulated hour: laptop CPU 51.1 / 57.7 / 59.5 at 16 / 64 / 256
environments; Kaggle T4 41.4 / 42.5 / 39.2. 256 environments fit (6.7 GB laptop, 5.5 GB GPU). Laptop time is ~85 % cortex twin pass + relay
backward; on the T4 the 4 CPU cores doing physics dominate. **Identity (R, test rerun):** with the new relay at zero, cortex outputs equal B7
epoch 6: float64 max difference 0.0, float32 0.0.
- **Caveat for the real M3 run:** B7 runs in 2 s blocks (200 frames), and a chunk must start on a block edge. With epoch 6 frozen, the policy
  sees the cortex state of the previous block (up to 2 s old). The toy used 0.5 s blocks (its cortex is retrained). Question 3.

**T-M3 (R), from `try1.result.json`, `try2.result.json`.** Fails twice, so M3 stops by plan §6.
- Grid: 18 settings. Chosen by the rule: β 0.1, λ 1, c_sw 0.1. Toy cerebellum: the round-1 bundle (the builder's choice, for comparability with
  the grid's calibration; the prompt said the better bundle, round 2).
- Try 1: (a) 0.799 [0.767, 0.832] pass; (b) 42.1 °/s pass; (c) PLV 0.0285, surrogate max 0.0352, p = 0.016, needs < 0.01: **fail**.
- Try 2 (one change, logged before the run: learning rate 1e-3): (a) 0.645 [0.616, 0.676] pass; (b) 46.7 °/s pass; (c) p = 0.90: **fail**.
- Selection collapsed in both tries: 2 programs used, counts 1,432 and 8 (identical in both tries), 0.67 switches/min, entropy 0.034 nats.
- **(b) comes mostly from the wrist roll and the base.** Per-joint RMS speed, try 1: base 53.0, shoulder 14.5, elbow 0.13, wrist bend 5.6, roll 76.2 °/s;
  the dominant joint is the roll in all 8 episodes. The roll moves no point of the chain (it only turns the mirror ball).
- **Control on (a):** feeding the proprioception shifted by half an episode gives still − shifted 0.68 against still − moving 0.80. So about 85 %
  of (a) is the relay preferring a moving arm's input in general; about 0.13 depends on the actual timing.
- SYNC fallback γ grid (flag on, report only): no γ passes (c) (PLV 0.016 / 0.013 / 0.023). γ fixed at 1 by the builder.
- Process note: try 1's first launch was killed for memory in evaluation before the policy was saved, so training was rerun with the same
  setting (logged as engineering, not try 2). Kaggle GPU used about 0.05 h.

**H2 (R), from the run logs.** Fails both tries; the hippocampus is closed for this plan. Ratio repeat / first (≤ 0.5), A | B | C:
try 1 (k 64, τ 0.05) 1.000 | 0.810 | 0.769; try 2 (k 16, τ 0.02) 1.000 | 0.861 | 0.852. T1a: try 1 passes only on C; try 2 none.
Baselines: frozen H1 keys 1.000 | 0.856 | 1.054; oracle 0.327 | 0.440 | 0.348 (T1b passes on all three). The untrained H2 code passes T1a on all (builder's number)
three designs; training the relay does not make it use the retrieval.

**brainDump (R).** B7 epoch 6, 30 Hz, float16 `.npz` + JSON schema, in `/secondary/hyst-data/brain/braindump/`: Instant Crush 46.1 MB, Five Years
38.6 MB, Presence 36.8 MB. Coherence thresholds L1–L4 0.1454 / 0.2046 / 0.1408 / 0.1654 (99th percentile, 20 training songs, seed 20261104),
committed 13:00:22, before the danced songs ran (13:00:46 onward). **Crossings: 0 on every danced song** (recomputed); no window there has even
2 layers above threshold; the per-layer share above threshold is at most 2.9 % (Five Years, L4). The 20 training songs also had 0 crossings in
53,177 windows (builder's number). With this definition the ignition lane is empty. Question 4.

**B7 lanes in `mindState`.** `/secondary/hyst-data/brain/mindstate/mind-<song>.json` = the core-2b file plus an additive `mindState.brain`
object (mechanism names, 0.1 s bins); `mood.*` unchanged; the authoring tool reads it. The reserved `bands` / `surprise` / `neuromod` arrays stay
empty: the version-1 Rust reader rejects them non-empty, so moving lanes there needs a version 2 and a Rust change.

**Trace viewer:** built (`scripts/brain/braindump_view.py`), not opened in a browser.

**FOR USER items:** `manifest.py` should skip `dataset-metadata.json` (the Kaggle verify job's only mismatch; every data file's hash matched);
the self-surprisal export (question 1); `mindState` version 2 (question 5).

## Where this leaves the plan

The body track stops at M3 (T-M3 failed twice). By §6 the fallback drives the arm: the authoring tool on brain lanes. The memory track is
closed (H1 and H2). The show track has its first data (brainDump, `mindState` lanes).

## Questions

1. **Self-surprisal lane.** K1 failed, so no claim. Export it from the round-2 bundle anyway as a mechanism-named data lane for the monitor (the
   cerebellum's prediction error of its own arm)? Recommendation: yes, no claim, like self-similarity.
2. **T-M3's failure.** Selection collapsed to one program, and most of the movement went into the wrist roll, which turns the mirror but moves
   no point of the arm. (a) is mostly "a moving arm in general". Is M3 closed for this plan (the fallback drives the arm), or is there a
   restart with a new pre-registered toy? Recommendation: treat it as closed by the rule. Any restart is a new plan item with its own toy bar, and it
   should name the roll problem (for example, exclude the roll from (b) and from the dominant joint).
3. **The 2 s staleness** matters only if a real M3 run ever happens. Recommendation: park it with question 2.
4. **Ignition lane.** With the per-layer 99th-percentile and 3-of-4 rule, there are zero crossings on all songs, so the lane shows nothing. Keep the
   definition (an honest empty lane), or change it before any display (for example 2 of 4, or a 95th percentile)? Recommendation: this is a
   design choice for the monitor, not a claim; let the user decide by eye on the trace viewer.
5. **`mindState` version 2** (B7 lanes in the reserved arrays, Rust reader change). Recommendation: do it with the monitor build, keeping v47
   byte-identical in `Off`.
6. **Next work order.** The fallback (the authoring tool on B7 lanes) and the monitor (mockups, then build) are what is left. Recommendation:
   the planner's mockups next, then a builder order for the monitor page on brainDump; the authoring fallback on B7 lanes in parallel.
