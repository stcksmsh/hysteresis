# For the planning agent: B7 round 1 results (Hysteresis, 2026-11-03)

From the overseer. B7 (BRAIN_SPEC.md §7 with the 7.10 rulings of 2026-11-02) has trained and been checked once. C4 and C5 failed; C1–C3 cannot be claimed because the hippocampus was dropped. §7.4 allows two rounds per check. Please rule on round 2, or on stopping. Where the user must choose, give options and a recommendation. Key numbers were recomputed by the overseer from the saved results (the MSE ratio, and the C4(a) interval from the per-song scores); the rest are as the check code wrote them.

## What ran

- **The overnight work order of 2026-11-02, followed as written.** Log: `docs/NIGHT_LOG.md` on branch `b7`. The laptop lost power at 01:44 (battery), and the order resumed the next morning.
- **Hippocampus: dropped,** as the order's decision tree prescribes.
  - **T1a** (retrieval finds the source) passed on designs B and C, and failed on A after training.
  - **The oracle** (true pointer forced) passed T1b, at error ratio 0.348.
  - **Trained T1b failed in every try.** Error ratios (repeat / first), needing ≤ 0.5:

| Try | A (iid) | B (levels + clock) | C (smooth AR) |
|---|---|---|---|
| 1 | 0.609 | 0.745 | 0.712 |
| 2, aux loss 0.1 | 0.737 | 0.808 | 0.804 |
| 2, aux 0.1 + new-parameter lr × 10 | 0.958 | 0.773 | 0.790 |

  - The hippocampus stays in the code behind a flag, off.
- **T2 (relay):** with a 1-frame skip, 1.069 × ridge AR (fail). With the 10-frame tapped skip of R4, 1.017 (pass); relay off 1.515.
- **T3 (modulation, unit tests):** pass.
- **Identity, B7 at step 0 against B3:** float64 4.6e-14 (criterion ≤ 1e-9, pass); float32 1.2e-4 (logged).
- **Memory:** the step-2 growth (15 → 20.5 GB) was not found. Training ran with gradient checkpointing (8.4 GB), at 8 streams × 180 s.
- **The B7 model:** relay (features + grid phase), a head skip with a 10-frame tapped delay, and acting modulation on 2 s blocks. 1,415,789 parameters, warm-started from B3 round 2 epoch 12.
- **Training:**
  - 8 epochs, 17.3 h of wall time, best epoch 6. Neither early stopping nor the 24 h cap ended it.
  - A new optimiser and a fresh learning-rate schedule (warm-up to 1e-3, cosine down to 1e-4 over 8 epochs), as built.
- **Checks:** run on epoch 6, on 357 held-out songs. Baselines fitted on the same 90 % of training artists.

**Validation by epoch** (217 tracks). The warm start (B3 round 2, epoch 12) scored β-NLL 0.622 and mean MSE 0.151.

| Epoch | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 |
|---|---|---|---|---|---|---|---|---|
| β-NLL (selects) | 0.733 | 0.776 | 0.681 | 0.654 | 0.702 | **0.590** | 0.624 | 0.605 |
| Mean MSE | 0.162 | 0.158 | 0.160 | 0.155 | 0.154 | 0.149 | 0.149 | 0.147 |

The first epochs were worse than the warm start. The likely cause, unverified: the restarted schedule ran at about 9× the rate B3 ended on.

## Results (held-out)

### C5, prediction (§4.3 rerun): FAIL on the MSE condition

**NLL condition, baseline − B7, per-song 95 %:** holds against all three.

| Baseline | Difference [95 %] |
|---|---|
| persistence | +3.18 [3.04, 3.30] |
| ridge AR | +0.70 [0.60, 0.81] |
| B2 | +1.23 [1.12, 1.34] |

**MSE.** The gate needs B7 at most 0.95 × ridge AR.

| Model | Pooled MSE | Ratio to ridge AR |
|---|---|---|
| B7 | 0.1363 | 1.041 |
| ridge AR | 0.1309 | 1 |
| B3 round 2 (for reference) | 0.141 | 1.080 |
| B3 round 1 (for reference) | 0.149 | 1.137 |

**Per layer:**

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| MSE, B7 | 0.139 | 0.124 | 0.143 | 0.140 |
| MSE, ridge AR | 0.129 | 0.112 | 0.136 | 0.147 |
| NLL, B7 | 0.205 | 0.077 | 0.110 | 0.124 |
| NLL, ridge AR | 0.385 | 0.222 | 0.290 | 0.267 |

**Ablations on the same weights (MSE ratio to ridge AR):**
- relay off: 5.40 (MSE 0.706);
- modulation frozen: 1.044;
- hippocampus off: 1.041 (it is already off).

### C4, modulation acts: FAIL on (b)

- **(a) Frozen-arousal NLL minus full NLL:** +0.061 [0.025, 0.103] (overseer's recomputation from the per-song scores; the code wrote [0.026, 0.101]). Holds.
- **(b) Effective time constant, top against bottom arousal quartile** (median relative change over songs; share of songs with the same sign):

| | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| Median relative change | +36 % | −29 % | −8 % | −12 % |
| Share of songs, same sign | 99.4 % | 99.4 % | 99.4 % | 99.4 % |

  - L3 is below the 10 % bar.
  - L1 moves the opposite way from L2–L4.
  - The rule "all four layers pass with one common direction" is the builder's fill of §7 (in the `check_b7.py` docstring and `B7_NOTES.md`, committed before results). §7.4's claim wording, "its layers [shorten/lengthen] their memory", implies one direction.
  - The identical same-sign share across layers follows from the design: one arousal signal and a fixed sign of w_τ per layer.

### C1–C3: not claimable (hippocampus dropped)

- **C1 and C3:** recognition and novelty are 0 everywhere.
- **C2 (habituation):** drop 0.007 [−0.031, 0.049], median drop / SD 0.007.
- **§4.5 rerun on total surprisal (reported):**
  - z ≥ 3 on 61.8 % of 1,412 cross-song cuts (B3 round 2: 60.5 %);
  - median z 5.26 cross-song, 0.66 within;
  - cross − within 10.9 [6.8, 14.8].
- **A note for any future hippocampus:** its novelty lane updates only every 2 s, so C3's 1 s window after a cut could not have seen it.

### Reported only

**DEAM / MERP within-song arousal r:**

| Set | B7 | B3 round 2 | Smoothing control | core-2b |
|---|---|---|---|---|
| DEAM | 0.192 [0.174, 0.210] | 0.202 | 0.323 | 0.276 |
| MERP | 0.419 [0.361, 0.474] | 0.408 | 0.480 | 0.644 |

**PAC:** L3 phase against L1 and L2 amplitude is above the network's own surrogates on 77.5 % and 85 % of 40 songs. No claim; the PAC control was not run on B7.

## What the overseer reads in this, for you to confirm or correct

- The relay and the tapped skip moved B7's MSE from 8 % above ridge AR (B3 round 2) to 4 % above. The model now leans on them heavily: with the relay off, MSE goes to 5.4× AR.
- Acting modulation makes held-out NLL measurably better (C4a). But its effect on memory has no single direction: L1 lengthens, while L2–L4 shorten.
- The hippocampus never learned to use retrieval in the toys, although the oracle shows the downstream path can.

## Questions

1. **Round 2 at all?** §7.4 allows two rounds per check. Is a round 2 worth one more training run of up to 24 h, or should B7 stop at round 1?
2. **If round 2, for C5 (MSE gap 4.1 % above AR, needs 5 % below).** What may change?
   - The learning-rate schedule for the warm start: a low constant rate, or a short warm-up to B3's final rate.
   - More epochs.
   - Something in the architecture, e.g. more taps, or a skip into the layer inputs as well as the heads.

   Which counts as "limited to what the check names"?
3. **If round 2, for C4(b).**
   - Is "one common direction across all four layers" the right reading of §7.4? Or may the claim state a direction per layer, e.g. "fast layers lengthen, slower layers shorten"? Changing the reading after the result would be a rule change; say whether it is allowed at all.
   - Is the 10 % bar per layer fixed?
4. **The hippocampus.** Does it get another attempt, in round 2 or later? If so, with what change? The overseer sees two candidate causes:
   - trained retrieval collapses (T1a failed on design A after training);
   - the network never learns to use replay (the oracle passes, trained runs don't).
   Also: should C3's window change to fit a 2 s read, or should the read get faster?
5. **The budget.** One B7 run costs about 17–24 h of a mostly idle machine. Is a further run justified against starting the authoring work, which the user is waiting on?
6. **Truth table now.** Which B7 lines may be stated from round 1?
   - For example: "with its modulation frozen, its prediction is measurably worse" (C4a alone).
   - For example: the NLL wins over three baselines (C5's NLL condition, as with B3).

   What stays forbidden?

Please answer point by point, so that the overseer can record the rulings as a dated note in `docs/BRAIN_SPEC.md` §7.
