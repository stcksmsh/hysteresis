# Planner brief: end-point smoothness (Step A) and space retarget V3 (Step B), BRAIN_SPEC 7.54, 2026-11-13

TO: planner. FROM: overseer. Steps A and B ran report-only. V3 passes 0 of 20, so Step C (the blind look) cannot run as specified. Nothing
has been shown to Kosta. Report: `docs/V3_REPORT.md` (branch body-v3 27e482d); numbers: `/secondary/hyst-data/body/retarget_look/v3/`.

## What ran

- **Step A** on the 20 look-test clips. Signals:
  - the human end point (right wrist for V1, head for V2), in world space and relative to its origin (right shoulder / pelvis);
  - the stage-1 joint angles;
  - the robot lamp position under the stage-1 angles.

  Human positions come from FineDance forward kinematics with canonical T-pose bone offsets (no body model file).
- **Q2:** the C04_V2 shoulder offset.
- **Step B**, the same 10 windows. V3a: the lamp follows the right wrist relative to the right shoulder. V3b: the lamp follows the head
  relative to the pelvis.
  - Inverse kinematics: damped least squares at 100 Hz, warm-started. Every weight comes from a rule stated before any run (damping from a
    90 % step-response rule, a per-frame change penalty, 3 iterations from convergence probes).
  - Then the round-1 spinal layer (H1), the limiter, the servo, the v2p body, and the gates at 1.25.
- **Overseer correction before the run, recorded as BRAIN_SPEC 7.54.9; please confirm or overrule.**
  - My 7.54.8 default put the workspace centre at the lamp position of round 1's centre pose. That point is 0.673 m from the shoulder joint
    p1, and the arm reaches 0.69 m, so the centre sat at the edge of reach.
  - I replaced it with: the human origin maps onto the robot's shoulder joint p1, lamp target = p1 + scale x relative vector. That keeps
    98 % of targets within 0.55 m of p1, reachable by distance.
  - The builder's alternative (centre on the pooled median at the old centre) was rejected for the same reason.
- **Overseer checks:**
  - V3a realised medians and V3b's shoulder and wrist-bend medians recomputed from the realised CSVs: equal to the report;
  - frames at the joint stops counted independently;
  - rules note (m) reviewed before the run;
  - every run followed a pushed commit.

## Results

**Step A** (median over 20 clips; acceleration sign changes per second at 30 fps / share of speed power above 3 Hz):

| signal | changes /s | power > 3 Hz |
|---|---|---|
| human end point, world | 6.5 | 0.031 |
| human end point relative to its origin (what V3 follows) | 6.3 | 0.048 |
| robot lamp position under the stage-1 angles | 8.8 | 0.150 |
| stage-1 joint angles (mean of 5 joints) | 8.9 | 0.129 |

- The human end point carries 3-5x less fast motion than the retargeted angles or the lamp path they produce. This matches Kosta's
  viewing judgement and the planner's hypothesis.
- **By variant:** for V1 (wrist relative to shoulder) power above 3 Hz is 0.029 vs 0.183 for the lamp. For V2 (head relative to pelvis) it
  is 0.085 vs 0.147, a smaller gap.
- The human end point is not free of direction changes by this count (about 6 per second at 30 fps).

**Q2:** the C04_V2 shoulder offset is **gravity sag in the servo model**: mean +4.8 deg (range -4.4 to +12.4) over seconds 8-12, +0.1 deg
with gravity off, and 5.3 deg predicted from the gravity torque (1.55 N m) over the servo stiffness (16.86 N m/rad). It is not the limiter,
the guard, the end stops or the column.

**Step B, gates at 1.25: V3a 0 / 10, V3b 0 / 10.**
- **V3b fails only on the end stops (all 10).** The head sits about 0.5 m above the pelvis, so the lamp target sits about 0.5 m above p1.
  The arm points straight up and the shoulder holds its -110 deg stop for 37-343 consecutive 50 Hz samples per clip.
- **V3a fails contact, end stops and limits on all 10, and clearance on 7.** The hand is often below the shoulder, so the target sits low
  beside the column and the arm folds into it. The elbow and wrist bend reach +-110 deg, and the 7-14x acceleration ratios are the contact
  impacts.
- **IK residual over 2 cm** (2,001 frames): V3a median 448 (125-1,140), V3b median 97 (3-397). The causes are the column, the joint limits
  and the 3-iteration solve.
- **The IK stage adds jitter of its own.** Its output angles change direction 9.5-14.3 times per second, with power above 3 Hz of 0.28-0.58
  (V3a). That is more than V1's stage-1 angles and much more than the path it follows (5.9 / 0.049).
- **After the spinal layer and the limiter, the realised motion is about where V1/V2 + H1 already were:**

  | realised (median) | shoulder changes /s | wrist bend changes /s |
  |---|---|---|
  | V3a | 2.47 | 3.70 |
  | V1 baseline (shown) / V1 + H1 | 2.62 / 2.10 | 5.09 / 3.67 |
  | V3b | 2.27 | 3.65 |
  | V2 baseline / V2 + H1 | 3.45 / 2.67 | 4.95 / 3.60 |
  | S03 reference | about 1.1 | about 0.9 |

## Questions

1. **Next step for the jitter.**
   - (a) **Smooth the joint-space retarget to the human end point's own smoothness, then run the held session.**
     - Low-pass the stage-1 angles of V1/V2 with a cutoff fixed by a rule before any render. Default rule: the lowest cutoff at which the
       lamp path under the filtered angles has no more power above 3 Hz than the human end point it came from (median over the 20 clips).
     - Keep H1 (the spinal layer) in, and gate at 1.25.
     - Then the blind re-look: 4-6 clips including C04_V2 and C10_V1, old vs fixed in pairs, order mixed.

     **[recommended]** Step A gives a measured target for "as smooth as the human". V3's realised motion is no better than V1/V2 + H1, and
     V3 fails on geometry.
   - (b) **V3 round 2 with geometry fixes:**
     - map the dancer's median pose to a centre inside the joint ranges;
     - soft joint limits in the IK (e.g. 80 % of range, as V1/V2);
     - more iterations or a stronger change penalty.

     This is the second and last round allowed for V3, and its new weights would have to come from rules. The IK noise would remain unless
     it is damped harder.
   - (c) Both (a) and (b), each report-only first; the blind look only on what passes.
2. **V3 status.** If (a): park V3 (code kept on its branch, not merged into the look-test path), or merge it as a report-only tool.
   **Recommended: merge the code and report as report-only.**
3. **The 7.54.9 correction** (origin onto the shoulder joint p1 instead of the edge-of-reach centre): **confirm as recorded, or overrule.**
4. **Record** as BRAIN_SPEC 7.55: Step A, Q2, Step B 0 / 20 with causes, and that Step C did not run.
