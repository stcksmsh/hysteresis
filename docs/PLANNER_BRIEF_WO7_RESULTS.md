# Planner brief: work order 7 results (2026-11-05, midday)

Answers `docs/BRAIN_SPEC.md` §7.18. Numbers marked (R) were recomputed or re-read by the overseer from the saved files. All three orders
are done and merged into `body`. The installation is one arm (user rule, §7.17 point 4).

## 1. M3d report-only controls (7.18 point 1) (R)

Branch `body-m3d` bc1d1c7. Same 16 held-out toy episodes; no retraining; not a try. Every row, trained included, uses one observer procedure:
a fresh observer (init key 0), 600 steps, seed 999, trained on 4 hard rollouts of the 16 training episodes by the fixed policy in the scored
mode. The trained row is therefore not comparable to try 1's (a) 0.480, whose observer was warm-started and fitted on soft training rollouts;
policy and held-out rollouts are identical to try 1 ((b) 33.0, MI 0.536, kappa means match). Tests: 13 OK (3 new). Wall 1,560 s, peak 12.8 GB.

| Policy | Mode | (a) shifted − matched [95 %] | (b) °/s | (c) MI (null mean), p |
|---|---|---|---|---|
| trained | argmax | 0.688 [0.600, 0.791] | 33.0 | 0.536 (0.058), 0.001 |
| trained | sampled | 0.485 [0.420, 0.558] | 39.3 | 0.055 (0.018), 0.001 |
| (i) untrained | argmax | 0.416 [0.335, 0.509] | 45.0 | 0.554 (0.124), 0.001 |
| (i) untrained | sampled | 0.227 [0.173, 0.280] | 44.8 | 0.017 (0.014), 0.163 |
| (ii) trained, kappa = 0 | argmax | 0.669 [0.589, 0.757] | 39.5 | 0.536 (0.058), 0.001 |
| (ii) trained, kappa = 0 | sampled | 0.304 [0.256, 0.352] | 43.6 | 0.055 (0.018), 0.001 |
| (iii) untrained, kappa = trained means | argmax | 0.430 [0.342, 0.538] | 38.5 | 0.554 (0.124), 0.001 |
| (iii) untrained, kappa = trained means | sampled | 0.249 [0.196, 0.300] | 38.9 | 0.017 (0.014), 0.163 |

Paired (a)_trained − (a)_control over the 16 episodes, mean [95 % bootstrap] (R, recomputed from the per-episode values):

| Control | argmax | sampled |
|---|---|---|
| (i) untrained | 0.272 [0.192, 0.356] | 0.258 [0.158, 0.365] |
| (ii) kappa = 0 | 0.019 [−0.023, 0.064] | 0.181 [0.133, 0.234] |
| (iii) untrained + trained kappa | 0.258 [0.156, 0.363] | 0.236 [0.141, 0.341] |

Numbers only:
- The untrained motor cortex passes the toy bar in argmax mode ((a), (b) and (c)), as the planner's recorded flaw predicted.
- The trained one beats the untrained one by about 0.26 in both modes, intervals above 0.
- In argmax mode the phase coupling adds nothing measurable ((ii) interval spans 0); in sampled mode, switching it off lowers (a) by 0.18.
- Giving the untrained cortex the trained coupling adds little ((iii) vs (i): 0.430 vs 0.416 argmax, 0.249 vs 0.227 sampled).

## 2. MJX one iteration vs full MuJoCo, 60 s (7.18 point 2) (R)

Branch `body-parity` 31e33f2. 10 trajectories × 60 s (4 argmax + 4 sampled from try 1 on held-out toy episodes, 2 from v47), same start
pose and targets. Joint-angle difference, mjx1 vs MuJoCo (100 iterations), max over all: base yaw 7.2e-05°, shoulder 2.6e-03°, elbow 2.8e-02°,
wrist bend 3.8e-03°, wrist roll 3.6e-07°; over the first 10 s ≤ 6e-14°. MJX with 100 iterations vs MuJoCo: 2.3e-13°. 8 of 10 trajectories
agree to ≤ 1.1e-13°; the other two diverge only after the elbow reaches its ±110° limit. Descriptors: median relative difference 0, worst
0.10 in one block of a limit-touching trajectory. Tests 4 OK. No bar was set; no claim.

## 3. Camera framing (7.18 point 4): done

The one-arm camera now frames the arm's whole reach envelope (links + disc + 5 cm, 40 px margin at 1280×720); the hexagon reference output is
untouched (v47 `Off` byte-identical, R). Projected hand and disc every 0.1 s, example-sketch mapping: 0 % of samples outside the view on all
three songs, minimum margin 134–145 px (builder's check; the old camera gave 7.1 % outside on Presence). Re-rendered whole songs sent to the
user; verdict pending.

## Questions

1. **K5 bar, given the controls.** 7.18 point 2 already requires K5 to beat both the time-shifted and the untrained-policy control. The toy
   shows the untrained margin is real but that argmax-mode coupling adds nothing.
   - (a) Keep the K5 bar as fixed; evaluate both modes; the claim follows 7.18 point 2.
   - (b) Also require the trained policy to beat the kappa = 0 version before the movement may be called phase-locked to the inner state.
   - Recommendation: (a) for the pass, plus (b) as a wording rule only (no "locks to its inner rhythm" unless (ii) is beaten).
2. **K5 size and budget.** Proposed default for the builder, unless the planner sets it: state = B7 epoch-6 lanes on training-artist songs
   (no held-out artist ever in training or tuning); 60 s windows; check on held-out songs with per-song paired bootstrap; the three danced
   songs rendered for the user's eye next to the fallback videos; two tries, 8 h box each, on the laptop; the observer procedure of the WO7
   controls (fresh observer per scored policy). Accept, or set numbers (songs, window, box)?
3. **Which observer procedure is "the" (a).** Try 1 used a warm-started observer on soft training rollouts; the controls a fresh observer on
   hard rollouts of the fixed policy. Recommendation: the controls' procedure for every K5 number (same for trained and controls).
