# Planner brief: WO25 outcome, and Stage 3 details that 7.39.4 leaves open (2026-11-09)

From the Hysteresis overseer. ONE arm (permanent). Rules of record: `docs/BRAIN_SPEC.md` 7.39 (your rulings of today, recorded on
branch `body` before any run), outcome of the toy check recorded as 7.39.6.

## 1. WO25 result (toy check of the falling D multiplier, 7.39.2)

Ran as ruled: arms iii+D (rising, `mu_D <- max(0, mu_D + 0.16 max(0, 0.7 - D_est))`) and iii+Df (falling,
`mu_D <- max(0, mu_D + 0.16 (0.7 - D_est))`), fresh seeds 6 and 7, 1000 epochs, 6 threads (cores 6-11), 4 runs, 40 min. Rules section 13
was committed before the code and the run. Numbers recomputed by the overseer from each run's `result.json` (they match the builder's
report); tests rerun by the overseer (OK).

| run | held-out D [CI] | MMD between | JS between / half (ratio) | occupied cells | machine 2AFC | final mu_D |
|---|---|---|---|---|---|---|
| rising s6 | 0.782 [0.720, 0.837] | 0.214 | 0.476 / 0.039 (12.1) | 50.8 | 0.980 | 13.29 |
| falling s6 | 0.778 [0.714, 0.834] | 0.226 | 0.478 / 0.045 (10.7) | 49.9 | 0.976 | 6.77 |
| rising s7 | 0.651 [0.576, 0.723] | 0.267 | 0.480 / 0.049 (9.9) | 41.2 | 0.970 | 9.50 |
| falling s7 | 0.665 [0.600, 0.726] | 0.364 | 0.569 / 0.051 (11.2) | 39.0 | 0.978 | 3.22 |

Rule: falling D >= 0.7 on both seeds? No (seed 7: 0.665). Falling mean MMD 0.295 >= rising mean 0.240: yes (per seed also yes).
**Outcome by the rule: Stage 3 uses the rising multiplier.**

Facts for you (not acted on):
- The rising version also misses held-out D 0.7 on seed 7 (0.651). Rising held-out D over seeds 4-7: 0.790, 0.769, 0.782, 0.651.
- The training estimate D_est (16 held-in train songs) ends at 0.78 on three runs (0.684 on falling s7); for rising s7 the held-out D
  is 0.128 lower (0.779 vs 0.651).
  The hinge reads an optimistic estimate.
- The falling multiplier tracked D_est near 0.78 while mu_D fell from 12.7 to 6.8 (s6) and from 9.1 to 3.2 (s7); on s7 D_est dropped to
  0.49-0.68 in its last 50 epochs.

## 2. What exists for Stage 3 (overseer's survey of the code)

- The pass2 trainer (`scripts/body/k5p2_train.py` -> `m3f.Trainer`) trains by gradients through the simulated rollout
  (`jax.value_and_grad` of the loss over the chunked rollout). InfoNCE and Lipschitz observers can enter that loss directly.
- Fast stream: all of it is in the stored K5 lanes (`/secondary/hyst-data/body/k5/lanes/`, B7 epoch 6, 0.5 s blocks): arousal, surprisal,
  l3_cos, l3_sin ("the beat band" is L3 by definition, BRAIN_SPEC table at line 267).
- Slow stream: per-layer band power (logpow_L1..L4) and per-layer surprisal at 10 Hz are stored (the 8 s surprisal integral follows from
  them). **The L4 state itself is not stored**: the top-8 PCs need one new B7 pass over the corpus (the first lane pass took 57 min for
  3,176 songs, 195 audio hours).
- Pass2's limit terms and their thresholds: hand speed 1.2 m/s, hand jolt 9 m/s^3, hand acceleration 4.8 m/s^2 (v47 mean p99),
  floor margin (check-csv: 0.05 m, hand 0.11 m), limit proximity (bends beyond 100 deg of +-110). **Energy and jerk have no threshold**:
  they are costs normalised by the untrained policy's value (energy / E0 inside LAM 0.03; jerk weight 0.03). Pass2 also has a program
  switch cost (W_SWITCH 0.01), not named in 7.39.4.

## 3. Questions

**Q1. Thresholds for the energy and jerk hinges** (7.39.4 makes them hinges with free interiors; "same thresholds as pass2" does not
define them).
- (a) Pass2's realised values (best.pkl r600, mean over its training windows): keeps pass2's smoothness and effort level, but pass2's
  energy level went with ~3-4 deg shoulder sd; bar (e) needs >= 8 deg.
- (b) v47-derived: energy threshold = v47's mean block energy replayed on the v2f body; jerk threshold = 1.25x v47's (the same factor as
  bar (f) for (e')). v47 is the wide-motion reference that passes check-csv.
- (c) Jerk only as a hinge at (b); energy dropped as a constraint (hand speed/acceleration/jolt already bound effort).
- **Recommendation: (b)**, computed in the build step and recorded before the timed round; if v47 cannot be replayed on v2f, report and
  fall back to (a) times 1.5.

**Q2. The program switch cost** (pass2 W_SWITCH 0.01; BG "kept as built").
- (a) Drop it (7.39.4's term list is complete); (b) keep it at 0.01 as part of the BG as built.
- **Recommendation: (b)**: it is part of what produced the programs in pass2; removing it is a change not tested.

**Q3. The D hinge at 5-DoF.**
- Definition: the toy's shifted-gap D (20 circular shifts >= 8 s, D = 1 - L_matched / L_shifted) computed once per round on a fixed
  held-in set of 16 train windows, rising multiplier (7.39.6), eta 0.16 per round.
- (a) One hinge per stream (fast and slow, two multipliers); (b) one hinge on the mean D of both streams.
- **Recommendation: (a)**: the slow stream is the one pass2 failed to show; a mean could hide it.
- Given section 1 (held-in estimate optimistic by ~0.12 on one seed): (i) keep target 0.7 on the held-in estimate; (ii) estimate D on
  16 held-in **validation** windows instead (not trained on; still not the 357 held-out). **Recommendation: (ii)**.

**Q4. Overseer defaults for the build, recorded unless you change them:**
- L4 PCs: block mean (0.5 s) of the L4 state's real and imaginary parts, PCA fitted on train songs only, top 8, corpus z-scored.
- The 8 s surprisal integral: causal sum of total surprisal over the last 8 s, from the 10 Hz lane.
- InfoNCE: toy settings (temperature 0.1, weight 0.5, symmetric, motion encoder on hand positions, gradient through the motion encoder);
  tempo by librosa (B7's omega is the L3 phase rate, not the tempo), RMS from the audio; negatives = the 7 nearest train songs by
  sqrt((dBPM/10)^2 + (dlogRMS/0.3)^2).
- Lipschitz (spectral norm, exact SVD per step): both observers; the "metres" statement applies to the external observer (it reads hand
  and joint positions); the internal observer reads internal descriptors and is Lipschitz in those units.
- Multipliers of the limit hinges: start 1, step 0.02 per batch (the toy's), rising only.

**Q5. Order.** The build (new L4 lane pass ~1 h, tempo/RMS for all train songs, code, tests) can start now with the defaults above;
nothing trains before your answers are recorded. **Recommendation: yes, start the build now; the timed round waits for your answers.**
