# NIGHT LOG: work order 5, the H4 toy (uncertainty-based arbitration), branch body-h4

## MORNING SUMMARY (filled at the end; updated after every phase)

- H4 toy try 1 (window 100, k 64, tau 0.05): T1a pass on A, B, C; T1b FAIL on all three (ratio repeat/first A 0.876, B 0.737, C 0.566; cortex-only 1.00; oracle 0.327|0.440|0.348). Try 2 (window 200) running.

## LOG

- 2026-11-04 Setup. Order: origin/body:docs/BUILDER_PROMPT_WO5_H4.md; BRAIN_SPEC 7.16 point 3, 7.15, 7.10 R3. Worktree `.claude/worktrees/body-h4`, branch body-h4 from origin/body 75ad095. Power: mains. Share 3 threads, 4 GB
  (a run peaks near 2.4 GB). Read: NIGHT_LOG_body-h3 / body-h2show, hippo_h2.py, hippo_h3.py, toy_h3.py, test_h3.py, core_b7.py.
- 2026-11-04 Build, before any result recorded here (`hippo_h4.py`, `test_h4.py`, `toy_h4.py`). No change to `core_b7.py` (H3's `tap_replay` flag is reused). **Nothing is trained**: no new parameter,
  every parameter frozen, the toy cortex is H3's (trained as in H2's toy with the hippocampus off, then frozen; the files `/secondary/hyst-data/brain/h3/cortex_<design>.pt` are loaded, not retrained), the
  code and store are H2's, the replay is the B7 pointer replay from the top-4 sources.
  **Causal error bookkeeping (stated before the first recorded run):** the prediction made at frame s for the window [s + h, s + 2h) is scored when its target has arrived, at frame u = s + 2h - 1.
  err_c[u] is the model's own error; err_h[u] = err_c[u] + (mu_c - replay)[s] (the same window mean minus the replay made at s), counted only where a source existed at s. q = mean over the 44 features of the squared
  error. e_c[t] = mean of q_c[u], e_h[t] = mean of q_h[u], over the valid frames u in (t - WINDOW, t], WINDOW = 100 frames = 1 s (try 2: 200). If the window holds no valid hippocampal frame, w = 0 (no
  evidence: the cortex alone). Each e is floored at 1e-6. w = (1/e_h) / (1/e_h + 1/e_c) = e_c / (e_c + e_h). w[t] uses only errors at frames <= t, whose targets ended by t (a unit test changes everything
  after t0 and checks w up to t0 is bit-identical, in the pure function and in the model). Mean and variance blended exactly as in H3: mean = (1 - w) mu_c + w replay; var = (1 - w) var_c + w 0.05 +
  w (1 - w) (mu_c - replay)^2; the blend's err = err_c + (mu_c - mu) shifted 2h - 1 frames.
  Unit tests (`test_h4.py`, 10): equal errors give w = 0.5; hippocampal error to 0 gives w -> 1; no source gives w = 0; causality (function and model); the window is the last 100 frames; nothing is trained and
  there is no new parameter and no output carries a gradient; arbitration off recovers the cortex's mean and err exactly; storage one-shot and 17 s eligibility; the blend formula is H3's.
  Citation: Daw, Niv & Dayan, "Uncertainty-based competition between prefrontal and dorsolateral striatal systems for behavioral control", Nature Neuroscience 8(12):1704-1711, 2005. From memory; **not verified**.
  Reported per design: T1a, T1b (ratio repeat / first over L1-L3), cortex-only (arbitration off, a real w = 0), mean w per layer inside the repeat (from its 2nd second) and outside it (from 17 s on).
  Oracle = H2's runs (0.327 | 0.440 | 0.348), same toy and evaluation, not rerun. Bar: T1a + T1b of 7.10 R3; two tries; try 2 may change only the window, to 200 frames.
  Disclosure: design A was run once as a smoke test of the runner (window 100, k 64, tau 0.05, the order's values) before this entry was written; the full try 1 below reruns all three designs (deterministic).
- 2026-11-04 Try 1 rerun cleanly (A, B, C; earlier killed partial run kept as try1_killed_partial.log, A identical). Results in docs/h4_try1_results.jsonl.
  T1a pass A/B/C; T1b fail A/B/C: ratios 0.8759 / 0.7369 / 0.5655 (cortex-only 1.0000 / 1.0000 / 1.0001). Mean w L1-L3,L4 inside repeat / outside from 17 s:
  A 0.522 0.519 0.531 0.385 / 0.431 0.424 0.358 0.239; B 0.188 0.445 0.596 0.397 / 0.067 0.221 0.366 0.243; C 0.313 0.610 0.691 0.535 / 0.074 0.227 0.326 0.280.
  Next: try 2, window 200 only.
