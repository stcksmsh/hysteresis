# Motor-network toy round 2 rules (work order 30B, 2026-11-13)

Binding: `docs/BRAIN_SPEC.md` 7.47 (with the overseer notes 7.47.6), 7.46, 7.45, 7.44. Disposable study: no learning, no training, no hand-shaping, no
verdict by the builder; Kosta judges blind. One arm. Written and pushed before any clip is rendered; nothing here changes after the push.
Code: `scripts/body/motornet2.py` (network, calibration, sim, gates), `motornet2_fit.py` (silent fit), `motornet2_lanes.py` (L4 lanes), `motornet2_run.py`
(sampling, clips). Round 1 (`motornet.py`, `docs/MOTORNET_RULES.md`, `docs/MOTORNET_PARAMS.md` at body-mnet 265fe79) is imported unchanged for the spinal
layer, servo, limiter, simulation, contact rule and gate code.

## (a) Network

- **Two populations**, N = 200: **slow** units 0-99, tau 300 ms; **fast** units 100-199, tau 75 ms. `tau_i dx_i/dt = -x_i + (W r)_i + (Win u)_i`,
  `r = tanh(g_i x_i)`; Euler 5 ms (200 Hz, input held for two steps), read at 100 Hz; x = 0 at start.
- **Recurrent W**: full 200 x 200, iid Gaussian / sqrt(200), seed **30001** stream 0. For each population p the raw within-population block (100 x 100) has
  spectral radius rho_p (raw: slow 0.7672, fast 0.7300); **all rows of population p are multiplied by 1.05 / rho_p**, so each within-population block has spectral
  radius exactly 1.05, and the between-population blocks keep their row's factor. **Radius of the full matrix: 1.4978** (reported, not tuned).
- **Readout** (seed 30001 stream 3, iid normal / sqrt(100)): base yaw and shoulder from the **slow** population only; elbow, wrist bend, wrist roll from the
  **fast** population only (other columns zero). Fixed.
- **Inputs** (8): beat-band phase `cos`, `sin` to both populations (music: round 1's `l3_cos`, `l3_sin`, cortex lane y columns 2 and 3, 0.5 s blocks, linear
  interpolation; silent: phase `2 pi t 100/60`); **L4** to the slow population only: the complex state (real and imaginary parts, 512 numbers, B7 epoch 6,
  frames 9::10 = 10 Hz) projected by a Gaussian matrix (seed **30002**, 512 x 4) to 4 signals, standardised with one mean and sd per signal pooled over the three
  danced songs, clipped to +-3, no extra filtering; **ear energy** (WO30A, `scripts/body/ear_energy.py`, its standardised network lane) and **`arousal_b7`**
  (standardised with the pooled mean and sd of the three danced songs, as round 1, clipped +-3) to both. Silent: L4, energy and arousal are 0. Input weights
  `Win` (200 x 8) iid normal, seed 30001 stream 1; the L4 columns are zero for fast units. Inputs are interpolated linearly to 100 Hz.
- **Drive ratio**: one input scale per population, applied to that population's rows of `Win`; fixed-point iteration `s_p <- s_p * 0.25 * rec_p / in_p` on the
  gain-1 silent run (10 s warm-up, 30 s shown; in_p / rec_p = mean over the population's units of the std over time of `Win u` / `W r`), stopped when both ratios
  are within 0.5 % of 0.25 (the allowed 2 % being looser). **s_slow = 0.194744, s_fast = 0.180399** (3 iterations; final ratios 0.2503 and 0.2505; final input / recurrent
  stds: slow 0.1696 / 0.6777, fast 0.1664 / 0.6644). The same scales are used for music.
- **Control units**: 4 (as round 1), each scaling the gain of a random subset of **80 of the 200** neurons (seed stream 2, without replacement per unit; subsets
  overlap, drawn from both populations). Subset sizes (slow, fast): (39, 41), (43, 37), (41, 39), (33, 47). Neuron gain `g_i = prod_k c_k ^ m_ki`; each `c_k` in
  [0.5, 2.0], log-uniform. No global gain.

## (b) Calibration and body

- **Calibration** (as round 1, one scale and offset per joint): gain 1, silent, 10 s warm-up + 30 s (the shown length): per-joint mean m and sd s of the raw
  readout over the 30 s; target = `centre + 0.6 * AMP * (y - m) / (2 s)`, centre (0, -60, 30, -15, 0), AMP (30, 12, 16, 16, 45) deg: **+-60 %**. Raw sd
  (0.236, 0.574, 0.181, 0.523, 0.456), raw mean (0.0056, 0.0221, 0.0273, -0.0559, -0.0580). Fixed for every clip.
- **Spinal / limiter rule (7.45.2)**: at gain 1 silent, limiter output p5-p95 / target p5-p95 at spinal 3 Hz: base yaw 1.001, shoulder 1.000, elbow 1.000, wrist bend
  1.000, wrist roll 0.984. Neither base yaw nor shoulder lost more than half: **the spinal spring-damper stays at 3 Hz** (zeta 0.7). Target p5-p95 (deg):
  34.5, 13.7, 17.2, 14.8, 41.3.
- **Body**, warm-up (10 s, the song's 10 s before the excerpt for music), servo, limiter, contact rule (counted from 1.5 s before the shown part), gates and
  minimum motion (hand p5-p95 extent >= 0.10 m on one axis, no 3 s stretch under 0.01 m/s): exactly round 1 (`MOTORNET_PARAMS.md` at body-mnet 265fe79).
  **One change forced by the clip length**: the reversal rate divides the reversal count by the clip length (30 s; round 1's code divides by 12 s), thresholds
  unchanged (hf share <= 0.01, reversals <= 6 per s). Gain-1 silent: extent 0.297 m, all gates pass; realised p5-p95 (deg) 34.2, 15.1, 17.3, 14.5, 37.4.
- Recorded CSV: realised joint angles at 50 Hz (1501 rows), `arm_sim.csv_text`; activity: rates at 50 Hz (1501 x 200, columns 0-99 slow, 100-199 fast).

## (c) Sampling, gates per song

- `numpy.random.default_rng(30011)`: draw d = 1, 2, ... four values `exp(uniform(ln 0.5, ln 2.0))`. Each candidate is simulated (10 s warm-up + 30 s, no render)
  **silent** and on each of the five check songs at Kosta's start times: Blue Lagoon 0:20 (20 s); 21st Century Schizoid Man 0:58 (58 s); Epitaph 5:45 (345 s);
  Breathe 1:17 (77 s); One of These Days 3:57 (237 s). It must pass the gates on all six runs. The **first 8 that pass, in draw order, are S01-S08**. Every
  discard is logged with its failing gate(s) and song.
- **Round-1 reference**: round-1 S03 (settings from `motornet_toy/clips/settings.json`; the round-1 network, inputs and calibration unchanged: `motornet.py`,
  `l3_cos`, `l3_sin`, `arousal_b7`, input scale 0.04278) simulated at 10 s warm-up + 30 s per song and gated. If it fails on a song, that song's pair is not
  rendered and is reported; S03 is not replaced.
- **Stop rule (7.47.4.8)** on the Part A silent runs: if all 8 settings have PR < 3 in both populations AND base yaw p5-p95 < 20 deg, write STOP RULE HIT with
  the numbers in the night log, push, and stop before Part B. PR = participation ratio of the covariance of the 50 Hz rates of each population, over the 30 s shown.

## (d) Renders and numbers

- Lamp, round 1's camera and framing, 30 s, 1280x720 h264, aac where music. **Part A**: S01-S08 silent. **Part B**: `default_rng(30031)` draws 5 different
  settings from S01-S08 (`rng.choice(8, 5, replace=False)`), one per song in the order above; per song the new setting and round-1 S03 are rendered on the
  song's 30 s excerpt, excerpt audio muxed.
- `numbers.json`: per clip PR per population, base yaw and shoulder p5-p95 (deg), facing drift (mean base yaw over the last 3 s minus over the first 3 s,
  deg; and the range of its 3 s moving mean), mean hand speed (m/s); per song mean ear energy and mean `arousal_b7` over the 30 s shown (raw and as the standardised
  input). `manifest.json` per clip: id, part (A / B), files, setting, song, excerpt_start_s, csv, activity, population index per unit (0 slow, 1 fast), gates.
- `settings.json` (S01-S08, draw indices, discards) is written before any clip is viewed. Three frames per clip are looked at by the builder, never to select or
  reshape a setting.

## (e) Energy and lanes

L4 projection and `arousal_b7` lanes (all 8 songs; arousal checked bit-identical to round 1's lanes) are computed. The ear-energy lane is WO30A's function and is
merged only after "ENERGY READY <commit>" on `origin/body-mnettool4`; no music input is computed before that.
