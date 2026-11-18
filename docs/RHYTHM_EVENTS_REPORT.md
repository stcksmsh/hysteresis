# Movement rhythm vs beat and event responses in human data: report (WO52, BRAIN_SPEC 7.81 item 4)

Report only; no verdict, nothing trained, A and B unchanged. Rules: `docs/RHYTHM_EVENTS_RULES.md` (pushed in `5cb8e7a` before any result).
Code `scripts/body/rhythm_events.py`, tests `scripts/body/test_rhythm_events.py` (8, synthetic, pass). Every table (per dataset, source,
signal, variant, copy, pulse-confidence split, histograms, per-dataset event-lock tables): `docs/RHYTHM_EVENTS_TABLES.md`.
Per-window, per-token, per-song values: `/secondary/hyst-data/body/rhythm/` (`windows_<ds>.npz`, `tokens_<ds>.npz`, `events.json`,
`lock_<ds>.npz`, `results.json`). Motorica appears only as dataset aggregates.

## Data and run

- Input scan: 0 bad. Non-mirror sequences (V1 + V2) / kept 20 s windows / songs / song groups: FineDance 375 / 1,658 / 197 / 166;
  AIOZ 3,084 / 4,664 / 700 / 198; PhantomDance 450 / 1,677 / 244 / 244; Motorica 147 / 860 / 74 / 74. No song is under 12 s.
- Units `hyst-wo52-ext2` (scan + extract, 0 failures) and `hyst-wo52-ana1` (analyses), cores 14-19. The first unit (`ext1`) ran out of
  memory in the scan (each row kept a view of a freshly loaded array); fixed and rerun before any output. The analysis unit wrote
  `results.json` and then failed on the histogram PNG (matplotlib is not in the env, no installs allowed); the PNG was dropped, histograms
  are given as tables (rules section 2 named a PNG: deviation).
- 3 s analysis windows: 157,026 with a librosa period, 159,462 with a pulse v2 period (all datasets).

## A. Movement-rhythm ratio

Movement periods (lamp speed, rhythmic windows) are long relative to the beat: median period 1.2-1.3 s per dataset (quartiles about
0.7-0.8 / 1.8 s), median ratio to the librosa beat 2.2-2.7 (to pulse v2 1.9-2.4). About two thirds of windows pass strength 0.2
(0.63-0.71); 30 % pass the narrow variant's 0.3. Of rhythmic windows, 55-66 % fall in "other" (mostly r > 2.5). The log2 histograms
(TABLES) rise smoothly towards r = 2-4 with no sharp peaks at 1/2, 1 or 2.

**Main rule, lamp speed, W = 3 s (shares of rhythmic windows; excess with 95 % song-group bootstrap interval):**

| | cluster share {1/2,1,2} | chance 1, similar-tempo song | excess 1 | chance 2, shuffled | excess 2 |
|---|---|---|---|---|---|
| all, librosa | 0.398 | 0.397 | +0.001 [-0.001, +0.003] | 0.380 | +0.018 [+0.010, +0.027] |
| all, pulse v2 | 0.435 | 0.435 | +0.000 [-0.003, +0.004] | 0.420 | +0.015 [+0.008, +0.022] |

Per dataset, excess 1 lies within -0.009..+0.003 with every interval including 0 except Motorica/pulse v2 (-0.009 [-0.018, +0.001]
includes 0 too); excess 2 is above 0 only for AIOZ (+0.026 librosa, +0.023 pulse v2), the others -0.001..+0.014 with intervals including 0.
Circular concentration of log2 r mod 1 is low (C = 0.03-0.14); its excess over chance 1 is +0.007 [+0.005, +0.010] (librosa) and
+0.012 [+0.007, +0.017] (pulse v2) pooled, over chance 2 +0.071 / +0.050.

Variants (pooled, excess 1 / excess 2 of the cluster share): narrow edges and strength >= 0.3: +0.017 [+0.014, +0.021] / +0.072 (librosa),
+0.014 / +0.050 (pulse v2), carried mostly by AIOZ (+0.022 / +0.101); W = 4 s: +0.000 / +0.021; joint speed +0.001 / +0.033; yaw speed
+0.000 / +0.043. V1 and V2 agree. Pulse-confidence split: conf >= 0.3 excess 1 -0.009 [-0.013, -0.004], conf < 0.3 +0.005.

**Reading of the two chances, stated:** chance 1 keeps the song's tempo within ±10 % while the bins are ±20-25 % wide, so a window
locked to its own beat still lands in the same bin with a similar-tempo partner's period; excess 1 therefore measures what the
song's own beat adds beyond its tempo class. Chance 2 (shuffled within dataset) also removes the tempo match; excess 2 measures what
tempo matching adds beyond the dataset's tempo distribution.

**Item 4's rule (clusters present or absent), as numbers against chance:** with the main rule and the chance named first (similar-tempo
song), the share of rhythmic windows at 1/2, 1 or 2 beats exceeds chance by **+0.001 [-0.001, +0.003] (librosa) and +0.000 [-0.003, +0.004]
(pulse v2)**: this points to **clusters absent** beyond the tempo class. Against the shuffled-period chance the excess is **+0.018
[+0.010, +0.027] / +0.015 [+0.008, +0.022]** (4-5 % relative, mainly AIOZ), and the stricter narrow variant gives +0.017 / +0.014 against the
similar-tempo chance: small clustering, concentrated in AIOZ and in the strongest-rhythm windows. No verdict beyond these numbers.

## B. Event responses vs music events

Response rates per second of covered motion (pooled): hold 0.036, burst 0.136 (1.5 sd: 0.046), change 1.951, of which family change
1.948 and posture change 0.200. **The family-change part fires at nearly every token boundary (the maximum is 2 per s)**, so "change" is
almost the token grid itself; its event lock is a token-level grid effect more than a response. The posture threshold D = 37.0 deg (pooled
p90) is dominated by AIOZ's token count: AIOZ posture changes 0.026/s against 0.26-0.44/s elsewhere. Vigour sd 0.905.

Event counts in B are summed over sequence copies (V1 and V2 and AIOZ performers each count the same music event once).
Top peak excesses (pooled over datasets; responses/s, lag bin centre, positive = response after the music event; max-stat p over the 20
lags, 200 shifts):

| response x event | peak excess @ lag | 95 % CI | ratio to chance | max-stat p | mean excess ±0.3 s |
|---|---|---|---|---|---|
| hold x novelty (pulse v2) | +0.028 @ -0.65 s | [+0.014, +0.045] | 1.78 | 0.005 | +0.000 [-0.004, +0.005] |
| hold x cortex L2 | +0.015 @ -0.25 s | [+0.006, +0.024] | 1.42 | 0.010 | +0.006 [+0.003, +0.010] |
| hold x dropout end | +0.015 @ -0.85 s | [+0.003, +0.027] | 1.42 | 0.060 | -0.003 |
| hold x dropout onset | +0.013 @ -0.45 s | [+0.003, +0.026] | 1.37 | 0.070 | +0.004 |
| hold x onset peak | +0.010 @ -0.75 s | [+0.002, +0.017] | 1.27 | 0.050 | -0.000 |
| burst x dropout end | +0.051 @ -0.45 s | [+0.014, +0.099] | 1.38 | 0.005 | +0.008 [-0.006, +0.023] |
| burst (1.5 sd) x dropout end | +0.023 @ -0.45 s | [+0.003, +0.048] | 1.51 | 0.005 | +0.005 |
| burst (1.5 sd) x cortex L2 | +0.016 @ +0.25 s | [+0.003, +0.029] | 1.35 | 0.005 | +0.002 |
| burst x onset peak | +0.018 @ -0.15 s | [+0.001, +0.036] | 1.13 | 0.050 | +0.005 |
| change x cortex total | +0.180 @ -0.65 s | [+0.051, +0.329] | 1.09 | 0.005 | -0.001 |
| change x dropout end | +0.157 @ -0.45 s | [+0.031, +0.292] | 1.08 | 0.005 | +0.004 |
| change (posture) x onset peak | +0.021 @ +0.45 s | [+0.004, +0.040] | 1.11 | 0.065 | -0.002 |

- The largest relative effects are holds (1.3-1.8 x chance) and bursts at dropout ends (1.4-1.5 x), mostly at negative lags (the response
  before the detected event time). Detection times are stamps, not perceptual times: the pulse v2 novelty boundary is a causal detector
  (compares the last 1 s with the 1 s before, plus 30 ms delay) and the dropout end is the first stamp of a 0.3 s recovery, so negative lags
  of 0.3-0.8 s are partly where these detectors place the event.
- The mean excess over ±0.3 s is near zero for every pair except hold x cortex L2 (+0.006 [+0.003, +0.010]).
- Per-dataset tables in TABLES; the pooled table follows.

## Main tables (copied from TABLES)

### Ratio bins: signal lamp, variant main, subset all

| dataset | source | groups | windows | rhythmic share | 1/2 | 1 | 2 | other | cluster share | chance 1 (similar tempo) | excess 1 [95 % CI] | groups out (1) | chance 2 (shuffled) | excess 2 [95 % CI] | C | C excess 1 [CI] | C excess 2 [CI] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| finedance | librosa | 166 | 29408 | 0.639 | 0.014 | 0.124 | 0.227 | 0.635 | 0.365 | 0.363 | +0.002 [-0.001, +0.005] | 0 | 0.357 | +0.008 [-0.007, +0.022] | 0.049 | +0.002 [-0.003, +0.007] | +0.035 [+0.018, +0.053] |
| finedance | pulse2 | 166 | 29844 | 0.638 | 0.024 | 0.140 | 0.247 | 0.589 | 0.411 | 0.413 | -0.001 [-0.008, +0.006] | 0 | 0.405 | +0.007 [-0.011, +0.024] | 0.034 | +0.001 [-0.008, +0.012] | +0.022 [+0.007, +0.040] |
| aioz | librosa | 198 | 82645 | 0.710 | 0.024 | 0.156 | 0.239 | 0.581 | 0.419 | 0.417 | +0.001 [-0.002, +0.004] | 1 | 0.393 | +0.026 [+0.014, +0.040] | 0.141 | +0.012 [+0.008, +0.016] | +0.101 [+0.084, +0.118] |
| aioz | pulse2 | 198 | 83952 | 0.709 | 0.057 | 0.182 | 0.215 | 0.545 | 0.455 | 0.452 | +0.003 [-0.002, +0.009] | 0 | 0.432 | +0.023 [+0.012, +0.035] | 0.100 | +0.021 [+0.014, +0.029] | +0.074 [+0.058, +0.091] |
| phantom | librosa | 244 | 29845 | 0.626 | 0.012 | 0.123 | 0.210 | 0.655 | 0.345 | 0.345 | -0.000 [-0.003, +0.003] | 0 | 0.339 | +0.006 [-0.003, +0.016] | 0.076 | +0.000 [-0.004, +0.004] | +0.028 [+0.016, +0.042] |
| phantom | pulse2 | 244 | 30186 | 0.625 | 0.024 | 0.135 | 0.227 | 0.614 | 0.386 | 0.389 | -0.003 [-0.008, +0.003] | 0 | 0.380 | +0.007 [-0.005, +0.019] | 0.060 | +0.002 [-0.007, +0.011] | +0.024 [+0.010, +0.038] |
| motorica | librosa | 74 | 15128 | 0.711 | 0.026 | 0.147 | 0.267 | 0.560 | 0.440 | 0.436 | +0.003 [-0.002, +0.009] | 0 | 0.426 | +0.014 [-0.010, +0.037] | 0.051 | +0.009 [+0.003, +0.015] | +0.029 [+0.006, +0.053] |
| motorica | pulse2 | 74 | 15480 | 0.709 | 0.031 | 0.151 | 0.264 | 0.554 | 0.446 | 0.454 | -0.009 [-0.018, +0.001] | 0 | 0.447 | -0.001 [-0.018, +0.016] | 0.034 | +0.010 [-0.003, +0.023] | +0.024 [+0.005, +0.047] |
| all | librosa | 682 | 157026 | 0.681 | 0.020 | 0.144 | 0.234 | 0.602 | 0.398 | 0.397 | +0.001 [-0.001, +0.003] | 1 | 0.380 | +0.018 [+0.010, +0.027] | 0.103 | +0.007 [+0.005, +0.010] | +0.071 [+0.059, +0.082] |
| all | pulse2 | 682 | 159462 | 0.680 | 0.043 | 0.164 | 0.228 | 0.565 | 0.435 | 0.435 | +0.000 [-0.003, +0.004] | 0 | 0.420 | +0.015 [+0.008, +0.022] | 0.073 | +0.012 [+0.007, +0.017] | +0.050 [+0.040, +0.061] |


### Event lock, all: peak excess (responses/s) at lag (bin centre, s) [95 % CI], ratio to chance, max-stat p; mean excess over -0.3..+0.3 s [CI]; events

| response | onset | dropout_on | dropout_end | novelty | cortex_L2 | cortex_total |
|---|---|---|---|---|---|---|
| hold | +0.010 @ -0.75 [+0.002, +0.017], x1.27, p 0.050; ±0.3: -0.000 [-0.003, +0.003]; n 32033 | +0.013 @ -0.45 [+0.003, +0.026], x1.37, p 0.070; ±0.3: +0.004 [-0.001, +0.009]; n 14651 | +0.015 @ -0.85 [+0.003, +0.027], x1.42, p 0.060; ±0.3: -0.003 [-0.008, +0.003]; n 14419 | +0.028 @ -0.65 [+0.014, +0.045], x1.78, p 0.005; ±0.3: +0.000 [-0.004, +0.005]; n 12635 | +0.015 @ -0.25 [+0.006, +0.024], x1.42, p 0.010; ±0.3: +0.006 [+0.003, +0.010]; n 26400 | +0.011 @ -0.45 [+0.001, +0.022], x1.31, p 0.174; ±0.3: -0.001 [-0.005, +0.003]; n 15504 |
| change | +0.055 @ -0.15 [-0.049, +0.163], x1.03, p 0.080; ±0.3: +0.003 [-0.013, +0.017]; n 32033 | +0.103 @ +0.65 [-0.007, +0.216], x1.05, p 0.020; ±0.3: -0.004 [-0.025, +0.018]; n 14651 | +0.157 @ -0.45 [+0.031, +0.292], x1.08, p 0.005; ±0.3: +0.004 [-0.020, +0.031]; n 14419 | +0.094 @ -0.55 [-0.034, +0.223], x1.05, p 0.030; ±0.3: -0.011 [-0.030, +0.009]; n 12635 | +0.073 @ -0.45 [-0.021, +0.166], x1.04, p 0.015; ±0.3: -0.006 [-0.022, +0.010]; n 26400 | +0.180 @ -0.65 [+0.051, +0.329], x1.09, p 0.005; ±0.3: -0.001 [-0.019, +0.017]; n 15504 |
| change_fam | +0.059 @ -0.15 [-0.046, +0.168], x1.03, p 0.065; ±0.3: +0.002 [-0.013, +0.016]; n 32033 | +0.096 @ +0.65 [-0.015, +0.208], x1.05, p 0.035; ±0.3: -0.004 [-0.025, +0.018]; n 14651 | +0.161 @ -0.45 [+0.035, +0.296], x1.08, p 0.005; ±0.3: +0.003 [-0.022, +0.029]; n 14419 | +0.097 @ -0.05 [-0.034, +0.225], x1.05, p 0.040; ±0.3: -0.009 [-0.028, +0.011]; n 12635 | +0.073 @ -0.45 [-0.021, +0.164], x1.04, p 0.010; ±0.3: -0.005 [-0.021, +0.010]; n 26400 | +0.185 @ -0.65 [+0.056, +0.334], x1.10, p 0.005; ±0.3: -0.001 [-0.020, +0.016]; n 15504 |
| change_post | +0.021 @ +0.45 [+0.004, +0.040], x1.11, p 0.065; ±0.3: -0.002 [-0.007, +0.003]; n 32033 | +0.025 @ +0.25 [-0.002, +0.054], x1.13, p 0.229; ±0.3: +0.009 [+0.000, +0.018]; n 14651 | +0.025 @ -0.15 [-0.005, +0.055], x1.13, p 0.313; ±0.3: +0.007 [-0.002, +0.016]; n 14419 | +0.029 @ -0.85 [-0.002, +0.063], x1.11, p 0.299; ±0.3: +0.007 [-0.003, +0.019]; n 12635 | +0.013 @ -0.55 [-0.005, +0.031], x1.07, p 0.687; ±0.3: -0.003 [-0.010, +0.003]; n 26400 | +0.021 @ -0.55 [-0.006, +0.050], x1.10, p 0.468; ±0.3: +0.003 [-0.005, +0.011]; n 15504 |
| burst | +0.018 @ -0.15 [+0.001, +0.036], x1.13, p 0.050; ±0.3: +0.005 [-0.002, +0.012]; n 32033 | +0.024 @ +0.15 [-0.003, +0.051], x1.18, p 0.114; ±0.3: -0.003 [-0.012, +0.007]; n 14651 | +0.051 @ -0.45 [+0.014, +0.099], x1.38, p 0.005; ±0.3: +0.008 [-0.006, +0.023]; n 14419 | +0.022 @ +0.95 [-0.001, +0.047], x1.16, p 0.234; ±0.3: +0.006 [-0.005, +0.017]; n 12635 | +0.020 @ +0.25 [-0.002, +0.041], x1.15, p 0.055; ±0.3: +0.002 [-0.005, +0.009]; n 26400 | +0.018 @ +0.35 [-0.002, +0.039], x1.14, p 0.398; ±0.3: -0.003 [-0.011, +0.006]; n 15504 |
| burst15 | +0.005 @ -0.95 [-0.003, +0.015], x1.12, p 0.871; ±0.3: +0.000 [-0.003, +0.004]; n 32033 | +0.011 @ +0.35 [-0.003, +0.028], x1.25, p 0.353; ±0.3: -0.003 [-0.007, +0.002]; n 14651 | +0.023 @ -0.45 [+0.003, +0.048], x1.51, p 0.005; ±0.3: +0.005 [-0.001, +0.012]; n 14419 | +0.014 @ -0.05 [-0.000, +0.029], x1.29, p 0.239; ±0.3: +0.003 [-0.003, +0.009]; n 12635 | +0.016 @ +0.25 [+0.003, +0.029], x1.35, p 0.005; ±0.3: +0.002 [-0.002, +0.006]; n 26400 | +0.009 @ -0.35 [-0.002, +0.022], x1.19, p 0.711; ±0.3: +0.001 [-0.004, +0.006]; n 15504 |

## FOR USER

1. Mirrors left out; V1 and V2 pooled (per-copy tables agree).
2. W = 3 s main, 4 s variant; biased autocorrelation, linear detrend, highest local maximum in 0.2-2.5 s.
3. librosa local period = median IOI within the window ±1.5 s, >= 3 intervals.
4. Similar-tempo chance within the same dataset, 20 draws, seed 52103; shuffle 20 permutations, seed 52104.
5. hold threshold 0.2; change = family change or posture distance > pooled p90 (37.0 deg); burst > 1.0 sd (variant 1.5).
6. Response time = token boundary (change, burst) or still-run start (hold).
7. Histogram PNG dropped (no matplotlib in the env); histograms given as tables.
8. The family-change response fires at almost every token (1.95/s of a possible 2/s); a sparser family-change definition would be needed
   for "change" to act as a response control. Not changed here (rules fixed).
