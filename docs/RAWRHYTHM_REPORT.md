# Raw-joint movement rhythm vs beat: report (WO53 part B, BRAIN_SPEC 7.84 item 3)

Report only. No verdict, nothing trained, A and B unchanged. Rules: `docs/RAWRHYTHM_RULES.md`, pushed in `59855a2` before any result.
One amendment came before any result, in `72ce91e`: Motorica's non-root BVH position channels must stay below 1 cm sd instead of being
exactly constant. Code `scripts/body/rawrhythm.py`; tests `scripts/body/test_rawrhythm.py` (6, synthetic, pass).
Full tables (every dataset, signal, source and variant; period and ratio quantiles; paired bins): `docs/RAWRHYTHM_TABLES.md`.
Per-window values (row-aligned to WO52's `rhythm/windows_<ds>.npz`), per-song-group counts and chance expectations, and `results.json`
are in `/secondary/hyst-data/body/rawrhythm/` (`windows_<ds>.npz`, `songs_<ds>.npz`, `seq/<ds>/<perf>.npz`, `condition.md`).
Motorica appears here only as dataset aggregates.

## Data and run

- Scan: 0 bad out of 2,128 performances. FineDance had 197, AIOZ 1,613 dancer sequences, PhantomDance 244 and Motorica 74. Every raw source
  loads, its values are finite, and it covers its last WO52 window. Motorica's non-root position channels vary by at most 0.06 cm (sd).
- Unit `hyst-wo53b-run1` failed at start because the log directory was missing. It was rerun as `hyst-wo53b-run2` on cores 17-19:
  scan, extract, assemble, analyse and tables ran in about 6 min, with 0 failures. All 310,065 WO52 rows have raw values.
- **The lamp was recomputed in the same run and matches WO52's point estimates exactly** (max abs difference 0.0 over cluster share,
  both excesses and C, all datasets, sources and variants). Intervals here use seed 53201.
- **Deviations:**
  - FineDance, AIOZ and PhantomDance positions come from approximate FK with generic bone lengths (WO47's skeleton).
  - Motorica uses its own BVH skeleton.
  - The raw sources of PhantomDance and Motorica are read from `/secondary/hyst-data/{phantomdance,motorica}/raw/`.
  - Foot means the ankle joint.
  - Pelvis-relative pelvis is identically zero, so it is "none" in every window (rhythmic share 0.000).

## Headline: cluster-share excess, raw (mean of the six joints, world) vs retargeted lamp, W = 3 s, main rule

Excess is the share of rhythmic windows at 1/2, 1 or 2 beats minus chance, with a 95 % song-group bootstrap interval (2,000 resamples,
seed 53201). Chance 1 draws a similar-tempo song; chance 2 shuffles the periods.

| dataset | source | raw mean, excess 1 | lamp, excess 1 | raw mean, excess 2 | lamp, excess 2 |
|---|---|---|---|---|---|
| FineDance | librosa | +0.004 [+0.001, +0.007] | +0.002 [-0.001, +0.005] | +0.083 [+0.059, +0.108] | +0.008 [-0.007, +0.023] |
| FineDance | pulse v2 | +0.011 [-0.001, +0.022] | -0.001 [-0.008, +0.006] | +0.053 [+0.027, +0.081] | +0.007 [-0.011, +0.023] |
| AIOZ | librosa | -0.008 [-0.014, -0.004] | +0.001 [-0.002, +0.004] | +0.095 [+0.069, +0.121] | +0.026 [+0.013, +0.040] |
| AIOZ | pulse v2 | +0.010 [+0.002, +0.018] | +0.003 [-0.002, +0.009] | +0.082 [+0.063, +0.101] | +0.023 [+0.012, +0.036] |
| PhantomDance | librosa | -0.003 [-0.007, +0.002] | -0.000 [-0.003, +0.003] | +0.030 [+0.016, +0.046] | +0.006 [-0.004, +0.016] |
| PhantomDance | pulse v2 | +0.001 [-0.008, +0.010] | -0.003 [-0.008, +0.003] | +0.038 [+0.022, +0.056] | +0.007 [-0.005, +0.019] |
| Motorica | librosa | +0.006 [-0.013, +0.020] | +0.003 [-0.002, +0.009] | +0.113 [+0.065, +0.158] | +0.014 [-0.009, +0.038] |
| Motorica | pulse v2 | +0.005 [-0.021, +0.029] | -0.009 [-0.019, +0.001] | +0.075 [+0.029, +0.119] | -0.001 [-0.019, +0.016] |
| all | librosa | -0.004 [-0.007, -0.001] | +0.001 [-0.001, +0.003] | +0.084 [+0.069, +0.100] | +0.018 [+0.010, +0.027] |
| all | pulse v2 | +0.008 [+0.002, +0.014] | +0.000 [-0.003, +0.004] | +0.070 [+0.056, +0.082] | +0.015 [+0.008, +0.022] |

Per joint, in the pooled main rule:
- Against chance 2 (shuffled), every one of the 13 raw signals has an excess between +0.032 and +0.084, all with lower bound > 0. The lamp
  has +0.015 to +0.018.
- Against chance 1 (similar tempo), raw signals lie between -0.005 and +0.008. With librosa, none has a lower bound > 0, and pelvis,
  head, the mean and the relative mean lie below 0. With pulse v2, four signals have a lower bound > 0: head, mean, left foot relative
  and right foot relative.

## Raw and lamp side by side

- **Bin shares (librosa, pooled, rhythmic windows):** raw mean 1/2 0.090, 1 0.165, 2 0.269, other 0.477; lamp 0.020 / 0.144 / 0.234 /
  0.602. The raw cluster share is higher (0.523 against 0.398), mostly through the 1/2 and 2 bins. Chance cluster shares are higher too:
  chance 1 0.527, chance 2 0.439.
- **Periods (W = 3, rhythmic windows, quantiles 5/25/50/75/95, s):**
  - lamp 0.38 / 0.73 / 1.24 / 1.77 / 2.29;
  - raw mean 0.27 / 0.58 / 1.07 / 1.67 / 2.24;
  - right wrist 0.28 / 0.64 / 1.18 / 1.72 / 2.27;
  - pelvis 0.24 / 0.62 / 1.06 / 1.61 / 2.21.

  The median ratio to the librosa beat is 2.40 for the lamp and 2.02 for the raw mean; to pulse v2 it is 2.05 and 1.90. Raw periods are
  shorter, especially in PhantomDance (median 1.04 s raw mean against 1.31 s lamp) and Motorica (0.80 against 1.24).
- **Rhythmic share (strength >= 0.2):** lamp 0.681; raw signals 0.61-0.69 (mean 0.684).
- **Circular concentration C (pooled, librosa):**
  - lamp 0.103, excess over chance 1 +0.007 [+0.005, +0.010];
  - raw mean 0.343, excess over chance 1 +0.035 [+0.029, +0.041], over chance 2 +0.276.

  Most of the raw C is also present under chance 1, i.e. it comes from the tempo class.
- **Variants (pooled, mean of six against the lamp, excess 1):**
  - narrow edges and strength >= 0.3: raw mean +0.049 [+0.045, +0.054] (librosa), +0.060 (pulse v2); lamp +0.017 [+0.014, +0.020],
    +0.014. Both have lower bounds > 0;
  - W = 4 s: raw mean -0.005 [-0.009, -0.001] (librosa), +0.008 [+0.001, +0.015] (pulse v2); lamp +0.000, -0.001 (intervals include 0).
- **Paired per window (W = 3, main), pooled.** Share of rows in the same bin, observed against the share expected if raw and lamp bins
  were independent:

  | raw signal | librosa | pulse v2 |
  |---|---|---|
  | mean | 0.333 against 0.276 | 0.325 against 0.268 |
  | right wrist | 0.347 against 0.291 | 0.339 against 0.280 |
  | pelvis | 0.316 against 0.275 | 0.309 against 0.267 |

  Among rows where both are rhythmic, the mean gives 0.438 against 0.367 (librosa). Raw and lamp agree on the bin in about a third of
  windows, 5-7 points above independence. Per dataset these are 0.27-0.37 against 0.24-0.32.

## 7.84 item 3 condition as numbers (no verdict)

The condition holds when at least one raw signal (13 non-degenerate: six joints, the mean, and their pelvis-relative versions minus the
pelvis) has an excess with 95 % lower bound > 0 AND the lamp's interval includes 0. No multiple-comparison correction is applied, and 13
signals are examined per cell. Main rule:

| dataset | librosa, chance 1 | librosa, chance 2 | pulse v2, chance 1 | pulse v2, chance 2 |
|---|---|---|---|---|
| FineDance | holds (9 of 13 raw > 0; lamp includes 0) | holds (13; lamp includes 0) | holds (5; lamp includes 0) | holds (12; lamp includes 0) |
| AIOZ | does not hold (0 raw > 0) | does not hold (13 raw > 0, but lamp +0.026 > 0) | holds (4; lamp includes 0) | does not hold (13 raw > 0, but lamp +0.023 > 0) |
| PhantomDance | does not hold (0 raw > 0) | holds (13; lamp includes 0) | does not hold (0 raw > 0) | holds (13; lamp includes 0) |
| Motorica | does not hold (0 raw > 0) | holds (13; lamp includes 0) | does not hold (0 raw > 0) | holds (13; lamp includes 0) |
| all | does not hold (0 raw > 0) | does not hold (13 raw > 0, but lamp +0.018 > 0) | holds (4; lamp includes 0) | does not hold (13 raw > 0, but lamp +0.015 > 0) |

Stated plainly:
- **Against the shuffled-period chance:** raw joints cluster in every dataset (excess +0.03 to +0.11). The lamp's interval includes 0 in
  FineDance, PhantomDance and Motorica, so the condition holds there. In AIOZ and pooled, the lamp also clusters, but less (+0.015 to
  +0.026 against +0.07 to +0.10).
- **Against the similar-tempo chance (WO52's first-named chance):** the raw excesses are small (at most +0.012).
  - The condition holds with librosa beats only in FineDance, and with pulse v2 in FineDance, AIOZ and pooled.
  - It does not hold in PhantomDance and Motorica with either source.
  - Pooled with librosa, the raw mean lies below chance (-0.004 [-0.007, -0.001]; AIOZ -0.008).

The cell-level table, with the largest raw excess and the lamp interval per cell, is in `/secondary/hyst-data/body/rawrhythm/condition.md`.
Some lower bounds print as +0.000 at three decimals but are above 0.

## FOR USER

1. Approximate FK with generic bone lengths for FineDance, AIOZ and PhantomDance; there is no SMPL model locally, and PhantomDance's json
   has no offsets. Motorica uses its BVH offsets.
2. Foot = ankle joint (SMPL 7/8, BVH LeftFoot/RightFoot).
3. Raw sources for PhantomDance and Motorica are read from `/secondary/hyst-data/{phantomdance,motorica}/raw/`, outside
   `/secondary/hyst-data/datasets/`, where Motorica is marked BLOCKED and PhantomDance is absent. No dataset was skipped. AIST++ has no
   WO52 windows and was not analysed.
4. Positions go from 30 Hz to 50 Hz by cubic spline before the speed. AIOZ is taken at 30 fps, as in T0; its derived rate is 29.7-30.0.
5. Each raw value is attached to both the V1 and V2 rows, so windows and chance draws equal WO52's.
6. Narrow and W = 4 variants were run only for the lamp and the two means. No multiple-comparison correction.
7. The rules were amended before any result: Motorica's non-root BVH position channels must have sd < 1 cm, not be exactly constant
   (observed maximum 0.06 cm).
8. Bootstrap seed 53201, as ordered. WO52 used 52101, so lamp intervals here can differ from WO52's in the last digit; point estimates are
   identical.
