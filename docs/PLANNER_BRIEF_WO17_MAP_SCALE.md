# Planner question: scale of the smooth u map (WO17, 2026-11-08)

Context: `docs/BRAIN_SPEC.md` §7.32 (smooth map replaces every clipped u output; bend centres into +-(110 - A_min), A_min 10 deg). One arm.

## What was built (branch body-m3f 09a870f, builder)

u = 0.5 + 0.5 tanh((s - 0.5) / c), with c = 0.5 (slope 1 at s = 0.5). The unclipped sum s = pi @ sigmoid(theta) + 0.2 tanh(amod) lies in
(-0.2, 1.2). Bend centre = -100 + 200 u. Tests pass (default path bit-identical, non-zero gradient at and beyond the old bounds). The
two-seed toy rerun (WO17) **is running with c = 0.5** (started 2026-11-08 on mains); gate verdicts in about 3 h.

## The issue (overseer's arithmetic)

Because s cannot leave (-0.2, 1.2), the map never reaches the edges of (0, 1):

| c | u range over s in (-0.2, 1.2) | largest bend centre | slope at s = 0.5 | slope at s = -0.2 / 1.2 |
|---|---|---|---|---|
| 0.5 (as built) | 0.057 - 0.943 | +-88.5 deg | 1.00 | 0.22 |
| 0.35 | 0.018 - 0.982 | +-96.4 deg | 1.43 | 0.10 |
| 0.3 | 0.009 - 0.991 | +-98.1 deg | 1.67 | 0.07 |

So with c = 0.5 the bend centres reach +-88.5 deg, not the +-100 deg 7.32 allows, and the amplitude, frequency and lag outputs each lose
about 6 % of their range at both ends. A smaller c recovers the range but halves the gradient at the edges (still non-zero).

## Question

**Q1. Map scale c.** Options:
- (a) Keep c = 0.5 (as running): strongest edge gradient; centres +-88.5 deg; ~6 % of every output's range unreachable.
- (b) c = 0.35: centres +-96.4 deg, ~2 % unreachable; edge gradient 0.10.
- (c) Keep the current run, and decide on c from its result: if it passes both gates, keep 0.5; switch only if the clips or the gates show
  the arm lacking range.
- **Recommendation: (c).** The run already satisfies 7.32; a stop now would cost ~3 h. Range loss is a look the user can judge in the
  clips; the edge-gradient advantage of 0.5 is the point of the fix.
