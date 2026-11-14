# Builder prompt: work order 39, T1a retrain (Step 1 report, then Runs A and B) (2026-11-14)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.61** (all, including the overseer notes 7.61.7), then 7.59 / 7.60. No verdict. One arm. **Stop before
S1.**

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-t1a2 origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo39-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`; `python -u`; read logs 1 min after start. Run on battery. Commit and
push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads of data, uploads; reading the
Bailando paper and its official repository (web pages) for the loss is allowed. Env `/secondary/hyst-env/brain`. In: `t0/`, `t1a/`
(read-only). Out: `/secondary/hyst-data/body/t1a2/`. Keep messages short.

## The work

1. **Step 1 (report-only, from the round-1 K = 1024 model and the T0 data):** variance explained per joint (FineDance / AIOZ, validation
   and test); gesture RMS and p5-p95 per joint FineDance vs kept AIOZ (train split); effective weight share by dataset. Apply rule 7.61.3
   mechanically and write which applied. `docs/T1A2_STEP1.md`, push "STEP1 DONE <commit>" in the night log; no need to wait.
2. **Rules note `docs/T1A2_RULES.md`** (push before training): Bailando's loss terms quoted (source URL) and used as written; the B-spline
   decoder head (control points every 40 ms, total right reach <= 0.25 s); Run B residual quantiser (2 x 1024, EMA + dead-code reset per
   stage, how the correction stage is trained); 80-epoch cap; the weights (with or without the 50 % AIOZ cap); seeds.
3. **Tests:** decoder causality with the spline head; residual quantiser shapes and EMA update; the weight cap sums.
4. **Runs A and B in parallel** (cores 6-13 / 14-19, 4 threads each), resumable per epoch.
5. **Evaluation** for each run: variance explained per joint and dataset (validation and test), all T1a stop measures (usage, jitter,
   ranges, gates at 1.25, per source), plus the new rule (>= 0.85 on every joint, FineDance validation). Report which run passes; S1
   candidate = the smaller passing model (A before B).
6. **Done when:** `docs/T1A2_REPORT.md` (numbers only) and "T1A2 READY <commit>" in `docs/NIGHT_LOG_body-t1a2.md`, pushed. Then STOP.
