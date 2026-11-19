# Planner brief — Stage 3 stopped on the user's verdict (2026-11-12)

Overseer handover for the planning agent. Rules of record: `docs/BRAIN_SPEC.md` on branch `body`, latest 7.39-7.41 (Stage 3 design,
bars (a)-(f), launch rulings). Every number below was recomputed by the overseer unless marked "builder".

## 1. User verdict (verbatim, 2026-11-12 ~19:13, on the round-400 clip)

> "Again same issue, it's the same tight move all the time with variations. Stop all work and make handoff explaining state so far to planner"

This is the third learned policy rejected by eye for the same reason. pass2's rejection (7.33.7) was: "the same exact shape of movement, just
repeated at different speeds/accelerations/etc, it's not conveying anything to me."

## 2. What ran

- **Design:** 7.39.4 + 7.40 + 7.41: pass2 body (v2f), frozen B7 epoch 6. Two state streams: fast (beat phase, arousal, surprisal) and slow
  (8 L4 PCs, 8 s surprisal integral, band power; corpus-normalised). The objective has four parts:
  - ii: matched InfoNCE;
  - iii: Lipschitz observers in metres;
  - rising D hinge per stream;
  - limit hinges with dual multipliers.

  The energy threshold is 0.375 J/block (v47 replayed on v2f) and the jerk threshold is 4.75e6 (1.25x v47). Basal ganglia as built.
- **Code and resources:** code body a9fd858, 6 threads on cores 6-11, 14 GB cap. Out: `/secondary/hyst-data/body/s3/run/`.
  - Unit `hyst-wo26b-run-r1` ran from 2026-11-09 22:16. The machine powered off twice.
  - The run was resumed as `-r3` on 2026-11-12 09:28.
- **Stopped by the overseer at the user's word:** round 511 of 977, 10.94 h compute of the 30 h box (2026-11-12 19:14, clean stop). It is
  resumable (`ckpt.pkl` at round 511). `best.pkl` = round 400.
- **Side-car (WO27, report-only, 7.41.3):** `/secondary/hyst-data/body/s3/run_report/` (summary.txt, <round>/hinges.json, 400/ clip + CSV).
  The branch body-s3r was merged into body (e4e5c68); its tests were rerun OK.
- **Not run:** the bar evaluation `s3_eval.py` on the 357 held-out songs. None of bars (a)-(f) has a Stage 3 value. The three-panel videos
  were not made.

## 3. Training log (validation = the K5 external readability (a) on the validation windows)

| | round 200 | round 400 | round 510 (last epoch line) |
|---|---|---|---|
| ext a (validation) | 0.442 | **0.572** (best) | — |
| active share energy hinge (builder side-car) | 15.6 % | 7.3 % | — |
| active share jerk hinge (builder) | 0 % | 0.33 % | — |
| other hinges (hand_v, jolt, acc, floor, lim) | 0 % | 0 % | — |
| mu energy / jerk | 11.4 / 165.3 | 13.2 / 165.4 | 13.96 / 165.4 |
| D_fast / D_slow (16 val windows) | 0.459 / 0.155 | 0.509 / 0.326 | 0.505 / 0.343 |
| muD fast / slow | 12.1 / 18.2 | 19.2 / 32.5 | 22.6 / 39.0 |

The D safeguard (0.7) was never reached on either stream. Its multipliers only rose, as the rising rule allows. The jerk multiplier stopped
moving at ~165 after the first rounds; the starting jerk was ~90x its threshold (7.41 fact). The energy multiplier was still rising at round 510.

## 4. Movement measured on Instant Crush (best.pkl r400, full-song argmax rollout, 50 Hz CSV from the side-car)

Hand = the last point of `m3f_report.fk_points`, cells = 5 cm cubes. Comparison is on the same song and the same duration (339.5 s):
pass2 r600 (the song CSV from `k5p2/check/songs/`) and v47 arm 0 (`/secondary/hyst-data/body/hf/v47/instant-crush-arm0.csv`).

| whole song | Stage 3 r400 | pass2 r600 | v47 arm 0 |
|---|---|---|---|
| hand extent p5-p95, x / y / z (cm) | 36 / 27 / 17 | 59 / 58 / 21 | 84 / 83 / 40 |
| hand position 3-D sd (cm) | 14.1 | 29.0 | 40.9 |
| occupied 5 cm cells, whole song | 203 | 441 | 1,841 |
| occupied cells per 60 s (mean of 5 windows) | 78 | 277 | 474 |
| joint sd (deg) base / shoulder / elbow / wrist bend / roll | 12.4 / 8.8 / 13.8 / 12.1 / 76.0 | 99.0 / 3.0 / 14.4 / 10.4 / 70.8 | 525 / 16.7 / 19.5 / 26.9 / 437 |
| hand speed p50 / p99 (m/s) | 0.19 / 0.48 | 0.37 / 0.61 | 0.28 / 1.00 |
| top-3 PC variance share of centred 4 s hand paths | 0.53 | 0.78 | 0.70 |

On the clip window (60-120 s), the builder's numbers were sent with the clip: shoulder sd 5.42 deg (pass2 1.94) and 67 cells (pass2 279).
The overseer's recompute matched them.

Readings (facts, not causes):
- Stage 3 raised shoulder sd over pass2: 8.8 vs 3.0 deg whole-song. That passes the 8 deg level of bar (e) on this one song.
- The hand's workspace shrank to about half of pass2's in x and y, and to about a quarter of v47's.
- Cells per 60 s fell to 0.28x pass2's. Bar (d) needs >= 1.5x pass2's median over held-out songs. That bar was not measured, but this song
  is far below it.
- pass2's spread came mostly from base rotation (sd 99 deg). Stage 3 barely rotates the base (sd 12 deg).
- The median hand speed halved against pass2.
- The PC-share column is a crude repetition measure: it is lower for Stage 3 than for pass2 and v47, yet the user still saw one repeated
  move. **It does not track the user's eye; do not use it as a bar.**
- v47 (authored, approved earlier as the one-arm reference) moves in a far larger space: base and roll rotate continuously, so their sd is
  not an angle spread.

## 5. Causes — none checked

Candidate explanations the overseer can name but has **not** tested:
1. The energy hinge (threshold ~ pass2's own budget, 0.375 vs 0.363 J/block; multiplier ~14 and rising) and the jerk hinge (multiplier ~165)
   price large or fast motion. Readability can be met inside a small envelope.
2. InfoNCE and the observers can separate songs by small differences in timing/micro-shape, which the eye does not read as different moves.
   This is the same failure as pass2, at a smaller scale.
3. Every learned objective so far (K5 try 1, pass2, Stage 3) has a machine readout that the eye does not share. The design-by-eye pivot
   (`docs/NEXT_DECODER_THEN_BRAIN.md` §2, 2026-11-01; authoring tool on B3's lanes) has not been followed through.

## 6. Questions

**Q1. Status of Stage 3.**
- (a) Close Stage 3 as rejected by eye at round 400. Keep the checkpoints. No bar evaluation.
- (b) As (a), plus a report-only bar evaluation of best.pkl r400 on the 357 held-out songs (`s3_eval.py`, cores 6-11; time not measured),
  so that bars (b)-(e) have numbers next to pass2's.
- (c) Resume to round 977 (≈ 466 rounds x 73 s ≈ 9.5 h + 3 validations) and judge at the end.

Recommendation: **(a)**. The user's stop order and the 7.39.4 order (the user's eye after the bars) make (c) moot. (b) only records how far
the bars miss, and section 4 already shows (d) missing on the danced song.

**Q2. Next direction** (the user wants a single arm that reads as dancing to the music; 7.34-7.41 have not delivered it):
- (a) Report-only diagnosis on the r400 policy first, no training: (i) does movement amplitude or workspace follow the music at all
  (per-60 s cells and hand extent vs song RMS/tempo across the held-out songs); (ii) energy per block vs the 0.375 threshold, i.e. how
  much of the run sat at the energy limit. This tests cause 1.
- (b) A Stage 3 round 2 that raises the energy threshold (7.41.1 allowed this only if bar (e) failed; it would need a new ruling) and/or
  adds a workspace term (a reward or hinge on per-window occupied cells or hand extent). Another long run: ~20 h.
- (c) Return to the authored path: state-to-body mapping designed by eye on B3/B7 lanes (NEXT_DECODER §2 pivot), with v47 as the movement
  vocabulary and the brain only choosing and modulating. Short clips for the user's eye at every step; no long training.
- (d) Stop the dance work and keep v47 one arm as the installation's motion.

Recommendation: **(a) then (c)**. (a) is cheap (hours, no training) and tells whether the energy budget made the arm small. Three learned
objectives have now failed the eye with one shared symptom; the authored path is the one the user has approved before (v47).

**Q3. Record the verdict.** Record the user's verdict (section 1) and the section 4 numbers as a dated note (7.42) before any new result
is scored. Recommendation: yes.

## 7. State left behind

- Nothing is running. Units `hyst-wo26b-run-r3` and `hyst-wo27-watcher-s3` are stopped.
- Data stays in `/secondary/hyst-data/body/s3/` (`run/`, `run_report/`, `eval_pass2/`).
- Branches: body e4e5c68, keys-decide (this brief).
- No builder is assigned. The overseer's scripts for section 4 (`clip_check.py`, `tight.py`) were in the job tmp folder and are not durable.
  They are short: per-CSV FK via `m3f_report.fk_points`, `floor(h/0.05)` unique cells, percentiles.
