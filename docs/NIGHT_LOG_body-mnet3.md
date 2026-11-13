# Night log, body-mnet3 (WO29C, motor-network toy test Part 3)

## MORNING SUMMARY

All 10 Part 3 renders are gated, rendered (1280x720 h264 + aac, 12 s, lamp, song excerpt muxed), in the manifest, 3 frames per render looked at (frames 15/180/345, all sane: lamp and arm in frame, no glitches).
3 of the first 10 sims failed the gates with music; replaced by the rule of BRAIN_SPEC 7.46.7 (7.44.3.4), no gate changed, no network change.
Cores 6-11; lanes 6 torch threads, simulations single-threaded, 3 recorder workers; mains only.

Generator handling: `default_rng(29031)`; the 5 original pair draws (`rng.choice(10, 2, replace=False)`) are replayed from the fresh generator, then replacements continue from that state with `rng.integers(10)` one at a time, in song order (1b, 3b, 5a). A skipped draw (the pair's two settings, or one already failed for that song) is consumed.

## Failures and replacements (gate numbers)

- P3_1b: S04 FAILED parts ['contact', 'limits']: contact_substeps 13, accel_ratio 1.18, speed_ratio 1.00, extent 0.526 m
  -> replaced by S06 (passed)
- P3_3b: S02 FAILED parts ['contact', 'limits']: contact_substeps 339, accel_ratio 7.32, speed_ratio 1.00, extent 0.584 m
  -> replaced by S03 (passed)
- P3_5a: S06 FAILED parts ['contact', 'limits']: contact_substeps 180, accel_ratio 1.96, speed_ratio 0.55, extent 0.145 m
  -> replaced by S08 (passed)

## Part 3 numbers (mean hand speed m/s a|b; mean arousal_b7 over the shown 12 s, raw, standardised input)

- P3_1 blue-lagoon ['S03', 'S06']: hand 0.365 | 0.473; arousal raw 0.485, std -0.23
- P3_2 schizoid-man ['S01', 'S07']: hand 0.297 | 0.292; arousal raw 1.405, std 0.66
- P3_3 epitaph ['S08', 'S03']: hand 0.184 | 0.273; arousal raw 0.106, std -0.59
- P3_4 breathe ['S03', 'S05']: hand 0.281 | 0.797; arousal raw 1.166, std 0.43
- P3_5 one-of-these-days ['S08', 'S01']: hand 0.063 | 0.163; arousal raw -0.733, std -1.40

- FOR USER: P3_5a (S08, One of These Days) is nearly still (hand 0.063 m/s), passes the gates (extent >= 0.10 m). Part 3 song 5 has a low arousal input (std -1.40), so low motion is expected.

Files: `scripts/body/motornet_part3.py` (prep, clips, replace, manifest), `motornet_part3_job.sh`, `motornet_part3_render.sh`. Data in `/secondary/hyst-data/body/motornet_toy/` (clips/P3_*, manifest.json, manifest_parts124.json, part3_numbers.json, work3/replacements.json, work3/*.failed0.json). No audio in git.
