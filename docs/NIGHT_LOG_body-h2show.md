# NIGHT LOG: work order 2, builder 2 (memory and show tracks), branch body-h2show

## MORNING SUMMARY (filled at the end; updated after every phase)

- Phase 1 (H2 toy): not finished.
- Phase 2 (brainDump): not started.
- Phase 3 (B7 lanes into mindState): not started.
- Phase 4 (trace viewer): not started.

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
