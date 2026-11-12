# Motor-network toy test rules (work order 29A, 2026-11-12)

Binding: `docs/BRAIN_SPEC.md` 7.44. Disposable study: no learning, no training, no hand-tuning by eye, no pass bars beyond the safety gates,
no verdict by the builder. Written and pushed before any clip is rendered. Code: `scripts/body/motornet.py` (network, spinal layer, sim, gates),
`scripts/body/motornet_run.py` (sampling, render, manifest). Every number actually used is repeated in `docs/MOTORNET_PARAMS.md`.

## (a) The network

- One rate network, **N = 200** units, state `x`, rate `r = tanh(g_i x_i)`, dynamics `tau dx/dt = -x + W r + Win u`, **tau = 75 ms**.
  Euler at **200 Hz** (5 ms, input held for two steps); the network is read at the 100 Hz control rate. Start state `x = 0`.
- **Recurrent W**: iid Gaussian / sqrt(N), seed `29001` (stream 0), then rescaled so its spectral radius (largest |eigenvalue|, computed with
  `numpy.linalg.eigvals`) is exactly **1.05**. At gain 1 the linearised matrix at r = 0 is W, so the network sits just past the edge between
  decaying and self-sustained activity. Fixed for the whole study. Check (in PARAMS): activity of the gain-1 network with zero input from a
  small random start persists or decays slowly (reported, not tuned).
- **Inputs** (3): `cos` and `sin` of the beat-band phase, and arousal. Silent clips: phase `2 pi t 100/60` (fixed 100 BPM, t = network time from
  the start of the warm-up), arousal 0. Music clips: the cortex lanes `l3_cos`, `l3_sin` (0.5 s blocks, linearly interpolated to 100 Hz) and
  `arousal_b7` (10 Hz, interpolated; standardised with one fixed mean and sd taken over the three danced songs' lanes, clipped to +-3). Input
  weights `Win` (N x 3): iid standard normal, seed 29001 stream 1, fixed.
- **Control units**: **4**. Each owns a random subset of **80 neurons (40 %)** (seed stream 2, drawn without replacement per unit; subsets overlap).
  Neuron gain `g_i = prod_k c_k ^ m_ki` (m = 1 if neuron i is in unit k's subset). **No global gain** (not used). Each `c_k` ranges over
  **[0.5, 2.0]**, sampled **log-uniform** (symmetric in log). A setting = the 4 values (c1..c4); c = 1 everywhere is the reference gain 1.
- **Readout**: 5 linear outputs `y = Wout r`, `Wout` iid normal / sqrt(N), seed 29001 stream 3, fixed. Outputs map to (base yaw, shoulder, elbow,
  wrist bend, wrist roll).

## (b) The one calibration

At gain 1 (all c = 1) run the silent network for 10 s warm-up + 12 s; per joint take the mean `m_j` and sd `s_j` of `y_j` over the 12 s.
Joint target (deg) = `centre_j + CAL_FRAC * AMP_j * (y_j - m_j) / (2 s_j)` with `centre = (0, -60, 30, -15, 0)` (round 1's neutral centre),
`AMP = (30, 12, 16, 16, 45)` (round 1's neutral amplitudes), **CAL_FRAC = 1.0**: the gain-1 mean maps to the neutral centre and +-2 sd maps to
+-100 % of round 1's neutral amplitudes. Fixed for every clip. Nothing else is fitted.

*Deviation from the default (+-60 %), for feasibility:* at +-60 % the gain-1 silent run reached a hand extent of 0.056 m, under the minimum-
motion gate. The values 0.6, 1.0 and 1.5 were each tried once, at gain 1 only (the calibration run, not a sampled setting): extent 0.056, 0.084
and 0.062 m. The beat-rate drive is limited by the joint speed limits (`LIMITS`), so more amplitude does not give more extent. 1.0 is the
natural round-1 reading ("+-2 sd = the neutral amplitude") and the largest of the three. Logged FOR USER.

## (c) Spinal layer and body

- Per joint a second-order spring-damper `theta'' = wn^2 (target - theta) - 2 zeta wn theta'`, **wn = 2 pi 3 Hz, zeta = 0.7**, integrated at 1 ms
  (semi-implicit Euler), starting at rest on the first target. Same for every joint and every clip. Its output is the goal handed to the round-1
  command path (below).
- Body and stepping as `docs/DIALSTUDY_RULES.md` (a): v2f model (`make_arm_v2.xml_v2`, table plane z = 0.053 m, self-collision, solref
  [0.006, 1]), plain MuJoCo CPU, 100 Hz control, 5 substeps of 2 ms, the braking-aware limiter of `arm_sim.ArmSim.limit_target` (limits of
  `make_arm.LIMITS`), ranged targets clipped 0.5 deg inside the range, hard end stops after every substep. Servo gains: `kp = make_arm.KP`
  (kp_scale 1.0), zeta 1.5 (round 1's neutral stiffness; `kv = 2 zeta sqrt(kp I)` per joint, `I` from `make_arm.tune_kv`'s pose). Never changed per clip.
- The mirror-ball mass and inertia stay for every clip. The end effector is visual only: **lamp** for Parts 1; **ball** for Part 2.
- **Warm-up**: the network, spinal layer and sim run **10 s** before the 12 s shown (the sim starts at rest on the first goal; no pre-roll). For a
  music clip the 10 s of the song before the excerpt drive the warm-up. The shown 12 s are the CSV and the video. The recorded CSV is the
  realised joint angles at 50 Hz (601 rows), `arm_sim.csv_text` format.

## (d) Gates (clip rejection, not pass bars)

Round 1's gates (`DIALSTUDY_RULES.md` (d)), same code (`dialstudy.gate_values`, `dialstudy.judge`) with round 1's thresholds (hf share <= 0.01,
reversals <= 6 /s per joint; no stricter value was needed): clearance (FK points 1-4 >= 0.05 m, hand >= 0.11 m above z = 0), no contact at any
substep (from 1.5 s before the shown clip, the end of round 1's pre-roll equivalent; the earlier warm-up seconds are not counted), end stops
(no ranged joint within 3 deg of a limit for 6 or more consecutive 50 Hz samples), jitter (hf power share above 8 Hz, reversals), speed and
acceleration within `LIMITS` (5 % tolerance), finite. **Plus minimum motion**: hand-point p5-p95 extent **>= 0.05 m** on at least one axis over
the 12 s, and **no 3 s stretch** with mean hand speed below **0.01 m/s**.

*Deviation from the default (0.10 m), for feasibility:* the default is above what the speed-limited beat-rate drive can reach at the reference
gain (0.084 m); round 1's lowest-vigour clip has 0.094 m, its neutral 0.29 m. 0.05 m still excludes a static arm. Logged FOR USER.

A failing setting is discarded and replaced by the next sampled one; discards are counted per gate (a setting can fail several; all failed
gates are counted). Three frames per clip and a contact sheet are looked at by the builder before a clip is listed, never to select or reshape a
setting. A failing clip is never shown. Nothing is discarded for any other reason.

## (e) Sampling

Control-unit values are drawn with `numpy.random.default_rng(29011)`: for draw d = 1, 2, ... four values `exp(uniform(ln 0.5, ln 2.0))`, in order.
Each draw is simulated silent; draws that pass all gates are kept **in draw order until 10 are kept**: S01-S10. **S11** = all four c at 0.5 (low),
**S12** = all four at 2.0 (high). If S11 or S12 fails a gate it is not shown and not replaced; reported. Settings are fixed (and written to
`settings.json`) before any clip is watched or any measurement is read. Part 3 pairs and Part 4 clips are drawn with seeds recorded in the
manifest: Part 4 with `default_rng(29041)` choosing 4 of round 1's 22 clips (without replacement, sorted by id); Part 3 (held) with
`default_rng(29031)` choosing two different settings of S01-S12 per song.

## (f) Measurements (computed by `scripts/body/motornet_measure.py` from the per-clip files; numbers only)

- **Participation ratio** of the network activity: `r(t)` (601 x 200, 50 Hz, the shown 12 s), covariance over time, eigenvalues l_i,
  `PR = (sum l_i)^2 / sum l_i^2`.
- **Regime** (silent clips, with input): *decays* if the std over units-and-time of `r` in the last 4 s is < 0.1 x that of the first 4 s; else
  *cycles* if the autocorrelation of the first principal-component score (mean-removed, 50 Hz) has a peak > 0.5 at a lag of 0.3-5 s; else
  *wanders*. (Note: the warm-up has run for 10 s before the shown 12 s, so "decays" means the shown 12 s decay further.)
- **Dominant movement frequency**: frequency of the maximum of the summed power spectra of the three mean-removed hand-position coordinates
  (x, y, z; 50 Hz, Hann window, whole 12 s, no zero-padding, DC excluded, bins above 0.1 Hz). Not the hand-speed spectrum (it doubles the
  frequency of back-and-forth motion). Amended by the overseer 2026-11-12.
- **Mean hand speed** (m/s): mean of the hand-speed samples. **Mean hand height** (m): mean z of the hand point (`m3f_report.fk_points`, index 5).
- **Hand-path straightness**: strokes are the hand path between consecutive local minima of hand speed (50 Hz, speed smoothed with a 0.1 s box
  window, minima at least 0.3 s apart, strokes whose arc length is under 0.05 m skipped); per stroke chord / arc; reported as mean, and min.
  The round-1 definition is a fixed 1.2 s window (`dialstudy_straight.py`); here the strokes are speed-defined because the network has no
  fixed move grid.
