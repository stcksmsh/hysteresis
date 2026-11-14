# For the planning agent: B3 round 1 results and a fair round 2 (Hysteresis, 2026-10-31)

From the overseer. B3 has been trained once and checked once on held-out data. All three gated checks failed. The spec allows one round 2, limited to what each failing check names. Please rule on what round 2 may change. Where the user must choose, give options and a recommendation. Every number below was recomputed by the overseer from the saved results unless marked.

## What was run (as specced and committed before results)

**The core.**
- 4 complex diagonal LRU layers: L1 8–20 Hz, L2 4–8 Hz, L3 0.5–4 Hz ("the beat band"), L4 0.01–0.5 Hz.
- Width 128, 256 modes per layer, 1,010,020 parameters.
- Gated MLP, residual and layer norm per layer. Frequencies clamped to their bands.
- One Gaussian head per layer at its horizon: +100 ms, +0.5 s, +2 s, +8 s. The target is the 44 fast features averaged over [t+h, t+2h).
- Learned precision coupling. Precision comes from the layer's input, not its own state, to keep the scan parallel.
- A parameter-free layer norm before the heads (`head_norm`), added because the untrained core diverged without it.

**Input.**
- 44 fast features at 100 Hz, standardised on the training side.
- Grid phase (cos, sin) from the offline beat grid. B1, the pulse, had failed twice.
- 6 of 3,176 tracks had fewer than 2 grid beats and get zero phase.

**Training.**
- Corpus: 174.7 h of FMA (CC BY/BY-SA/CC0/PD), half electronic/pop/rock; 20 h held out by artist.
- 8 epochs, about 11 h on CPU. AdamW at lr 1e-3, 60 s chunks with the state carried. NLL summed over the 4 layers.
- No early stopping. The final checkpoint (epoch 8) was checked, as fixed.

**Held-out NLL per layer by epoch** (L1, L2, L3, L4):
- epoch 1: 0.487, 0.563, 0.618, 0.339;
- epoch 4: 0.330, 0.232, 0.184, 0.174;
- epoch 8: 0.263, 0.140, 0.085, 0.093.

Training values at epoch 8: 0.261, 0.064, 0.035, 0.135. L2 and L3 sit lower on training songs than on held-out songs (gaps 0.08 and 0.05). Held-out NLL was still falling at epoch 8 on every layer.

**Two crash fixes during the run, no rule changes:**
- the zero phase for the 6 beatless tracks;
- the B2 baseline's readout rows, every 2 s as documented, instead of every 0.2 s by a bug. The bug caused an out-of-memory kill.

## Results, round 1 (357 held-out songs from 73 artists)

### §4.3, "it learned to predict music": FAIL, on the MSE condition only

**NLL condition, per baseline (baseline − B3), per-song bootstrap 95 %:** passes for all three.

| Baseline | Difference [95 %] |
|---|---|
| persistence | +3.07 [2.89, 3.23] |
| ridge AR (last 1 s + 16 s pooled) | +0.57 [0.45, 0.68] |
| B2 (untrained core, ridge readouts) | +1.11 [0.98, 1.23] |

**MSE of the predicted mean, pooled:**

| Model | MSE |
|---|---|
| B3 | 0.149 |
| ridge AR | **0.131** |
| B2 | 0.197 |
| persistence | 0.452 |

The rule needs B3 ≥ 5 % below the best baseline. B3 is 13.7 % above ridge AR.

**Per-layer NLL:**

| Model | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| B3 | 0.264 | 0.141 | 0.085 | 0.093 |
| AR | 0.384 | 0.217 | 0.279 | 0.267 |
| B2 | 0.629 | 0.365 | 0.358 | 0.348 |

Reading: B3's predicted variance is far better calibrated (likelihood), but its predicted mean is less accurate than a linear model with 16 s of history. Per-layer MSE is not in the report; the overseer can get it.

### §4.4, habituation (synthetic repeat, H = S F S vs N = S' F S, 16 s passages): FAIL

- B3 over 329 songs: mean drop 0.0003 nats [−0.115, 0.070]. The median drop/SD (SD of 8 s window means) is 0.010, against 0.25 needed.
- B2 (control): 0.087 [0.020, 0.182], median drop/SD 0.006.
- B3 − B2: −0.087 [−0.286, 0.029].

Reading: B3 shows no memory of a passage heard 30 s earlier, at least not in its total surprisal. The untrained B2 shows a small one.

### §4.5, surprisal at abrupt change (4 cuts per song, 353 songs, 1,412 cross-song cuts): FAIL on condition 1

- z ≥ 3 on 59.8 % of cross-song cuts; the rule needs 80 %.
- Median cross z 4.76, median within z 0.59.
- Cross − within per song: 12.49 [7.46, 18.69], above 0 (holds).

### §4.6, reported only

- **Phase-amplitude coupling** (Tort MI against surrogates, 40 songs):
  - L3 phase / L1 amplitude 0.0048 vs 0.0008, 85 % of songs p < 0.05;
  - L3 / L2 0.0071 vs 0.0014, 82.5 %;
  - L4 / L1 and L4 / L2 at about chance (20 %, 22.5 %).
- **DEAM/MERP within-song arousal r** (ridge on layer-mode magnitudes pooled to 0.5 s, 5 folds by song):

  | | Brain | Smoothing control | core-2b |
  |---|---|---|---|
  | DEAM | 0.201 [0.184, 0.218] | 0.323 [0.298, 0.347] | 0.276 [0.251, 0.302] |
  | MERP | 0.399 [0.326, 0.472] | 0.480 [0.371, 0.584] | 0.644 [0.575, 0.703] |

- **No-phase ablation:** running now, results in about 12 h.

## Constraints for round 2

- Round 2 may change only what the failing checks name. Rules committed before results, nothing tuned on the held-out artists, no round 3.
- Compute: about 11 h per training run of 8 epochs on this CPU. The original cap was 3 nights in total; about 11 h was used by the main run and up to 19 h by the ablation.
- Under the user's pivot, the body is driven by an authored mapping from the brain's state (neuromod lanes, surprisal spikes, band power). The public claims ("learned to predict", "surprisal rises at abrupt changes", "habituates") need their checks to pass. The authored mapping does not.

## Questions

1. **§4.3.** B3 wins on likelihood but loses on mean accuracy to ridge AR. Is the MSE condition the right test of "learned to predict music"? Was it set fairly, given that AR gets 16 s of explicit history and B3's heads are tiny linear maps from a 128-wide state? What may round 2 change?
   - **Training:** more epochs, since held-out NLL was still falling; an MSE term in the loss; larger heads.
   - **Architecture:** precision from the layer's own state.
   - **The check:** compare per layer.

   Which of these counts as "limited to what the check names"?
2. **§4.4.** B3 shows no habituation, and the untrained core shows a little. Is this an architecture limit? Nothing in the objective rewards recalling a passage 30 s back, and L4 at 8 s horizons may forget. Or is it a training-length limit? What would a fair round 2 be, if any? Should "habituates" be dropped as a claim instead?
3. **§4.5.** 59.8 % against 80 %, with a median z of 4.76. Is 80 % at z ≥ 3 the right bar? Or should round 2 target the cause, e.g. surprisal dominated by L1, or variance heads that widen quickly after a cut?
4. **One round 2 or none.** One retrain costs about 11 h. Can one retrain address all three, or must round 2 choose? Recommend the smallest round 2 that tests each failing claim honestly.
5. **Pre-check.** The brain's arousal tracking is below core-2b and below the smoothing control. Does that change what the body should read under the pivot (core-2b's `mood.energy` vs the brain's neuromod lanes)?
6. **Truth table now.** What may be claimed from round 1 as it stands? For example, the calibrated-likelihood win and the beat-band coupling, both of which passed or were reported. What stays forbidden?
