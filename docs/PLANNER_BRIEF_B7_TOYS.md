# For the planning agent: B7 is built, but toy tests T1 and T2 fail and the budget does not fit (Hysteresis, 2026-11-01)

From the overseer. B7 (BRAIN_SPEC.md §7, the user's decision of 2026-11-01) is built on branch `b7` (commit 1e95c5b, 141 tests pass). Nothing has trained. §7.3 makes the toy tests an engineering go/no-go: "fix code until they pass". Two fail, and the fixes now in view change §7, so they need you. The builder's numbers are below. The overseer has checked the commit and the notes; the toy numbers come from the builder's runs, not overseer recomputation. The B3 rulings stay closed.

## What was built, and where §7 had to bend

**The model** (`core_b7.py`, `B7_NOTES.md`):
- The network runs in 50-frame (0.5 s) blocks.
- **Read:** once per block, using the L3 + L4 state from the last frame of the previous block. §7.1a says "every frame from the current state", but that is a cycle: the current state depends on the relay input, and the relay input depends on the read.
- **Key and query projections** start as the same random matrix, not at zero. With both at zero, each one's gradient is multiplied by the other, and neither can ever move.
  - Relay, skip, w_g and w_τ are zero, so B7 still equals B3 at step 0.
- **Entries** become eligible 16 blocks (8 s) after they are written.
- **Arousal:** a one-pole filter on L1 + L2 surprisal, with a 60 s running mean.
- **Modulus exponent:** e = clamp(1 + w_τ·dev, 0.1, 10).
- **Relay input:** 91 dimensions (44 features, 2 grid phase, 44 retrieved, 1 recognition).

**Identity, B7 at step 0 against B3 round 2 epoch 12, on 10 held-out songs.** Maximum absolute difference:
- float32: 1.6e-4. §7.2 asks < 1e-5.
- float64: 3.3e-13.

The two scans use different block sizes, so they round differently. It is not a different function.

## Toy tests

**T3 (modulation, unit tests): pass.**

**T2 (relay): fail.** Synthetic AR(4), +100 ms horizon, 500 steps at reduced width:

| | MSE | Ratio to ridge AR | Needed |
|---|---|---|---|
| Model with relay | 0.0319 | 1.163 | ≤ 1.05 |
| Model, relay off | 0.0480 | 1.753 | |
| Ridge AR | 0.0274 | 1 | |

The loss was still falling at step 500. More steps were not run.

**T1 (recall): fail in all three data designs tried.** The test needs the error on the 16 s repeat at most 50 % of the error on the first occurrence.

| Data design | Error ratio (repeat / first) |
|---|---|
| iid noise | 0.99–1.00 |
| 2 s levels, no clock | 0.99 |
| clock channel, repeat-rich training draws | 0.99–1.00 |

- **Untrained, retrieval works.** On noise input, the top-1 source points into the first S. Recognition is 0.78–0.84 on the repeat, against 0.59 elsewhere.
- **After brief training, the relay does not use the retrieved value.** This held even with the key and query projections frozen.
- **Recognition saturates.** Its 95th percentile before the repeat is 0.43–0.99, so the repeat does not stand out.
- **The builder's reading,** untested: the cosine of trained, layer-normed L3 + L4 states is dominated by a common offset, so every entry looks alike. One likely fix is centring the keys and queries, for example subtracting a running mean before normalising. That changes §7.1a.

## Budget

Smoke run at 8 streams × 180 s, on a shared machine. On this machine B3 itself measured 2.35 h per epoch, against the real 1.46 h of round 2.

| Setting | Step | Epoch | 8 epochs | Peak memory |
|---|---|---|---|---|
| B3 | 14.5 s | 2.35 h | 18.8 h | 14.2 GB |
| B7, 8 streams | 30.5 s | 4.96 h | 39.6 h | 22.2 GB, killed at the 20 GB cap |
| B7, 8 streams + gradient checkpointing | 41 s | 6.59 h | 52.7 h | 10.4 GB |
| B7, 3 streams | 22.9 s | 9.86 h | 78.9 h | 8.8 GB |

- The 0.5 s block-sequential modulation makes a step 2.1× slower than B3's.
- The 4.7 ladder's branch is gradient checkpointing at 8 streams. Scaled by B3's real-to-smoke ratio (1.46 / 2.35), that is about 4.1 h per epoch. 24 h then covers about 5–6 epochs of the allowed 8.
- Memory grows over the first steps (14 GB at step 1, about 20 GB at step 2, without checkpointing). The cause was not found.
- The checks (C1–C5) have not yet been run end to end on real songs.

## Questions

1. **T1, the hippocampus.** Which of these, if any?
   - a) Centre the keys and queries (subtract a running mean per song, or a learned bias) before normalising, then retest T1 on the same three designs.
   - b) Change what is stored: a key from the raw features or the layer inputs, not the trained L3 + L4 states.
   - c) An auxiliary loss on the retrieval, e.g. predict the 2 s ahead from the retrieved value alone. That is a new objective.
   - d) Something else.
   - How many tries before you drop the hippocampus from B7?

   The overseer leans to a) first, as the smallest change that tests the builder's diagnosis.
2. **T1's bar.** Is "error ratio ≤ 0.5 after brief training on a small model" the right go/no-go? Or should T1 be split into "retrieval finds the source" (passing now, untrained) and "the network uses it" (failing)?
3. **T2.** May the toy run longer, say 2,000 steps, before it counts as failed? Or is a 16 % gap to ridge AR at +100 ms a design problem in the relay?
4. **Read timing and key initialisation.** Do you accept the two departures above (a read once per 0.5 s block from the previous block's state; key and query starting equal and random)?
5. **Identity threshold.** Is it met by the float64 check (3.3e-13), with float32 rounding (1.6e-4) recorded as expected? Or is some other tolerance needed?
6. **Budget.** At about 4 h per epoch, 24 h buys 5–6 epochs from the warm start. Options:
   - a) Keep 24 h and accept fewer epochs; early stopping may end it sooner anyway.
   - b) Raise the stop to about 34 h for 8 epochs. That is the user's call.
   - c) Cut the cost: modulation blocks of 2 s instead of 0.5 s, or modulation on L3 and L4 only.

   Which do you recommend, given that the warm start begins from a trained B3?
7. **Order.** Must T1 and T2 pass before any training, or may B7 train with relay and modulation while the hippocampus is fixed? The latter means a second, separate training run later.

Please answer point by point, so that the overseer can record the rulings as a dated note in `docs/BRAIN_SPEC.md` §7 before any further B7 code.
