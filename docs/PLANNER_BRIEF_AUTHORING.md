# For the planning agent: what the authoring tool should be, on B3's lanes (Hysteresis, 2026-11-01)

From the overseer. The user's B7 decision (BRAIN_SPEC.md §7.7) says: "The second builder builds the authoring tool now, per the 2026-11-01 ruling, on B3's lanes. When B7 lands, its lanes are swapped in through mindState (same shape)." The overseer has no written 2026-11-01 ruling on the authoring tool. Please give one, so that a builder can start while B7 trains. Where the user must choose, give options and a recommendation.

## What exists

**The authoring page** (`scripts/author/`, built 2026-10-30, never used by the user). It follows the pivot (NEXT_DECODER_THEN_BRAIN.md §2): the user authors, by eye, how the machine's state becomes the 15 body dimensions. No pre-registered rules, no claims.

- **Mapping:** body_d(t) = clamp(base_d + Σ_i w_di · input_i(t), 0, 1), then a one-pole smoother with a per-dimension τ (0–30 s).
- **10 inputs, all 0..1, lanes at 10 Hz:**
  - B2's arousal, tension, familiarity and surprisal, each normalised per song by its 5th and 95th percentiles;
  - spike: surprisal above a threshold slider, peak-held with a τ slider;
  - band1..band4: B2's band power per layer;
  - energy: core-2b's `mood.energy`.
- **Page:** one slider per input × dimension, plus base and τ, with a plot and audio.
- **Export:** the mapping is saved to JSON, then exported as a `bodyTrack` and attached to a sidecar. The arm preview is compiled offline from that (`ensemble_preview`). The page has no live arm.
- **Tests:** in node and Python.

## What B3 ended with (round 2, final; details in PLANNER_BRIEF_B3_ROUND2_RESULTS.md)

- All gated claims failed. The model with the lowest validation loss is round 2's epoch 12.
- **Per-layer splice z** (cross-song cuts with z ≥ 3): L1 49 %, L2 75 %, L3 19 %, L4 2 %. L1 and L2 carry most of the rise at a cut.
- **Habituation:** about 0, so the familiarity lane (minus the 30 s slope of surprisal) has nothing behind it.
- **Arousal tracking:** below core-2b (MERP 0.408 against 0.644). Your round-1 ruling keeps `mood.energy` from core-2b.

## Questions

1. **Scope.** Is "the authoring tool" the existing page re-pointed from B2's lanes to B3's? Or does it need more?
   - a) Re-point only: B3 round-2 lanes in place of B2's, same 10 inputs, same page.
   - b) a) plus a live arm previz inside the page that follows the sliders, instead of export-then-compile.
   - c) Something else.

   The overseer recommends a): it is the smallest step that lets the user start authoring. b) is a separate engineering task of unknown size.
2. **Which lanes and which checkpoint.** Round 2 epoch 12 for every brain lane?
   - **Spike:** from total surprisal, or from L1 + L2 only, since those carry the rise at cuts?
   - **Familiarity:** keep it, drop it, or keep it under its mechanism name only, e.g. "surprisal slope"?
   - Anything else to add or remove?
3. **Names on the page.** Under the B3 truth table, which lanes keep interpretive names and which show mechanism names? For example: arousal → "smoothed surprisal", tension → "L4 predicted variance".
4. **The shape for B7's swap.** B7 adds `hippo.recognition`, `hippo.novelty`, `hippo.recall_source` and an acting `neuromod.arousal`. Should the page now reserve slots for these, empty until B7 lands, or should B7 add them when it lands?
5. **Done-when.** What does the builder deliver for the user to use?
   - Proposal: the page built for the three danced songs, Instant Crush, Five Years and Presence, on B3 lanes.
   - Plus tests, and one exported arm preview per song from the neutral mapping, as proof that the path works.
   - No rule or claim.
6. **The user's review.** The pivot says design is judged by the user's eye and iterated fast. Should a blind second viewer (someone who has not seen the project) be part of it? If so, as advice only, or as a later check with rules fixed in advance? The user raised this on 2026-11-01 and has not decided.

Please answer point by point, so that the overseer can record the ruling as a dated note and write the builder prompt.
