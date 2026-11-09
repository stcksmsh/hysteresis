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
