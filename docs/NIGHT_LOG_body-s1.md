# Night log, builder (body-s1), work order 20, Stage 1 toy (2026-11-09)

## MORNING SUMMARY

Stage 1 RAN (12 runs, 1000 epochs, one detached unit, 51 min at 6 threads). `/secondary/hyst-data/body/s1/summary.json`.

**Collapse precondition (first): NOT MET. Verdict by the rules: NO VERDICT on (ii)-(iv).** Neither arm 0 nor arm i collapses on both measures in both seeds.
- Between-song JS collapses clearly (trained / untrained): arm 0 0.20, 0.13; arm i 0.18, 0.29 (all <= 1/3).
- Occupied cells do NOT fall: arm 0 1.05, 0.79; arm i 1.22, 1.52 (need <= 0.33). The untrained policy already occupies only 23-27 cells of 576, so there is no wide posture set to collapse from; training with the legibility objective spreads the hand, it does not narrow it.

Held-out numbers (mean over 32 songs; seeds s0/s1; JS = between-song median, half-song control in brackets; D = decoding on the arm's own target):
| arm | JS s0 | JS s1 | D s0 / s1 | occupied cells s0 / s1 | entropy bits s0 / s1 | MMD s0 / s1 | 2AFC s0 / s1 |
| 0 | 0.146 (0.19) | 0.128 (0.12) | 0.875 / 0.886 | 27.8 / 18.4 | 3.78 / 2.88 | 0.031 / 0.023 | 0.73 / 0.78 |
| i | 0.135 (0.15) | 0.283 (0.10) | 0.852 / 0.888 | 32.5 / 35.2 | 4.37 / 4.32 | 0.030 / 0.093 | 0.70 / 0.86 |
| ii | 0.766 (0.04) | 0.773 (0.04) | 0.733 / 0.767 | 25.2 / 26.3 | 3.76 / 3.77 | 0.48 / 0.50 | 0.98 / 0.99 |
| iii | 0.806 (0.06) | 0.559 (0.06) | 0.698 / 0.757 | 50.6 / 51.3 | 5.13 / 5.13 | 0.57 / 0.29 | 0.98 / 0.98 |
| iv(0.05) | 0.866 (0.07) | 0.835 (0.06) | 0.684 / 0.690 | 48.2 / 47.1 | 4.99 / 4.96 | 0.60 / 0.62 | 0.98 / 0.97 |
| iv(0.5) | 0.974 (0.10) | 0.939 (0.09) | 0.651 / 0.665 | 45.4 / 48.9 | 4.76 / 4.95 | 0.84 / 0.72 | 0.98 / 0.98 |
Untrained policy (held-out): JS 0.739 (s0), 0.976 (s1); occupied cells 26.6, 23.2.

Informational only (NOT a verdict; the rules say stop): relative to arm i the JS of ii-iv is 3-7x higher (ii 0.77 vs i mean 0.21), but arm i's low JS comes from the policy hand being close to the same distribution
for all songs, and arms ii-iv simply recover roughly the untrained policy's high between-song JS (0.74-0.98), i.e. they do not exceed the untrained policy. Decoding D in iv is 0.65-0.69 (< 0.7), so the (iv) pass condition would fail on D anyway.
Machine 2AFC is 0.70-0.86 for arms 0/i (above chance, so the song identity is partly readable even there) and 0.97-0.99 for ii-iv. Lambda chosen by validation for arm iv per seed: see summary.json (verdict_detail not written because no reference).
FOR USER: the precondition as ruled (cells <= 1/3 of untrained) cannot be met here because the untrained toy policy is nearly still; a different baseline (e.g. a trained-without-legibility policy) would be needed to ask the question the precondition meant.

## Log

- Environment has no optax, sklearn, torch, pytest: own Adam, own L2 logistic regression (scipy L-BFGS), unittest (18 tests).
- Rules amendments in `docs/STAGE1_RULES.md` section 10 (epochs, batches, 7.35 rulings, 7.36 occupied cells). Run: `scripts/body/s1_chain.sh`, unit `hyst-wo20-stage1-a`, log `/secondary/hyst-data/body/s1/chain.log`.
- Per-run results: `/secondary/hyst-data/body/s1/run_*/result.json` (val and held-out measures, untrained reference, params.pkl).


---

# WO22: Stage 1 rerun on seeds 2 and 3 (2026-11-09)

## MORNING SUMMARY (WO22)

12 runs, 1000 epochs, one detached unit, 3197 s (53 min), cores 6-11. Data `/secondary/hyst-data/body/s1r/` (`verdict.json`, `verdict.txt`).
**Collapse precondition (7.37.1): NOT MET. NO VERDICT.** JS ratio (between-song / half-song), need <= 1.5 on both seeds:
- arm 0: seed 2 0.93, seed 3 4.84 (not met)
- arm i: seed 2 4.82, seed 3 1.21 (not met)
Each arm meets it on one seed only. Not interpreted beyond the rule.

Note: the chain's built-in `summary.json` (via `s1_summary.py`) still applies the old 7.35.2 rule (ratios to untrained). It is superseded by `verdict.json` (7.37.1).

```
WO22 Stage 1 rerun, seeds 2 and 3 (7.37.1)

precondition arm 0: JS ratios {2: 0.9272531780335673, 3: 4.838300919587495} -> not met
precondition arm i: JS ratios {2: 4.820806459635642, 3: 1.206434087763201} -> not met
VERDICT: no verdict (collapse precondition not met: neither arm 0 nor arm i has JS ratio <= 1.5 on both seeds)

arm       seed      JS JSratio      D   cells entropy   2AFC     MMD
0            2   0.072    0.93  0.893    20.3    2.85  0.630  0.0092
0            3   0.396    4.84  0.869    36.7    4.03  0.880  0.0672
i            2   0.399    4.82  0.881    27.4    3.65  0.860  0.1011
i            3   0.112    1.21  0.840    31.7    4.00  0.768  0.0261
ii           2   0.986   11.82  0.689    33.2    3.97  0.986  1.1133
ii           3   0.843   16.66  0.739    25.7    3.67  0.994  0.6184
iii          2   0.976   12.08  0.643    52.9    4.97  0.974  0.8205
iii          3   0.984   12.39  0.576    56.1    4.97  0.984  0.8535
iv(0.05)     2   0.966    9.32  0.589    54.3    5.05  0.967  0.7933
iv(0.05)     3   0.804   14.12  0.716    48.4    4.99  0.976  0.5874
iv(0.5)      2   0.975    8.76  0.643    58.3    5.17  0.976  0.7363
iv(0.5)      3   0.951   13.56  0.546    36.8    4.40  0.984  0.8567

Seeds 0/1 (WO20): informational only (7.37.1)
arm       seed      JS JSratio      D   cells entropy   2AFC     MMD
0            0   0.146    0.77  0.875    27.8    3.78  0.734  0.0311
0            1   0.128    1.09  0.886    18.4    2.88  0.780  0.0234
i            0   0.135    0.92  0.852    32.5    4.37  0.697  0.0299
i            1   0.283    2.84  0.888    35.2    4.32  0.864  0.0926
ii           0   0.766   17.79  0.733    25.2    3.76  0.978  0.4838
ii           1   0.773   20.48  0.767    26.3    3.77  0.986  0.4991
iii          0   0.806   13.84  0.698    50.6    5.13  0.982  0.5718
iii          1   0.559    8.87  0.757    51.2    5.13  0.976  0.2874
iv(0.05)     0   0.866   12.48  0.684    48.2    4.99  0.976  0.5967
iv(0.05)     1   0.835   13.01  0.690    47.1    4.96  0.967  0.6187
iv(0.5)      0   0.974   10.05  0.651    45.4    4.76  0.982  0.8429
iv(0.5)      1   0.939   10.21  0.665    48.9    4.95  0.980  0.7240
```

Pushed before the run: s1_chain --seeds, s1r_chain.sh, s1r_verdict.py + test, STAGE1_RULES section 11 (3de54c7).
