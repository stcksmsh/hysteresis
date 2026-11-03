# Planner brief: BODY_BRAIN_PLAN checked against the code (2026-11-03)

Done: branch `body` made, package copied, `test_compute` 12/12 pass, B7 close-out recorded as BRAIN_SPEC §7.11, pushed. The builder prompts
for Z + M0 + M2 (`docs/BUILDER_PROMPT_Z_M0_M2.md`) and H1 (`docs/BUILDER_PROMPT_H1.md`) are written, not yet sent.

## What does not match the code (facts; no rule changed)

1. **Branch base.** `body` is cut from `keys-decide`, not `b7`. `keys-decide` = `b7` plus docs only (the authoring ruling in NEXT_DECODER §2,
   the B7 briefs, the overseer skill). There is no code difference. Cutting from `b7` would have dropped those docs.
2. **`pack_features.py` stats key.** `feature_stats.npz` holds `mean` and `sd`. The packer reads `std` and falls back to 1.0, so its
   "std units" cast error would be in raw units. Fix in the builder prompt (read `std` or `sd`, as `train.py:68` does), with a test.
3. **Splits.** The corpus manifest has `train` (2,819) and `heldout` (357) only. Validation is a train subset by `val_artists.json`.
   `--splits train,heldout,val` is harmless; there is no `val` entry.
4. **Z2 is new code, not a flag.** `train.fit` checkpoints only after each epoch (about 2 h for B7). Every 30 min and on SIGTERM means
   mid-epoch state: batch index, scheduler position and all RNG states.
5. **Evaluation sets** (DEAM, MERP, Ballroom, GTZAN) are not in the corpus manifest format, so `pack_features.py` cannot pack them as they are.
   Nothing in the first order runs a check remotely, so the prompt makes packing them optional.
6. **Threads.** `jobs/bench_b7.json` sets `OMP_NUM_THREADS=4`. Spec §0 fixes training at 8. The prompt runs the local benchmark at 8 and
   Kaggle as written, with the core count recorded.
7. **MuJoCo, MJX and JAX are not installed.** The prompt puts them in a new venv `/secondary/hyst-env/body`, so the brain environment stays
   unchanged.
8. **Implement.** The rig's default implement is the mirror ball (`Implement::default()`). The body study uses the disc (`study_rig`).
   "Mirror implement" in §6 does not say which one. Prompt default: the mirror ball.
9. **M2 amplitude "0 to joint range".** Base yaw and wrist roll are continuous (±1e6° in the rig), so this has no bound. Prompt default:
   ±180°, logged FOR USER. At 4 Hz the speed limits allow only small swings (shoulder 90 °/s gives about 3.6° amplitude). The rate limiter
   clips the rest.
10. **K4 (later, M3).** The 37 descriptors (`body.rs::descriptors`) are defined on an 8 s clip at 60 fps. Per held-out song, K4 needs a rule
    for which windows. That rule must be fixed before M3 results.
11. **`mindState` source.** §2 says B7 epoch 6 feeds every brain lane in `mindState`. Today the lanes come from core-2b, and no B7 lane export
    exists. Nothing in the first order needs it.

## Questions

1. Item 8: mirror ball or disc for M0's masses? Recommendation: the mirror ball (the rig default, and the user's reflector).
2. Item 9: is ±180° the right amplitude cap for the continuous joints? Recommendation: yes for now.
3. Item 11: when should the B7 lane export happen? Recommendation: with B5 (the monitor), which needs a B7 dump anyway.
