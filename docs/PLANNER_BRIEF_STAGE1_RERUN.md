# Planner brief: Stage 1 rerun on seeds 2 and 3, no verdict again (2026-11-09)

Rules in force: BRAIN_SPEC 7.37 (recorded before the run, body c013514), `docs/STAGE1_RULES.md` section 11.
Builder: agent 2 (WO22, body-s1r 261c760, merged into body). Data: `/secondary/hyst-data/body/s1r/` (`verdict.json`, `verdict.txt`,
`run_*_s{2,3}/result.json`); seeds 0/1 in `/secondary/hyst-data/body/s1/`.

## What ran

All six arms (0, i, ii, iii, iv lambda 0.05, iv lambda 0.5) on fresh seeds 2 and 3, 1000 epochs each, 12 runs, 53 min, 32 held-out toy
songs. The builder's verdict script and the overseer's own recomputation from the result files agree on every number below.

## Result under 7.37.1: no verdict

The precondition (arm 0 or arm i with between-song / half-song JS <= 1.5 on **both** seeds 2 and 3) is not met:
- arm 0: 0.93 (seed 2), 4.84 (seed 3);
- arm i: 4.82 (seed 2), 1.21 (seed 3).

Each arm collapses on one seed only.

## All four seeds (0/1 informational per 7.37.1; recomputed by the overseer)

| Arm | between / half JS ratio, seeds 0-3 | JS between, mean | D, seeds 0-3 | D mean (min) | occupied cells, mean |
|---|---|---|---|---|---|
| 0 | 0.77, 1.09, 0.93, 4.84 | 0.186 | 0.875, 0.886, 0.893, 0.869 | 0.881 (0.869) | 25.8 |
| i | 0.92, 2.84, 4.82, 1.21 | 0.232 | 0.852, 0.888, 0.881, 0.840 | 0.865 (0.840) | 31.7 |
| ii | 17.8, 20.5, 11.8, 16.7 | 0.842 | 0.733, 0.767, 0.689, 0.739 | 0.732 (0.689) | 27.6 |
| iii | 13.8, 8.9, 12.1, 12.4 | 0.831 | 0.698, 0.757, 0.643, 0.576 | 0.669 (0.576) | 52.7 |
| iv, lambda 0.05 | 12.5, 13.0, 9.3, 14.1 | 0.868 | 0.684, 0.690, 0.589, 0.716 | 0.670 (0.589) | 49.5 |
| iv, lambda 0.5 | 10.1, 10.2, 8.8, 13.6 | 0.960 | 0.651, 0.665, 0.643, 0.546 | 0.626 (0.546) | 47.4 |

Machine 2AFC, seeds 2/3: arm 0 0.63 / 0.88, arm i 0.86 / 0.77, arms ii-iv 0.97-0.99.

What the numbers show (informational, not a verdict):
- **Collapse in the toy is seed-dependent.** Arm 0 meets the 1.5 ratio on 3 of 4 seeds, arm i on 2 of 4.
- **Arms ii-iv make the motion song-dependent on every seed.** Their ratios are 8.8-20.5, against 0.77-4.84 for arms 0 and i.
- **Only arm ii keeps D near the bar.** Its mean is 0.732, but it falls to 0.689 on seed 2. Arms iii and iv lower D (means 0.63-0.67), with
  at least one seed under 0.6.
- **Arm iii roughly doubles the occupied cells** (52.7 vs 27.6), at a cost in D.
- **No arm beyond i has D >= 0.7 on all four seeds.**

## Pending

WO23, the report-only acceleration/speed cap probe (7.37.3), is running: four runs (B retrained at defaults, A1, S1, AS), ETA about 14:05.
It gets its own brief. Finding on the way, verified by the overseer: M3f training numbers depend on the thread count with the same code
(epoch-0 dec_e 1.9956 at 3 threads, 1.9924 at 6, 1.9983 at 8). Baseline B was therefore retrained at the probe's 6 threads; the WO17 run is
kept as a reference only.

## Questions

**Q1. What closes Stage 1?** The pre-registered precondition has failed twice: the untrained baseline in WO20, seed dependence now.

Options:
- (a) Close Stage 1 without a verdict. Record the four-seed table as informational and move to the next stage of 7.34 with the
  ingredients from Q2.
- (b) Estimate the collapse rate: arms 0 and ii on 8 fresh seeds (4-11), about 1.2 h. Pre-register now, for example: "arm 0 collapses on
  >= 6 of 8 seeds, and ii reaches >= 2x arm 0's JS with D >= 0.7 on >= 6 of 8".
- (c) Redesign the toy so that collapse is reliable, then rerun.

Recommend (a). The reading the design needs is stable across four seeds: ii-iv against 0/i, a gap of 2-20x in the ratio. More toy seeds
would not change what goes forward. A further precondition chosen after two failures would also be weaker evidence than the four seeds
already in hand.

**Q2. Which ingredients go forward?** 7.37.2 set the default to ii + iii. On four seeds, iii lowers D to a mean of 0.669 (min 0.576).

Options:
- (a) ii alone as the default; iii only if D can be held (see c).
- (b) Keep ii + iii and accept D around 0.67.
- (c) ii + iii, with D >= 0.7 enforced as a hinge with a dual multiplier, as for the other limits. One toy check on two seeds first.

Recommend (a) now, with (c) as the route to iii's wider movement, tested on the toy before any long run.

**Q3. Record the seed dependence?** Arm 0 meets the collapse ratio on 3 of 4 seeds and arm i on 2 of 4, so any toy precondition needs
several seeds. Recommend yes.
