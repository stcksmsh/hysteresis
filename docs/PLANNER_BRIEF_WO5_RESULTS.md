# Planner brief: work order 5 results (2026-11-05, ~00:15)

Answers `docs/BRAIN_SPEC.md` §7.16. Branch `body` at d4c24e3 (merges of `body-reeval` and `body-fallback`). Numbers marked (R) were recomputed
or re-read by the overseer from the saved files. M3d has no result yet (see 4).

## 1. Sampled re-evaluation of T-M3, M3b, M3c (7.16 point 1) (R)

Code checked: in sampled mode the program is drawn from the softmax; modulation stays the mean; no noise. Seed 999, 8 episodes × 90 s as the
originals. MI = program vs 16 brain states (arousal quartiles × L3 phase in 4 sectors, state at block start), 1,000 within-episode shuffles.
Tests rerun by the overseer: test_tm3 13, test_tm3b 10, test_tm3c 11 OK. The MI values themselves could not be recomputed (per-decision
programs are not saved); they are read from the result files.

| Policy | Mode | (a) mean [95 % interval] | (b) °/s | (c) p | programs | switches/min | entropy nats | MI nats (shuffle mean) p |
|---|---|---|---|---|---|---|---|---|
| T-M3 try 1 | argmax | 0.795 [0.764, 0.829] | 42.1 | 0.016 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| T-M3 try 1 | sampled | 0.710 [0.666, 0.742] | 57.0 | 0.529 | 8 | 90.8 | 1.58 | 0.0071 (0.0085) 0.67 |
| T-M3 try 2 | argmax | 0.644 [0.615, 0.675] | 46.7 | 0.693 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| T-M3 try 2 | sampled | 0.526 [0.485, 0.562] | 61.8 | 0.246 | 8 | 99.3 | 1.88 | 0.0137 (0.0082) 0.032 |
| M3b l0.01 c0.1 e0.01 | argmax | −0.0030 [−0.0037, −0.0023] | 55.7 | 0.008 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| M3b l0.01 c0.1 e0.01 | sampled | 0.0019 [−0.0006, 0.0051] | 48.6 | 0.728 | 8 | 99.8 | 2.00 | 0.0095 (0.0083) 0.29 |
| M3b l0.01 c0 e0.01 | argmax | −0.0019 [−0.0035, −0.0001] | 53.4 | 0.289 | 4 | 3.7 | 0.17 | 0.0167 (0.0034) 0.001 |
| M3b l0.01 c0 e0.01 | sampled | 0.0040 [0.0016, 0.0071] | 47.1 | 0.325 | 8 | 102.6 | 2.06 | 0.0080 (0.0081) 0.49 |
| M3b l0.01 c0 e0.05 | argmax | −0.0019 [−0.0035, −0.0002] | 42.2 | 0.621 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| M3b l0.01 c0 e0.05 | sampled | 0.0031 [0.0007, 0.0061] | 47.4 | 0.657 | 8 | 103.6 | 2.07 | 0.0060 (0.0080) 0.80 |
| M3b l0.1 c0 e0.01 | argmax | −0.0037 [−0.0068, −0.0012] | 51.0 | 0.290 | 3 | 5.1 | 0.61 | 0.1548 (0.0025) 0.001 |
| M3b l0.1 c0 e0.01 | sampled | 0.0032 [0.0004, 0.0059] | 47.7 | 0.696 | 8 | 102.5 | 2.06 | 0.0079 (0.0081) 0.50 |
| M3c try 1 | argmax | 0.0003 [−0.0013, 0.0018] | 28.3 | 0.596 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| M3c try 1 | sampled | 0.0007 [−0.0043, 0.0056] | 32.1 | 0.904 | 8 | 48.3 | 0.73 | 0.0083 (0.0087) 0.57 |
| M3c try 2 | argmax | −0.0003 [−0.0021, 0.0012] | 28.1 | 0.686 | 2 | 0.7 | 0.03 | 0 (0) 1.0 |
| M3c try 2 | sampled | 0.0008 [−0.0016, 0.0036] | 33.3 | 0.061 | 7 | 57.4 | 0.75 | 0.0037 (0.0052) 0.81 |

(a) means different things per family (T-M3: S_still − S_moving; M3b: S_shifted − S_moving; M3c: shuffled − matched decoding loss).
- Sampled, every policy uses 7–8 programs and switches 48–104 times a minute. No sampled policy shows program–state MI at p < 0.01.
- The two M3b argmax policies with MI p = 0.001 use 3–4 programs with few switches; their sampled versions show none.
- M3b sampled (a): 3 of 4 intervals lie above 0, all by about 0.003. (c) fails for all four.
- Caveat: T-M3's saved files hold no cerebellum weights, so both T-M3 modes use the calibration cerebellum (argmax try 1 (a) 0.795 against the
  original 0.799).
- No pass is claimed (7.16 point 1).

## 2. H4, uncertainty-based arbitration (7.16 point 3): fails T1b in both tries (R)

Read from `docs/h4_try{1,2}_results.jsonl` and the run logs. Nothing trained; H3's frozen toy cortices; H2's code and store; top-k pointer
replay (k 64, tau 0.05). Causal error bookkeeping fixed before the first recorded run (night log). Unit tests 10 (builder; not yet rerun by the
overseer).

| | A | B | C |
|---|---|---|---|
| T1a | pass | pass | pass |
| T1b ratio repeat/first (≤ 0.5), try 1, window 1 s | 0.876 | 0.737 | 0.566 |
| T1b ratio, try 2, window 2 s | 0.878 | 0.709 | 0.572 |
| H3 cortex only (w = 0), from the WO4 brief | 0.881 | 0.656 | 0.566 |
| H4 run's own "cortex only" (arbitration off) | 1.000 | 1.000 | 1.000 |
| Oracle (H2) | 0.327 | 0.440 | 0.348 |

Mean w inside the repeat L1–L3 (try 1): A 0.52 0.52 0.53; B 0.19 0.45 0.60; C 0.31 0.61 0.69; outside (from 17 s): A 0.43 0.42 0.36;
B 0.07 0.22 0.37; C 0.07 0.23 0.33. The weight does rise inside the repeat, but the ratio stays at about the cortex-alone level.

**Open discrepancy (overseer, not resolved):** the H4 run's "cortex only" control gives 1.000 on all designs, while H3's cortex-only control on
the same cortex files gave 0.881 | 0.656 | 0.566. The two runners switch the hippocampus off differently (H4: `arbitrate = False`; H3: a blend
weight forced to 0). Not checked yet which is right. Either way the H4 ratios are above 0.5 on all designs. Citation (Daw, Niv & Dayan 2005,
Nat. Neurosci. 8:1704): not verified.

## 3. Fallback order (7.16 point 4): done, merged

- Authoring tool reads B7 lanes; arm previews for Instant Crush, Five Years, Presence with `mappings/example-sketch.json` (a sketch; the user
  tunes it by eye).
- Whole-song videos, one arm, H.264 1080p 30 fps (R: durations 339.83 / 283.77 / 270.73 s; audio payload hashes equal the sources). 12 frames
  inspected by the overseer; whole songs not inspected; the user has not judged them yet.
- Self-surprisal lane "cerebellum: prediction error of its own arm", no claim (R: median NLL −0.94 / −1.23 / 1.67, p99 29.9 / 10.5 / 91.7;
  6 arms × 30 Hz × 3 horizons). Heavy tail = v47 targets the servos cannot follow.
- mindState v2 (bands / surprise / neuromod groups of 0.1 s lanes; v1 still read unchanged). The grouping is the builder's choice.
- v47 Off byte-identical on all three songs (R); hyst-compile 102 + hyst-output 18 tests, clippy and fmt clean (R).

## 4. M3d (7.16 point 2): no result yet

First commit df9e73a (toy generator, JAX body: generators with L3 coupling, MJX arm, 31 descriptors). The three grid runs (λ 0.03 / 0.3 / 3,
12 epochs) were killed by the memory limit at 23:49–23:51, each capped at 3 GB, after 2.5–6 min of CPU. No result produced. Results will follow
in a separate note.

## Questions

1. **H4 and memory.** H4 fails T1b on all designs in both tries.
   - (a) Close memory for this plan, as 7.16 point 3 says. The cortex-only discrepancy is recorded and explained by the overseer as bookkeeping.
   - (b) Before closing, the builder explains the discrepancy (one short check, no new try).
   - Recommendation: (b), then (a). It costs minutes, and a wrong control could hide a real effect on design C (0.566 / 0.572).
2. **M3d's memory kills.** The grid died at start with no result.
   - (a) A run killed for memory before producing a result does not count as a try; relaunch with a larger cap (e.g. 3 runs × 6 GB) and keep the
     4 h box as compute time actually spent.
   - (b) It counts as try 1.
   - Recommendation: (a).
3. **Sampled numbers.** T-M3 sampled passes (a) and (b), fails (c) and shows no MI; M3b sampled has (a) about +0.003 above 0 in 3 of 4.
   - (a) Nothing reopens; record both modes; the families stay closed (7.16 point 1).
   - (b) Treat M3b sampled (a) as a lead for M3d's design.
   - Recommendation: (a). The M3b effect is tiny and (c) fails.
4. **Next step for the fallback.** It drives one arm. The installation is six arms (v47 runs on a hexagon, and arms sharing each other's reach
   is the intended effect).
   - (a) Next order: the fallback mapping drives the six-arm hexagon (same lanes, per-arm offsets or roles), whole-song videos of the three
     songs, v47 Off kept byte-identical.
   - (b) Wait for the user's verdict on the one-arm videos first.
   - (c) Both: the user tunes the mapping by eye on one arm while the six-arm export is built.
   - Recommendation: (c). The mapping is the user's; the six-arm wiring is mechanical.
5. **Self-surprisal as an authoring lane.** Offer it in the authoring tool as a lane the user may map (no claim), or keep it as data only?
   Recommendation: offer it.
6. **mindState v2 grouping** (bands / surprise / neuromod) was chosen by the builder. Accept as is, or prescribe a grouping?
   Recommendation: accept; nothing reads it yet.
