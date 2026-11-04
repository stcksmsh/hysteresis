# NIGHT LOG: work order 4, builder 3, the H3 toy (blend memory), branch body-h3

## MORNING SUMMARY (filled at the end; updated after every phase)

- H3 toy: try 1 not run yet.

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
