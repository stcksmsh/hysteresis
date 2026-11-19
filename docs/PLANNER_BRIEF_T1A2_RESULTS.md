# Planner brief: T1a retrain results (BRAIN_SPEC 7.61), 2026-11-15

TO: planner. FROM: overseer, for Kosta. Report: `docs/T1A2_REPORT.md` (branch body), data `/secondary/hyst-data/body/t1a2/`. The overseer
recomputed variance explained and the reconstruction jitter from the saved rebuilds; the realised-stage numbers were checked in
`realised.json`.

## What ran

Step 1 (7.61.2): kept-AIOZ gesture RMS was 0.46-0.78 of FineDance's (4 of 5 joints under 70 %) -> rule 7.61.3 applied, AIOZ capped at 50 %
of training weight (was 58 %). Run A: K = 1024 + Bailando's loss (from its official code: L1 reconstruction + velocity + acceleration,
weights 1 / 1 / 1, commitment 0.02) + 25 Hz B-spline decoder. Run B: the same with 2 x 1024 residual quantisation. Both early-stopped
(epochs 26 and 19 of 80). The spline decoder is about 5x faster per epoch than round 1 (37-82 s).

## Results (test windows unless stated; original / Run A / Run B)

- **Variance explained, FineDance validation** (new rule >= 0.85 on every joint; base, shoulder, elbow, wrist bend, roll):
  A 0.765 / 0.659 / 0.705 / 0.733 / 0.742 (FAIL); **B 0.889 / 0.855 / 0.873 / 0.877 / 0.878 (PASS)**. AIOZ validation B: 0.917 / 0.910 /
  0.895 / 0.785 / 0.839.
- Code usage 1.0 (pass); joint ranges 0.94-1.00 (pass).
- **Jitter on the rebuilt targets (the rule as worded, <= 1.1x): FAIL for both.** Acceleration direction changes 14-15/s vs 3.4-4.6 original
  (ratio about 3.5). But the size is now small: on Run B the movement above 3 Hz is at or below the original (RMS 0.12 / 0.37 / 0.75 / 1.03
  / 1.36 deg vs 0.12 / 0.37 / 0.74 / 1.27 / 1.88), and above 8 Hz it is a sub-degree wiggle (0.03-0.31 deg vs 0.02-0.16). The count reacts to
  any wiggle; the 40 ms spline knots are a likely source (not checked).
- **Jitter at the realised stage** (after H1, limiter, servo, v2p body: what the arm does; report-only measure added by the overseer):
  direction changes/s base 2.20 / 1.80 / 1.90, shoulder 2.80 / 2.55 / 2.60, elbow 2.80 / 2.55 / 2.60, wrist bend 3.75 / 3.15 / 3.30, roll
  3.65 / 3.10 / 3.20. Power above 3 Hz: rebuilds at or below the original on 4 joints (ratios 0.44-1.00); base yaw 1.26-1.29x on tiny values
  (0.00020 vs 0.00016). Same picture per source.
- **Gates at 1.25:** original 1.000 / A 0.979 / B 0.983; FineDance 1.000 / 0.948 / 0.948; AIOZ 1.000 / 0.985 / 0.990. Run B failures: 37
  speed/acceleration limits, 5 end stops (of 2,455 windows). Note: every original window passes by construction (T0 kept only passing
  windows). The rule "passes gates at 1.25" has no share defined; the builder used >= 0.95 per source, which FineDance misses by 0.002.

## Questions

1. **Run B to S1?**
   - (a) Yes: measure the jitter rule at the realised stage (what the arm does, what Kosta sees), where B is at or below the original
     except base-yaw power at 1.29x of a tiny value; S1 picks only windows whose rebuild passes the gates **[recommended]**;
   - (b) No: fix the reconstruction wiggle first (e.g. smoothness on the spline control points, or 50 Hz control points) and rerun B;
   - (c) other.
2. **Gate rule definition:** (a) >= 0.95 of windows overall, per source reported **[recommended]** / (b) >= 0.95 per source (B fails on
   FineDance 0.948) / (c) other.
3. Record as 7.62.
