# Night log: body-retime-b (WO55 part B, arm-only re-timed mismatch round 2 material)

- 2026-11-19 17:05 branch `body-retime-b` from `origin/body` e5d2b29. Rules note `docs/MISMATCH2_RULES.md` written and pushed before any clip.
- 17:20 `retime.py` appeared on `origin/body-retime-a` (1158ddf) and was copied unchanged. Builder, arm-only patch, proof script, session `intro` option and tests (28 pass) pushed (f40efe4).
- 17:25 plan (unit hyst-wo55b-plan1): 25 items. Different-song foils: 9 AIOZ, 1 PhantomDance (P10, Motorica movement), none same-dataset. Shifted offsets 4.0-6.0 s, none outside Q3.
- next: render 20 movements, arm-only page (unit hyst-wo55b-render1).
- 17:50 render: 20 of 20 movements rendered arm-only (P04 proof: 415 strokes with hint+trail vs 273 arm-only, hint 22 -> 0, trail 120 -> 0). Assemble: 25 clips, manifest with `intro`. Session built (seed 53201), not served.
- next: checks, order checks, synthetic scorer (unit hyst-wo55b-chk1).
