# Builder prompt: work order 43, the control representation (7.73 Steps 0a, 0b, 0c, clip candidates for 0b') (2026-11-16)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" where a choice is open.

**Binding:** `docs/BRAIN_SPEC.md` **§7.73** (including its overseer notes), then 7.59-7.71 where 7.73 does not change them. No verdict.
One arm. **This work order measures and reports only: no training of A or B, no grammar, no listener, no k-means control vocabulary, no
posture-vocabulary rebuild.** You do not run Kosta's viewing session: the overseer serves it. Another builder (WO44, chunk joining) works
on cores 14-19: stay on cores 6-13.

**Header rules:** in your current worktree `git fetch origin && git checkout -b body-controls origin/body`; absolute paths; no new
worktrees. Detached units `hyst-wo43-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`, cores 6-13, `python -u`; read logs 1 min after start.
Run on battery. Commit and push before every run. Plain commit messages, no co-author or attribution lines. No installs, downloads,
uploads. Env `/secondary/hyst-env/brain`. In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,t1a2,t1b}/` and the
FineDance / AIOZ / PhantomDance / Motorica audio they used. Out: `/secondary/hyst-data/body/controls/`. Nothing on the root disk.
**Motorica and anything derived from it stay on this laptop**; no per-file Motorica numbers in git (aggregates only, as in
`docs/T0_PHANTOM_REPORT.md`). Night log `docs/NIGHT_LOG_body-controls.md`. Keep messages short.

## Read first

`docs/BRAIN_SPEC.md` 7.73 (all of it), 7.59, 7.61-7.63, 7.69-7.71; `docs/T0_RULES.md`, `docs/T0_REPORT.md`, `docs/T0_AIOZ_RULES.md`,
`docs/T0_PHANTOM_RULES.md`, `docs/T0_PHANTOM_REPORT.md`, `docs/T1A2_RULES.md`, `docs/T1B_RULES.md`, `docs/T1B_CAUSAL.md`,
`docs/T1B_REPORT.md`. Code under `scripts/body/`: the T0 pipeline (`t0_*.py`, splits, gates at 1.25, V1/V2 + mirror copies), forward
kinematics (`fk_points`; point 5 is the lamp), the realised stage (`t1a2_realised.py`), the jitter measure (`pos_measures`, `p_gt3`), the
ear features and cortex precompute (`t1b_cortex.py`), the beat grid, `retarget_render.sh` (honours `RETARGET_ROOT`) and
`dialstudy_session.py`.

## The work

1. **Rules note `docs/CONTROLS_RULES.md`, pushed before any control value is computed (7.73 Step 0a "fixed in rules before
   computing").** Everything fixed in it, each with its exact formula and constants:
   - the source trajectory: realised (default; the T0 realised stage, as T1A2 measured jitter) or target; state which and why, and use
     the same one for every dataset;
   - token grid: 0.5 s tokens on the T0 token grid; frame rate used for derivatives; derivative and smoothing filters;
   - the six controls of 7.73 Step 0a, exactly as listed there: vigour (joint angular-speed RMS and lamp-speed RMS kept separately;
     combined = first principal component; global robust normalisation, constants fitted on FineDance training split only); height
     (absolute lamp height normalised to the usable workspace: state the workspace bounds and where they come from); accent pattern
     (normalised lamp acceleration + jerk, smoothing, 8 sub-slots of 62.5 ms); sharpness (high-frequency share of acceleration energy,
     dimensionless, independent of speed: state the band edges and show the speed independence on a synthetic test); direction (unit 3-D
     mean lamp velocity, workspace frame; rule for near-zero speed); continuity (activity measure + pause probability, lamp speed below a
     stated threshold for > 0.25 s);
   - movement lead (proximal vs distal onset order): measured only, onset rule stated;
   - slow structure on the motion side (phrase start/end, repetition, contrast): measured only, method stated;
   - which copies (V1/V2/mirrors) enter each statistic, and how mirror copies treat direction;
   - splits: the existing T0 splits per dataset, untouched;
   - the 0b statistics (step 3), the 0c measures (step 4) and the clip-candidate selection rule (step 5), all fixed here.
   Tests: each control on synthetic trajectories with a known answer (constant speed, a pure tone at known frequency, a pause of known
   length, a straight line in a known direction); sharpness invariant to uniform speed scaling; no use of data outside the token for
   per-token controls other than the stated filter support.
2. **Compute** the controls per token for every kept window of FineDance, AIOZ, PhantomDance and Motorica (all copies), saved per song
   to `controls/<dataset>/`. Night log "CONTROLS COMPUTED <counts per dataset>".
3. **Step 0b (numeric validation)** per dataset, PhantomDance and Motorica reported separately and marked "look check pending":
   distributions per control (quantiles, histograms), pairwise correlations between controls (Pearson and Spearman; flag every |r| > 0.7
   as redundant), within-song vs between-song variance share per control, bootstrap by song for every reported interval (seed fixed).
4. **Step 0c (report-only, human data):** acoustic measures per token: RMS, spectral flux, onset strength, low and high band energy
   (state the band edges), spectral centroid, local dynamic range, beat strength (from the existing offline beat grid). Relation of each
   control to each measure: global, within-song (song mean removed), per song, and over lags -1..+1 s in token steps; bootstrap by song.
   Musical structure layer, report-only: beat (existing grid), onsets, phrase boundaries and repetition from a self-similarity / novelty
   analysis of the cortex and ear features (`t1b/cortex/` for FineDance; compute the same features for the other datasets only if the
   existing code does it without changes, otherwise FineDance only and say so). No source separation, no instrument labels. Also report
   how the motion-side slow structure lines up with the music-side boundaries.
5. **Clip candidates for Step 0b'** (Kosta's ~15 min blind viewing; the overseer serves it): for each of vigour, height, sharpness,
   continuity, accent density, 3 pairs of real retargeted human clips at low vs high values of that control, the other controls matched
   where possible (state the matching rule and report the residual differences). Seeded selection from FineDance test/validation songs
   only (PhantomDance / Motorica only after Kosta's look check: not in this work order). Render on the arm with `retarget_render.sh`
   (`RETARGET_ROOT=/secondary/hyst-data/body/controls/look`), clip length fixed in the rules note. One manifest of pairs for
   `dialstudy_session.py` with the per-control question of 7.73 Step 0b' ("Which looks [bigger/faster | higher | sharper | more continuous
   | more accented]?", answers first / second / same). If the tool cannot carry a per-item question, add the smallest option that does and
   a test; change nothing else. Do not build or serve a session; do not open any answers file. Night log "LOOK CLIPS READY".
6. **Done when:** `docs/CONTROLS_REPORT.md` (every number of steps 3-5, redundant pairs, the clip list with control values) and
   "CONTROLS READY <commit>" in the night log, pushed; all tests pass. Then STOP.
