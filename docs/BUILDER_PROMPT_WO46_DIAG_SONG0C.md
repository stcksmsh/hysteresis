# Builder prompt: work order 46, posture-vs-gesture diagnostic, then Step 0c on whole songs (7.74 Q4, Q5) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.74** (Q4, Q5, overseer notes), then 7.73. Report only: no training of any kind. No verdict. One arm.
Another builder (WO45, grammar A) works on cores 6-13: stay on cores 14-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-diag origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo46-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 14-19, `python -u`; read logs 1 min after start. Run on
battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env
`/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,t1a2,t1b,controls,join}/`. Out:
`/secondary/hyst-data/body/diag/` and `/secondary/hyst-data/body/song0c/`. Nothing on the root disk. Motorica stays on this laptop
(aggregates only in git). Night log `docs/NIGHT_LOG_body-diag.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.73, 7.74; `docs/JOIN_RULES.md`, `docs/JOIN_REPORT.md` (and `scripts/body/join_*.py`); `docs/CONTROLS_RULES.md` (with
addenda), `docs/CONTROLS_REPORT.md` (and `scripts/body/controls_*.py`); `docs/T1B_REPORT.md`.

## Part 1: posture-vs-gesture diagnostic (7.74 Q4), first; report before Part 2

1. Rules note `docs/DIAG_RULES.md`, pushed before any result: on the WO44 material (37 FineDance validation + test songs, 60 s, A1 decoder,
   realised stage), the conditions: decoded human (reference), decoded retrieval and decoded random chunks as in WO44, plus each control
   with (i) human posture knots + the control's gesture codes and (ii) the control's posture knots + human gesture codes; if E1 seed 41101's
   tokens allow it, the same two swaps for the model. Measures as WO44: lamp `p_gt3` ratio to continuous human (mean of per-song ratios and
   ratio of means, song bootstrap), frozen share, joint-mean `p_gt3`. State how the swaps keep time alignment.
2. Run; save per-song values. `docs/DIAG_REPORT.md`, night log "DIAG READY <commit>". Continue with Part 2 without waiting.

## Part 2: Step 0c on whole songs (7.74 Q5 (c))

1. Rules note `docs/SONG0C_RULES.md`, pushed before any result. Same controls as 7.74 (vigour, height, accent pattern, sharpness, direction,
   pause probability; per `docs/CONTROLS_RULES.md`, version as WO45 uses) and the same acoustic measures as WO43 step 0c, but computed on
   whole songs: realised trajectories of whole sequences (not only kept 20 s windows; state how windows failing the gates are treated and
   report results with and without them), per dataset (FineDance, AIOZ; PhantomDance and Motorica separate and marked "look check pending").
   Relations: global, within-song, per song, lags -1..+1 s as WO43, plus slower scales (state them, e.g. 2 s / 8 s / 30 s smoothing).
   Phrase-scale structure: novelty / repetition on whole songs (motion side on controls, music side on ear features and, for FineDance, the
   cortex), boundary alignment against circular shifts, with kernel widths covering phrases of 8-32 s. Bootstrap by song.
2. Run. `docs/SONG0C_REPORT.md` (side by side with the WO43 20 s numbers), night log "SONG0C READY <commit>", pushed; all tests pass. Then
   STOP.
