# For the planning agent: five gaps in the B3 round-2 rulings (Hysteresis, 2026-10-31)

From the overseer. Thank you for the round-2 rulings: one retrain, β-NLL with β = 0.5, 180 s chunks, up to 12 epochs with early stopping on 10 % of the training artists (patience 2), the extra reports, the PAC control, the source of each lane and the truth table. The user has the rulings in front of them. Before they go into the spec and the code is written, five points are open. Each needs a rule fixed before any round-2 result. Please rule on each. Where the user must choose, give options and a recommendation.

## Facts you need

- Round 1 trained with 8 parallel streams of 60 s chunks (6,000 frames at 100 Hz). Each chunk also carries 1,600 frames of lookahead, used only to build targets. The state is carried across chunks and the gradient is cut at chunk edges.
- Round 1's training process peaked at 13.9 GB RAM. The machine has 30 GB; jobs run in a scope capped at 20 GB, because an out-of-memory kill on 2026-10-31 took down every session in the terminal.
- Round 1 checked the final checkpoint (epoch 8), as the spec fixed. There was no early stopping.
- Round 1's baselines were fitted on the whole training side:
  - the predicted variances of persistence and ridge AR;
  - the ridge AR weights;
  - B2's ridge readouts.
- The standardisation statistics come from the whole training side.
- Your PAC ruling: "the same Tort MI on the input itself (grid phase against the fast features' amplitude envelopes in the matching bands)". Round 1's coupling measured network L3 phase and L4 phase against network L1 and L2 amplitude. The pairs above the surrogates were L3/L1 and L3/L2.

## Questions

1. **Memory at 180 s chunks.** A step now holds three times as many frames, so the peak may pass the 20 GB cap. The builder measures it on a short smoke run first. If it is too high:
   - a) gradient checkpointing: the maths is unchanged, about 30 % more wall time;
   - b) fewer parallel streams, e.g. 3 × 180 s, which matches round 1's frames per step;
   - c) both.

   (b) changes the batch, which you did not rule on. Which is allowed, and in what order? If (a) pushes the run past the ~17 h one-run limit you proposed, what then: fewer epochs (the 12-epoch cap cut short), or (b)?
2. **Early stopping.**
   - a) Which checkpoint is checked: the best validation epoch, or the last epoch before stopping? The overseer proposes the best one.
   - b) Which validation score decides it:
     - β-NLL, the training loss;
     - plain Gaussian NLL, the reported surprisal;
     - MSE, the quantity the §4.3 condition 2 failed on.

     The overseer proposes β-NLL summed over the 4 layers, so that nothing gated selects the model. Note that only the training loss avoids aiming at the gate.
3. **What the baselines are fitted on.** The 10 % validation artists leave B3's training side. Should the baselines and the standardisation statistics also drop them, so that every model sees the same data? Or should they stay as committed, fitted on the full training side? The overseer proposes leaving the statistics as committed (you said features unchanged) and fitting the baselines on the same 90 % as B3.
4. **The PAC control, made exact.** The input has one phase signal, the grid phase. It has no phase in L4's band.
   - a) Is the control for L3 only: grid phase against the input's L1-band (8–20 Hz) and L2-band (4–8 Hz) amplitude envelopes?
   - b) Which input signal gives those envelopes: the summed onset strength, or RMS, or every feature's envelope, averaged?
   - c) "Exceeds", paired over songs: is that the difference of raw MI with a 95 % bootstrap interval above 0, or a comparison against each side's own surrogates?
   - d) Should the control also run on round 1's model now, before round 2, for the truth table?
5. **The no-phase ablation.** It finishes on the round-1 model tonight. Is that the reported ablation, or must round 2 also train a no-phase twin (another ~15 h, past the cap)? The overseer proposes: the round-1 ablation is reported as it stands, with no round-2 twin.

Please answer point by point, so that the overseer can write the answers into `docs/BRAIN_SPEC.md` as a dated note before any round-2 code runs.
