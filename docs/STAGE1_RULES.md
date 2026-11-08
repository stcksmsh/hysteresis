# Stage 1 rules (work order 20, builder branch `body-s1`), written 2026-11-09 before the toy is built

Binding source: `docs/BRAIN_SPEC.md` 7.34. This file only fixes the definitions so a reader can recompute the verdict. Toy only: a 2-link planar arm,
synthetic songs. No hardware, no connection to the real brain/pass2 code. All code in `scripts/body/s1_*.py`; data in `/secondary/hyst-data/body/s1/`.
Amendments before the run are allowed only as dated entries at the end of this file, committed and reported before "run Stage 1".

## 1. Arm

- 2-link planar arm, link lengths L1 = L2 = 0.30 m, base at the origin. Hand = end of link 2 (the "mirror ball"); workspace is the disc of radius 0.60 m.
- Joint limits q1 in [-2.0, 2.0] rad, q2 in [-2.4, 2.4] rad.
- Kinematic dynamics, 20 Hz control steps (dt = 0.05 s): the policy outputs targets q*_t = 0.95 * qmax * tanh(a_t); the joints follow a first-order lag,
  q_{t+1} = q_t + 0.35 (q*_t - q_t) (time constant about 0.12 s). q_0 = 0. Everything is differentiable (JAX), rollouts by `lax.scan`.
- Policy: GRU (hidden 32) over the music features (section 2), linear head to the 2 targets. Same net in every arm.

## 2. Synthetic songs

- 40 s each, 20 Hz (800 steps). Corpus: 64 train, 16 validation (only to choose lambda for arm iv), 32 held-out; seeds disjoint (train 1000+i, val 2000+i, held 3000+i).
- Per-song constants: tempo bpm ~ U(90, 130), beat phase offset ~ U(0,1), gain log g ~ N(0, 0.3), slow latent z = (z1, z2) ~ N(0, I).
- Within the song z drifts: z_t = z + an Ornstein-Uhlenbeck swing (sd 0.15, tau 10 s) per component. The beat phase is phi_t (cycles) = offset + bpm/60 * t.
- Beat pulse p_t = exponential decay (tau 0.1 s) of a unit impulse at every integer crossing of phi; every 4th beat is accented.
  Pulse level e_t = g * (1 + 0.4 tanh(z1_t)) * p_t * exp(0.3 z2_t * [accent beat]) (z1 sets the loudness character, z2 the accent strength).
- Music features the policy sees (5): cos(2 pi phi_t), sin(2 pi phi_t), e_t, s1_t = z1_t + 0.3 n, s2_t = z2_t + 0.3 n (n standard normal per step, i.e. slow channels with noise).
  Mean of the policy input per song is not removed; the recurrent policy may average s1, s2 itself.
- Decoding target ("state"), 8-D per step: fast stream (4): cos(2 pi phi_t), sin(2 pi phi_t), cos(2 pi phi_t / 4), sin(2 pi phi_t / 4); slow stream (4): z1_t, z2_t, (bpm - 110)/20, log g.

## 3. Observer and the decoding loss (the same network in every arm, apart from the constraint of arm iii)

- Causal MLP over the last K = 30 hand positions (1.5 s, metres, both coordinates, 60 inputs; zero padded at the start): 60 -> 64 -> 64 -> 8, tanh hidden layers, times a fixed output gain G = 4.
  G sets the scale: a one-sd song difference must be separated by about 0.25 m of hand position.
- Loss = mean squared error over the 8 dims and steps t >= 60 (3 s).
- Arm i target ("the current objective"): causal exponential z-score of every dim within the song, time constant 30 s, bias corrected, sd floored at 0.1 x the corpus sd of that dim.
  (Slow dims are nearly constant in a song, so this target mostly erases between-song differences; that is the hypothesis being tested.)
- Arms ii-iv target: fast dims as in arm i; slow dims standardised by the train-corpus mean and sd (a fixed affine map, no within-song normalisation).
- Time-shifted control (a), as in M3d: per song, the mean over t >= 60 of [observer loss against the target circularly shifted by s steps] - [matched loss], s >= 160 steps (8 s),
  20 seeded shifts averaged. **Decoding score D = 1 - L_matched / L_shifted** on held-out songs, each arm on its own target (0 = chance level for this observer, 1 = perfect).
  Secondary, not binding: D under a common ridge probe (fit on train, arm ii-iv target), reported for all arms.

## 4. The four arms (cumulative)

- **(i)** decoding loss with the arm-i target + hinge constraints (section 5).
- **(ii)** (i) with the arm ii-iv target + contrastive music<->motion InfoNCE. Two encoders: music (mean of the 5 features over an 8 s window -> 32-D, MLP 5->32->32) and motion
  (hand-position window of 8 s subsampled every 4 steps -> 80 inputs -> 64 -> 32, unconstrained). L2-normalised, temperature 0.1, symmetric InfoNCE over a batch of B = 8 songs,
  one random 8 s window per song and step, the same window for music and motion. **Negatives are tempo and gain matched**: a batch is an anchor song plus its 7 nearest train songs by
  distance sqrt(((bpm_i - bpm_j)/10)^2 + ((log g_i - log g_j)/0.3)^2). Weight 0.5. The gradient reaches the policy through the motion encoder.
- **(iii)** (ii) with the observer made 1-Lipschitz: each weight matrix divided by max(1, its spectral norm), computed exactly (SVD) each step; with the output gain G the observer is
  G-Lipschitz in metres of hand position (tests measure it).
- **(iv)** (iii) + `-lambda * log det (K + 1e-3 I)` over a batch (the same matched batches) of per-song posture embeddings: a soft hand-position histogram over an 8 x 8 grid on
  [-0.6, 0.6]^2 (Gaussian soft assignment, sigma = one cell), normalised to sum 1, whole song; RBF kernel K_ij = exp(-|e_i - e_j|^2 / (2 * 0.05^2)).
  lambda grid {0.05, 0.5}; the value is chosen per seed by the pass-rule quantity (between-song JS subject to D >= 0.7, else D) on the **validation** songs; held-out numbers are reported for both.

## 5. Hinge constraints (every arm), dual ascent

Per song, constraint values g_k >= 0 are violation means (zero inside the envelope):
- hand speed: mean_t relu(|v_t| / 1.2 - 1) (|v| in m/s, central difference);
- jerk envelope: mean_t relu(J_t / 400 - 1), J_t = RMS over a 5-step window of the third finite difference of the hand position / dt^3 (m/s^3);
- joint-limit margin: mean_t relu((|q_t| - (qmax - 0.15)) / 0.15) summed over joints.
Loss adds sum_k mu_k g_k (batch mean); after each step mu_k <- max(0, mu_k + 0.02 g_k) (slow multiplier rate), mu_k starts at 1. No other cost terms (no energy, no posture variety cost).

## 6. Optimisation

Adam (own implementation, no new package), lr 3e-3 for policy and encoders, 3e-3 for the observer, gradient clip 1.0. One epoch = 8 batches of 8 songs (one pass over the train songs in anchor order, arms ii-iv with the
matched-batch rule; arm i uses the same batches so the data order is shared). **Budget: 300 epochs per run** (2400 updates), 2 seeds per arm (seed = the network initialisation and the batch/window draws; the corpus is fixed).
Runs: i, ii, iii, iv(0.05), iv(0.5), each x 2 seeds = 10 runs. The projected compute is written in the night log after the smoke runs; if it exceeds 8 h at 6 threads the epochs are amended here before the run.

## 7. Measures (held-out 32 songs, argmax = the deterministic policy; no noise in the rollout)

- **Between-song JS**: each song's whole-song hand-position histogram on a 24 x 24 grid of 0.05 m cells over [-0.6, 0.6]^2; Jensen-Shannon divergence base 2 (in [0,1]) between every pair of the 32 songs (496 pairs);
  median. **Half-song control**: JS between the first and second 20 s of each song, median over songs. Report both and their ratio.
- **Decoding D** (section 3), with its bootstrap interval over songs.
- **Distinct postures**: cells with dwell >= 0.5 % of the song, mean over songs.
- **Machine 2AFC**: all held-out pairs with |dBPM| <= 5 (not one-to-one; toy). Clips are non-overlapping 8 s windows (5 per song, clip index 2 dropped); train on clips 0,1, test on clips 3,4 of both songs.
  Features per clip: a 12 x 12 hand-position histogram (0.1 m cells), per-joint mean and sd of angle and of angular speed. L2 logistic regression (own numpy/scipy implementation, no sklearn in the env),
  standardised features, C = 1. Accuracy = mean over test clips; report the mean over pairs with a 10,000-resample bootstrap over pairs, and a label-shuffled control (about 50 %).

## 8. Pass rule (verbatim from 7.34, with the operational choices)

**Pass: (iv) between-song JS >= 3 x (i) with decoding D >= 0.7. Report the smallest arm reaching >= 2 x (i).**
Operationally: (i)'s reference value is the mean of its two seeds' between-song JS. A seed of (iv) passes when its JS >= 3 x that reference and its D >= 0.7. **Both seeds must pass** for the verdict "pass"
(the lambda used is the validation-chosen one per seed). The smallest arm reaching >= 2 x: the first arm in the order i, ii, iii, iv whose two seeds both have JS >= 2 x the (i) reference (the D >= 0.7 condition is reported alongside, not required for that line).
The 2AFC is reported for all arms as supporting evidence; it is not part of the verdict.

## 9. Notes and choices to be aware of (FOR USER, not blocking)

- The output gain G = 4 and the `sd floor` are scale choices of this toy, not derived. G matters for arm iii: with G = 1 a 1-Lipschitz observer could not decode unit-sd latents from a 0.6 m workspace at all.
- Decoding D in arm i is measured on its own (within-song z-scored) target and therefore is not directly comparable with arms ii-iv; hence the common ridge probe as a secondary column.
