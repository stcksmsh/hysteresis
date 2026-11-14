# Planner brief: work order 16 results (diagnosis of the elbow-stop slump) and the fix (2026-11-07)

Context: `docs/BRAIN_SPEC.md` §7.30.8-7.31. One arm. Analysis only; nothing trained. Data `/secondary/hyst-data/body/m3f/rerun3/diag/
summary.json` (builder, branch body-m3f d543db4). The overseer recomputed the hold census from the saved joint angles (match, below), reran
the 6 new tests (OK) and checked the code change (a default-off diagnostics branch in `arm_step` plus new files). The per-step mechanism
numbers (generator centre, amplitude, stop hits, contacts, decoder losses) come from the builder's re-simulation and were not recomputed.

## 1. What ran

The scored held-out argmax rollouts of both WO15A seeds were re-simulated with logging of pre-clip targets, generator state, stop hits and
contacts. Every saved key reproduces bit for bit (max |dq| = 0.0) with the logging on and off. Every hold >= 2 s with a ranged joint within
0.05 deg of 110 was analysed on the six points of 7.31.1.

## 2. Results

**Census (overseer recomputed, matches):** seed 0: 46 holds, 467.1 s (elbow 443.0, wrist 21.5, shoulder 2.6 s); seed 1: 32 holds,
119.9 s (shoulder 97.0, elbow 12.0, wrist 10.9 s). **Every hold is on the negative stop (-110 deg).**

| hypothesis | verdict | deciding number (builder) |
|---|---|---|
| H1 clipping | supported, but not as an overshoot | pre-clip target at/above the 109.5 clip bound 98.6 % of hold time; **the generator centre sits on its own +-110 limit 85.7 %** (seed 0 87.1 %); the clip removes at most 0.5 deg; **the bend amplitude cap (110 - abs(centre)) forces the amplitude to about 0.04 deg** while the phase keeps advancing (16.8-17.9 rad/s) |
| H2 chosen stillness | not supported | command inside the range with amplitude < 5 deg: 1.3 % of hold time |
| H3 resting on a contact | not supported | 0.0 % of hold time with any contact (table, ball/links vs column, link-link), 0 N |
| H4 pinned by stop hits | supported | the hard stop acts in 98.4 % of hold control steps (4.95 of 5 substeps), one continuous run per hold; joint speed 0.01-0.03 deg/s |
| H5 program / brain state | seed 0 only | seed 0: 99.4 % of hold blocks are program 2 vs 56.6 % outside (TV 0.43, p 0.0005), lower arousal and surprisal; seed 1: TV 0.115, p 0.14. Program 2's elbow prototype centre -101.7 deg; seed 1's program 3 shoulder centre -104.6 deg |
| H6 easy code | not supported at p < 0.01 | decoder loss lower inside holds (seed 0 ext -0.95) but the predict-mean baseline drops more (-1.29): calmer targets, not an easier pose. Shuffle-gap difference ext p 0.03-0.04, int p 0.08-0.14 (borderline, not clean) |

**Mechanism (overseer's plain reading of H1 + H4):** a program's generator centre for a bend joint drifts to its -110 limit; the amplitude
cap shrinks the swing to zero there; the oscillator keeps running but the joint cannot move, and the hard stop holds it. The arm is not
asking to be still (H2), not resting on anything (H3), and the pose is not clearly an easier code (H6). In seed 0 one program (2) produces
almost all holds. Builder inference, **untested** (no gradient run): once the centre saturates (u clipped to [0, 1], the target clip, the
position clip), no gradient from the limit-proximity cost reaches the centre, matching the planner's note in 7.31.4.

## 3. Questions

**Q1. The fix.** Options:
- (a) **Keep generator centres off the limits:** map each bend centre smoothly (tanh) into +-(110 - A_min), e.g. A_min = 10 deg, so the
  amplitude cap never drops below A_min and the mapping has a gradient everywhere. Targets the mechanism directly; changes the generator
  (a body/motor-model change).
- (b) **Time-on-stop cost** (the WO15 brief's Q1 (a)): a hinge on time within ~2 deg of a stop. Likely weak for the same reason the
  limit-proximity cost is: no gradient through the saturated centre.
- (c) **Narrower commanded range** (WO15 brief Q1 (c)): clip targets 10 deg inside the stops. Removes the pin (H4) but the centre could
  still saturate at the new bound with zero amplitude: a still pose 10 deg off the stop.
- (d) A **gradient check first:** measure d(loss)/d(centre) for saturated vs unsaturated centres on a held block (minutes), to test the
  inference before choosing.
- **Recommendation: (d) then (a).** (d) costs minutes and confirms the cause. (a) attacks the centre saturation itself and keeps stillness
  possible only through small chosen amplitudes inside the range. Then the two-seed toy rerun under the 7.30.3 gate plus the 7.31.2 parking
  gate (about 3 h), clips for the user, then pass2.

**Q2. A_min** (if (a)): 10 deg (matches the limit-proximity cost's onset at 100 deg) or 5 deg. **Recommendation: 10 deg.**

**Q3. Seed 0's program 2** produces 99 % of its holds. Nothing extra: if the centre fix works, program 2 should stop parking; check its
hold share in the rerun. **Recommendation: report-only.**

**Q4. Record:** hold census, six verdicts, the mechanism as the overseer's reading, the gradient inference as untested.
