# Planner brief: work order 13 results (new body + movement changes, M3e toy) and pass2 readiness (2026-11-07)

Context: `docs/BRAIN_SPEC.md` §7.23-7.26. One arm. All numbers below were recomputed by the overseer from the saved per-episode values
(`/secondary/hyst-data/body/m3f/`; paired intervals 10,000 resamples over the 16 held-out episodes), unless marked "builder".

## 1. What ran

- WO13A (merged): `hf_share.py`, the v47 references for (e) and (e') (§7.25).
- WO13B (branch body-m3f, merged into body): new body v2f (table plane at z = 0 with frictionless contact, self-collision, rig joint
  ranges, limit-proximity cost, hand-speed and hand-jolt hinge penalties; jerk / hand-speed / jolt normalised by the untrained policy on the
  OLD body, §7.25 point 4) and movement changes 1-4 (§7.24), each behind its own switch. Old M3e/K5 paths bit-identical (tests: 20 OK,
  incl. M3e try 1 epoch-0 reproduction). Grid 5.5 h, main stage 4.6 h (other jobs shared the cores).
- Grid on the tune episodes (jerk {0.01, 0.03, 0.1} x switch {0.01, 0.05}): eligible only j0.03/s0.01 (ext (a) 1.019) and j0.03/s0.05
  (0.994); three points failed (c) (p 0.022 / 0.016 / 0.098), one failed (e'2) (0.0415). Selected j0.03/s0.01 by the §7.25 rule (stated
  before the held-out run). Nobody read (e') values before §7.25 (overseer; builder states the same in its log).

## 2. Results (argmax; sampled reported only)

### 2.1 Try 1, held-out: PASSES the toy bar and (e')

| component | value | pass |
|---|---|---|
| ext (a) | 0.946 [0.847, 1.053] | yes |
| int (a) | 1.004 [0.895, 1.127] | yes |
| (b) | 53.9 | yes |
| (c) | MI 0.151, p 0.001 | yes |
| (e'1) hand-acc p99 | 3.511 m/s2 (limit 6.001) | yes |
| (e'2) share hand > 1 m/s | 0.01071 (limit 0.01101) | yes, 3 % margin |
| (e) reported | 0.00013 | |

Sampled: ext 0.721, int 0.803; (e'2) 0.0183 (would fail; reported only). Table contact 1.7 % of the time (1.03 s per episode, almost all
in 1 of 16 episodes). For comparison (different body and objective): K5 try 1 hand-acc p99 9.2-11.0 m/s2, v47 4.1-6.0.

### 2.2 WO7 controls (paired trained - control, (a))

| control | ext | int |
|---|---|---|
| untrained | +0.701 [0.509, 0.899] | +0.748 [0.556, 0.951] |
| kappa = 0 | +0.142 [0.076, 0.217] | +0.091 [0.039, 0.149] |

### 2.3 Ablations of the movement changes (each off alone; paired try 1 - ablation; report only)

| change off | ext (a) | (e'1) | (e'2) | table contact of the ablated run |
|---|---|---|---|---|
| 1 jerk cost | -0.113 [-0.202, -0.028] | -0.208 [-0.515, 0.098] | -0.013 [-0.022, -0.005] | 24.8 % |
| 2 observer low-pass | +0.022 [-0.111, 0.134] | +0.183 [-0.079, 0.414] | -0.002 [-0.006, 0.003] | 92.6 % |
| 3 phase low-pass + order-parameter weighting | -0.001 [-0.129, 0.139] | +0.884 [0.584, 1.152] | +0.008 [0.003, 0.012] | 0.1 % |
| 4 crossfade + switch cost | -0.057 [-0.172, 0.077] | +0.641 [0.401, 0.868] | +0.010 [0.007, 0.013] | 0.0 % |

Positive (e') entries mean try 1 has MORE hand acceleration / fast-hand time than the ablated run. All four ablated runs also pass the toy
bar. Reading (one seed, 16 episodes; WO11 spread up to 0.35 applies): the jerk cost lowers fast-hand time and keeps the arm off the table;
removing the observer low-pass leaves the arm lying on the table 93 % of the time; changes 3 and 4, as built, RAISE hand acceleration
(removing either lowers (e'1) by 0.6-0.9 m/s2 and (e'2) to 0.001-0.003). Untested why.

### 2.4 check-csv-style breaches on the held-out argmax rollouts (report only on the toy; binding for pass2)

floor margin: 1.9 % of rows, 5 of 16 episodes, worst 0.055 m short; hand speed: 0.35 % of rows, 13 episodes, worst 0.13 m/s over; hand jolt
~0 (1 episode); joint range: 19.1 % of rows, all 16 episodes, worst 0.13 deg beyond +-110 deg: the shoulder is parked at -110.1 deg 18.8 % of
the time (the soft limit leaks about 0.1 deg; the 10-deg proximity cost does not stop the parking) (builder's reading, rows recomputed by
the builder). A strict check-csv run would refuse these rollouts. Joint acceleration over the limit in 8 episodes.

## 3. Questions (pass2 cannot start before 1-3 are answered)

1. **Terms for the §7.26 round-2 rule.** The loss has no floor-margin term and no hand-acceleration term (only physical contact, hand-speed
   and hand-jolt hinges), so a floor-margin or (e'1) failure would have no weight to scale. Options: (a) add a floor-margin hinge (check-csv's
   margin) and a hand-acceleration hinge (above v47-level, e.g. 4.8 m/s2) now, rerun the toy try 1 with them (about 1 h), then pass2;
   (b) keep pass2 as built and accept that §7.26 cannot repair those two failures. Recommendation: (a), because the toy already breaks the
   floor margin in 5 of 16 episodes and pass2 must pass check-csv in full.
2. **Joint-range parking.** The shoulder sits 0.1 deg past the rig limit 19 % of the time, which check-csv refuses. Options: (a) a hard clip
   of the commanded target to the rig range (the arm_sim limiter already clips two bends; extend to all ranged joints) so the leak cannot
   occur; (b) a stronger limit cost. Recommendation: (a): it is a body-model fix (like the floor), not a behaviour change, and it cannot be
   gamed.
3. **Changes 3 and 4 raise hand acceleration on the toy.** They were set before results as human motor-control design (§7.24). Options:
   (a) keep both as set (the bar passes with them); (b) drop one or both. Recommendation: (a) for pass2 (pre-registered design; one seed);
   report the finding; revisit only if pass2 fails (e').
4. **(e'2) margin 3 %.** Pass2 is scored per song. No change proposed; noted as the main risk with check-csv.
5. **Pass2 timing.** Before launch, one K5 round on v2f is timed to replace the 21.1 h upper bound (24 h box). If above 22 h: ask before
   launching.
