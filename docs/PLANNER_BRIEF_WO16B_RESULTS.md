# Planner brief: work order 16b results (clip-boundary holds, network saturation H1b, torque/gravity H7) and the fix questions (2026-11-08)

Follow-up to `docs/PLANNER_BRIEF_WO16_RESULTS.md` (read that first; its section 2 still holds). Your additions are recorded as
`docs/BRAIN_SPEC.md` §7.31.5 and were run as WO16b (branch body-m3f 595cf39). Analysis only; nothing trained. Overseer checks: re-simulation
still bit-identical to the saved rollouts (builder, diag off and on); the code change only adds default-off torque logging (diff read);
test_m3f_park 6 OK (overseer rerun); the clip-boundary hold census below was recomputed from the saved joint angles (exact match). The
torque, gravity and network-output numbers come from the builder's re-simulation and were not recomputed.

## 1. Results

### 1.1 Clip-boundary holds (>= 2 s within 1 deg of 109.5 deg, less than half of the stretch on the stop itself)

| | holds | total | joints | hard stop acting |
|---|---|---|---|---|
| seed 0 | 38 | 549.5 s | all wrist bend (mean 109.3 deg) | 4.9 % of steps |
| seed 1 | 17 | 82.8 s | shoulder 54.5 s, wrist bend 28.3 s | 25.5 % of steps |

Same signature as the stop holds: pre-clip target at or beyond 109.5 for 96-98 % of the time, generator centre on its limit, amplitude
about 0.05 deg, no contact. So seed 0 parks the wrist at the clip boundary as well as the elbow on the stop (467.1 s of stop holds,
mostly elbow; the two overlap in time). Point 1 now reads "beyond the clip boundary" (109.5): 98.6 % of stop-hold time.

### 1.2 H1b, network saturation: supported

The centre output for a bend joint is u[2, joint] = clip(pi @ sigmoid(theta) + 0.2 tanh(amod[10 + joint]), 0, 1), bounds [0, 1], pre-clip
range [-0.2, 1.2]. During holds it is within 2 % of a bound in **99.8 %** of hold blocks, always the hold-side bound 0 (centre = -110
deg); the unclipped value lies outside [0, 1] in 99.8 %, so **the zero-gradient clip is active**. The tanh term alone is saturated (> 0.98)
in only 0.4 %: it is the sum that leaves the range, and the program's own prototype is already low (u about 0.04). The amplitude output is
never near a bound (0 %); it is moot because the cap 110 - |centre| zeroes the amplitude.

### 1.3 H7, torque saturation: not supported; gravity into the stop: supported

Position actuators, gear 1, so `actuator_force` is the joint torque (N m), forcerange +-2.94; gravity torque = -`qfrc_bias`; substep
averages. Held-joint torque at stall 0.0 % of hold time, shoulder 0.0 %; mean -0.15 N m (the servo pulling back its 0.5 deg error).
**Gravity points into the stop 99.9 % of hold time** (mean +0.43 / +0.48 N m, seed 0 / 1), i.e. 1.5-1.6 deg of servo droop, more than the
0.5 deg the clipped target sits inside the stop. Static replay (plain MuJoCo, no policy) from each hold pose with the target 5 deg inside
the stop: the joint settles at 106.4 / 106.5 deg mean (min 105.3), off the stop; with the run's own target it ends at 110.0. Wrist
boundary holds: negligible gravity (-0.02 N m); the wrist simply sits at the clipped target.

### 1.4 All verdicts

H1 clipping (as centre saturation) **yes** (98.6 %); **H1b network saturation yes** (99.8 %, zero-gradient clip active); H2 chosen stillness
no (1.3 %); H3 contact no (0 %); H4 pinned by the stop yes (98.4 %); H5 program/brain state seed 0 only; H6 easy code no (borderline,
p 0.03-0.04); **H7 torque no / gravity yes**.

**Overseer's plain reading of the chain:** the policy's centre output for a bend joint is pushed past its lower bound, so the clip to [0, 1]
holds it at 0 (centre -110 deg) with no gradient back; the amplitude cap then zeroes the swing; gravity sags the joint 1.5 deg, past the
0.5 deg clip margin, onto the hard stop, which holds it there. The limit-proximity cost cannot pull it out because no gradient passes the
saturated clip (supported now by H1b; the gradient itself was still not measured).

## 2. Questions (replace Q1-Q4 of the WO16 brief)

**Q1. The fix.** Options:
- (a) **Smooth centre map:** replace the hard clip of the centre output by a smooth map into +-(110 - A_min) (e.g. sigmoid/tanh of the
  unclipped sum), so the centre never reaches the limit, the amplitude cap never falls below A_min, and the gradient never vanishes.
  Targets H1/H1b directly; with A_min >= 2 deg it also keeps gravity droop (1.5-1.6 deg) off the stop (H4/H7).
- (b) **Clip margin above the droop:** CLIP_MARGIN_DEG 0.5 -> 2.5 deg. Stops the pinning (H4/H7) only; the centre still saturates and the
  arm still freezes, 2.5 deg off the stop.
- (c) (a) and (b) together.
- (d) The gradient measurement first (minutes). H1b already shows the zero-gradient clip active 99.8 % of hold time, so this mainly
  confirms the arithmetic.
- **Recommendation: (a) alone, A_min 10 deg** (the limit-proximity cost's onset, 100 deg). It removes the saturation, the zero gradient
  and the stop contact in one change; (b) would hide the freeze, not remove it. Then the two-seed toy rerun under the 7.30.3 gate plus the
  7.31.2 parking gate, clips for the user, then pass2.

**Q2. Scope of the smooth map.** The same saturation can occur in other u rows (amplitude: never near a bound so far). Options: (a) centre
rows of the three bend joints only; (b) every clipped u output. **Recommendation: (b)**, same map for all, so no output can hide behind a
zero-gradient clip; A_min applies to centres only.

**Q3. Seed 0's program 2** (99 % of its stop holds): report-only. **Recommendation: report-only.**

**Q4. Record:** the WO16 + WO16b verdicts and the chain above as the overseer's reading; gradient not measured.
