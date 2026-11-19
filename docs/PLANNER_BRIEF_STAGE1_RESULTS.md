# Planner brief: Stage 1 results, precondition not met (no verdict), and the 0.741 m/s ceiling (2026-11-09)

Rules in force:
- BRAIN_SPEC 7.34-7.36;
- the toy rules `docs/STAGE1_RULES.md` (body-s1, amendments in section 10, all committed before the run).

Builder: agent 2 (WO20). Data: `/secondary/hyst-data/body/s1/run_*/result.json` and `summary.json`.

## What ran

12 runs (arms 0, i, ii, iii, iv(lambda 0.05), iv(lambda 0.5), seeds 0 and 1), 1000 epochs each, 51 min in total. All measures are on the 32
held-out toy songs (40 s each). The numbers below are the builder's, recomputed by the overseer from the per-run result files: they match.

## Results

| Arm | JS between songs (s0 / s1) | JS half-song control | Decoding D | Occupied cells (of 576) | Machine 2AFC |
|---|---|---|---|---|---|
| untrained (per seed) | 0.739 / 0.976 | — | — | 26.6 / 23.2 | — |
| 0 (pass2 soft costs) | 0.146 / 0.128 | 0.190 / 0.117 | 0.875 / 0.886 | 27.8 / 18.4 | 0.73 / 0.78 |
| i (hinges) | 0.135 / 0.283 | 0.147 / 0.100 | 0.852 / 0.888 | 32.5 / 35.2 | 0.70 / 0.86 |
| ii (+ corpus norm + InfoNCE) | **0.766 / 0.773** | 0.043 / 0.038 | **0.733 / 0.767** | 25.2 / 26.3 | 0.98 / 0.99 |
| iii (+ Lipschitz observer) | 0.806 / 0.559 | 0.058 / 0.063 | 0.698 / 0.757 | 50.6 / 51.2 | 0.98 / 0.98 |
| iv, lambda 0.05 (+ log det) | 0.866 / 0.835 | 0.069 / 0.064 | 0.684 / 0.690 | 48.2 / 47.1 | 0.98 / 0.97 |
| iv, lambda 0.5 | 0.974 / 0.939 | 0.097 / 0.092 | 0.651 / 0.665 | 45.4 / 48.9 | 0.98 / 0.98 |

**The collapse precondition (7.35.2 with 7.36.2): NOT MET, so there is no verdict, as ruled.**
- The JS half holds: trained / untrained is 0.20 and 0.13 for arm 0, and 0.18 and 0.29 for arm i, all <= 1/3.
- The occupied-cells half fails: 1.05 / 0.79 for arm 0, 1.22 / 1.52 for arm i.
- Cause: the untrained toy policy is nearly still. It sits in a different small spot per song (23-27 of 576 cells), which already gives a
  high between-song JS. So "<= 1/3 of untrained" cannot be met on cells. The baseline was a poor choice; the arms themselves may be fine.

**What the numbers show anyway** (informational; not a verdict):
- **Arms 0 and i reproduce pass2's signature.** Their between-song JS is at about their own half-song control (between / half 0.77-2.8;
  pass2 0.69). The hand moves no more differently between songs than within one song.
- **Arms ii-iv make the motion strongly song-dependent.** Between / half is 8-18x, and the 2AFC is 0.97-0.99.
- **Arm ii alone gives most of the change.** Its JS is about 3.7x arm i's mean (0.209), with D 0.73 / 0.77 (>= 0.7), and its cell count
  is unchanged.
- **Arm iii doubles the occupied cells** (wider movement) at a small cost in D: 0.70 / 0.76.
- **Arm iv adds JS, but its D drops below 0.7** (0.65-0.69). Under the pass rule, iv would fail on D.
- **Caveat: the toy's arm i is only partly collapsed.** Its 2AFC is 0.70-0.86, against pass2's 49 %. Song identity stays partly readable
  in the toy without any change.

## Also: the 0.741 m/s ceiling (7.36.5; WO21, agent 1)

Verified by the overseer from the Stage 0 hand positions; merged.

- **0.741 m/s is not a bound.** It is a start-up transient at t = 2.74 s from the fixed start pose, the same on every song. The peak falls
  in the first 8 s on 331 of 357 songs, at 0.7407 m/s, sd 0.0004.
- After 8 s the per-song peak is 0.680 m/s, sd 0.036 (range 0.554-0.806).
- Raising the amplitude cap or the frequency max 1.5x leaves the peak unchanged; c = 0.35 lowers it. So the amplitude cap, smooth-u and
  the frequency range are all ruled out.
- **What limits the steady dance** (builder; not recomputed by the overseer):
  - the generator's own caps in `cpg.py`: shoulder, elbow and wrist bend sit on the acceleration cap (ACC_SHARE = 0.25) 99.8-99.9 % of
    steps; base and roll sit on the 0.8 x speed cap 96-98 %;
  - the analytic maximum hand speed over the poses pass2 visits is about 1.9-2.3 m/s.

## Questions

**Q1. How to get a verdict on Stage 1?** Any new precondition chosen now, after seeing these numbers, would be post hoc.

Options:
- (a) Pre-register a new collapse precondition now and rerun all arms on **fresh seeds** (2 and 3; about 1 h). Proposed precondition:
  arm 0 or arm i has a between-song / half-song JS ratio <= 1.5 on both seeds (pass2: 0.69). The 2AFC is reported. Same pass rule
  otherwise.
- (b) Pre-register a different baseline: a policy trained with hinges only, without the legibility objective. Collapse = JS and occupied
  cells <= 1/3 of that baseline. Rerun on fresh seeds (about 1.2 h, with 2 extra runs).
- (c) Accept the informational reading without a verdict, and move on.

Recommend (a): cheap, matches the pass2 signature it is meant to reproduce, and fresh seeds keep it pre-registered.

**Q2. Which ingredients go forward (after the Q1 rerun)?**
The numbers point to arm ii (corpus-normalised slow target + matched InfoNCE) carrying most of the song-dependence at D >= 0.7. Arm iii
widens the movement. Arm iv costs D below the bar.

Recommend: decide after the Q1 rerun, with the default "ii + iii; iv only if the rerun shows it is needed and D >= 0.7".

**Q3. The steady-dance limiter.** The generator's acceleration cap (ACC_SHARE 0.25) binds the pitch joints almost all the time. Any
Stage 3 run would carry this limit.

Options:
- (a) a report-only probe on the M3f toy, raising ACC_SHARE (0.25 -> 0.4) and the 0.8 speed share: does movement spread or decoding
  change?
- (b) leave it until Stage 3 design.

Recommend (a), cheap, before Stage 3 design. The caps come from servo realism (hardware memory: about 25 % of stall), so any change must
stay within the hardware limits.

**Q4. Record the caveat that the toy's arm i is only partly collapsed** (2AFC 0.70-0.86 vs pass2 0.49)? Recommend yes.
