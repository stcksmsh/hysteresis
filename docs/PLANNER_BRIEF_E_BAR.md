# Planner brief: bar component (e) does not catch the jitter (2026-11-06)

Context: `docs/BRAIN_SPEC.md` §7.24 (bar (e) and the overseer's (e) defaults), work orders 13A (done) and 13B (running). One arm.

## 1. What ran

- WO13A (branch body-hf, merged into body 731675f): `scripts/body/hf_share.py` (§7.24 default: joint velocity by central difference of the
  50 Hz joint CSV, Welch 4 s Hann 50 % overlap, power above 3 Hz / power above 0 Hz, summed over base_yaw, shoulder, elbow, wrist_bend),
  7 tests OK. v47 reference from the v47 Off hexagon scores (six arms per song, `hyst score-csv`; v47 html byte-identical). K5 try 1 and the
  fallback measured the same way (report only).
- WO13B (branch body-m3f) is running its 6-point grid on the new body (v2f: table contact without friction, self-collision); ETA ~20:40.
  Its selection rule uses (e).

## 2. Results (overseer recomputed the K5 values from the joint CSVs; v47 per-arm values from the exported CSVs)

### 2.1 (e) as defined does not separate the movement the user called spastic

| song | v47 (mean of 6 arms) | K5 try 1 | fallback |
|---|---|---|---|
| Instant Crush | 0.00242 | 0.00245 | 0.00181 |
| Five Years | 0.00283 | 0.00315 | 0.00116 |
| Presence | 0.00366 | 0.00238 | 0.00247 |
| mean | 0.00297 (limit 1.25x = 0.00371) | 0.00266 | 0.00181 |

K5 try 1, which the user judged "spastic (frequent flicking, jittering, stuttering)", **passes (e)**. Above 3 Hz holds about 0.3 % of joint
velocity power in all three; even above 1 Hz the K5 share (0.09-0.12) is not larger than a smooth motion's would need to be.
Other joint-space measures also fail to separate K5 from v47 (arm 0; IC / FY / PR): share of joint-acceleration power above 3 Hz K5 0.061 /
0.072 / 0.069 vs v47 0.126 / 0.143 / 0.147; jerk RMS / velocity RMS 47 / 49 / 41 vs 49 / 54 / 53; joint-velocity reversals per second per
joint 1.18 / 1.15 / 1.14 vs 0.89 / 0.87 / 1.04.

### 2.2 Hand-space measures do separate (FK of the CSV rig, 50 Hz, central differences)

| song | hand acceleration p99 (m/s2): v47 mean 6 arms / K5 / fallback | share of time hand speed > 1 m/s: v47 / K5 / fallback |
|---|---|---|
| Instant Crush | 4.26 / 10.19 / 3.36 | 0.010 / 0.160 / 0.005 |
| Five Years | 4.15 / 9.22 / 2.57 | 0.005 / 0.128 / 0.002 |
| Presence | 6.00 / 11.05 / 3.67 | 0.011 / 0.113 / 0.008 |

v47's six arms agree within 0.2 m/s2. K5 try 1 is 1.8-2.4x v47 on hand acceleration and 10-26x on time above 1 m/s. Reading: the flicks are
whole-arm throws of the hand (large, fast, low-frequency joint swings amplified by the long links), not high-frequency joint tremor.
Untested: whether hand acceleration tracks what the user sees as "spastic" beyond these three songs and one policy.

## 3. Questions

1. **Replace (e)?** Options:
   - (a) replace with (e'): hand-acceleration p99 per song <= 1.25 x v47's (IC 5.33, FY 5.19, PR 7.50 m/s2; toy: mean over episodes vs the
     mean of v47's three, 4.80 x 1.25 = 6.00);
   - (b) keep (e) and add (e');
   - (c) (e') plus time above 1 m/s <= 1.25 x v47's.
   Recommendation: (a). (e) as defined passed the motion it was meant to stop, so keeping it adds nothing; check-csv's hand-speed limit
   already covers speed. (e') must be fixed before WO13B selects its grid point (~20:40); the grid records all measures, so no rerun is needed.
2. **v47 as the reference** (mean of its six arms; the arms agree within 0.2 m/s2). Recommendation: keep.
3. **Report-only ablation of movement changes 1-4** (7.24): on (e') instead of (e). Recommendation: yes, and report (e) too.
4. **Recorded overseer decisions in WO13B, for the record:** the new body uses frictionless contact (v2f; full friction projects pass2 to
   30.6 h, over the 24 h box; v2f 21.1 h, an upper bound); jerk, hand-speed and jolt terms are normalised by the untrained policy's value on
   the OLD body (the new body's untrained jerk is contact-spike dominated, about 1e9 vs 2e6). Confirm or correct.
