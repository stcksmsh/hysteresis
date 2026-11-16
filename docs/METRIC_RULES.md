# Metric rules: beat-phase / metrical analysis of human motion (WO46 part 2, BRAIN_SPEC 7.76 point 1, 7.74 Q4) — written before any result

Report only; no training, no verdict. One arm. Decides B's targets (does coupling sit in timing or in character). Code `scripts/body/metric_*.py`.
Out `/secondary/hyst-data/body/metric/` (outside git). **Motorica and anything derived from it stays on this laptop; git gets aggregates only.**
Defaults where the spec is open are marked **(default)** and listed under FOR USER in the night log.

## 1. Beat grids

- FineDance: stored grids `t1b/cortex/beats/<key>.json` (`analyze_mix`). AIOZ, PhantomDance, Motorica: the same `analyze_mix` (as `t1b_cortex.core_input`: ffmpeg mono 44.1 kHz,
  `b2.load_mono`) on their audio (wav lists of the T0 lane runs) -> `metric/beats/<key>.json`. Check: `analyze_mix` rerun on 10 seeded FineDance songs against the stored grids,
  max abs beat-time difference per song (`metric/grids_check.json`).
- Beat times are used as given (no tempo smoothing). A song's grid covers its audio; events outside [first beat, last beat) are dropped.
- Levels: **beat** (phase = fraction of the current inter-beat interval), **half-beat** (double time: phase of 2 subdivisions per beat, = (2f) mod 1), **half-time** (period 2 beats: ((i mod 2)+f)/2),
  **bar** (period 4 beats: (((i-o) mod 4)+f)/4). The parity of half-time and the offset o of the bar are chosen per song by the largest mean onset strength (ear column 40, un-standardised with
  `braindump.stats()`, max within +-30 ms of each beat) over the beats with that residue. **No downbeat source exists: 4/4 assumed, bar phase from onset strength; all bar and half-time results are
  "provisional".** Beat and half-beat need no such choice.
- Motion/audio alignment: motion row t is at audio time t (T0 alignment, the same as the WO43 lanes). No offset is fitted (the lead/lag scan in section 4 reports every offset).

## 2. Material

- Four paired datasets (FineDance, AIOZ, PhantomDance, Motorica), **whole sequences** (the whole `targets` of each T0 sequence, not 20 s windows). Realised stage: one pass over the whole
  sequence through the WO43 chain (`controls_run.sim_file` recipe: pre-roll 1.5 s of the first row, yaw/roll re-referenced to the first row, guard, `motornet.spinal`, limiter, servo, v2p body);
  50 Hz `q50` and lamp = point 5 of `m3f_report.fk_points`. Code `metric_sim.py`.
- Copies: **V1 main, V2 alongside** (V2 is sharper, 7.75 pending). **Mirrors (V1m, V2m) excluded** (they flip x/y and would double-count the same dancer).
- Unit = the T0 sequence copy; **resampling unit = the song group** (`group` in the T0 npz: FineDance song group, AIOZ YouTube id, Phantom/Motorica group), with all its dancers and copies.
  Per-song statistics are first computed per sequence copy, then averaged within the song group.
- **Gate treatment (default):** the T0 gate is per 20 s window (`win_pass`, window w = rows 2000w..2000w+2000 at 100 Hz = samples 1000w.. at 50 Hz). Two sets reported side by side:
  **ALL** = every event/token of the whole realised sequence; **PASS** = only events and tokens inside windows with `win_pass` true (the tail after the last whole window counts as not passing).
  Tables mark which. The main text of the report quotes ALL for the V1 copy and gives PASS next to it.
- Realised lamp trajectory and **each joint separately** (the 5 joints: base yaw, shoulder, elbow, wrist bend, wrist roll).

## 3. Motion events (sample rate 50 Hz; definitions fixed here)

Let v = lamp velocity (np.gradient x 50), speed = |v|, a = np.gradient(v) x 50, w_j = np.gradient(q50_j) x 50 (deg/s). `box5(x)` = 5-sample centred box (reflect). `find_peaks` = `scipy.signal.find_peaks`.
Constants: A = FineDance-train p95 of |a| and p90_j = FineDance-train p90 of |w_j| from `controls/norm.json`; P = p90 of lamp speed over the FineDance V1 whole sequences (computed once, stored).

| id | event | rule | minimum separation |
|---|---|---|---|
| E1 | lamp-speed local minimum | find_peaks(-box5(speed)), prominence >= 0.05 m/s | 10 samples (0.2 s) |
| E2 | lamp-acceleration peak | find_peaks(box5(\|a\|)), prominence >= 0.25 A | 10 samples |
| E3_j | joint angular-velocity peak (each joint j) | find_peaks(box5(\|w_j\|)), prominence >= 0.25 p90_j | 10 samples |
| E4 | direction reversal | E1 minima where the angle between mean v over [t-0.20, t-0.04] s and over [t+0.04, t+0.20] s exceeds 120 deg and both mean speeds >= 0.10 m/s | as E1 |
| E5 | movement onset | `controls_lib.onsets(speed, P)`: speed crosses 0.25 P upward after dipping below 0.125 P within the previous 10 samples; a later onset within 15 samples of the previous one is dropped | 15 samples (0.3 s) |

Event time = sample index / 50 s. Per-joint onsets are not defined (E3_j only).

## 4. Phase statistics

- Per song, event type and level: phase phi in [0,1) from section 1; mean resultant R = |mean exp(2 pi i phi)|; preferred phase = arg of the mean resultant (reported as fraction of the period).
  Songs/levels with < 30 events are excluded from that cell (counted). Chance level of R for n uniform events ~ 1/sqrt(n) (reported next to it).
- Dataset value = mean of per-song R over song groups; **bootstrap by song group, 2,000 resamples, seed 46101, 95 % percentile interval** for every reported mean/difference. Pooled preferred
  phase = arg of the mean over songs of the per-song mean-resultant vectors (each song equal weight); the spread of per-song preferred phases is reported as the R of the unit vectors.
- **Lead/lag scan:** hit rate H(L) = share of events within +-50 ms of a beat time shifted by L, L = -250 ... +250 ms in **steps of 25 ms (21 lags)**; **every lag reported, no maximum is
  singled out in the tables** (the figure marks nothing as "best"). Also the median signed offset event - nearest beat (ms) at L = 0. The scan is run at beat level and half-beat level (grid at b + k/2 ibi).
  (R itself is invariant to a uniform shift of an exactly periodic grid, so the scan uses H.)
- **Controls**, applied to every statistic above (R at each level, H(L)):
  (a) **time-shuffled beats:** the song's inter-beat intervals randomly permuted (seeded per song, seed 46102, 100 permutations), first beat kept, so tempo distribution is preserved and alignment destroyed;
  (b) **other songs' beat grids, tempo-matched:** donor = another song of the same dataset (other group) whose median inter-beat interval is within 5 % of the song's; if fewer than 5 donors, donors from
  all datasets; 20 donors drawn per song (seed 46103), the donor's grid shifted so its first beat equals the song's first beat and tiled (repeating its intervals) to cover the sequence.
  Control value of a statistic = mean over draws; **excess = real - control**, bootstrap by song.
- **Tests** (`test_metric.py`): synthetic events locked to a known phase give that phase and R near 1; uniformly random events give R near 1/sqrt(n); the lag scan recovers a known shift of the grid (H peaks at the injected L).

## 5. Tempo, density, pauses

- Tempo = 60 / median inter-beat interval (BPM). Motion-event rate = events per minute per type. **Onset density** = peaks per second of onset strength (ear col 40 un-standardised, find_peaks,
  prominence >= 1 robust sd (1.4826 MAD) of the song, distance 0.1 s). **Pulse clarity, two measures:** (P1) maximum of the normalised autocorrelation of onset strength for lags 0.3-1.2 s (0..1);
  (P2) mean onset strength at beats (max within +-30 ms) / mean onset strength over all frames.
- Pauses: lamp speed < 0.05 m/s for >= 13 samples (`controls_lib.pause_mask`). **Pause occupancy** = share of time inside pauses; **long-pause occupancy** = share of time inside pauses of
  duration 2-8 s (pauses > 8 s counted in a separate "> 8 s" share); mean duration and count per minute of the 2-8 s pauses.
- Relations (across song groups): Spearman of event rate against tempo and against onset density; of pause occupancy, long-pause occupancy against onset density, P1 and P2. Bootstrap by song, 2,000, seed 46104.

## 6. Whole-song structure

- **Token grid:** 0.5 s (25 samples). **Motion controls on whole songs:** `controls_lib.raw_window`/`finalise` on consecutive 1000-sample windows (T0 window grid, last partial window dropped) with
  `controls/norm.json`; per-token vector = (vigour, height, sharp [NaN -> 0], pause_prob, accent_mean), z-scored within the song. The controls are token controls of the 7.74 set (vigour, height, accent_mean, sharpness, pause probability).
  **Motifs:** the movement motif is the **4-token (2 s) block of that control vector** (no gesture-code n-grams: codes exist only for FineDance; **(default)**, the n-gram variant is logged FOR USER).
- **Music features per token** (`controls_stats.music_features`): ear (44) + mode amplitudes (32) from the T0 token files for every dataset; for FineDance also the frozen cortex token means (2048 components).
  Z-scored within the song.
- **Change points:** `controls_stats.novelty` (cosine SSM, Gaussian-tapered checkerboard) at two scales, half-width 4 tokens (2 s, sigma 2) and 16 tokens (8 s, sigma 8); boundaries = local maxima >= mean + 1 sd,
  at least half-width tokens apart (`controls_stats.peaks`). Motion side: control vector; motif side: the 4-token block vector (novelty computed on the block features, stride 1).
  **Repetition** = `controls_stats.repetition` (4-token block, any block >= 8 tokens away, whole song).
- **Alignment vs music, delays -2..+2 s in steps of 0.5 s (-4..+4 tokens):** share of motion boundaries with a music boundary within +-1 token after shifting the music boundaries by the delay, against
  **200 circular shifts** (>= 10 tokens, seeded 46105) of the music boundaries over the song (chance); excess = real - mean of circular shifts. Novelty-curve Pearson correlation and repetition-curve
  Spearman correlation between motion (control and motif) and music, at each delay, against the same circular-shift null (mean and 95 % band). Bootstrap by song, 2,000, seed 46106.
  Music-side for FineDance reported separately for ear and cortex features.
  **Amendment (before any result was reported; first run showed an edge artefact, short AIOZ clips gave implausibly large excess):** all boundary/curve statistics are cut to tokens 16..n-16 (16 = widest kernel half-width, so
  novelty/repetition edge profiles are removed), the null rotates the music inside that interval (no wrap into the edge region), sequences with fewer than 62 tokens give no structure result; the sum of
  the novelty kernel at the edges is never compared across real and null. Test: unrelated feature streams of a 75-token clip give excess ~0.
- **Side table: WO43 Step 0c on whole songs.** Controls (vigour, vj, vl, height, sharp, pause_prob, accent_mean, dir_z) against the acoustic token measures of `controls_stats.acoustic` (RMS, spectral flux,
  onset strength, low-band, high-band, centroid, local dynamic range, beat strength for FineDance and for the others now from the new grids), Pearson and Spearman: global, within-song (song mean removed),
  per-song Spearman median/quartiles/share positive (songs with >= 60 tokens), lags -2..+2 tokens (control of token k against measure of token k+L), bootstrap by song (seed 46107, 200).

## 7. Spot check (prepared only)

10 songs seeded (46108), balanced across datasets (FineDance 3, AIOZ 2, PhantomDance 3, Motorica 2) among songs with >= 90 s of audio; music-side boundaries = the 8 s-scale ear-feature novelty boundaries (section 6) in the
song; excerpts of +-8 s around each boundary (at most 6 boundaries per song, strongest first, ffmpeg lossless to wav) in `metric/spotcheck/` with `manifest.json` (song, dataset, boundary times, excerpt files). Not served.
Motorica excerpts stay on this laptop and are marked.

## 8. Tests (`scripts/body/test_metric.py`, synthetic)

Phase of events locked to known phase at each level; R near 1 and near the chance level for uniform events; lag-scan shift recovery; shuffled-IBI keeps the intervals' multiset and the first beat; donor tiling covers the span;
E1-E5 on synthetic signals (a sinusoidal speed gives minima at known times; reversal on a back-and-forth line; onset after rest); novelty peak at a built-in change point; circular shift keeps the shift >= 10 tokens.

## 9. Outputs

`metric/q50/<dataset>/<name>.npz`, `metric/beats/<key>.json`, `metric/events/<dataset>.npz`, `metric/results/*.json` (per-song values), `docs/METRIC_REPORT.md`, `docs/NIGHT_LOG_body-diag.md`.

## FOR USER (defaults taken)

1. V1 main / ALL main with PASS alongside; mirrors excluded. 2. 30-event minimum per cell. 3. 50 ms hit window, 25 ms lag step. 4. Bar/half-time provisional (4/4, onset strength). 5. Motif = 4-token control block
(gesture-code n-grams only for FineDance, not done). 6. Zero motion/audio offset. 7. Whole sequences are one simulation pass; the tail beyond the last full 20 s window counts as not passing.
