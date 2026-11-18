# Movement rhythm vs beat and event responses in human data: rules (WO52, BRAIN_SPEC 7.81 item 4) — written and pushed before any result

Report only. No change to A or B, nothing trained, no verdict. One arm. Code `scripts/body/rhythm_events.py` (one file), tests
`scripts/body/test_rhythm_events.py` (synthetic only). Out: `/secondary/hyst-data/body/rhythm/`. When these rules were pushed only the
synthetic tests had been run and the inputs had been scanned for presence (4,056 non-mirror window files, every one with librosa beats, a
pulse v2 file and T0 lanes); no rhythm, response or event value had been computed on human data. Defaults are marked **(default)** and
listed under FOR USER.

## 0. Data (read-only, nothing recomputed upstream)

- **Human windows = A's windows:** every kept 20 s window of `grammar/win_<ds>.npz` (the windows A trains and checks on, all splits), four
  datasets (FineDance, AIOZ, PhantomDance, Motorica). Window w of a sequence covers song time [20 w, 20 w + 20) s (T0 grid, token k of the
  window = [20 w + 0.5 k, 20 w + 0.5 k + 0.5) s).
- **Copies:** V1 and V2 (the two retargetings). **The mirror copies V1m / V2m are left out** **(default)**: a mirrored motion has the same
  speeds and the same token timing, so it would count one performance twice. V1 and V2 are pooled in the main tables (one performance gives
  two windows; the bootstrap resamples whole songs, so this does not narrow intervals); a per-copy split is reported.
- **Motion as retargeted to the arm:** `controls/q50/<ds>/<key>.npz`, realised joints `q50` (1001 x 5, deg) and lamp point `lamp`
  (1001 x 3, m) per kept window, 50 Hz (the same trajectory the A controls were measured on). Per-token controls version 2 (`ctl`, 18 per
  token), gesture code 1 (`code1`) from `grammar/win_<ds>.npz`. Absolute posture from `t0*/seq/<key>.npz` field `posture` (100 Hz, 5 joints,
  deg; token = mean of its 50 rows).
- **Music key** = the sequence key before `__`, with AIOZ's performer suffix `_pN` removed. Beat sources: librosa beats
  `beatv/librosa/<song>.json` (WO47 section 0); pulse v2 `pulse2/songs/<song>.npz` (`period`, `conf`, `boundaries`, 100 Hz). Ear features
  and cortex surprisal from the T0 lanes (`ear` 100 Hz, `s10` 10 Hz), as `cortexev.py`.
- **Bootstrap unit = song group** (`group` of the window file, the T0 split unit: all copies and, for AIOZ, all performers of a clip share
  it). Songs under 12 s are excluded (7.79 Q4); every song with a kept 20 s window is longer, so none is excluded by this rule (counted).
- Motorica stays local: only dataset aggregates leave the laptop.

## 1. Movement rhythm

- **Analysis windows:** W = 3 s **(default)**, hop 1 s, inside each 20 s window: starts 0, 1, ..., 17 s (18 per window, samples
  [50 s, 50 s + 150)). Variant W = 4 s (starts 0..16).
- **Signals:** main = lamp speed |d lamp / dt| (np.gradient at 50 Hz, m/s). Report-only variants: joint speed = sum over the 5 joints of
  |d q50 / dt| (deg/s); yaw speed = |d base yaw / dt|.
  Note on meaning: a speed signal has two minima per back-and-forth swing, so a swing of period P gives a speed period of P / 2. The measured
  "movement period" is the period of the speed pulsation (stops and pushes), as in the kinematic-beat literature (BAS uses speed minima).
- **Detrending:** the window's linear least-squares trend is removed (`scipy.signal.detrend`, linear).
- **Autocorrelation:** biased estimate, a(l) = sum_t x_t x_{t+l} / sum_t x_t^2 (normalised so a(0) = 1). Biased on purpose: a period T in a
  window W can reach at most (W - T) / W, so long lags with little overlap are not inflated (with W = 3 s and strength >= 0.2 the longest
  detectable period is about 2.4 s; stated, not corrected). A window whose speed variance is below 1e-12 is "none".
- **Peak rule:** candidate lags l in [10, 125] samples (0.2-2.5 s) with a(l) > a(l - 1) and a(l) >= a(l + 1) (local maxima); the
  **highest** one is the peak; its lag is refined by a parabola through l - 1, l, l + 1. No local maximum in the range -> "none".
  **Period** = refined lag / 50 s; **rhythm strength** = a at the integer peak lag.
- **Beat period, per analysis window [a, b):**
  - librosa = median of the inter-beat intervals of the librosa beats lying in [a - 1.5 s, b + 1.5 s] **(default)**; fewer than 3 intervals
    -> no value (the window is counted as missing for this source);
  - pulse v2 = median of `period` over the 100 Hz frames in [a, b); also the median `conf` there (reported as a split: conf >= 0.3 vs < 0.3).
- **Ratio** r = movement period / beat period.
- **Bins:** "none" when strength < 0.2 or no peak; else "1/2" for r in [0.4, 0.6], "1" in [0.8, 1.25], "2" in [1.6, 2.5] (closed intervals),
  otherwise "other". **Sensitivity variant (narrow):** [0.45, 0.55], [0.9, 1.11], [1.8, 2.22], none below 0.3.
- **Rhythmic windows** = windows not "none". **Cluster share** = share of rhythmic windows in {1/2, 1, 2}. Bin shares are also given over all
  windows (none included).

## 2. Analysis A: ratio distribution against chance

Per dataset (and pooled), per beat source, per signal and variant:
- histogram of log2 r over rhythmic windows (bins of 0.05 from -3 to +3, saved; a coarse 1/6-octave table and a PNG in the report folder);
- bin shares; cluster share; circular concentration C = |mean exp(2 pi i log2 r)| over rhythmic windows (1/2, 1, 2 all map to phase 0).
- **Chance 1, similar-tempo song:** each rhythmic window's beat period is replaced by the local beat period of a random analysis window of
  another song of the **same dataset** **(default)** with a different group whose song tempo (median local beat period over its analysed
  windows, same source) is within +-10 % of this song's; 20 draws per window **(default)**, seed 52103 **(default)**. Songs with no such
  partner are left out of this comparison (counted).
- **Chance 2, shuffled:** the beat periods of all analysed windows of the dataset permuted among them (same source); 20 permutations,
  seed 52104 **(default)**.
- The movement period and strength are unchanged under both chances, so the rhythmic set is the same; chance cluster share and chance C use
  the replaced periods (windows whose replacement is missing are dropped from that chance).
- **Clustering measure** = cluster share minus chance cluster share; and C minus chance C. Per song the counts (rhythmic windows, in-cluster
  windows, sum of exp(2 pi i log2 r)) and the chance expectations (mean over draws) are stored; **bootstrap by song group, 2,000 resamples,
  seed 52101**, 95 % percentile interval of each excess, observed and chance resampled together.

## 3. Event responses per token (the existing token grid)

Computed on **segments** = runs of consecutive kept windows of one sequence copy (so a response at a window junction is seen); the first
token of a segment has no predecessor and gives no response. Times are song time.
- **hold** = pause onset: token k with pause control (ctl 14) >= 0.2 and token k - 1 < 0.2 **(default threshold 0.2 = 5 of 25 samples)**.
  Time = the first sample of the still run (lamp speed < 0.05 m/s for >= 13 samples, `controls_lib.pause_mask` on the window's lamp) that
  overlaps token k (sub-token timing; the run may start in token k - 1).
- **change** = token k whose gesture family differs from token k - 1's (family = code 1 grouped into 32 families, k-means of the run-B
  stage-1 codebook, seed 45004, as A_RULES 6.5), **or** whose absolute posture differs from token k - 1's by more than D, Euclidean over the
  5 joints in degrees, D = the 90th percentile of all consecutive-token posture distances of the analysed tokens (pooled over datasets)
  **(default)**. The two parts are also reported separately (`change_fam`, `change_post`). Time = start of token k (the boundary).
- **burst** = vigour (ctl 0) of token k minus token k - 1 > 1.0 x sd **(default)**, sd = standard deviation of vigour over all analysed
  tokens (pooled). Variant 1.5 sd. Time = start of token k.

## 4. Music events (per song, whole song, from the lanes and pulse v2)

- **onset** = peaks of ear column 40 (raw onset strength) with `cortexev.peaks`' rule (causal 0.3 s mean on the 10 Hz stamps, maximum within
  +-1 s, above every value in the preceding 1 s) at the song's **95th** percentile instead of 90th.
- **dropout_on / dropout_end** = `cortexev.dropouts` with the **low band only** (WO50 amendment): c(t) = L(t) < 0.25 x running median of L
  (10 s before, frozen while a dropout is open), no onset condition; run >= 0.4 s; end after >= 0.3 s of recovery. Fraction 0.25 as cortexev.
- **novelty** = pulse v2's causal novelty boundaries (`boundaries` in the song's pulse2 file).
- **cortex_L2, cortex_total** = `cortexev.peaks` on `s10` columns 1 and 4 (p90 rule), threshold over the song's finite stamps (from 16 s
  for total, which needs L4; L2 is finite earlier).
- Event times are the stamp/boundary times as stored (no latency correction).

## 5. Analysis B: event-locked response rates

For each response type x music event, per song group and pooled per dataset:
- An event counts if [e - 1.1 s, e + 1.1 s] lies inside one segment (span = segment's first token start + 0.5 s to its end).
- Lags -1.0 .. +1.0 s in 0.1 s bins, bin j = [-1.0 + 0.1 j, -0.9 + 0.1 j), j = 0..19; lag = response time - event time (positive = response
  after the music event). Rate in bin j = responses in it / (counted events x 0.1 s) (responses per second).
- **Chance:** the response times of each segment shifted circularly within the segment's span by a uniform random offset, independent per
  segment, **200 shifts** (>= 100), seed 52102; chance rate = mean over shifts. Excess(j) = observed - chance.
- **Peak excess** = max over j of the pooled excess; its lag (bin centre); interval: bootstrap by song group (2,000, seed 52101) of the excess
  at that bin; **max-statistic p** = share of shifts (each shift's curve minus the mean of all shifts) whose maximum excess is >= the observed
  peak (corrects for picking the best of 20 bins); also the mean excess over [-0.3, +0.3] s with its interval, and the ratio
  observed / chance at the peak.
- Saved per song: counts per bin, chance counts per bin, events counted.

## 6. Outputs

`/secondary/hyst-data/body/rhythm/`: `scan.json`, `windows_<ds>.npz` (per analysis window: key, copy, group, start, period, strength per signal
and W, librosa and pulse periods, pulse conf), `responses_<ds>.npz` (per token response flags and times), `events.json` (music events per
song), `results.json` (every table), `lock_<ds>.npz` (per-song lock counts), `hist.png`; report `docs/RHYTHM_EVENTS_REPORT.md`. The report
states which outcome 7.81 item 4's rule points to (clusters present or absent) as the cluster-share excess over chance; no verdict beyond that.

## 7. Tests (`test_rhythm_events.py`)

A lamp moving round a circle with speed pulsing at the beat period gives r = 1 (bin "1"); pulsing at twice the beat period gives r = 2;
a back-and-forth sinusoid of period 2 beats gives r = 1 (speed halves the period); white noise speed gives "none"; a response planted 0.3 s
after each music event gives the peak excess in the +0.3 s bin and none at shuffled events; the circular shift keeps times inside the span.

## FOR USER (defaults taken)

1. Mirrors left out; V1 and V2 pooled.
2. W = 3 s main, 4 s variant; biased autocorrelation, linear detrend, highest local maximum in 0.2-2.5 s.
3. librosa local period = median IOI within the window +-1.5 s, >= 3 intervals.
4. Similar-tempo chance within the same dataset, 20 draws, seed 52103; shuffle 20 permutations, seed 52104.
5. hold threshold 0.2; change = family change or posture distance > pooled p90; burst > 1.0 sd (variant 1.5).
6. Response time = token boundary (change, burst) or still-run start (hold).
