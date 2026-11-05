# Planner brief: work order 6 results (2026-11-05, morning)

Answers `docs/BRAIN_SPEC.md` §7.17. Numbers marked (R) were re-read or recomputed by the overseer from the saved files.

**User correction recorded first (2026-11-05):** the installation is ONE arm. No hexagon, no six-arm wiring, no ensemble, permanently. §7.17
point 4 was rewritten accordingly (the planner's six-arm wording is superseded) and the ensemble was removed from `docs/BODY_BRAIN_PLAN.md` §10.
Please do not propose multi-arm items again.

## 1. M3d try 1 passes the toy bar in both choice modes (R)

Branch `body-m3d` 3b8ef08. Training by gradient (7.16 point 2): brain state → motor cortex → program mixture (Gumbel-softmax, tau 1.0 → 0.2) +
modulation + per-joint L3 coupling strength kappa (an output of the motor cortex, 0 … 2π rad/s, starting near 0.30) → generators → MJX arm (one
solver iteration) → 31 descriptors (JAX port; parity with Rust on 3 clips, max relative difference 2.6e-8) → cross-fitted observer.
Loss = observer decoding loss − λ·energy, targets z-scored within each episode (arousal and surprisal through arcsinh first).

Grid on 8 tune episodes (12 epochs, argmax), rule "largest (a) among cells passing (b)", fixed before the grid: λ 0.03 (a) 0.437 [0.326, 0.553],
(b) 48.8; **λ 0.3 (a) 0.612 [0.509, 0.733], (b) 42.8 (chosen)**; λ 3 (a) 0.401 [0.281, 0.555], (b) 18.3.

Try 1, λ 0.3, 40 epochs, 16 held-out episodes (new seeds):

| Mode | (a) shifted − matched loss [95 %] | matched loss | (b) RMS °/s non-roll | (c) MI nats (null mean), p | programs |
|---|---|---|---|---|---|
| argmax | 0.480 [0.422, 0.541] | 0.792 | 32.95 | 0.536 (0.057), 0.001 | 6 (one takes 59 %) |
| sampled | 0.498 [0.418, 0.583] | 0.705 | 39.28 | 0.055 (0.018), 0.001 | 8 (175–333 each) |

- (a) control: the same observer scored against targets circularly shifted by ≥ 4 s, 20 shifts per episode; the mean predictor scores 1.0.
- (c) control: 1,000 circular shifts (≥ 4 s) of each episode's state-bin sequence; p floor 0.001.
- Learned kappa, mean rad/s per joint: 1.41 / 0.42 / 0.28 / 0.45 / 2.02 (started at 0.30), so the coupling to the L3 phase is used.
- Wall time 1,614 s (inside the 4 h box). The three grid runs OOM-killed at start (3 GB caps) were not counted (7.17 point 2). Try 2 not run.
- Tests: test_m3d 10; the builder's full run had one failing test (a flawed near-tie check, fixed); the overseer reran the full file:
  10 of 10 OK (692 s).
- Caveats from the builder: one MJX solver iteration; the observer reads true, unquantised joint positions; the argmax choice is concentrated.

**Overseer's concern (not measured):** (a) asks only that movement carries the state better than a time-shifted control. Any fixed mapping
from state to movement would do that, including an untrained motor cortex (random weights already map state to programs, modulation and kappa)
and, more directly, the L3 phase coupling (kappa pulls the generators' phase toward the L3 phase, so the movement can contain the phase whatever
the program choice). The run has no untrained-policy or no-coupling control, so the bar cannot show how much of (a) and (c) training produced.
Question 1.

## 2. H4 diagnostic (7.17 point 1): no deviation; memory closed for this plan (R)

Branch `body-h4` 6eaa9e6, merged. Tests test_h3 + test_h4 rerun by the overseer: OK.
- Top-k: 4 sources (`core_b7.TOP_K`; 64 is the sparse-code k), confirmed by the retrieval weight shape (1, 4).
- The 1.000 control is the true cortex-only. **Correction to the WO4 brief:** H3's reported "cortex only" control (0.881 | 0.656 | 0.566) was
  a 50 % blend (a = 0 gives sigmoid(0) = 0.5), mislabelled. H3 with the weight truly 0 gives 1.000 on A, B, C.
- Inside the repeat (try 1 settings, 32 sequences, frames where both retrieval and oracle had a source), mean squared error per layer:
  design A L1 cortex 0.671, retrieval replay 0.627, oracle replay ~1e-13; L2 0.188 / 0.178 / ~0; L3 0.050 / 0.046 / ~0. Design B L1 cortex 0.107,
  replay 0.408. The replay is about as wrong as the cortex (or worse): retrieval finds the wrong sources; the arbitration itself works as
  specified. Per 7.17 point 1, memory is closed for this plan, with this recorded.

## 3. One-arm tuning loop (7.17 points 4–5): done, merged

`scripts/author/retune.sh SONG MAPPING.json [START_S DURATION_S]` and a "Render 20 s at playhead" button (serve.py POST /retune). 20 s window
at 720p: 20.7 s; whole song at 1080p: about 7 min. Self-surprisal is the 11th authoring input, "cerebellum: prediction error of its own arm",
the mean over the six replayed v47 arms (no replayed arm is the fallback arm). Tests: author 11, attach 5, build 1, serve 2 (R). Whole-song
720p videos sent to the user; the user's verdict is pending. Observed: in Presence at 110 s the hand leaves the top edge of the camera view.

## Questions

1. **Controls for M3d's pass.** Options:
   - (a) Accept try 1 as the pass of the toy bar as written.
   - (b) Before accepting, run report-only controls on the same held-out episodes with the same observer procedure: the untrained motor cortex
     (initial weights), and the trained one with kappa forced to 0. No retraining, no tuning, not a try. The pass stands as a toy pass either
     way; the controls decide what the story may say (trained selection vs. any state-driven mapping).
   - Recommendation: (b). It costs minutes; the bar was written before an untrained baseline was known.
2. **What follows the toy pass.** The plan says the self-driven body then moves to the real run (B7 lanes on the danced songs, one arm).
   - (a) Order the real M3d run now (B7 lanes as the state, the three songs, the user's eye as the judge), with the fallback mapping kept as the
     comparison.
   - (b) Wait for question 1's controls first.
   - Recommendation: (b), then (a).
3. **Memory closed.** Confirm nothing from H1–H4 joins the arm for this plan, and that the WO4 brief's H3 control is corrected as in §2.
   Recommendation: confirm.
