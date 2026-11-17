# Pulse flash check (WO48 material, Kosta, 2026-11-17)

Session `/secondary/hyst-data/body/pulse/flash/session_2026-11-17` (seed 48201): 20 items, blind random order, 10 songs x (pulse, librosa),
the same 30 s excerpts as the V4 check. Two questions per item: "Is the flash on the beat?" and "Is it the right speed?". All 20 were
answered. Scored by the overseer from `answers.csv` against the session key and `pulse/flash/key.json`. Server stopped.

## Totals

| source | on beat: yes / partly / no | speed: right / too fast / too slow |
|---|---|---|
| pulse | 6 / 3 / 1 | 8 / 0 / 2 |
| librosa | 7 / 3 / 0 | 7 / 3 / 0 |

## Per song (excerpt pulse / librosa tempo ratio from `pulse/songs/<key>.json` "excerpt")

| song | pulse/lib | pulse answer | librosa answer |
|---|---|---|---|
| aioz_8JQ0 | 0.92 | partly, too slow ("a bit too slow and not right on beat") | yes, right ("finds the 4/4 well, doesnt catch the pre-drop doubling and quadrupling") |
| aioz_SZhU | 0.75 | no, too slow ("not catching it almost at all") | partly, too fast |
| fd_018 | 0.61 | partly, right ("about correct?") | partly, too fast ("on beat but follows fast element not the beat") |
| fd_053 | ~1 | yes, right ("finds the beat, doesnt catch the short beat dropouts or the pre-drop changes") | yes, right ("doesnt find the beat dropout") |
| fd_183 | 0.88 | yes, right ("a bit off beat and slow sometimes (SLIGHTLY) but usable and ok") | yes, right |
| Motorica jazz | 1.02 | partly, right ("matches it sometimes ... does 'double rapid detections' sometimes") | yes, right ("jittery intervals somewhat") |
| Motorica street | ~1 | yes, right ("doesnt catch the dropout section as having no beat") | yes, right |
| ph_084 | 1.00 | yes, right ("start it finds a beat that isnt there somewhat") | partly, too fast ("very beginning has no real beat and it imagines it") |
| ph_102 | 0.97 | yes, right | yes, right ("jittery inter-click timings ... when the beat drops out it continues") |
| ph_137 | 0.98 | yes, right | yes, right |

## Notes

- **Failures:** the pulse fails where it runs 8-25 % slower than the beat (aioz_8JQ0 0.92, aioz_SZhU 0.75). Neither song is one of the clean
  3:2 cases.
- **Metrical level:** on fd_018, where librosa chases the fast element, the pulse at 0.61 of librosa was judged the right speed.
- **3:2 question not decided:** the excerpts contain only two items near 2:3 (fd_018 partly; aioz_SZhU no). The check cannot settle
  PLANNER_BRIEF_PULSE_AIST Q1.
- **Dropouts:** both sources continue through beat dropouts. Kosta noted this as a miss 4 times (dropouts, pre-drop doubling, a dropout
  section).
- **Kosta's statement of purpose** (Motorica street, librosa item, verbatim): "the purpose isnt to find the beat, but possible end locations
  to match music, so it isnt just flashing on beat, but flashing at oportune moments e.g. beat/dropout/accent whatever right?"
