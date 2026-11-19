# Planner brief: plan version 2 and work order 2, checked against the code (2026-11-04)

Done: plan v2, work order 2 and the rulings (BRAIN_SPEC §7.12) are committed on `body` (bf38d65) and pushed. The builder prompts are written
with the defaults below. They are not sent until the user says.

## What cannot be met as written, or is not defined (no rule changed)

1. **M1 command space.** The babbling input "current command + last 100 ms of commands" is M2's command vector (frequency, amplitude,
   centre, lag per joint, at 10 Hz). The v47 set is "replayed as servo targets (no pattern generator)", so it has no M2 commands. The
   cerebellum cannot take both as written. **Default:** the command the cerebellum sees is the servo target (joint angles at 100 Hz, what
   the generators output) in both sets, and the efference copy is the last 10 targets.
2. **The v47 set has six arms per song** (hexagon ensemble), not one trajectory. **Default:** all six arms' trajectories of each of the
   three songs, each replayed as its own trajectory (18 trajectories). The bootstrap unit is the trajectory.
3. **K1's per-trajectory bootstrap on babbling.** Babbling is one long stream per seed. **Default:** 2 h held out = 120 independent
   60 s trajectories (each its own seed and start pose). Bootstrap over trajectories, 10,000 resamples, 95 % interval.
4. **The Kaggle job that verifies the whole `hyst-features` upload** (ruling §2) is not in either builder's order. **Default:** builder 1
   runs it first (a few GPU-free minutes of kernel time).
5. **The ignition readout** says "cross-band coherence of the four layers' phases" but a layer has 256 modes, not one phase. The bands also differ in frequency
   (8–20 Hz against 0.01–0.5 Hz), so plain phase differences between layers drift by construction. **Default:** a layer's phase = the
   magnitude-weighted circular mean of its 256 mode phases. Coherence = the mean resultant length over a 1 s window of each adjacent pair's
   n:m phase difference (n:m = the rounded ratio of the two bands' centre frequencies), averaged over the 3 pairs. The planner may prefer
   a simpler one (for example the L2–L3 pair only).
6. **The self-similarity lane** does not say what state, how often, or which past entries. **Default:** the same input and timing as H2
   (random projection of [features pooled over 2 s, L3 + L4 state], every 0.5 s, against entries ≥ 17 s old), but with no sparsification,
   so it does not depend on H2 passing.
7. **Memory for the M3 step benchmark.** The twin cortex pass at 256 environments with a backward pass through the relay may not fit
   builder 1's 14 GB cap (a B7 training step with batch 8 already uses 9 GB). **Default:** report the largest environment count that
   fits, and note the rest.
8. **Night logs.** The work order uses `docs/NIGHT_LOG_<branch>.md`; plan §11 says `docs/NIGHT_LOG.md`. **Default:** the work order's
   form (it avoids merge conflicts between the two builders).

## Questions

1. Items 1, 5 and 6 are design choices inside a check (K1) or a lane (ignition, self-similarity). Accept the defaults? Recommendation:
   accept 1 and 6. For 5, choose: the default above, or the simpler L2–L3 pair only.
