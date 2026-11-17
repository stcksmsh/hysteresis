# Internal pulse rules (WO48, BRAIN_SPEC 7.78 2.1) — written and pushed before any result

Report only; no motor clock, no coupling, no change to A or B, no verdict. One arm. Code `scripts/body/pulse_lib.py` (model),
`pulse_run.py` (run + numeric check + report tables), `pulse_flash.py` (flash material); tests `test_pulse.py`, `test_dialstudy_wo48.py`.
Out: `/secondary/hyst-data/body/pulse/`. Defaults are marked **(default)** and repeated under FOR USER.
Nothing below is tuned on any song. Before these rules were pushed only synthetic signals were run (the four tests of section 6 and a
timing run on noise); no song audio was passed through the pulse.

## 1. Model: a gradient-frequency oscillator bank (canonical model of Large et al.)

**Equation** (one sensory network, no oscillator-oscillator coupling, stimulus coupling only):

    dz_i/dt = z_i ( alpha + i w_i + beta1 |z_i|^2 + eps beta2 |z_i|^4 / (1 - eps |z_i|^2) ) + c P(eps, x(t)) A(eps, conj z_i)
    P(eps, x) = x / (1 - sqrt(eps) x),    A(eps, conj z) = 1 / (1 - sqrt(eps) conj z),    w_i = 2 pi f_i

**Sources** (local copies saved under `/secondary/hyst-data/brain/papers/` during B1, 2026-10-29; nothing downloaded now):
- Large EW, Herrera JA, Velasco MJ (2015). Neural networks for beat perception in musical rhythm. *Front. Syst. Neurosci.* 9:159,
  doi 10.3389/fnsys.2015.00159, section 3: **Eq. (2)** the canonical GrFNN, `tau_i dz_i/dt = z_i(alpha + i2pi + beta1|z_i|^2 + eps beta2 |z_i|^4 + ...)
  + sum_j c_ij P(eps, z_j) A(eps, conj z_i) + b_i s(t)`, f_i = 1/tau_i, alpha = 0 the critical point; **Eq. (3)** `P(eps, z) = z + sqrt(eps) z^2 + eps z^3 + ... =
  z / (1 - sqrt(eps) z)`; **Eq. (4)** `A(eps, conj z) = 1 + sqrt(eps) conj z + eps conj z^2 + ... = 1 / (1 - sqrt(eps) conj z)`. (Read in the local text copy.)
- Velasco MJ, Large EW (2011). Pulse detection in syncopated rhythms using neural oscillators. *Proc. ISMIR 2011*, PS2-3: section 1.2 Eq. (3) (the
  stimulus-driven canonical oscillator with c, beta1, beta2, delta1, delta2, eps, and the stimulus entering through P(eps, x(t)) A(eps, conj z));
  **section 2.1 parameter values: alpha = 0, beta1 = -1, beta2 = -0.25, eps = 1**, "289 oscillators ... logarithmically spaced from 0.25 Hz to 16 Hz",
  critical regime. (Values read in the local text copy.)
- Lambert AJ, Weyde T, Armstrong N (2014). Beyond the beat. *Proc. ICMC/SMC 2014*, section 3.1 **Eq. (1)**:
  `dz/dt = z(alpha + i w + beta eps |z|^4 / (1 - eps |z|^2)) + x / (1 - sqrt(eps) x) * 1 / (1 - sqrt(eps) conj z)` (read in the local text copy; used to
  confirm the closed forms).
- Large EW, Almonte FV, Velasco MJ (2010). A canonical model for gradient frequency neural networks. *Physica D* 239:905-911. **Not read** (no local copy).

**What could not be reconstructed exactly, and the replacement:**
1. Velasco & Large 2011 Eq. (3) is an image in the local PDF; its text layer has only the surrounding prose. The form above is reconstructed from
   memory of Large et al. 2010 / Velasco & Large 2011 and checked against the readable closed forms of Large 2015 Eq. (3)-(4) and Lambert 2014 Eq. (1).
   **The detuning terms delta1, delta2 are set to 0** (Large 2015 Eq. (2) has none; Velasco & Large 2011 names them without values).
2. Large 2015 Eq. (2) feeds an external signal linearly (`b_i s(t)`) and uses P A only between oscillators; Velasco & Large 2011 and Lambert 2014 feed the
   stimulus through `c P(eps, x) A(eps, conj z)`. **The P A stimulus form is used** (the one with published parameter values for pulse detection).
3. Large 2015 Eq. (2) scales time by tau_i = 1/f_i (so alpha and beta scale with f_i). **Unscaled time, w_i = 2 pi f_i, is used** (Velasco & Large 2011,
   Lambert 2014), because the beta values above are given for that form.
This is the same model the B1 work used (`scripts/brain/GRFNN_PARAMS.md`), whose integrator `grfnn._run` is reused unchanged.

**Parameters:**

| item | value | source / status |
|---|---|---|
| alpha, beta1, beta2, eps | 0, -1, -0.25, 1 | Velasco & Large 2011 section 2.1 |
| delta1, delta2 | 0 | replacement 1 above |
| oscillators | **73, f_i = 0.5 * 2^(i/24), i = 0..72 (0.5-4 Hz, 24 per octave, log-spaced)** | range and count 50-100 from the work order; 24 per octave chosen to fall in it (Velasco & Large: 48 per octave over 0.25-16 Hz) **(default)** |
| c (coupling of the input) | 1, with the input scaled by C_IN = 0.05 and capped at X_MAX = 0.5 | B1 values (`GRFNN_PARAMS.md`: C_IN from a synthetic sweep, cap from the singularity of P at x = 1) |
| integration | classical RK4, time step 5 ms (2 sub-steps per 10 ms frame), input held constant over each frame | B1 (`grfnn._run`) |
| initial state | z_i = 0.001 (real) for every oscillator | B1 |
| safety clip | abs(z) clipped to 0.95 after every step (keeps A finite at eps = 1) | B1 |

Alpha = 0 (critical) means an oscillator decays without input; persistence through a silence is the slow critical decay
(d|z|/dt = -|z|^3 - ... at alpha = 0), not self-sustained oscillation. Alpha is not changed.

## 2. Drive: onset envelope with low-band weighting, causal

From the ear features (`scripts/brain/fast_features.py`, 44 columns at 100 Hz, from the song's mono mix at 44.1 kHz):

    u(t) = 1.0 * z_32(t) + 0.5 * z_33(t) + 0.5 * z_40(t)
    x(t) = min( C_IN * max(u(t - 30 ms), 0), X_MAX ),   C_IN = 0.05, X_MAX = 0.5

- **column 32** = half-wave-rectified dB flux of the 30-200 Hz STFT bins (kick), weight **1.0**;
  **column 33** = the same for 200-400 Hz (rim / snare body), weight **0.5**;
  **column 40** = onset strength, mean rise over all 32 log-mel bands (broadband; includes hats), weight **0.5** **(default)**.
  The weights sum to 2, the scale of B1's two-channel equal-weight sum for which C_IN = 0.05 was chosen.
- **Normalisation:** each column is a running z-score with exponential mean and variance, time constant 10 s, prior mean 0 and variance 1
  (`grfnn.standardise_causal`), SD floor 1e-3 x a fixed reference SD (column 32 and 33: 4.4373, column 40: 1.4513, B1's synthetic references;
  column 33 has no own reference and uses column 32's; the floor only acts in digital silence).
- **Causality:** the centred 2048-sample STFT of frame t reaches 1024 samples (23.2 ms) past t. The drive is **delayed by 3 frames (30 ms)**, so x(t)
  uses audio up to t - 6.8 ms only. Running statistics, RK4 and the readout use no future samples. The whole song is processed in one pass from its start.

## 3. Pulse selection

- **Arm limit.** Reference movement: a side-to-side swing theta(t) = A sin(pi f t), i.e. one traverse from -A to +A per pulse period, with
  **A = 5 degrees** **(default)** (10 degrees peak to peak, about 12 cm at the lamp of the 0.69 m arm; the smallest swing that reads as keeping time;
  A was chosen knowing that a 2 Hz pulse must be admissible, the work order's 120 BPM test). Peak speed pi f A, peak acceleration (pi f)^2 A. With
  `make_arm.LIMITS` (shoulder 90 deg/s, 300 deg/s^2; base yaw 120 deg/s, 600 deg/s^2):

      f_max = min over {shoulder, base yaw} of min( v / (pi A), sqrt(a / A) / pi )
            = min(5.73, 2.466, 7.64, 3.49) Hz = 2.466 Hz  (147.9 BPM; binding: shoulder acceleration)

  Only oscillators with f_i <= f_max can be selected (the bank still spans 0.5-4 Hz).
- **Score:** S_i(t) = |z_i(t)| * P(f_i), **P(f) = exp(-0.5 (log2(f / 2 Hz) / 1)^2)**: a log-Gaussian preferred-tempo prior, centre 2 Hz (120 BPM),
  **width sigma = 1 octave** **(default)**. (B1 round 2 used sigma 0.5 octave, `exp(-2 log2^2)`; a wider prior is used here so that the bank's amplitude
  decides more; P(1 Hz) = P(4 Hz) = 0.61.)
- **Hysteresis / smoothing:** start at argmax S at the first frame. Every frame, (1) the selection follows the local maximum of S among the
  current oscillator and its +-2 neighbours (+-1/12 octave, +-5.9 %) without hysteresis (tempo following); (2) it jumps to the global argmax only when
  that oscillator's S exceeds the current one's by 20 % on 200 consecutive frames (2 s) (B1's rule). **(default)**
- **Phase** = arg z of the selected oscillator. **Rate** = mean phase advance of the selected oscillator over the past 1 s (100 frames, the same
  oscillator at both ends of every step), / 2 pi, in Hz; BPM-equivalent = 60 x rate. **Amplitude (confidence)** = |z| of the selected oscillator.
- **Pulse events** = upward crossings of phase 0 of the selected oscillator (from < 0 to >= 0, not the +-pi wrap), time linearly interpolated within
  the frame; no event in a frame where the selection jumped. No readout offset is applied.

**Outputs per song** (`pulse/songs/<key>.npz`, 100 Hz, frame t at t/100 s): `rate` (Hz), `phase` (rad), `amp`, `sel` (index), `freq` (natural frequency
of the selected oscillator), `events` (s), and `f_max`. `pulse/songs/<key>.json`: events and the per-song summary of section 5.

## 4. Inputs

The 1,341 songs of the four datasets (`t0/lanes_list_fd.json`, `t0/lanes_list_aioz.json`, `t0_phantom/lanes_list.json`, `t0_motorica/lanes_list.json`),
scanned first (file exists, decodes, length). Librosa beats `beatv/librosa/<key>.json`; project grid `t1b/cortex/beats/` (FineDance) and
`metric/beats/` (others). Per-song errors are caught, logged by name to `pulse/failed.txt` and the run continues.

## 5. Numeric check (pulse vs librosa vs project grid)

For each of the three event series (pulse events, librosa beats, project grid) per song, saved per item in `pulse/check/<key>.json`:
- **tempo** = 60 / median inter-event interval (IOI), BPM; for the pulse also 60 x median rate.
- **metrical level** = ratio of the pulse tempo to the librosa tempo and to the grid tempo; nearest of {1/4, 1/3, 1/2, 2/3, 1, 3/2, 2, 3, 4} and its
  deviation.
- **gaps** = longest IOI (s, and in units of the series' own median IOI); the time to the first event reported separately.
- **local regularity** = windows of 8 consecutive events, hop 2, least-squares line t_k = t0 + T k, residual RMS (ms), median over windows (as BEATV).
- **persistence**, found two ways (both stated before computing):
  (a) **quiet passages**: maximal runs of at least 2 s where the 1 s centred moving mean of the frame RMS (feature column 41) is below 0.5 x the song's
  median of that moving mean, starting at or after 10 s; (b) **grid dropouts**: project-grid IOIs longer than 2 x the grid's median IOI, starting at or
  after 10 s. Per passage and per series: the longest gap inside it, counted with the passage bounds ([start] + events inside + [end], consecutive
  differences), divided by the series' own median IOI; **kept = at most 1.5**. For the pulse also the amplitude at the passage end over that at its start.
- **stability**: number of selection jumps (rule 2 of section 3) per minute; share of frames whose rate is within +-6 % of the song's median rate.
- **tempo following**: librosa windows of 8 beats, hop 2, whose line residual is below 20 ms (regular); local librosa tempo 1/T; local pulse rate =
  median rate inside the window; octave-folded log ratio d = log2(pulse/lib) - round(log2(pulse/lib)); reported: median |d| (as %), share of
  windows with |d| <= log2(1.04); and, in songs whose local librosa tempo varies (SD of log2 tempo over windows > 0.02), the Pearson correlation of
  log2 pulse rate with log2 librosa tempo over windows.

**The 10 V4 songs** (`metric/spotcheck/manifest.json`), on the same 30 s excerpts as `beatv/clicks_visual` (starts from its `key.json`) and on the
whole song: all of the above, from the whole-song causal runs (events inside the excerpt). **Kosta's judged level** (from `docs/BEATV_V4_RESULT.md`):
fd_018 = half of librosa ("we follow the FASTEST element"); librosa level for the songs where librosa was judged "yes" with no level remark (fd_053,
fd_183, aioz_8JQ0, ph_084, ph_102, ph_137, Motorica street); aioz_SZhU "too fast?" = slower than librosa, level not stated; Motorica jazz not stated.
Reported: pulse tempo / judged tempo where stated.

**All songs**, per dataset and overall: tempo quantiles (5/25/50/75/95), share of songs with median pulse BPM-equivalent below 80 and above 150
(above f_max = 147.9 is impossible by construction and reported as a check), longest-gap quantiles, regularity quantiles, the level distribution
against librosa, stability, persistence (share of passages kept, per series), tempo following. No bootstrap (description, no claim).

## 6. Tests (`scripts/body/test_pulse.py`, synthetic audio through `fast_features` and the whole pulse)

Synthetic audio: 60 Hz decaying kick (200 ms) and noise hats (50 ms), 0.005 RMS noise bed, 44.1 kHz.
1. Click (kick) train at 120 BPM, 40 s: median rate after 15 s within 2 % of 2 Hz; events after 15 s have a median offset to the nearest click within
   +-50 ms and SD below 20 ms.
2. The same train with a 4 s digital silence (16-20 s): events continue (longest IOI in 14-24 s at most 0.55 s), the selection stays at 2 Hz, events
   in and after the gap within +-50 ms of the (continued) click grid.
3. 60 BPM kicks with 240 BPM hats: median rate after 20 s is at most f_max and within 4 % of 1 Hz or 2 Hz (an admissible level, not the hats).
4. Tempo ramp 100 -> 120 BPM (100 BPM to 10 s, linear to 120 BPM at 40 s, 120 BPM to 60 s): rate within 7 % of the true tempo over 12-40 s,
   Spearman correlation of rate with true tempo over 10-40 s above 0.9, rate within 2 % of 2 Hz over 50-60 s.
5. f_max formula (2.466 Hz with the stated limits and A); causality: changing audio after time t leaves the drive and the readout before t unchanged.
Tolerances for 1-4 are set from the work order's wording and the synthetic prototype, not from songs.

## 7. Flash-check material (prepared, not served)

Same 10 songs and the same 30 s excerpts as `beatv/clicks_visual`, same rendering (`beatv_clicks_visual.render`: 640x360, 60 fps, white disc at each
event, intensity 1 at the first frame at or after the event, linear fade to 0 over 120 ms, music without clicks). One item per song at the pulse events,
plus one item per song at librosa's beats again (blind comparison) = 20 items, ids assigned in a seeded random order (seed 48101), `key.json` keeps which.
Two questions per item: "Is the flash on the beat?" (yes / partly / no) and "Is it the right speed?" (right / too fast / too slow). `dialstudy_session.py`
asks one question per item, so it gains the smallest option that asks several (manifest field `questions`, a list of {q, labels}; the answer is stored as
the labels joined by "|"), with a test. Folder `pulse/flash/`, manifest `pulse/flash/manifest.json`. Motorica items stay on this laptop.

## FOR USER (defaults taken)

73 oscillators at 24 per octave; drive weights 1.0 / 0.5 / 0.5 (30-200 Hz flux, 200-400 Hz flux, broadband onset) and the 30 ms causal delay;
reference swing A = 5 degrees (f_max 2.466 Hz, 147.9 BPM, shoulder acceleration binding); prior sigma 1 octave; local following +-2 oscillators
plus B1's 20 % / 2 s jump rule; detuning 0 and the P A stimulus form (Velasco & Large 2011 Eq. (3) reconstructed, Large 2010 not read);
quiet = below half the song's median 1 s RMS for at least 2 s; dropout = grid IOI above 2 x its median; kept = longest gap at most 1.5 IOI.
