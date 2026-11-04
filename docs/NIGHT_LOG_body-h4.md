# NIGHT LOG: work order 5, the H4 toy (uncertainty-based arbitration), branch body-h4

## MORNING SUMMARY (filled at the end; updated after every phase)

- H4 toy try 1 (window 100, k 64, tau 0.05): T1a pass on A, B, C; T1b FAIL on all three (ratio repeat/first A 0.876, B 0.737, C 0.566; cortex-only 1.00; oracle 0.327|0.440|0.348). Try 2 (window 200): T1b FAIL on all three (0.878 / 0.709 / 0.572), T1a pass. Both tries failed: memory is closed for this plan (per the order).

- WO6 diagnostic (no new try): top-k = 4 (`core_b7.TOP_K`; 64 is the sparse-code k). H4's control (arbitrate off) = 1.000 is the TRUE cortex-only; H3's "0.881|0.656|0.566" control was w = 0.5 (a=0 gives sigmoid(0), b is irrelevant), a 50% blend, mislabelled. H3 with w truly 0 gives 1.0000 on A, B, C. No deviation found in H4 (top-k, control, bookkeeping, blend) -> memory closed for this plan. Replay MSE in repeat vs cortex vs oracle: see WO6 entry below / docs/h4_diag_results.jsonl.

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
- 2026-11-04 Try 2 (window 200 only; results docs/h4_try2_results.jsonl). T1a pass A/B/C; T1b fail: ratios 0.8782 / 0.7091 / 0.5716 (cortex-only 1.0). Mean w inside repeat L1-L4: A 0.516 0.514 0.517 0.383; B 0.229 0.504 0.581 0.396; C 0.291 0.590 0.664 0.523; outside: A 0.432 0.424 0.360 0.238; B 0.071 0.248 0.369 0.242; C 0.076 0.230 0.330 0.281.
  Both tries failed. Unit tests 10/10 pass. Citation Daw, Niv & Dayan 2005 not verified. FOR USER: none.
- 2026-11-05 WO6 diagnostic (`scripts/brain/diag_h4.py`, results docs/h4_diag_results.jsonl). Try 1 settings, repeat from its 2nd second, 32 sequences, frames where both retrieval and oracle had a source.
  Replay shape (1, 200, 4, 44) = block, 4 horizons. MSE cortex | retrieval replay | oracle replay (L1, L2, L3):
  A: 0.671|0.627|1e-13; 0.188|0.178|5e-15; 0.050|0.046|4e-16.  B: 0.107|0.408|2e-12; 0.442|0.434|8e-14; 0.663|0.424|6e-15.  C: 0.120|0.344|3e-12; 0.441|0.346|1e-13; 0.674|0.307|9e-15.
  Oracle replay is exact (target is the stored frames), the retrieval replay is far from it: it reads the top-1 entry's pointer quantised to TICK = 50 frames (0.5 s) and blends up to 4 sources with softmax(sim/0.05); H2's oracle takes the exact frame s1+(n0-s2). That is H2/B7 design, not an H4 deviation.
  Control: H3's `_with(m, 0.0, 1e3)` gives w = sigmoid(0) = 0.5, not 0; H3 with a=1, b=1e3 (w=0) gives 1.0000/1.0000/1.0001 = H4's control. H4's 1.000 is correct. Cortex has no memory, so repeat = first.
  Remainder (diag rerun logging the retrieval source count, test_h3/test_h4/full unittest) runs detached: unit hyst-wo6-h4-rest, logs /secondary/hyst-data/brain/h4/{diag2,tests_h3h4,tests_all}.log, marker wo6_rest.done.
- 2026-11-05 WO6 remainder finished: retrieval weights shape (1, 4) = top-4 sources (diag2.log). Tests: test_h3 + test_h4 16 OK; full unittest 192 OK (1 skipped).
