# Planner brief: retarget look test blocked by the table (BRAIN_SPEC 7.49.5 / 7.50), 2026-11-13

TO: planner. FROM: overseer. Needs a ruling before any clip of the retarget look test can be rendered. Nothing has been rendered or viewed.

## What ran

- **FineDance public part downloaded** (203 sequences, 7.66 h, 30 fps; plain public HTTPS, no login; archive sha256 re-checked by the
  overseer). Motorica is BLOCKED: its only link is a SharePoint folder that needs a browser login (STOP rule, 7.50.5). AIOZ-GDANCE and AIST++
  motion are still downloading.
- **Retarget rules** (`docs/RETARGET_RULES.md`, branch body-retarget), reviewed by the overseer before any render:
  - V1 arm-as-arm and V2 arm-as-whole-body as 7.49.5;
  - angles from FineDance's local rotations (6D = first two rows of R, checked against FineDance's own code), no SMPL model file;
  - scaling: each human angle's pooled p2-p98 fills 80 % of the distance from round 1's centre to the joint limit, for shoulder, elbow and
    wrist bend: shoulder -100..-20, elbow -34..94, wrist bend -91..61 deg;
  - one change made before scaling, from angles only: yaw and twist are measured from each 20 s window's start. Dancers' spin accumulates to
    1,000-10,000 deg per sequence, which would have given a base scale of 0.04; the scale is now 0.23.
- **Gating:** both variants of the first 200 seeded 20 s windows were simulated through the round-1 limiter, servo and v2f body, without the
  spinal layer, and gated as 7.44.

## Result

| | Passes all gates | Contact | Limits | End stop | Clearance | Motion |
|---|---|---|---|---|---|---|
| V1 | 2 / 200 | 194 | 196 | 30 | 15 | 1 |
| V2 | 13 / 200 | 161 | 184 | 40 | 1 | 0 |
| Both variants | **1 / 200** (10 needed) | | | | | |

- The minimum hand height sits at the gate floor (0.11 m) in nearly every window.
- The "limits" failures are contact impacts: acceleration 5-15 times the limit at thousands of contact substeps. The command limiter itself
  holds speed and acceleration.
- **Builder's reading (not checked by the overseer):** human reach covers the whole hemisphere, including poses below the shoulder, and the
  robot's base sits on the table, so the 80 % share folds the hand into the table for a large part of every window. The mapping code is not
  at fault: elbow flexion median 61 deg, all rotation matrices orthonormal.

## Question

1. **How to keep the retargeted arm off the table.** Rendering and gating stay as ordered; only the step that produces the command changes.
   - (a) **Share ladder, fixed before running [recommended]:** for each variant separately, use the largest share from (80, 70, 60, 50,
     40 %) of the centre-to-limit distance for which the seeded stream yields 10 clips passing in both variants within 200 candidates; report
     the pass counts at every step. No new mechanism. The human motion keeps its shape and becomes smaller, which works against Kosta's "too
     small" notes; if 40 % still fails, report and hold.
   - (b) **Floor guard in the command path:** clamp each commanded pose so that FK keeps the hand >= 0.11 m and the links >= 0.05 m above the
     table; the share stays at 80 %. This is a new mechanism; the real installation will need red zones anyway. Human amplitude is kept
     elsewhere, but the arm can flatten against the guard, the "stuck" look Kosta named before.
   - (c) Shift the centre upward (e.g. map the human's mid pose to a higher robot pose) at 80 % share. This needs one more fixed number
     chosen without viewing.
   - (d) Keep the scale and relax the contact gate: not recommended (the clips would show the arm pressing into the table).
2. **Record** as BRAIN_SPEC 7.51.
