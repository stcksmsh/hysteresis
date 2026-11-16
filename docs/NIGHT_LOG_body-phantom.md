# Night log, branch body-phantom (work order 42: PhantomDance + Motorica, T0, look clips)

2026-11-15

- PROVENANCE PhantomDance: 260 pairs, 9.502 h, 30 fps, audio 16 kHz (257 files; 3 are 44.1 kHz stereo); zip v1.2, inner folder v1.1; licence MIT (music rights not stated).
  Motorica: 74 paired sequences (47 further BVH have no music), 3.558 h, 120 fps motion (decimated to 30), audio 48 kHz mono; licence copied verbatim, stays on this laptop.
  Files: `/secondary/hyst-data/{phantomdance,motorica}/PROVENANCE.md` + `FILES.sha256`. Downloads untouched (copies).
- Rules note pushed before any retarget run: `docs/T0_PHANTOM_RULES.md` (mapping for both sources, seeds 42001 / 42002, look-clip rule). Nothing needed a STOP: both skeletons map without
  a design choice beyond Motorica's missing spine2 (identity; logged FOR USER).
- Lanes, split (seeds 42001 / 42002), four-copy T0 sequences with gates: PhantomDance 260 dancers (1040 npz), 19.28 usable h over four copies (kept share V1 .46, V2 .60);
  Motorica 74 dancers (296 npz), 9.66 usable h (kept share .69-.76). Report `docs/T0_PHANTOM_REPORT.md` (jitter and gesture amplitude vs FineDance, band-limit check: Motorica audio is NOT band-limited, 0.3 % of power above 8 kHz against FineDance 0.5 %; PhantomDance has none).
- Look clips: 6 per source rendered (1280x720, h264+aac, 20 s), manifests (labels "follow") in `t0_phantom/look/` and `t0_motorica/look/`; throwaway sessions built, loaded, deleted. Motorica strata changed to jazz x2 / street x4 (no misc has music; rules addendum).
- Existing T0 and retarget tests plus 5 new adapter tests: 31 pass.
- FOR USER: see the list at the end of `docs/T0_PHANTOM_RULES.md` (no PhantomDance genres; Motorica spine2 identity; tokens standardised with FineDance constants, raw stored; PhantomDance file 000 cut at its malformed frame; look clips alternate V1/V2).
- PHANTOM READY 8acdc69
