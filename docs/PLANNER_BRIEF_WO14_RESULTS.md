# Planner brief: work order 14 results (floor/acceleration hinges, hard end stop, floor weight 3) — pass2 not launched (2026-11-07)

Context: `docs/BRAIN_SPEC.md` §7.26-7.29. One arm. Numbers recomputed by the overseer from the saved per-episode values and rollouts
(`/secondary/hyst-data/body/m3f/rerun1/` = WO14A, `rerun2/` = WO14C; paired intervals 10,000 resamples over the 16 held-out episodes),
unless marked "builder". All verdicts argmax; sampled reported.

## 1. What ran

- **WO14A** (branch body-m3f 207ac3c + 838b5f0, bf4037d): §7.27 floor-margin and hand-acceleration (> 4.8 m/s2) hinges, weight 1 each,
  normalised like the hand-speed hinge (untrained policy on the OLD body; floors 0.005 m and 0.05 m/s2), and the hard clip. Engineering
  rerun of toy try 1 (jerk 0.03, switch 0.01, seed 0) + WO7 controls. 27 tests OK (old paths bit-identical; WO13B and M3e first-epoch
  reproductions).
- **Deviation in the clip, accepted by the user (§7.28):** clipping targets was not enough (contact and the soft limit carried joints past
  held targets: shoulder -110.1, elbow 110.71, wrist 111.13 deg), so `--hard-clip` also clips joint positions to the range after every
  physics substep and zeroes that joint's speed (a hard end stop, like servo firmware angle limits). The limit-proximity cost stays.
- **User ruling §7.29** after WO14A: end stops accepted as built; floor-margin hinge weight 3; one more toy rerun; gate = bar + (e') pass
  AND floor-margin breaches in <= 2 of 16 episodes, else stop and report.
- **WO14C** (body-m3f ad48642): `--w-floor` (default 1, bit-identical), same rerun with weight 3. 1 h 20 min.
- K5-pass2 trainer (WO14B, branch body-k5p2 5542992) is built, tested and waiting. **Not launched** (gate failed).

## 2. Results

### 2.1 Bar, (e') and controls (held-out, argmax)

| | WO13B (no hinges, no stop) | WO14A (weight 1) | WO14C (floor weight 3) | limit |
|---|---|---|---|---|
| ext (a) | 0.946 | 1.010 [0.912, 1.107] | 0.888 [0.775, 1.019] | CI > 0 |
| int (a) | 1.004 | 1.018 [0.902, 1.128] | 0.943 [0.822, 1.085] | CI > 0 |
| (b) | 53.9 | 48.6 | 56.9 | pass all |
| (c) MI, p | 0.151, 0.001 | 0.108, 0.001 | 0.099, 0.001 | pass all |
| (e'1) hand-acc p99 m/s2 | 3.51 | 3.42 | 3.77 | 6.001 |
| **(e'2) share hand > 1 m/s** | 0.0107 | 0.0091 | **0.0188 (fail)** | 0.0110 |
| trained - untrained, ext / int | +0.70 / +0.75 | +0.76 / +0.76 | +0.64 [0.46, 0.81] / +0.69 | |
| trained - kappa0, ext / int | +0.14 / +0.09 | +0.21 [0.12, 0.29] / +0.14 [0.01, 0.26] | +0.15 [0.05, 0.26] / +0.10 [-0.01, 0.22] | |

WO14C per-episode (e'2): 0.001-0.045, 9 of 16 above 0.011. The kappa0 control on WO14C has (e'2) 0.0181, so the higher hand speed comes
with the weight-3 training itself. Sampled WO14C: ext 0.782, int 0.841, (e'2) 0.0337.

### 2.2 Breaches (check-csv style, argmax; row share, episodes of 16, worst)

| | WO13B | WO14A | WO14C |
|---|---|---|---|
| **floor margin** | 1.9 %, 5, 0.055 m | 1.2 %, 9, 0.051 m | 0.73 %, **11**, 0.052 m |
| joint range | 19.1 %, 16, 0.13 deg | 0 | 0 |
| hand speed > 1.2 m/s | 0.35 %, 13 | 0.08 %, 3 | 0.13 %, 7 |
| joint speed | 0 | 0.65 %, 13, 4.6 deg/s (wrist only) | 0.18 %, 7, 1.1 deg/s |
| shoulder within 2 deg of a limit | — | 3.9 % | **38.5 %** |

### 2.3 Why the floor weight did nothing useful (overseer, from the training history)

The floor hinge's normaliser is the untrained policy on the OLD body: 0.117 m (the old body sank through the table). On the new body the
untrained value is 0.022 m (builder). At the last training epoch the raw floor term is 0.00006 m (WO14A) and 0.00002 m (WO14C), so the
normalised floor term is about 5e-4 (WO14A, weight 1) and 2e-4 before weighting (WO14C, so 5e-4 after weight 3). The limit-proximity term at the same epoch is 0.35 (WO14A) and 2.2 (WO14C);
hand acceleration 0.07. **The floor term is roughly 1,000 times smaller than the limit-proximity term**, so a weight of 3 cannot act on it,
while held-out episodes still breach the margin. With one seed per setting, the WO14A -> WO14C differences ((e'2) doubling, shoulder at its
limit 10x as often, limit-proximity term 6x) cannot be separated from run-to-run variation; the floor weight is not shown to cause them.

### 2.4 End stops (trained, argmax; correction of an earlier overseer statement)

About 2.4 events per one-minute episode in WO14A (elbow 1.44, shoulder 1.00; builder), 5.7 in WO14C (overseer count: a control step with a
ranged joint on +-110 deg). Hand acceleration p99 within +-0.05 s of events vs all samples, WO14A:

| method | 50 Hz | 100 Hz | jerk p99, 100 Hz |
|---|---|---|---|
| per episode (builder) | 3.45 vs 3.41 | 5.35 vs 3.44 | 230 vs 38 |
| pooled over episodes | 5.42 vs 3.46 | 6.90 vs 3.51 | 286 vs 38 |

The overseer first told the user the stops add nothing at 50 Hz; that holds only per episode. Pooled, they do (5.42 vs 3.46, still under
the 6.0 (e'1) limit). The user accepted the stops before the pooled 50 Hz figure was known; pass2 reports both methods at both rates.

## 3. Questions

**Q1. Floor term scale.** Options:
- (a) Normalise the floor hinge by a fixed physical scale, the margin itself (0.05 m), so a full-margin breach costs about 1 like the other
  normalised terms; weight stays 3 (or back to 1).
- (b) Normalise by the untrained policy on the NEW body (0.022 m): x 5.3 stronger than now, probably still small.
- (c) Make the margin physical: raise the contact plane to z = 0.05 m. With the existing link (0.01 m) and ball (0.06 m) radii, contact
  then starts exactly at check-csv's margin, so breaches become impossible (like the accepted end stops). Cost: more time in contact;
  its effect on hand acceleration is untested.
- **Recommendation: (a)**, with the weight back to 1. It keeps the penalty soft and puts the term on the same scale as the others.
  (c) is the fallback if (a) still leaves more than 2 of 16 episodes.

**Q2. Run-to-run variation.** (e'2) has a 3 % (WO13B) to 17 % (WO14A) margin, and one setting doubled it. Options: (a) next toy rerun with
two seeds (2 x 1 h 20 min, sequential), gate on both; (b) one seed as before. **Recommendation: (a)**, so a pass is not one lucky seed
before a 30 h run.

**Q3. Gate for the next rerun.** Keep §7.29.3: bar + (e') pass and floor-margin breaches in <= 2 of 16 episodes (on every seed, if Q2 (a)).
Then merge and launch pass2 without asking. **Recommendation: keep it.**

**Q4. Shoulder at its limit 38.5 % of the time (WO14C).** §7.27.2 says parking is a look the user judges by eye, not a bar. Confirm that
it stays report-only. **Recommendation: report-only**, and show it in the pass2 videos.

**Q5. Record:** the WO14A rerun passes the bar and (e') with both hinges and the end stop; WO14C fails (e'2) and the floor gate; the
floor term as normalised is too small to act; §7.26 round-2 scaling is relative to the weights in force when pass2 launches.
