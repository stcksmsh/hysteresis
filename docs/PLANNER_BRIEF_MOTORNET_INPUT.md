# Planner brief: motor-network toy test (BRAIN_SPEC 7.44), clips held before Kosta's session (2026-11-13)

From the overseer, for the planning agent. Paste-ready. One arm only.

## What ran

Work order 29A (`docs/MOTORNET_RULES.md` on branch `body-mnet`, rules pushed before any clip):
- **Network:** 200 rate units, tau 75 ms, `r = tanh(g x)`. Recurrent W is Gaussian/sqrt(N), rescaled to spectral radius 1.05.
- **Inputs:** cos/sin of a fixed 100 BPM phase, arousal 0 (silent clips). Input weights Win are iid N(0, 1), **not scaled by 1/sqrt(N)**.
- **Control units:** 4, each owning 80 neurons (subsets overlap), `g_i = prod_k c_k^m_ki`, c in [0.5, 2] log-uniform, no global gain.
- **Readout:** 5 random linear outputs.
- **Calibration:** the gain-1 mean maps to round 1's neutral pose, and +-2 sd maps to +-100 % of round 1's neutral amplitudes. This
  deviates from the +-60 % default, for feasibility.
- **Body below the network:** a spinal spring-damper (3 Hz, zeta 0.7), then round 1's command limiter, servo (kp 1.0, zeta 1.5) and v2f
  MuJoCo body.
- **Gates:** round 1's, plus a minimum motion of 0.05 m hand extent (deviates from the 0.10 m default, for feasibility).

Results:
- **Sampling:** seed 29011. The first 10 draws all passed (0 discarded). The two extremes failed the motion gate: S11 (all c = 0.5)
  and S12 (all c = 2). By overseer default 7.44.5d they are not shown and not replaced.
- **Rendered:** 10 silent lamp clips (S01-S10) and 2 ball clips (S01, S02). Part 4 is referenced. Part 3 is held because no audio
  exists.
- **Session:** **NOT started.** The overseer held it because of the numbers below.

## Results

Recomputed by the overseer from the clip CSVs and activity files (`scripts/body/overseer_mnet_check.py`, keys-decide):

| | S01-S10 (range over the 10) |
|---|---|
| Joint peak frequency, every joint | 1.66 Hz in all 10 (= the 100 BPM input) |
| Activity participation ratio | 2.02-2.21 |
| Realised p5-p95 range, deg (base, shoulder, elbow, wrist bend, roll) | 5.3-6.4, 1.3-3.9, 9.7-13.9, 10.6-18.1, 42.7-43.1 |
| Hand p5-p95 extent, largest axis | 0.060-0.092 m |
| Mean hand speed | 0.30-0.42 m/s |

From the builder's diagnosis (night log `body-mnet` d3961db, "DIAGNOSIS FOR OVERSEER"; not recomputed by the overseer):
- **Drive sizes at gain 1:** input drive std 0.864, recurrent drive std 0.553. Recurrent drive in S01-S10 is 0.43-0.67 (S11 0.28,
  S12 0.78).
- **Zero input at gain 1:** recurrent drive 0.113. Activity does not decay and peaks at 0.5 Hz, with PR 1.99.
- **PR of the extremes:** S11 1.97, S12 2.41. Every joint peaks at 1.664 Hz in S01-S12.
- **Amplitude chain, p5-p95 in degrees** (target -> spring-damper -> after the command limiter alone -> realised):

  | Joint | Target | Spring-damper | Command limiter | Realised |
  |---|---|---|---|---|
  | Base yaw | 47.5 | 41.7 | 13.4 | 5.4 |
  | Shoulder | 18.6 | 16.4 | n/a | 3.2 |
  | Elbow | 21.4 | 21.1 | n/a | 13.9 |
  | Wrist bend | 21.6 | 21.2 | n/a | 15.4 |
  | Wrist roll | 59.3 | 58.4 | n/a | 43.1 |

  The builder gave the command-limiter value for base yaw only. A 20 deg base swing at 1.66 Hz needs about 2,200 deg/s^2; the limit
  is 600.
- **Correction:** the overseer first said no limit was reached. That check was on realised angles, which lag the command. The command
  limiter does cut the amplitude.

## Reading (facts, no verdict)

- **The movement follows the beat input.** The input drive is larger than the recurrent drive. Every setting moves at the input
  frequency with about 2 activity dimensions, and the gains change only the size of the activity (recurrent drive 0.43-0.67).
- **The 1.66 Hz movement is too fast for the base and shoulder.** At this rate the command limiter and servo lag cut base yaw from
  47.5 deg to 5.4 deg and shoulder from 18.6 deg to 3.2 deg.
- **What a viewer would see:** about 10 versions of the same small fast wobble, mostly wrist roll (43 deg), with the hand moving
  6-9 cm.
- **What the test can answer as built:** the 7.44.3 question is whether changing ONLY the gains gives movements of different feeling.
  As built, the clips mainly show the input drive, not the gain settings.

## Questions

**Q1. Input drive.** Options:
- (a) Show the 10 clips as they are.
- (b) Fix the input weight scale by a rule written down before anything is looked at, then redraw and re-render with the same seeds.
  The rule: input drive std = 0.25 x recurrent drive std at gain 1, silent. The music clips use the same scale.
- (c) Silent clips run with no input. The network is autonomous, as in Stroud et al., and runs at gain 1 from a seeded small random
  start; it does not decay and peaks at 0.5 Hz. Music clips keep the input, scaled as in (b).

*Recommendation: (b).* It is the smallest change, it keeps the beat link the music part needs, and it lets the recurrent dynamics, and
so the gains, shape the movement. The fraction 0.25 is fixed in advance, not chosen by watching.

**Q2. Movement too fast for the base and shoulder.** Options:
- (a) Make no separate change. Re-measure after Q1, and report the limiter's share of the command per joint.
- (b) Also lower the spinal spring-damper to 1.5 Hz, fixed for the whole study, so the beat-rate wobble is low-passed before the
  limiter.
- (c) Make the time constant 100 ms (the top of 7.44's range).

*Recommendation: (a).* Then, if after Q1 base or shoulder still lose more than half their target range to the limiter, use (b)
without asking again. This is a pre-registered rule, not a choice made by eye.

**Q3. Gate deviations.** The minimum motion is 0.05 m instead of 0.10 m, and the calibration is +-100 % instead of +-60 %. Options:
- (a) Keep both.
- (b) After the Q1/Q2 changes, return to the defaults (0.10 m, +-60 %) if the gain-1 run reaches 0.10 m at +-60 %.

*Recommendation: (b).*

**Q4. Extremes.** S11 and S12 failed minimum motion. Options:
- (a) Keep 7.44.5d: after the changes, they are re-gated, and shown only if they pass.

*Recommendation: (a).*

**For Kosta (not the planner):** Part 3 still needs the five audio files in `/secondary/hyst-data/audio/checkset/`, and a 12 s excerpt
start time for each song.

## State

- **Branches:** body-mnet (29A, on hold) and body-mnettool (29B, tool + measurement + report scripts, tests verified). Not merged yet.
- **Nothing is running.** No clip has been shown to Kosta.
