# Builder prompt: work order 46, posture-vs-gesture diagnostic, then beat-relative coupling of human motion (7.74 Q4, 7.76.1) (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.76** (point 1 and its overseer notes) and **§7.74** (Q4), then 7.73. Report only: no training of any kind. No verdict. One arm.
Another builder (WO45, grammar A) works on cores 6-13: stay on cores 14-19.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-diag origin/body`; absolute paths; no new worktrees.
Detached units `hyst-wo46-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 14-19, `python -u`; read logs 1 min after start. Run on
battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads, uploads. Env
`/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,t1a2,t1b,controls,join}/`. Out:
`/secondary/hyst-data/body/diag/` and `/secondary/hyst-data/body/metric/`. Nothing on the root disk. Motorica stays on this laptop
(aggregates only in git). Night log `docs/NIGHT_LOG_body-diag.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.73, 7.74, 7.76; `docs/JOIN_RULES.md`, `docs/JOIN_REPORT.md` (and `scripts/body/join_*.py`); `docs/CONTROLS_RULES.md` (with
addenda), `docs/CONTROLS_REPORT.md` (and `scripts/body/controls_*.py`); `docs/T1B_REPORT.md`.

## Part 1: posture-vs-gesture diagnostic (7.74 Q4), first; report before Part 2

1. Rules note `docs/DIAG_RULES.md`, pushed before any result: on the WO44 material (37 FineDance validation + test songs, 60 s, A1 decoder,
   realised stage), the conditions: decoded human (reference), decoded retrieval and decoded random chunks as in WO44, plus each control
   with (i) human posture knots + the control's gesture codes and (ii) the control's posture knots + human gesture codes; if E1 seed 41101's
   tokens allow it, the same two swaps for the model. Measures as WO44: lamp `p_gt3` ratio to continuous human (mean of per-song ratios and
   ratio of means, song bootstrap), frozen share, joint-mean `p_gt3`. State how the swaps keep time alignment.
2. Run; save per-song values. `docs/DIAG_REPORT.md`, night log "DIAG READY <commit>". Continue with Part 2 without waiting.

## Part 2: beat-phase / metrical analysis of human motion (7.76 point 1; report-only; decides B's targets)

1. **Beat grids first.** FineDance: the stored offline grids (`/secondary/hyst-data/body/t1b/cortex/beats/<key>.json`, made by
   `analyze_mix` in `t1b_cortex.py`). AIOZ, PhantomDance, Motorica: run the same `analyze_mix` on their audio (no installs). Check it on 10
   FineDance songs against the stored grids (beat-time differences). Bar level: no downbeat source exists; state the rule (e.g. 4/4 assumed,
   bar phase chosen by onset strength) and mark bar results "provisional". Night log "GRIDS <counts, FineDance check>".
2. **Rules note `docs/METRIC_RULES.md`, pushed before any result**, everything fixed in it:
   - material: all four paired datasets, whole songs (whole sequences, not 20 s windows; state how passages failing the T0 gates are
     treated, results with and without them), V1 copies as the main result and V2 reported alongside (V2 is sharper, 7.75 pending), mirrors
     excluded or stated; realised lamp trajectory and each joint separately;
   - motion events by several definitions, each with thresholds and minimum separation: lamp-speed local minima, lamp-acceleration peaks,
     joint angular-velocity peaks, direction reversals, movement onsets;
   - phase of each event relative to beat, half-beat (double time), half-time and bar; circular concentration (mean resultant length) and
     preferred phase per level; lead/lag scan +-250 ms with its step, every lag reported (not maximised silently);
   - controls: the same events against time-shuffled beats (state the shuffle) and against other songs' beat grids, tempo-matched (within
     5 %, seeded);
   - tempo / density: motion-event rate vs tempo and vs onset density; pause occupancy and duration (2-8 s scale) vs rhythmic density and
     pulse clarity (state both measures);
   - whole-song structure: change points in control distributions (7.74 controls, `controls_lib.py`) and in movement motifs (state the
     motif representation, e.g. gesture-code n-grams) vs music novelty and repetition (ear features; cortex for FineDance), delays -2..+2 s,
     against circular shifts; plus the whole-song control-vs-acoustics relations of WO43 step 0c (global, within-song, per song, lags) as a
     side table;
   - bootstrap by song for every interval (seed fixed); per dataset, PhantomDance and Motorica separate.
   Tests: synthetic events locked to a known phase give that phase and concentration near 1; uniformly random events give concentration
   near its chance level; the lag scan recovers a known shift.
3. **Run**; save per-song values. `docs/METRIC_REPORT.md`, night log "METRIC READY <commit>".
4. **By-ear spot check (prepare only):** 10 songs (seeded, across datasets) with the music-side section boundaries the analysis found,
   as audio excerpts of +-8 s around each boundary plus a list of the boundary times; one folder `metric/spotcheck/` with a manifest. Do not
   serve; the overseer serves it to Kosta. Night log "SPOTCHECK READY". Then STOP; all tests pass.
