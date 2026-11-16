# Builder prompt: work order 43, fix 1: height bounds from the v2p body (2026-11-16)

Overseer check of CONTROLS READY (8a3e9f6), branch `body-controls`, same header rules as `docs/BUILDER_PROMPT_WO43_CONTROLS.md`.

**Finding.** `CONTROLS_RULES.md` 3.2 takes the lower workspace bound 0.11 m from `m3f_report.FLOOR_M + DISC_M` (the old table body, floor at
z = 0.05). The realised stage simulates the v2p body (`make_arm_v2p.py`): base on a pillar, `FLOOR = TOP - 1.0 = -0.947` m, hand margin 0.11
m, so the lamp may go down to -0.837 m. Kept tokens reach z_mean = -0.344 m (FineDance); 16.6 % of FineDance tokens (AIOZ 5.3 %,
PhantomDance 13.2 %, Motorica 7.0 %) sit below 0.11 m and are clipped to height 0. Every other control matched the overseer's independent
recompute exactly (3 files, 800 tokens; FineDance between-song shares and vigour x accent Spearman 0.829 match).

**Do:**
1. Rules addendum 2 (pushed before recomputing): usable workspace for height = the lamp z range the v2p body allows, computed (not
   assumed) over the joint ranges with `make_arm_v2p.margins >= 0` (state the grid and the resulting [z_lo, z_hi]); height = clip((z_mean -
   z_lo) / (z_hi - z_lo), 0, 1). Also report, report-only, the FineDance-train p1 / p99 of z_mean next to these bounds. Nothing else in
   the rules changes.
2. Recompute height and everything that uses it: Step 0b tables (distributions, histograms, correlations, variance shares), Step 0c rows
   for height, the motion-side structure (height is in its control vector), the clip selection (height pairs and the matching residuals of
   every pair; same seeds and rule), and re-render only the clips that change. Update `CONTROLS_REPORT.md` and the manifest; state which
   pairs changed.
3. Add a test: a pose with the lamp below the old 0.11 m bound but clear of the v2p floor gives 0 < height < 1.
4. Night log "CONTROLS READY <commit> (fix 1)", pushed. Then STOP.
