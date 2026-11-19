# NIGHT LOG: work order 2, builder 2 (memory and show tracks), branch body-h2show

## MORNING SUMMARY (2026-11-04; phases 1-3 done, phase 4 built and syntax-checked only)

- **H2: FAIL after two tries. The hippocampus stays closed for this plan** (the work order's default). Ratio repeat / first (<= 0.5 needed), A iid | B levels+clock | C smooth:
  try 1 (k 64, tau 0.05) 1.000 | 0.810 | 0.769; try 2 (k 16, tau 0.02) 1.000 | 0.861 | 0.852. Retrieval off: 1.000 everywhere. T1a (share in first S >= 0.5 and recognition median above the
  p95 of the non-repeat frames): try 1 A fail (0.071; 0.833 vs 0.845), B fail (0.821; 0.257 vs 0.287), C pass (0.853; 0.230 vs 0.228); try 2 A fail (0.335; 0.807 vs 0.783), B fail
  (0.835; 0.312 vs 0.341), C fail (0.750; 0.207 vs 0.222). Untrained H2 passes T1a on all three (1.0 | 0.96 | 0.96 in try 1).
- **Baselines, same toy:** untrained-H1 keys (frozen key / query / tau, relay trains) ratio 1.000 | 0.856 | 1.054, T1a fail on all three (share 0.0 | 0.777 | 0.527). Oracle (true pointer) ratio
  0.327 | 0.440 | 0.348, T1b pass on all three. So the relay uses a correct replay; no tried code (trained H1 keys, frozen H1 keys, H2 sparse codes) got a trained model to retrieve it.
- **brainDump** (`scripts/brain/braindump.py`, schema `braindump.schema.json`): B7 epoch 6, 30 Hz, float16 `.npz` + json. Size per song: instant-crush 46.1 MB (340 s), five-years 38.6 MB (284 s),
  presence 36.8 MB (271 s), in `/secondary/hyst-data/brain/braindump/`. Coherence thresholds (per layer L1..L4): 0.1454, 0.2046, 0.1408, 0.1654 = the 99th percentile of the windowed order
  parameter over 20 training songs (seed 20261104; ids in `scripts/brain/braindump_thresholds.json`, committed before the danced songs ran). Crossings (>= 3 of 4 layers above own threshold):
  0 of 53,177 windows on those 20 songs and 0 on each of the three danced songs. With 99th-percentile thresholds and a 3-of-4 rule a crossing is a very rare event; nothing was changed.
- **B7 lanes in `mindState`:** `/secondary/hyst-data/brain/mindstate/mind-<song>.json` = the core-2b mind file with an additive `mindState.brain` object (0.1 s bins, mechanism names:
  surprisal L1..L4 + total, smoothedSurprisal, arousalSignal, l4PredictedVariance, surprisalSlope30s, bandPower, gain, exponent, selfSimilarity, coherence, crossing). `mood.*` is unchanged
  (verified equal to the input file). The authoring page now builds from these lanes (`scripts/author/build.py`).
- **v47 check:** not run. No file the dance path reads was changed: `mind_state.rs` got one added test, the planner does not read mindState (D3), the compiler and `scripts/emotion/` are untouched;
  the existing `mind_state` Rust tests pass (11). Say if the overseer wants `three.sh` run anyway.
- **Tests:** `scripts/brain` 176 pass (1 skipped = cuda); `cargo test -p hyst-compile mind_state` 11 pass.
- **FOR USER:** (1) the lanes sit in `mindState.brain`, not in the reserved `bands/surprise/neuromod` arrays: the version-1 Rust reader rejects anything non-empty there. Moving them needs mindState
  version 2 and a Rust change; default taken: no Rust change. (2) The 3-of-4 coherence crossing never fires at the ruled thresholds. (3) The trace viewer (`braindump_view.py`) was built and its script
  syntax-checked, not opened in a browser or looked at. (4) A and B of try 1 hit the flat-loss rule before 1,500 steps (as in H1); all runs did.
- **Branch** `body-h2show`, data under `/secondary/hyst-data/brain/{h2,braindump,mindstate}/`. Nothing is running.

## LOG

- 2026-11-04 Setup. Order: origin/body:docs/BUILDER_PROMPT_WO2_SHOW.md. Worktree `.claude/worktrees/body-h2show`, branch body-h2show from origin/body 6f414dd.
  Read: BODY_BRAIN_PLAN v2, WORK_ORDER_2026-11-04, NIGHT_LOG (H1, B7), core_b7.py, toy_b7.py.
- 2026-11-04 H2 build. `core_b7.py` gained two hook methods (`_key_of`, `_query_of`), default behaviour unchanged. `hippo_h2.py`: `Core7H2` = Core7 with
  a fixed random projection (buffer `dg_proj`, seed 20261104) of [raw features pooled over 2 s, layer norm of L3 + L4 modes] to 2,048 dimensions, top-k by value
  (k = 64), L2-normalised, no centring; key and query both detached (no gradient anywhere into the code); `log_tau` frozen. Storage, 17 s eligibility,
  top-4 softmax, pointer replay + recognition into the relay, 0.5 s novelty lane are the unchanged Core7 code. In the toy the whole small model trains from
  random init as in H1 (the cortex is not frozen on the toy), but nothing in the code path is learned.
  Baselines (same toy, same settings): `frozen` = the H1 architecture (learned-type 64-d centred key, tau 0.1) with key / query projection and tau frozen at their
  random init (the untrained H1 keys; relay and the rest train); `oracle` = toy_b7's oracle run (true pointer), now on all three designs.
  Unit tests (`test_h2.py`): projection fixed and no gradient; code sparse, unit, detached; storage one-shot (entries unchanged after every weight is perturbed) and
  eligibility age (every source <= n - 1700); novelty lane every 50 frames; an exact repeat is found.
- 2026-11-04 TRY 1 PARAMETERS (written before the run): k = 64 (of 2,048, 3.1 %), tau = 0.05 fixed, 1,500 steps planned, lr 3e-3, 8 sequences per step, seed 0, eval 32
  draws seed 991, 2 threads per run, three designs in parallel (6 threads), existing flat-loss stop (300 s without improvement) kept. Bar: T1a + T1b of BRAIN_SPEC 7.10 R3
  (T1b ratio repeat / first <= 0.5; T1a source share >= 0.5 and recognition median above the 95th percentile of the pre-repeat frames). Try 2 may change only k, the
  sparsity and tau.
- 2026-11-04 Phases 2 and 3 done while try 1 ran (see below). Run-time notes: three parallel runs peak past the 6 GB cap (2.4 GB each), so runs go two at a time at 3 threads;
  run_job's idle limit killed design C of try 1 after 1,800 s of silent logs (stdout goes to files); C was rerun alone from scratch with the idle limit at 10,800 s
  (killed log kept as try1_h2_C.killed-idle.log). Nothing about the toy changed.
- 2026-11-04 TRY 1 RESULT (k = 64, tau = 0.05; each stopped by the flat-loss rule at ~425-450 steps). Ratio repeat / first (<= 0.5 needed), A | B | C: 1.0004 | 0.810 | 0.769,
  T1b fails on all three; retrieval off 1.000 | 1.000 | 0.999. T1a: A fail (source share 0.071, recognition median 0.833 vs p95 0.845), B fail (0.821, 0.257 vs 0.287),
  C pass (0.853, 0.230 vs 0.228). The same model before training passes T1a on all three (share 1.0 | 0.96 | 0.96). Novelty lane (repeat-tick mean vs outside-tick mean):
  A 0.163 vs 0.278, B 0.733 vs 0.792, C 0.753 vs 0.858 (lower inside the repeat in every design). Logs: /secondary/hyst-data/brain/h2/try1_h2_{A,B,C}.log.
  Reading, numbers only: the codes retrieve the source before training and lose it as the model trains (its L3 + L4 state is part of the code), and the relay does not
  turn a found source into lower error (ratio near 1).
- 2026-11-04 TRY 2 CHANGE (written before the run; k, sparsity, tau only): k = 16 of 2,048 (0.8 %), tau = 0.02. Everything else as try 1. Reason (a reading, not tested):
  non-repeat recognition after training is high (0.83-0.84 on A), so sparser codes and a sharper softmax lower the similarity of unrelated moments. Baselines on the same
  toy, one run per design: `frozen` (H1 architecture, key / query / tau frozen at init) and `oracle` (true pointer), run after try 2.
- 2026-11-04 TRY 2 RESULT and baselines: see the MORNING SUMMARY (logs try2_h2_*.log, base_frozen_*.log, base_oracle_*.log in /secondary/hyst-data/brain/h2/). DECISION: both tries failed; the hippocampus is
  closed for this plan, as the order's default says.
- 2026-11-04 Phase 2: thresholds fitted (3 min on 3 threads) and committed, then the three songs exported (22 s, 10 s, 8 s). Phase 3: `brain_mindstate.py`. Phase 4: `braindump_view.py` (not looked at).
