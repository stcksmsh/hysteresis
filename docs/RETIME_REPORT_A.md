# Re-timing report, WO55 part A (BRAIN_SPEC 7.87): re-timed lamp analyses and token-level effect

Rules: `docs/RETIME_RULES.md` (pushed before any result). Helper `scripts/body/retime.py` (L(V1) = 0.35 s, L(V2) = 0.28 s; lamp arrays
read L later, tail dropped). Wrapper `scripts/body/retime_a.py`; tests `test_retime.py` (4) and `test_retime_a.py` (6), all pass.
Full tables `docs/RETIME_TABLES_A.md` (aggregates only); per-item outputs `/secondary/hyst-data/body/retime/a/`. Report only; no verdict.
"Outside" = how far the re-timed point lies outside the original's 95 % interval (0 = inside).

## Reproduction (original code path, unshifted)

- WO47 BAS: lamp BAS and chance recomputed on every file with L = 0 equal the stored WO47 values exactly (max diff 0.0); 4,594 sequences
  (AIOZ 3,520 of 3,704: the same 184 skipped in WO47 for too few beats).
- WO47 V3: raw best offset of all 203 FineDance files equals WO47 (max diff 0), so the per-file random streams are consumed as in WO47.
- WO52 analysis B rerun unshifted = stored WO52 (max |peak excess diff| 0).
- WO52/53 lamp rhythm recomputed on all 310,065 rows = stored values (0 mismatches).

## (a) WO47 lamp BAS and V3

- **BAS** (lamp-speed minima, 4 datasets x V1/V2 x librosa/project grid x music/kinematic sum = 32 cells): BAS minus shifted-beat chance
  stays within -0.006 .. +0.015 re-timed (original -0.011 .. +0.005). Outside the original interval: 15 of 64 numbers (excess and BAS),
  largest 0.017. Largest moves: Motorica V2 librosa music-sum excess -0.008 [-0.014, -0.003] -> **+0.011 [+0.005, +0.017]** (outside
  by 0.014), kinematic-sum -0.011 -> +0.015 (0.017); Motorica V2 project grid -0.005 -> +0.006; AIOZ V1 project grid -0.005 [-0.010,
  -0.001] -> +0.005 [+0.000, +0.009] (0.006). FineDance and PhantomDance: every re-timed excess inside +-0.005, intervals include 0.
  Raw FineDance BAS (not shifted) was 0.227 against chance 0.225 (WO47).
- **V3 realised** (FineDance, 203 files; k > 0 = music after motion): per-file best offset moves by exactly the shift (median per-file
  change +0.36 s V1, +0.28 s V2). Median best offset: V1 lamp -0.10 [-0.24, +0.06] -> -0.04 [-0.16, +0.08] s; V2 lamp -0.14 [-0.26,
  0.00] -> -0.06 [-0.20, +0.06]; V1 joints -0.08 -> -0.02; V2 joints -0.10 -> 0.00; all inside the original intervals (outside 0). The
  offsets stay spread over the whole +-1 s (5-95 % about -0.94 .. +0.96 s both before and after); share within 50 ms 0.025-0.039 ->
  0.034-0.059; max correlation median 0.035-0.042 unchanged; share above own 95 % shifted maximum 0.30-0.41 both.

## (b) WO52 event locks (6 responses x 6 music events, 4 datasets + pooled = 180 cells, 2 numbers each)

- Reproduction exact (above). Events counted change slightly because spans move (pooled e.g. onset 32,033 -> 32,106).
- Outside the original interval: 25 of 360 numbers (peak excess 3, mean +-0.3 s 22), largest 0.032 (Motorica change x onset +-0.3 s).
  Pooled: 4 of 72 (hold x cortex_L2 +-0.3: +0.006 [+0.003, +0.010] -> +0.001 [-0.003, +0.004], outside 0.002; change_post x
  dropout_end 0.002; burst15 x dropout_end 0.006; burst15 x cortex_total 0.003).
- Pooled peaks, original -> re-timed (excess resp/s @ lag, max-stat p): change x cortex_total +0.180 @ -0.65 p 0.005 -> +0.077 @ +0.95
  p 0.045; change x dropout_end +0.157 @ -0.45 p 0.005 -> +0.068 @ -0.75 p 0.144; change x cortex_L2 +0.073 @ -0.45 p 0.015 -> +0.041
  @ -0.35 p 0.313; hold x novelty +0.028 @ -0.65 p 0.005 -> +0.020 @ -0.95 p 0.010; burst x dropout_end +0.051 @ -0.45 p 0.005 -> +0.044
  @ -0.75 p 0.005; hold x cortex_L2 +0.015 @ -0.25 p 0.010 -> +0.013 @ -0.55 p 0.010. Peak lags of the hold/burst locks move by -0.1 to -0.5 s, mostly
  -0.3 s (as the shift predicts); the change-response peaks fall in size and lose their max-stat p (the original intervals of the
  change peaks were wide and include the re-timed values, so outside = 0).

## (c) WO53 B lamp column (reduced rows: 17,718 of 310,065 rows reaching the dropped tail removed from both sides)

- Lamp bin shares, cluster share and C: original vs re-timed differ by <= 0.008 in any cell (e.g. pooled librosa main: rhythmic share
  0.680 / 0.682, cluster 0.398 / 0.400, excess 1 +0.001 / +0.001, excess 2 +0.019 / +0.020). **Outside the original interval: 0 of 60.**
  The period-ratio result is unchanged by the shift, as stated in the rules; per-row values differ slightly (the 3 s of movement moves).
- Raw vs lamp same-bin share per window (W = 3, main, pooled, librosa): mean of six joints 0.333 -> 0.338 (independence 0.276 / 0.275);
  where both rhythmic 0.438 -> 0.441 (0.367); wrists 0.345 -> 0.349 and 0.346 -> 0.352. pulse v2 alike (+0.004 .. +0.005).

## (3) Token-level effect (7.87 Q4)

- Token 0.5 s; **L = 0.70 token (V1), 0.56 token (V2)**; whole-token alignment would be 1 token for both (residual -0.15 / -0.22 s).
- **Event-locked control at lag 0** (vigour, height, sharpness, pause onset x 6 events, excess over circular-shift chance): re-timed
  outside the original interval in 3 of 120 cells, largest 0.002. Pooled examples: vigour x onset -0.000 [-0.012, +0.012] -> +0.008
  [-0.004, +0.021] (one whole token: +0.014 [+0.002, +0.026]); vigour x cortex_L2 -0.033 -> -0.037; vigour x cortex_total +0.026 ->
  +0.028; pause onset x cortex_L2 +0.004 [+0.002, +0.006] -> +0.002 [+0.000, +0.004]; pause onset x dropout_on +0.001 -> +0.003; height
  and sharpness within +-0.002 everywhere.
- **Correlation with low-band energy and onset strength, lags -1..+1 s** (within-sequence r, pooled): the largest r are small (vigour x
  low band +0.11, vigour x onset +0.04; others |r| <= 0.03). Peak lag moves (pooled, re-timed minus original): vigour x low +0.4 s
  (+0.1 -> +0.5), vigour x onset +0.3 (-0.6 -> -0.3), height +0.3 / +0.4, sharpness +0.2 / +0.8, pause onset +0.4 / +0.3, against L =
  0.28-0.35 s (mixed V1/V2). The peak lags of the two clearest pairs (vigour) move by L within the 0.1 s lag step; the weak pairs have
  peak-lag intervals spanning most of +-1 s. By construction r_re-timed(lag) = r_original(lag - L) up to the token-interval sampling,
  so this confirms the bookkeeping, not a new effect.

## Skipped / not done

- WO47 V1 local phase locking was not re-timed (not in the work order's list; it is a phase measure and would change).
- Tokens were not re-cut; A's data not rebuilt; nothing trained or re-simulated.

## FOR USER

1. `metric/q50` (WO47) re-timed with the same L as `controls/q50`.
2. Rhythm rows that reach the dropped tail are removed from both sides (no continuation from the next window).
3. Token responses/controls moved by -L in time, not re-cut.
4. Token effect: mirrors left out; within-sequence demeaning; peak = max |r|; event-locked chance by shifting events within the span.
5. Median best-offset bootstrap for V3 added (WO47 gave none).
6. 50 Hz rounding: V1 shift is 18 samples (0.36 s), V2 14 samples (0.28 s).
