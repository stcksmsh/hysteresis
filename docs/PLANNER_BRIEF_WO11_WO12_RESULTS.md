# Planner brief: work orders 11 (seed 2) and 12 (K5 videos), results (2026-11-06)

Context: `docs/BRAIN_SPEC.md` §7.19-7.22 (7.21 = the two-seed credit rule, fixed before the runs; 7.22 = K5 try 1 rulings). One arm only.
All numbers below were recomputed by the overseer from the saved per-episode or per-row data unless marked otherwise.

## 1. What ran

- **WO12 (7.22 point 1), branch body-k5video, merged into body (722fe13).** B7 epoch-6 lanes in K5 format for the three danced songs
  (Instant Crush 339.8 s, Five Years 283.8 s, Presence 270.7 s); one continuous argmax rollout of K5 try 1 `best.pkl` per whole song (carry never
  reset, 30 s causal normalisation from the song's start); 50 Hz joint CSV; render with the one-arm camera (new off-by-default
  `--joint-csv` input to `ensemble_preview`), side by side with the fallback videos. Report-only readability per 60 s segment.
  Checks: lanes bit-identical to the stored K5 check file for song 009900; the rollout's first 60 s bit-identical to the K5 check's own
  window rollout (11 arrays, max difference 0); v47 hexagon exports byte-identical (3/3); videos equal audio within one frame.
- **WO11 (7.21 point 3), branch body-m3e, merged into body (885a982).** Seed 2 (Trainer seed 1) of M3e try 1 and of A1 (closed-loop inputs
  off), A2 (dopamine gating off), A3 (internal observer off); recipe unchanged (lambda 0.03, lr 1e-3, 40 epochs, same toy, same 16 held-out
  episodes, WO7 observer procedure). 2 h wall time; 15 unit tests OK.

## 2. Results

### 2.1 Seed 2 and the credit rule (argmax; paired try1 - ablation over the 16 held-out episodes, 10,000 resamples; recomputed, all match)

| ablation | decoder | seed 1 | seed 2 | both > 0? |
|---|---|---|---|---|
| A1 closed loop | ext | +0.097 [-0.042, 0.232] | -0.057 [-0.142, 0.028] | no |
| A1 closed loop | int | +0.213 [0.078, 0.352] | +0.004 [-0.074, 0.076] | no |
| A2 dopamine gating | ext | -0.086 [-0.209, 0.044] | +0.124 [0.034, 0.212] | no |
| A2 dopamine gating | int | -0.085 [-0.166, -0.006] | -0.000 [-0.100, 0.109] | no |
| A3 internal observer | ext | +0.112 [-0.019, 0.254] | -0.200 [-0.298, -0.099] | no |
| A3 internal observer | int | +0.279 [0.159, 0.408] | -0.164 [-0.264, -0.058] | no |

- By the rule fixed in 7.21 point 1: **no mechanism is credited for either decoding; all three stay "present".**
- Dopamine "measurably lowers decoding" (7.21 point 2) is **not** shown: only seed 1's internal interval is below 0.
- Try 1 seed 2 passes the toy bar in argmax: ext (a) 0.763 [0.646, 0.877], int 0.602 [0.494, 0.705] (seed 1: 0.991, 0.951).
  Run-to-run spread seed 1 - seed 2 (paired): ext 0.229 [0.098, 0.362], int 0.348 [0.252, 0.447] (builder's figure; the per-seed means were
  recomputed). The training-run spread is as large as the ablation effects tested. Seed 2 flips the sign of A1 and A3.

### 2.2 K5 videos: readability per 60 s (report only; ext / int (a) gap, interval over 20 shifts of one segment, not over songs)

| song | 0-60 | 60-120 | 120-180 | 180-240 | 240-300 | last part |
|---|---|---|---|---|---|---|
| Instant Crush | 0.135 / 0.261 | 0.497 / 0.427 | 1.253 / 1.287 | 0.698 / 0.816 | 0.516 / 0.508 | 300-340: 0.463 / 0.780 |
| Five Years | 0.396 / 0.389 | 0.365 / 0.389 | 0.781 / 0.757 | 0.692 / 0.677 | 240-284: 1.505 / 1.406 | |
| Presence | 0.250 / 0.258 | 0.787 / 0.785 | 0.634 / 0.409 | 1.116 / 1.010 | 240-270: 1.200 / 1.015 | |

All 16 segments are above 0 in both decoders (every interval's lower end > 0). K5 check values for comparison: ext 0.625, int 0.636. The first
minute is the lowest in two songs (the observers were fit on the K5 check's training rollouts; not refit per song). Builder's numbers; the
overseer checked the table against `segments.json`, not the gap computation.

### 2.3 K5 videos: the arm goes below the floor (new finding)

- `hyst check-csv` refuses all three songs. Rows with a floor-margin breach: 93 %, 91 %, 97 % (worst margin -0.72 m); hand speed above 1.2 m/s in
  955-1,510 rows (max 2.4 m/s); a few joint-range, acceleration and jolt rows.
- Overseer forward kinematics on Instant Crush (every 25th row): hand height vs the base median -0.28 m, min -0.61 m, max +0.60 m; shoulder
  -91 to +93 deg. Frames show the arm through the floor plane (e.g. Presence 200 s).
- Cause (checked in code): the MuJoCo arm of the toy and K5 has no floor geometry and no floor contact; the K5 objective has no floor or
  hand-speed term; only the two bends the rig bounds are clipped. The policy uses the space below the base freely.
- Consequence: try 1's poses cannot be played on a real arm. Try 1's record and wording (7.22) stand as a result about the simulated body.

## 3. Questions

1. **Record WO11 as "all present, none credited, dopamine not shown to lower"?** Recommendation: yes, as the rule says; also record that
   run-to-run spread (up to 0.35) is as large as the effects, so no third seed (more seeds would not change wording under a both-seeds rule
   unless all agree).
2. **K5-pass2 for a playable arm (only if the user wants it after watching; 7.22 point 3).** How to make the policy respect the floor and
   the speed limits:
   - (a) physical: floor plane with contact in the MuJoCo model, plus the check-csv hand-speed and jolt limits as soft penalties in the K5
     objective;
   - (b) penalties only: floor margin and hand speed as soft penalties, no contact;
   - (c) hard limits: narrow the shoulder/elbow ranges so no pose reaches the floor, plus a hand-speed penalty.
   Recommendation: (a) with the same weight scheme as the energy term, because it changes the body the policy learns in rather than only
   its score, and a real arm meets a real floor; the K5 check then also requires check-csv to pass on the three danced songs. It is a new
   labelled run with its own full K5 check (7.22 point 3); try 1's record stays.
3. **Does pass2 need the toy first?** Options: (i) rerun the M3e toy with the floor (2 h) to see the bar still passes, then pass2;
   (ii) straight to pass2 (about 13 h on 6 threads, inside the 24 h box). Recommendation: (i), because the floor removes most of the
   space try 1 used and the toy is cheap.
4. **Readability per 60 s:** report only as ruled. Any wording about "holds past 60 s" needs a ruling. Recommendation: none yet; three songs
   only, intervals over shifts, not over songs.
