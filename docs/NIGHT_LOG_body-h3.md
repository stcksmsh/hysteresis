# NIGHT LOG: work order 4, builder 3, the H3 toy (blend memory), branch body-h3

## MORNING SUMMARY (2026-11-04; both tries run)

- **H3: FAIL after two tries (T1b). The hippocampus stays off.** Ratio repeat / first (needs <= 0.5), A iid | B levels+clock | C smooth: try 1 (lr 0.05, 400 steps, b0 0.5) **0.921 | 0.681 | 0.520**; try 2 (lr 0.1,
  1,500 steps, b0 0.8) **0.921 | 0.699 | 0.552**. **T1a passes on all three designs in both tries** (source share 0.812 | 0.830 | 0.955; recognition median above the p95 of non-repeat frames: 0.853 vs 0.808,
  0.543 vs 0.463, 0.314 vs 0.220).
- **Baselines (same toy and evaluation):** cortex-only (frozen toy cortex, w = 0) 0.881 | 0.656 | 0.566 (so the blend is worse than cortex-only on A and B in both tries, better on C only in try 1, by 0.046);
  oracle (H2's runs) 0.327 | 0.440 | 0.348, T1b pass. Blend untrained (a 8, b 0.5) 0.904 | 0.801 | 0.817.
- **Learned a and b per layer (L1..L4):** try 1 A a [7.4, 8.8, 18.8, 6.7] b [0.993, 0.905, 0.801, 1.365]; B a [8.9, 22.8, 20.2, 22.5] b [1.338, 0.539, 0.425, 0.422]; C a [7.3, 8.4, 18.8, 21.7] b [0.745, 0.304, 0.158, 0.161].
  Try 2 A a [11.4, 13.3, 57.0, 3.5] b [0.94, 0.89, 0.76, 1.96]; B a [9.4, 40.7, 23.6, 33.2] b [1.36, 0.51, 0.41, 0.37]; C a [7.5, 8.5, 23.6, 36.1] b [0.87, 0.36, 0.20, 0.19].
- **Variance formula (fixed before the first run):** var = (1 - w) var_c + w VAR_H + w (1 - w) (mu_c - replay)^2, VAR_H = 0.05; w = has * sigmoid(a (recognition - b)). Cortex: trained as in H2's toy with the
  hippocampus off, then frozen, one per design (`/secondary/hyst-data/brain/h3/cortex_<design>.pt`).
- **Unit tests:** `test_h3.py` 6 pass (gradient only on a and b; w = 0 recovers the cortex; w = 1 gives the replay; err of the blend; one-shot storage and 17 s eligibility; cortex equals a hippocampus-off Core7).
  Whole `scripts/brain` suite: 182 pass (1 skipped = cuda).
- **Citation:** kNN-LM = Khandelwal, Levy, Jurafsky, Zettlemoyer, Lewis, "Generalization through Memorization: Nearest Neighbor Language Models", ICLR 2020 (arXiv 1911.00172). **Not verified** (written from memory, no check made).
- **FOR USER:** (1) the toy cortex trained without the hippocampus already reaches 0.57-0.88 on T1b (it carries some of the repeat in its slow state), so the 0.5 bar leaves the blend little room on A and B; the work
  order fixed the bar, nothing was changed. (2) The recognition gap between repeat and non-repeat frames is small on A (0.853 vs 0.808), so a recognition gate cannot separate them there. (3) `core_b7.py` gained one
  default-off flag (`tap_replay`).
- **Branch** `body-h3`, data `/secondary/hyst-data/brain/h3/`. Nothing is running.

## LOG

- 2026-11-04 Setup. Order: origin/body:docs/BUILDER_PROMPT_WO4_H3.md; rulings BRAIN_SPEC 7.15. Worktree `.claude/worktrees/body-h3`, branch body-h3 from origin/body 6526819.
  Read: BRAIN_SPEC 7.14 / 7.15, NIGHT_LOG_body-h2show, hippo_h2.py, toy_h2.py, core_b7.py, toy_b7.py.
- 2026-11-04 Build (before any result). `core_b7.py`: one default-off flag `tap_replay` (out[0]["replay_true"] = the replay as read even when `retrieval_on` is False). `hippo_h3.py`: `Core7H3` =
  `Core7H2` (H2's fixed sparse random code, one-shot store, 17 s eligibility, top-4 softmax, unchanged and untrained) with `retrieval_on` False, so no replay or recognition reaches the relay and the
  cortex is the same function as a hippocampus-off cortex (a test checks this). Per layer i: w = has * sigmoid(a_i (recognition - b_i)) (has = an eligible source exists); mean = (1 - w) mu_c + w replay;
  **variance (stated before the first run):** var = (1 - w) var_c + w VAR_H + w (1 - w) (mu_c - replay)^2, var_c = exp(cortex logvar), VAR_H = 0.05 fixed (the replay carries no variance), logvar =
  clamp(log var, -8, 4). The error scored for the blend is err_c + (mu_c - mu) shifted 2h - 1 frames (the cortex's coupling keeps using err_c: the cortex is unchanged). Only `blend_a`, `blend_b` (4 each)
  train. Unit tests (`test_h3.py`, 6): gradient only on a and b (code, cortex, key / query, log_tau none); w = 0 gives the cortex's mean and err exactly and its logvar to 1e-5, and the cortex output does not
  depend on a and b; w = 1 gives the replay and variance VAR_H, and w = 0 where nothing is eligible; err equals the window mean minus the blended prediction made 2h - 1 frames earlier; storage one-shot
  (entries unchanged after every weight changes) and 17 s eligibility; cortex equals Core7 hippocampus-off.
  **Toy cortex:** trained exactly as in H2's toy with the hippocampus off (Core7 at small width, hippocampus=False, toy_b7.fit, beta-NLL, lr 3e-3, seed 0, 1,500 steps planned with the flat-loss stop, 8
  sequences per step), once per design, saved to /secondary/hyst-data/brain/h3/cortex_<design>.pt, then frozen. Try 2 reuses that cortex (it is not part of what try 2 may change).
  Baselines: cortex-only = the same model with w = 0 (T1b ratio; T1a is undefined without a hippocampus); oracle = H2's oracle runs on the same toy and evaluation (NIGHT_LOG_body-h2show: 0.327 | 0.440 |
  0.348, T1b pass), not rerun.
  Citation: kNN-LM = Khandelwal, Levy, Jurafsky, Zettlemoyer, Lewis, "Generalization through Memorization: Nearest Neighbor Language Models", ICLR 2020 (arXiv 1911.00172), from memory; **not verified**
  (no network check made).
- 2026-11-04 TRY 1 PARAMETERS (written before the run): k = 64, tau = 0.05 (H2 try 1's); blend training: lr 0.05, 400 steps, a initial 8, b initial 0.5 (all four layers), seed 0, AdamW as train.make_optimizer,
  20 warm-up steps, clip 1, flat-loss stop 600 s; cortex stage as above; eval 32 draws seed 991 as in H2. Try 2 may change only the training of a and b (lr, steps, initial b; initial a is outside that list
  and stays 8) and k / tau, named before the run. Bar: T1a + T1b of 7.10 R3. Runs one design at a time (4 threads, 5 GB cap; one run peaks near 2.4 GB).
- 2026-11-04 TRY 1 RESULT (k 64, tau 0.05, blend lr 0.05, 400 steps planned, a0 8, b0 0.5; cortex stage per design as stated). Ratio repeat / first (needs <= 0.5), A | B | C: **0.921 | 0.681 | 0.520**, T1b fails
  on all three. Cortex-only (w = 0, the frozen toy cortex): 0.881 | 0.656 | 0.566. Blend before its training (a 8, b 0.5): 0.904 | 0.801 | 0.817. T1a passes on all three: source share 0.812 | 0.830 | 0.955;
  recognition median vs p95 of the non-repeat frames 0.853 vs 0.808 | 0.543 vs 0.463 | 0.314 vs 0.220. Learned a (L1..L4) A [7.4, 8.8, 18.8, 6.7], B [8.9, 22.8, 20.2, 22.5], C [7.3, 8.4, 18.8, 21.7];
  b A [0.993, 0.905, 0.801, 1.365], B [1.338, 0.539, 0.425, 0.422], C [0.745, 0.304, 0.158, 0.161]. Logs /secondary/hyst-data/brain/h3/try1_{A,B,C}.log. Oracle (H2's runs, same toy): 0.327 | 0.440 | 0.348.
  Reading, numbers only: the retrieval is right (T1a), the trained blend is no better than cortex-only on A and B and 0.046 better on C; the toy cortex already reaches 0.57-0.88 without the hippocampus,
  and the recognition gap between repeat and non-repeat frames is small on A (0.853 vs 0.808).
- 2026-11-04 TRY 2 CHANGE (written before the run; only the training of a and b): lr 0.1, 1,500 steps planned (flat-loss stop 600 s as before), b initial 0.8; k 64, tau 0.05, a initial 8 and the cortex unchanged.
- 2026-11-04 TRY 2 RESULT (lr 0.1, 1,500 steps planned, b0 0.8; rest as try 1). Ratio repeat / first, A | B | C: **0.921 | 0.699 | 0.552**, T1b fails on all three (cortex-only 0.881 | 0.656 | 0.566). T1a passes on
  all three (same retrieval as try 1: share 0.812 | 0.830 | 0.955). Learned a A [11.4, 13.3, 57.0, 3.5], B [9.4, 40.7, 23.6, 33.2], C [7.5, 8.5, 23.6, 36.1]; b A [0.94, 0.89, 0.76, 1.96], B [1.36, 0.51, 0.41, 0.37],
  C [0.87, 0.36, 0.20, 0.19]. Logs try2_{A,B,C}.log. DECISION: both tries failed; the hippocampus stays off.
