# Planner brief: work order 15 results (raised plane, two seeds) and the elbow-stop slump — pass2 held (2026-11-07)

Context: `docs/BRAIN_SPEC.md` §7.28-7.30 (7.30.6-7.30.9 are new since the WO14 brief). One arm. Numbers recomputed by the overseer from
the saved per-episode values and rollouts (`/secondary/hyst-data/body/m3f/rerun3/seed{0,1}/`; paired intervals 10,000 resamples over the
16 held-out episodes), unless marked "builder". Verdicts argmax; sampled reported.

## 1. What ran

- **Plane height (7.30.6-7).** A held-contact test at MuJoCo's default contact (time constant 0.02 s) gave 44 mm sinking (fully folded arm
  pressing the ball), above the 5 mm cap. The user chose a stiffer contact: time constant 0.006 s, sinking 2.9 mm, so d = 3 mm and the
  plane sits at 0.053 m. Stability check passed (no NaN, no growth, oscillation <= 0.031 mm, settled hand speed <= 3.5 mm/s in 29 held
  poses, six epochs finite). Cost check passed (epoch 61.8 s vs 62 s; pass2 projection <= 20.6 h). As built, the time constant applies to
  every collision geom (self-contacts too); the user accepted that (7.30.8).
- **Floor hinge** = sinking of capsule/ball surfaces below the raised plane / 0.05 m, weight 1. Hand-acceleration hinge weight 1. End stops,
  jerk 0.03, switch 0.01 as in WO14A. Pass2 options: `--body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane
  --w-floor 1.0`.
- **Toy try 1 on seeds 0 and 1** + WO7 controls. Gate (7.30.3) per seed: bar + (e') pass and floor breaches in <= 2 of 16 episodes.
- **Pass2 auto-launch held by the user (7.30.8)** to see clips first: 60 s clips of both seeds on held-out episodes 0 and 1 (silent; the
  toy input is a synthetic stream, no song; a song-length toy rollout would need a new feature mapping and was skipped).
- K5-pass2 (branch body-k5p2) is built and waiting.

## 2. Results

### 2.1 Gate: both seeds PASS

| | WO14A (old plane) | seed 0 | seed 1 | limit |
|---|---|---|---|---|
| ext (a) | 1.010 | 0.739 [0.611, 0.871] | 0.948 [0.795, 1.095] | CI > 0 |
| int (a) | 1.018 | 0.839 [0.704, 0.968] | 1.024 [0.874, 1.165] | CI > 0 |
| (b) RMS non-roll speed | 48.6 | 30.2 | 40.9 | >= 10 |
| (c) MI, p | 0.108, 0.001 | 0.103, 0.001 | 0.087, 0.001 | |
| (e'1) hand-acc p99 m/s2 | 3.42 | 2.33 | 2.89 | 6.001 |
| (e'2) share hand > 1 m/s | 0.0091 | 0.0002 | 0.0012 | 0.0110 |
| floor breaches (episodes of 16) | 9 | **0** | **0** | <= 2 |
| time in contact | — | 0.85 % | 0 % | report |
| other breaches | — | joint accel 12 eps | joint speed 2 eps (2.4 deg/s), joint accel 12 eps | report |

### 2.2 Controls (paired, trained - control)

| | seed 0 argmax ext / int | seed 1 argmax ext / int | sampled seed 0 / seed 1 (ext) |
|---|---|---|---|
| vs untrained | +0.51 [0.34, 0.68] / +0.60 | +0.41 [0.26, 0.56] / +0.38 | +0.75 / +0.81 |
| **vs kappa 0** | **-0.04 [-0.09, 0.01] / -0.05 [-0.11, 0.01]** | **+0.04 [-0.02, 0.10] / +0.10 [0.04, 0.18]** | +0.43 / +0.16 |

On the toy, neither seed beats kappa = 0 on both decoders in argmax (7.19 A.1, the "inner rhythm" wording rule). WO14A: +0.21 / +0.14.

### 2.3 Parking and programs (argmax, all 16 episodes)

| | seed 0 | seed 1 |
|---|---|---|
| exactly on a stop: shoulder / elbow / wrist | 0.8 / **46.3** / 3.4 % | **13.4** / 1.4 / 1.1 % |
| within 2 deg of a limit | 2.1 / 48.5 / 60.0 % | 35.8 / 1.5 / 5.3 % |
| end-stop events per episode (sh / el / wr) | 0.62 / 3.44 / 1.69 | 6.62 / 0.25 / 0.38 |
| programs used, top program share | 4, 79.5 % | 5, 68.2 % |

### 2.4 User verdict on the clips (7.30.9, verbatim)

"Video 1: the left one is mostly stuck in a single 'bowed down' position with the head close to the base and the arm slumped over for the
head to be there, its also more repetitive. The right one actually seems to be doing something, it looks alive and smooth, it has variety
and is overall decent. Video 2: The left is again stuck for a long period of time in the same pose (though the right also gets stuck in
that pose ~42s in and stays there until the end, for comparison left gets stuck at ~18 untill ~28, then ~29 untill ~45), as for fluidity
etc, I cant really tell, the left is only viable for first 15 and last 15 seconds (mostly) and the second has some strange behaviour at the
beginning, not as clear cut as vid 1."

Overseer, from the rollouts: the "bowed down" pose is the **elbow held on its -110 deg stop**, in both seeds. Stretches >= 2 s: seed 0
ep 0 9.3-24.6, 29.0-32.1, 40.7-45.1 s; ep 1 12.3-25.3, 31.2-44.1 s; seed 1 ep 1 44.6-56.6 s (seed 1 also holds the shoulder stop
17-20 and 31-33 s in ep 0, 14-19 s in ep 1).

### 2.5 Cost scale (overseer, from the code; nothing tested)

The limit-proximity cost is relu(|q| - 100 deg) / 10 deg, averaged over the three bends, normalised by the untrained policy's value
(0.030 / 0.035), inside LAMBDA = 0.03. One joint held on its stop for a whole block adds about 0.33 raw, so about 11 normalised and
**about 0.33 to the loss**; the decoding losses are about 1.3-1.4 per block. At the last training epoch the limit term adds 0.02-0.03 to the
loss (raw 0.022 / 0.033). So parking is not free, but it is about a quarter of a decoding loss per fully parked block. Two readings, both
**untested**: (i) the user's (7.30.8): parking is a cheap rest under the jerk/speed/floor costs (zero speed, no jerk); (ii) the slumped pose
is an easily readable "code" for the observer: a fixed, distinct pose is cheap to decode, so the decoding loss itself may reward it.

## 3. Questions

**Q1. What to do about the elbow-stop slump before pass2.** Options:
- (a) **Time-on-stop cost:** a hinge on time spent within ~2 deg of a stop (any ranged joint), normalised like the others, weight 1 inside
  LAMBDA. Directly targets the habit.
- (b) **Stronger limit-proximity cost:** the existing cost x 3 (round-2-style scaling). Cheapest change, but it also pushes on every near-limit
  pass, not only on holding.
- (c) **Narrower commanded range:** clip targets 10 deg inside the stops (end stops stay at +-110), so holding at the stop is impossible
  and resting has to happen inside the range. Changes the body's usable range.
- (d) **Dwell cost on any pose:** penalise holding any single pose (hand still) for longer than N s, which targets the "stuck" look itself,
  not only at the stops; risk: punishes legitimate stillness (breath, rests).
- (e) Launch pass2 as is and judge the song videos.
- **Recommendation: (a)**, weight 1, with a two-seed toy rerun (about 3 h) under the same gate plus a new report-only line: share of time
  on a stop per joint and the longest single hold. If (a) leaves holds over 5 s, (c) next.

**Q2. A gate line for parking?** Options: (a) report-only (as now, 7.27.2); (b) gate: no joint on a stop for more than 10 % of the time,
and no hold longer than 5 s, on each seed. **Recommendation: (b)**: the user has now judged the slump unacceptable, so it should be
checked before a 20 h run, not after.

**Q3. Inner-rhythm wording.** The toy no longer beats kappa = 0 on both decoders. Options: (a) nothing in training; pass2's own kappa-0
control decides the wording, as for K5 try 1; (b) add something that protects the phase coupling. **Recommendation: (a)**: it is a
wording rule, not a bar, and the 357-song check decides it.

**Q4. Record:** both seeds pass the 7.30.3 gate on the raised-plane body (floor breaches 0); the user judged both seeds' elbow-stop slump
unacceptable (seed 0 for most of both clips; seed 1 in episode 1 from 44.6 s to 56.6 s); pass2 held; neither seed beats kappa = 0 on both decoders.
