# Planner brief: WO23 cap probe and WO24 D-hinge toy check, results (2026-11-09)

Rules in force: BRAIN_SPEC 7.37.3 (WO23), 7.38.2 and 7.38.4 (WO24, thread count); `docs/STAGE1_RULES.md` section 12.
Both are report-only. Both branches are verified by the overseer and merged into body (caca60d).

## WO23: generator acceleration / speed caps on the M3f toy (agent 1, body-acc)

**What ran:** four runs on today's code, seed 0, the WO17 options, 40 epochs, 6 threads on cores 12-17. The 16 held-out episodes have
distinct synthetic sources (seeds 900-915) and stand in for songs. Wall time 6 h 42 min.
- B = defaults: acceleration share 0.25, speed share 0.8.
- A1 = acceleration share 0.4.
- S1 = speed share 0.95.
- AS = both.

Baseline B was retrained because the old WO17 run ran at 8 threads (7.38.4). That run is listed as a reference only.

**Checks:**
- The new options are bit-identical to the old code at defaults (identity control: epoch 0 identical except for timing).
- The overseer recomputed realised joint speed and acceleration from the saved rollouts with a different difference method. Speed and
  acceleration p99 match to 3 decimals.

| | B | A1 | S1 | AS |
|---|---|---|---|---|
| share of steps on the acceleration cap (base, shoulder, elbow, wrist bend, roll) | .99 .997 .996 .90 .03 | .50 .996 .03 .02 .02 | .996 .997 .99 .995 .05 | .87 .996 .97 .12 .02 |
| share of steps on the speed cap (same order) | 0 0 0 .10 .97 | .50 0 .96 .97 .98 | 0 0 0 0 .95 | .13 0 .02 .87 .97 |
| realised joint acceleration p99, worst joint (x limit) | 0.35 | 0.30 | 0.31 | 0.46 |
| realised joint acceleration max, worst joint (x limit) | 0.81 | 0.87 | 0.76 | 0.79 |
| realised joint speed max, worst joint (x limit) | 0.91 | **1.006** (wrist bend) | 1.000 (roll) | **1.001** (elbow, wrist bend) |
| occupied cells, pooled / per episode | 920 / 338 | 1029 / 443 | 1221 / 340 | 1160 / 348 |
| between / half-episode JS (ratio) | .611 / .781 (0.78) | .599 / .753 (0.80) | .620 / .766 (0.81) | .586 / .740 (0.79) |
| decoding ext / int (argmax gap) | 1.172 / 1.174 | 1.098 / 1.129 | 1.107 / 1.168 | 1.076 / 1.084 |
| e'1 hand acceleration p99 (m/s^2) | 2.55 | 3.86 | 3.03 | 4.51 |
| e'2 share of hand speed > 1 m/s (toy limit 0.0110) | 0.0013 | **0.0334** | 0.0023 | **0.0478** |
| programs used | 2 | 1 | 2 | 4 |

Floor breaches, contact and end-stop events are 0 in all four runs. The WO17 reference (8 threads) has a speed max of 1.004x on base yaw.

**Servo limits, as asked in 7.37.3.**
- Acceleration is within the limit in every setting: p99 at most 0.46x, max at most 0.87x (central differences, as in the report).
  - Caveat: the single-sample maximum depends on the difference method. With plain second differences, baseline B's shoulder reaches
    1.008x in one sample. p99 does not depend on the method.
- Speed maxima reach the limit in A1 (1.006x) and AS (1.001x); S1 reaches exactly 1.000x. Each overshoot is at most 0.6 %.

**What the probe shows** (report-only):
- **Raising the acceleration share does not free the movement; the joints move from the acceleration cap to the speed cap.** In A1,
  elbow and wrist bend drop from about 99 % on the acceleration cap to 2-3 %, and rise to 96-97 % on the speed cap. The shoulder stays on its
  acceleration cap about 99.6 % of the time in every setting.
- **Raising the speed share alone changes little.** S1's acceleration-cap picture equals B's, and its hand metrics stay close to B's.
- **Occupied cells rise only modestly** (pooled 920 -> 1029-1221).
- **Episode distinctness does not change.** The between/half JS ratio is 0.78-0.81 in all four runs: two different episodes differ less
  than the two halves of one episode. This is the M3f / pass2 setting, without Stage 1's ingredient ii.
- **The acceleration change costs hand smoothness.** e'2 rises 26-37x, to 3-4x the toy limit. Decoding falls slightly, with overlapping
  intervals.

The planner's hypothesis (7.37.3: the cap, not the brain, sets the shape) is not supported here. Removing the binding cap moves the
binding onto the other cap, and leaves episode distinctness where it was.

## WO24: ii + iii with a D >= 0.7 hinge on the Stage 1 toy (agent 2, body-s1d)

**What ran:** arms ii, iii and iii+D on fresh seeds 4 and 5, 1000 epochs, 6 threads, 34 min.

The hinge is defined in rules section 12:
- D is estimated in-sample on the first 16 train songs, once per epoch;
- the violation is `g_D = max(0, 0.7 - D_est)`;
- the multiplier follows `mu_D <- max(0, mu_D + 0.16 g_D)`, starting at 0;
- the decoding loss becomes `(1 + mu_D) dec`.

**Checks:** the default code path is unchanged; test_s1d passes (overseer rerun); all six result files were recomputed and match the report.

| Run | between / half JS (ratio) | D [95 % CI] | occupied cells | entropy (bits) | 2AFC | MMD | final mu_D |
|---|---|---|---|---|---|---|---|
| ii, seed 4 | .862 / .036 (24.0) | 0.780 [0.707, 0.848] | 21.4 | 3.30 | 0.988 | 0.447 | — |
| ii, seed 5 | .845 / .041 (20.5) | 0.767 [0.712, 0.819] | 24.1 | 3.60 | 0.990 | 0.505 | — |
| iii, seed 4 | .536 / .048 (11.2) | 0.737 [0.679, 0.794] | 44.5 | 4.99 | 0.992 | 0.310 | — |
| iii, seed 5 | .581 / .049 (11.9) | 0.752 [0.688, 0.813] | 44.8 | 4.96 | 0.988 | 0.324 | — |
| iii+D, seed 4 | .440 / .038 (11.6) | **0.790** [0.743, 0.835] | **47.3** | 5.12 | 0.967 | 0.210 | 8.45 |
| iii+D, seed 5 | .482 / .041 (11.9) | **0.769** [0.699, 0.832] | **46.9** | 5.10 | 0.967 | 0.220 | 10.21 |

What it shows (report-only):
- **iii+D reaches held-out D >= 0.7 on both seeds, with about twice arm ii's occupied cells.**
- **The hinge's own effect is not isolated.** Plain iii also reaches D >= 0.7 on these two seeds (0.737, 0.752). Over all six seeds (0-5),
  plain iii's D ranges 0.576-0.757 and is below 0.7 on 3 of 6.
- **iii+D has the lowest between-song distance.** JS is 0.44-0.48 (ii 0.85-0.86) and MMD 0.21-0.22 (ii 0.45-0.51). It is still about 12x
  the half-song control, with 2AFC 0.967.
- **The multiplier only rises** (the violation is clipped at 0). D_est reached about 0.70 by epoch 220-300 and then stayed at 0.75-0.80,
  but mu_D kept the decoding loss at about 9-11x weight to the end.

## Questions (the planner said: rule Stage 3 with both results in hand)

**Q1. The generator caps for Stage 3.**
- (a) Keep the defaults (0.25 / 0.8).
- (b) Use AS (0.4 / 0.95): acceleration stays within limits, but speed max reaches 1.001x and e'2 is 4x the toy limit.
- (c) Raise only the speed share (S1): little change.

Recommend (a). Raising the acceleration share trades one binding cap for the other, does not make episodes more distinct, and roughens
the hand. Record the 7.37.3 hypothesis as not supported by WO23.

**Q2. Ingredients for Stage 3.**
- (a) ii + iii + D hinge, as in WO24.
- (b) ii alone.
- (c) ii + iii without the hinge.

Sub-question: should the D multiplier be allowed to fall when D_est is above 0.7, i.e. `mu_D <- max(0, mu_D + eta (0.7 - D_est))`? Then
the decoding weight relaxes once D is safe.

Recommend (a), with the multiplier allowed to fall, as a cheap toy check (two seeds, ~35 min) before the Stage 3 run. Reasons:
- iii+D held D on both seeds with about twice the cells;
- plain iii fails D on 3 of 6 seeds, so the hinge is a safeguard, not decoration;
- the always-rising multiplier lowers the between-song distance (MMD 0.21 vs 0.45) and should be checked before a long run.

**Q3. Limit checks in Stage 3.**
- Report p99 and max of realised joint speed and acceleration per joint, with the difference method stated (central differences, as in
  WO23).
- Treat a single-sample max as a flag, not a failure. Speed overshoots of <= 0.6 % are clamped by the servo firmware.

Recommend yes; record it.

**Q4. Stage 3 design.** Both inputs are now in hand. Please rule the Stage 3 design, which so far is: 5-DoF run; bars including the human
real-vs-swapped-music test; thread count fixed and stated (7.38.4). In particular rule:
- the ingredient set (Q2);
- the caps (Q1);
- the compute box;
- whether a toy check (Q2 sub-question) comes first.
