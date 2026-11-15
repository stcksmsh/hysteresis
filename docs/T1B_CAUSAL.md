# T1b causality list (work order 41 step 1, BRAIN_SPEC 7.68.1)

LIST only; no input is changed (7.68.1: causal in the token sense; offline whole-song facts are allowed if listed here and in the report).
Frame f of a 100 Hz lane is at time f/100 s. "Lookahead" = how far past the frame time an input can see audio or an offline fact.

## A. The 44 ear features (`scripts/brain/fast_features.py`, then `b2.build_inputs`)

All 44 come from one STFT: Hann, N_FFT 2048, hop 441, `center=True` (reflect padding). Frame f covers samples [441 f - 1024, 441 f + 1024).
Lookahead of every column: 1024 samples = **23.2 ms** (half a window). No column uses a centred or whole-song window beyond that.

| cols | what | window relative to frame f | lookahead |
|---|---|---|---|
| 0-31 | log-mel (32 bands) of the frame | the STFT frame | 23.2 ms |
| 32-39 | 8-band flux: one-frame rise of dB(P), mean over the band | frames f-1, f | 23.2 ms |
| 40 | onset strength: one-frame rise of log-mel | frames f-1, f | 23.2 ms |
| 41 | RMS of the 2048-sample frame | the STFT frame | 23.2 ms |
| 42 | spectral centroid | the STFT frame | 23.2 ms |
| 43 | spectral flatness | the STFT frame | 23.2 ms |

- Start and end edges: reflect padding (a mirrored past / future of the file itself, no extra lookahead beyond 23.2 ms).
- Normalisation: global constants (`braindump.stats()` mean/sd of the B3 corpus), then clip (`b2.build_inputs`, `core.CLIP`). **No per-song statistic**, no whole-song fact.

## B. Cortex inputs (46 columns = 44 ear + 2 beat-grid phase)

1. 44 ear columns: as in A.
2. Beat-grid phase cos/sin (cols 44, 45), `b2.grid_phase`: phase at frame f by linear interpolation between the beat times around t = f/100.
   **Offline whole-song fact.** The beat times come from `analyze_mix` (an online PLL run over the whole file; a beat is logged at the PLL's phase wrap, time = a
   window start). The interpolation at t uses the *next* beat time, so the phase at f depends on a beat that can lie up to one inter-beat interval after t
   (about 0.3-1 s; measured per song, summary in the STORAGE entry). Before the first beat and after the last it is extrapolated from the first / last interval.
   Everything downstream of the cortex (all four layers, hippocampus, arousal) inherits this.
3. The cortex recurrence itself (B7, epoch 6) is causal (`core_b7.py` header: "All causal"): layer states, the 2 s block structure (a block's
   hippocampal read uses only entries >= 17 s old, the query is built from the previous block), `err` (prediction made 2h-1 frames ago scored against the last h frames),
   surprisal (`braindump.surprisal`, NaN before frame 2h-1 = 19, 99, 399, 1599 for the four layers), arousal (one-pole rise 1 s / decay 8 s, running mean tau 60 s).
   Their only non-causal content is the inherited items 1-2 above.

## C. Features NOT used by E1 (listed because T0 had them)

- **Ear energy** (`ear_energy.py`): 1 s centred loudness mean and 2 s centred onset-density window = **1.0 s lookahead**. E1's input is the 7.64.1 list (cortex state + 44 ear),
  so ear energy is **not an input** and is not computed for T1b.
- T0 token pooling (mode-amplitude groups, token-mean surprisal, token beat phase): not used (7.64.5 drops per-token pooled features).

## D. Decision time and the listener (the planner side)

- Chunk k covers [0.5 k, 0.5 k + 0.5) s. Decision time d_k = 0.5 k - 0.25 s.
- The listener runs at 50 Hz on pairs of 100 Hz frames (mean of frames 2j and 2j+1). Step j has consumed frames up to 2j+1, i.e. audio up to
  (2j+1)/100 s + 23.2 ms (item A) and the beat fact of item B.2.
- The planner for chunk k reads listener step **j_k = 25 k - 13** (= floor(50 d_k - 0.5): the last step with (2 j + 1)/100 <= d_k; equality for every k).
  Only k = 0 has no step (j < 0); it reads the zero state (the listener start state), by rule.
- Residual lookahead the planner sees at decision time d_k, all listed: **23.2 ms** of audio (A) and up to **one inter-beat interval** through the beat grid (B.2).
- Tests (`scripts/body/test_t1b.py`, written with the model code): (1) listener outputs at steps <= j are unchanged when the cortex input after frame 2j+1 changes;
  (2) the planner's logits for token k are unchanged when the cortex rows after 2(25k-13)+1 are replaced by noise; (3) the carried 60 s state equals the one-pass state.
