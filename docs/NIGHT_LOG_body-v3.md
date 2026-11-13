# Night log body-v3 (WO35, report only)

## MORNING SUMMARY: V3 READY (see the commit that carries this line)

**Report only: no verdict, no video, no blind session; V1/V2, the shown clips and round-1 files untouched.** `docs/V3_REPORT.md` (sections A, Q2, B), `/secondary/hyst-data/body/retarget_look/v3/numbers.json` (stepA, stepB), realised CSVs and IK angles in `v3/work/`, IK numbers `v3/ik_params.json`, Q2 data `v3/q2.json`. Rules note (m) with the 7.54.9 offset line pushed before the run (e1521d6); every run followed a pushed commit.

- **Step A** (STEP A READY 886ef28), Q2 (gravity sag of the servo model: +4.8 deg mean, 0.1 deg with gravity off, 5.3 deg predicted) and the note (m) review are in the report; see the earlier summary lines.
- **Step B, gates at 1.25: V3a 0 / 10, V3b 0 / 10.** V3b fails only "endstop" on all 10 clips (the head 0.5-0.6 m above the lamp's reference puts the shoulder against its +-110 deg stop for more than 6 samples). V3a fails contact, end stop and limits on all 10 and clearance on 7 (C02, C03, C06-C10): the lamp target below p1 beside the column drives the arm into the column; accel ratios of 7-14 x are the contact impacts. Guard share: 0 on 18 of 20 clips, 0.0005 (C03_V3a), 0.048 (C09_V3a).
- **IK residual > 2 cm, shown 20 s (2,001 frames):** V3a median 448 (range 125-1,140), V3b median 97 (range 3-397); median error per clip 0-4.5 cm, p95 up to 66 cm (C02_V3a), max 91 cm. (The targets are reachable by construction at the 98th percentile; the residuals come from the column, joint limits and the 3-iteration solve.)
- **Jitter, medians over the 10 clips (acceleration sign changes per second; speed power > 3 Hz):**
  - V3a: end-point target path 5.9 / 0.049; **IK output angles 9.5-14.3 / 0.28-0.58** (shoulder 11.2 / 0.283, wrist bend 13.1 / 0.578; stage-1 angles of V1 were 7.3 / 0.075 and 11.6 / 0.199); lamp FK of the IK output 11.7 / 0.246; after the spinal layer 4.7 / 0.040 (shoulder), 5.4 / 0.121 (wrist bend); limiter 2.1 / 0.002, 4.8 / 0.050; **realised shoulder 2.47 / 0.007, wrist bend 3.70 / 0.014** (V1 baseline 2.62 / 0.001 and 5.09 / 0.010, V1 + H1 2.10 / 0.001 and 3.67 / 0.007, S03 refs 1.07 / 0.000 and 0.85 / 0.000).
  - V3b: target path 9.2 / 0.101; IK output shoulder 11.3 / 0.270, wrist bend 14.1 / 0.311; lamp FK of the IK output 14.7 / 0.274; **realised shoulder 2.27 / 0.001, wrist bend 3.65 / 0.016** (V2 baseline 3.45 / 0.003 and 4.95 / 0.012, V2 + H1 2.67 / 0.001 and 3.60 / 0.006).
  - So the IK stage itself is noisier than the stage-1 angles of V1/V2 (its output has more direction changes and more power above 3 Hz than the end-point target path it follows); the spinal layer and the limiter remove most of it, and the realised numbers of V3 sit close to the V1/V2 + H1 numbers and above the S03 references.
- **Facts to know when reading:** (1) with the 7.54.9 offset V3b's lamp stays about 0.5 m above the shoulder (head above pelvis), V3a's targets are often low and beside the column; (2) the V3 gate failures are about geometry (end stop, column), not the 1.25 tolerance; (3) the IK uses N = 3 iterations per frame by rule; nothing was tuned on any of these outcomes.
- **FOR USER (defaults):** position deadband 0.01 m/s^2 in Step A; Step B shoulder numbers use the IK output as the commanded signal and the spinal output as the limiter input.

## STEP A READY (see the commit that carries this line)

`docs/V3_REPORT.md` section A; per-clip numbers `/secondary/hyst-data/body/retarget_look/v3/numbers.json` (key `stepA`). Medians over the 20 clips (acceleration sign changes per second, mean over axes for positions / share of speed power above 3 Hz):

| signal | sign changes /s | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| (0w) human end point, world | 6.52 | 0.031 | 0.003 |
| (0r) human end point relative to its origin | 6.28 | 0.048 | 0.004 |
| (1e) robot lamp position, FK of the stage-1 angles | 8.75 | 0.150 | 0.029 |
| (1) stage-1 joint angles, mean over the 5 joints | 8.93 | 0.129 | 0.037 |

Facts: the human end point has about 6.3-6.5 acceleration sign changes per second at the 30 fps sampling (so it is not free of direction changes by that count), but its speed power above 3 Hz is 0.03-0.05, a third to a fifth of the lamp-FK position (0.150) and of the angles (0.129 mean, wrist bend 0.199, roll 0.249). V1 clips (wrist) are smoother than V2 clips (head) in (0w); per-variant tables are in the report. Position deadband 0.01 m/s^2 (FOR USER: default; 1 deg/s^2 at a 0.57 m radius).
