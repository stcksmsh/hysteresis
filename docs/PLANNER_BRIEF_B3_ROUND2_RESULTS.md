# For the planning agent: B3 round 2 results, and what follows (Hysteresis, 2026-11-01)

From the overseer. Round 2 ran exactly as you ruled (BRAIN_SPEC.md §4.7, committed before any result). All three gated checks failed again. By your rule there is no round 3, and each failed claim is dropped. Please rule on what follows. Where the user must choose, give options and a recommendation. Every number below was recomputed by the overseer from the saved results, except where marked.

## What ran

- Same architecture, heads, precision source and features as round 1. 1,010,020 parameters, with grid phase.
- Changes:
  - **Loss:** β-NLL with β = 0.5. Seitzer et al. 2022, Eq. 7, p. 5, recorded in `B3_NOTES.md`.
  - **Chunks:** 180 s, state carried, gradient through the whole chunk.
  - **Validation split:** 72 of 722 training artists (217 of 2,819 tracks, seed fixed). It shares no artist with the held-out set.
  - **Epochs:** up to 12, with early stopping on validation β-NLL, patience 2.
- **Memory ladder, first branch:** 8 streams × 180 s, no checkpointing. Smoke peak 14.5 GB; during training the process held about 11 GB.
- **Hard stop:** the user raised it from 20 h to 24 h after epoch 1, because other CPU-heavy work shared the machine. The run resumed from the epoch-1 checkpoint and nothing else changed (spec note, commit 8b9da7f).
- **Training:** 12 epochs, 17.5 h of wall time. Neither the hard stop nor early stopping ended it.
  - Epoch 12 was the best (validation β-NLL 0.622). Epochs 7 and 11 were not new bests.
- **Checks:** run on epoch 12. The baselines were refit on the same 90 % of training artists (2,602 tracks). Standardisation statistics are as committed.

Validation by epoch (217 tracks; mean over the 4 layers):

| Epoch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| β-NLL (selects) | 0.919 | 0.807 | 0.759 | 0.744 | 0.707 | 0.659 | 0.690 | 0.650 | 0.650 | 0.625 | 0.640 | 0.622 |
| MSE (mean of layers) | 0.182 | 0.177 | 0.169 | 0.166 | 0.160 | 0.160 | 0.159 | 0.156 | 0.157 | 0.152 | 0.152 | 0.151 |

## Results, round 2 (held-out: 357 songs, 73 artists)

### §4.3, "it learned to predict music": FAIL, again on the MSE condition only

**NLL condition, baseline − B3, per-song bootstrap 95 %:** passes for all three.

| Baseline | Round 1 | Round 2 |
|---|---|---|
| persistence | +3.07 [2.89, 3.23] | +3.14 [3.02, 3.26] |
| ridge AR | +0.57 [0.45, 0.68] | +0.66 [0.57, 0.77] |
| B2 | +1.11 [0.98, 1.23] | +1.19 [1.09, 1.31] |

**MSE of the predicted mean, pooled.** The gate needs B3 at least 5 % below the best baseline (ridge AR).

| | B3 | ridge AR | Ratio B3 / AR |
|---|---|---|---|
| Round 1 | 0.149 | 0.131 | 1.137 |
| Round 2 | 0.141 | 0.131 | 1.080 |

**Per-layer MSE, round 2 (newly reported).**

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| B3 | 0.153 | 0.128 | 0.142 | 0.142 |
| ridge AR | 0.129 | 0.112 | 0.136 | 0.147 |
| B2 | 0.260 | 0.191 | 0.177 | 0.159 |

- B3 beats AR on L4 (the +8 s horizon) and loses on L1–L3.
- Per-layer NLL for B3: 0.261, 0.116, 0.095, 0.090. For AR: 0.385, 0.222, 0.290, 0.267.

### §4.4, habituation (synthetic repeat, H = S F S against N = S′ F S): FAIL

- 329 songs; 28 too short were skipped.
- **B3:** mean drop 0.016 nats [−0.023, 0.063], against 0.0003 in round 1. Median drop / SD = 0.006; the rule needs 0.25.
- **B2 (control):** 0.080 [0.018, 0.172]. Median drop / SD = 0.003.
- **B3 − B2:** −0.064 [−0.171, 0.021].
- **Per-layer drop, B3 (newly reported):** L1, L2 and L3 about 10⁻⁶ (intervals around 0). L4 0.016 [−0.026, 0.063]. Almost all of the total drop is on L4.

### §4.5, surprisal at abrupt change (1,412 cross-song cuts, 353 songs): FAIL on condition 1

- z ≥ 3 on 60.5 % of cross-song cuts (round 1: 59.8 %); the rule needs 80 %.
- Median z: 4.96 cross-song, 0.61 within-song.
- Cross − within, mean per song: 10.9 [7.5, 14.7]. That condition holds again.
- The overseer could not recompute the 60.5 %: `results.json` keeps no per-cut z values. The other values were checked.

**Per-layer splice z (newly reported):**

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| Median z, cross-song | 2.93 | 9.22 | 0.60 | −0.06 |
| Median z, within-song | 0.65 | 1.01 | −0.01 | −0.05 |
| Share of cross-song cuts with z ≥ 3 | 49 % | 75 % | 19 % | 2 % |

**Predicted σ after a cut (newly reported):** rise above the mean of the 5 s before.

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| Peak, cross-song | 0.098 | 0.120 | 0.195 | 0.137 |
| Peak, within-song | 0.044 | 0.063 | 0.081 | 0.038 |
| Time to half the peak, cross-song | 0.1 s | 0.1 s | 0.3 s | 0.7 s |
| Time of the peak, cross-song | 0.1 s | 0.2 s | 0.7 s | 5 s (end of the window) |

### PAC control (§4.7), round-1 and round-2 models: FAIL for both pairs, both rounds

Rule: network MI (L3 phase against L1 or L2 amplitude) minus input max MI (grid phase against the largest of the 44 band-passed feature envelopes), paired over 40 songs, 95 % interval above 0.

| Pair | Round | Network MI (median) | Input max MI (median) | Difference [95 %] |
|---|---|---|---|---|
| L3 / L1 | 1 | 0.0048 | 0.0207 | −0.038 [−0.059, −0.021] |
| L3 / L1 | 2 | 0.0024 | 0.0207 | −0.040 [−0.061, −0.023] |
| L3 / L2 | 1 | 0.0071 | 0.0071 | −0.010 [−0.025, +0.001] |
| L3 / L2 | 2 | 0.0056 | 0.0071 | −0.013 [−0.028, −0.002] |

**A fact you should weigh:**
- The input side's max-of-44 is mostly selection noise. On the L1 pair, the median input max (0.0207) is below the median of its own surrogates' max (0.0310). For L2 it is 0.0071 against 0.0114.
- Only 27.5 % (L1) and 15 % (L2) of songs have input coupling above their own surrogates.
- The network is above its own surrogates on 70–85 % of songs: round 1 85 % and 82.5 %, round 2 70 % and 77.5 %.
- The control compares one network value against the largest of 44 noisy values. You chose that on purpose, as the conservative test. The overseer has not changed it and is not asking you to rescore round 2 under another rule. If you think the control measured something else than intended, say so for the record.
- The input feature that most often gives the max is feature 43, spectral flatness.

### §4.6, reported only

**DEAM / MERP within-song arousal r:**

| Set | Brain, round 1 | Brain, round 2 | Smoothing control | core-2b |
|---|---|---|---|---|
| DEAM | 0.201 | 0.202 [0.185, 0.220] | 0.323 | 0.276 |
| MERP | 0.399 | 0.408 [0.331, 0.481] | 0.480 | 0.644 |

**No-phase ablation (round-1 model only, as ruled):**
- Grid phase changes held-out NLL by about 1 % summed (0.583 with, 0.590 without) and pooled MSE by about 0.4 % (0.1486 with, 0.1492 without).
- From epoch 2 on, the two runs stayed within 0.01 per layer.

## What the overseer reads in this, for you to confirm or correct

- β-NLL narrowed the MSE gap from 13.7 % to 8.0 %. B3 now beats AR on the +8 s horizon, but not on the short ones.
- Longer chunks did not produce habituation. The fast layers carry no trace of a passage 30 s back; L4 carries a small one, within noise.
- At a cut to another song, total surprisal rises clearly on most cuts, but not 3 SDs on 80 %. The fast layers (L1, L2) carry the rise; L3 and L4 barely move.
- The grid-phase input adds almost nothing to prediction.

## Questions

1. **The rule for failing twice versus your round-1 lane ruling.** These conflict:
   - The spec (§4.6, "if B3 fails twice") says core-2b stays the body's source. The brain may only drive the monitor, labelled "an untrained oscillatory network driven by the music", with no B3 claims.
   - Your round-1 ruling (§4.7) has the body read the brain's surprisal spikes, neuromod tension and familiarity, and band power, while `mood.energy` stays from core-2b.

   B3 has now failed twice. Which holds? And the label "untrained" is false for a trained model: what should the monitor say?
2. **Truth table, final.** Which lines stand after round 2? Round 1 allowed three partial claims:
   - bands by construction;
   - cross-song rise above within-song (§4.5 condition 2, which held again);
   - the NLL win over three baselines (§4.3 condition 1, which held again).

   Do they stay, with round-2 numbers? Is any wording change needed now that there is no further round?
3. **Lanes for the body under the pivot, if the brain may feed the body at all.**
   - **Surprisal spikes ("startle"):** §4.5 failed, but cross-song cuts do raise surprisal far more than within-song cuts, mostly on L1 and L2. May the authored mapping use them, and from which layers?
   - **Familiarity:** this is minus the slope of surprisal over 30 s. Habituation is about zero. Is the lane still meaningful, or should it be dropped?
   - **Tension:** the L4 predicted variance. Is anything needed before use?
   - Under the pivot, the authored mapping does not need checks. Does that still hold when the lanes' own claims failed?
4. **Which checkpoint drives the brain, wherever it is used:** round 1 (epoch 8) or round 2 (epoch 12)? Round 2 has lower MSE (0.141 against 0.149) and similar NLL.
5. **The PAC control.** Does the coupling line stay forbidden, with no further test? Is there anything you want recorded about the max-of-44 design?
6. **What next.** With B3's claims mostly dropped, what is the smallest sensible next step for the brain track?
   - Stop at monitor use.
   - Go to the pivot's authoring with the lanes as they are.
   - Something else. The user's next human step is authoring the state-to-body mapping by eye.

Please answer point by point, so that the overseer can write the rulings into `docs/BRAIN_SPEC.md` as a dated note.
