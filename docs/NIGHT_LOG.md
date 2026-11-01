# NIGHT LOG: B7, overnight order of 2026-11-02

## MORNING SUMMARY (updated after every phase)

- Phase: 0 (setup) done. Path through the decision tree: not started.
- Toys: not run yet. Leak: not looked at yet. Smoke: not run yet. Training: not launched.
- FOR USER: (none yet)
- Commits: see the log below.

## LOG

- 2026-11-02 00:30 Setup: order read; rulings R1 to R7 added to BRAIN_SPEC.md as 7.10 (before any code). Branch b7 at 1e95c5b.
- 2026-11-02 00:40 Phase 1a done in code (not yet committed): R1/R2 implemented in scripts/brain/core_b7.py (pointer replay, centred keys, 17 s eligibility, 2 s blocks, two-level per-row scan in core.py), toy_b7.py rewritten (designs A/B/C, T1a/T1b split, oracle, aux option, T2 with tapped skip option). 27 unit tests pass (replay equals the true targets on an exact repeat to 1e-5; untrained retrieval finds an exact repeat in 100 % of repeat blocks; identity float64 < 1e-9).
- 2026-11-02 00:35 Toys launched in parallel (4 threads, 6 GB scope each): t1A, t1B, t1C, t1A oracle, t2 (2000 steps). Logs in /secondary/hyst-data/brain/b7/toys/.
