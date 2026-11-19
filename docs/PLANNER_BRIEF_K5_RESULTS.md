# Planner brief: K5 try 1 results (2026-11-06)

For the planning agent. Rules of record: `docs/BRAIN_SPEC.md` §7.17–7.21. ONE arm only. Pass/fail in ARGMAX; sampled reported only.

## What ran

- Work order 10 (`docs/BUILDER_PROMPT_WO10_K5_RUN.md`), branch `body-k5train` at e8cbba5, merged into `body` (b74da7d).
- M3e recipe unchanged (§7.21 point 4). One full pass over the 15,624 training windows (977 rounds of 16 windows), on the laptop,
  13.15 h of the 24 h compute box. Pausable/stoppable with per-round checkpoints; one 11-minute wait on battery, not counted.
- Early stopping (fixed before the run): validation every 200 rounds on 217 validation songs (argmax, external (a)); stop after two
  validations in a row fail to beat the best. It never fired.
- K5 check on `best.pkl` (round 977): 1,071 windows of the 357 held-out check songs (73 held-out artists), policies trained / untrained /
  trained with kappa = 0, both modes, per-song bootstrap (357 songs, 10,000 resamples).
- The first check run was killed for memory (the trainer process stayed alive under the same 8 GB cap); the check alone was relaunched
  (14 GB), reusing the finished trained/untrained scores and cached rollout batches. Rescoring the cached kappa-0 argmax rollouts gave the
  killed run's numbers exactly. Cross-process runs differ by about 4e-12 (XLA float summation order).

## Results (recomputed by the overseer from the saved per-song values; all match the builder's report)

Validation curve, argmax external (a), rounds 200 / 400 / 600 / 800 / 977: 0.558, 0.544, 0.574, 0.596, **0.634**
(internal (a): 0.510, 0.470, 0.539, 0.597, 0.639). Still rising at the end of the pass.

K5 check, ARGMAX:

| Decoder | Trained (a) | Paired vs untrained | Paired vs kappa = 0 |
|---|---|---|---|
| External | 0.625 [0.603, 0.648] | +0.452 [0.435, 0.470] | +0.086 [0.073, 0.099] |
| Internal | 0.636 [0.613, 0.659] | +0.496 [0.477, 0.515] | +0.177 [0.165, 0.190] |

Controls, argmax: untrained ext (a) 0.173 [0.159, 0.187], int 0.139; trained with kappa = 0 ext 0.540 [0.517, 0.563], int 0.458.
Sampled (report only): trained ext 0.643, int 0.658; vs untrained +0.742 / +0.757; vs kappa = 0 +0.134 / +0.207; all intervals above 0
(the untrained policy sampled scores below 0: ext −0.098).
Other: (b) RMS joint speed 49.3 deg/s (untrained 45.4); (c) program/state MI 0.037 nats, p 0.001 (untrained 0.155); 8 programs used.

Toy comparison (different windows, not the same scale): M3e toy try 1 ext 0.991 / int 0.951; K5 is lower on real songs but the
trained-minus-untrained gap (0.45 / 0.50) is about the toy's (0.555 / 0.644).

## Verdict under the rules

- **K5 try 1 PASSES** (§7.18 point 2): in argmax the external (a) interval is above 0 (beats the time-shifted control) and the paired
  trained − untrained interval is above 0. The internal decoder passes the same two tests.
- Wording of record (§7.20 point 3): "It learned to move so that its inner state can be read from its body, by you and by itself (both
  read the same joint positions)."
- Phase-coupling wording ("moves in time with its inner rhythm") is allowed (§7.19 A1): trained beats kappa = 0, paired interval above 0,
  argmax, both decoders.
- Caveats: the two observers read the same joint positions, so the decodings are not independent; (a) is a gap against time-shifted targets,
  not absolute accuracy; MI is small and lower than the untrained policy's; one try, one seed.
- Mechanism wording stays "present" until the seed-2 ablations (§7.21 point 1).

## Not done

- **Danced-song videos from `best.pkl` (§7.19 C, the user's eye).** No path exists from a trained policy to a whole song: (1) the three
  danced songs' lanes are not exported in K5 format; (2) the policy trained on 60 s windows with 30 s causal normalisation, so a 200–340 s
  song needs a chunked rollout keeping the carry; no script rolls a full song and writes the joint CSV; (3) the one-arm camera/render
  lives in the authoring tool (fallback path), outside the K5 files.

## Questions

1. **Videos.** Build the path now: export the three songs' B7 lanes in K5 format, a chunked full-song rollout (carry kept across
   60 s chunks, 30 s causal normalisation as in training), joint CSV, then the existing one-arm camera render next to the fallback videos.
   Options: (a) build it now, before seed 2 (recommended: the user judges by eye, and seed 2 needs ~2 × 13 h of the same machine);
   (b) run seed 2 first. Recommendation: (a), the render job is light and can share the machine with seed 2 if needed.
2. **Seed 2 (§7.21 point 3).** Proceed as ruled: seed 2 of M3e try 1 and A1–A3 on the laptop (`docs/BUILDER_PROMPT_WO11_SEED2.md`).
   Is seed 2 of the K5 run itself also wanted, or only the toy seeds? Recommendation: toy seeds only now; a second K5 seed only if the
   wording needs it.
3. **Validation still rising at the end of the pass** (0.596 → 0.634 over the last 177 rounds). The rules allow one pass. Options:
   (a) accept try 1 as is (recommended: it passes, and §7.20 fixed one pass); (b) a second pass as a new, separately labelled run, never
   replacing try 1's verdict.
