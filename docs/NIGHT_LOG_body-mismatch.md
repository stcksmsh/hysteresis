# Night log: body-mismatch (WO53 part A, material) — 2026-11-19

Rules: `docs/MISMATCH_RULES.md` (pushed first). Code: `scripts/body/mismatch_build.py` (plan, assemble, checks), `mismatch_order.py`,
tests `test_mismatch_build.py` (6, pure logic). Out: `/secondary/hyst-data/body/mismatch/` (material_key.json, manifest.json, clips_src/,
clip_checks.json, order_checks.json, session_2026-11-19/). The session is built and NOT served.

- Plan: 20 pairs + 5 repeats, seed 53101. 10 V1 / 10 V2, 10 shifted / 10 different-song, real side 10/10 (5/5 per kind), 20 distinct
  songs, dataset x kind 4/3, 3/4, 3/3. Repeats R01..R05 = P07, P01, P16, P19, P17 (3 shifted, 2 different-song), sides reversed.
- Render: 20 movements via `retarget_render.sh` (lamp, pillar page, 1280x720, 30 fps). Page video proven independent of the music file
  (same csv, other m4a: max pixel difference 0 over 300 frames).
- Clip checks 25/25 pass: 645 frames, 21.5 s, 948,150 samples, gap digital silence and black, halves frame-identical, real half
  sample-exact on the pre-encode wav (diff <= 2/32768), AAC lag 0 samples and corr > 0.99, RMS ratio 1.00 +- 0.01, peak <= 0.99.
- Order checks pass (`order_checks.json`): position Spearman rho 0.28 (p 0.18), longest side run 4, code parity agrees 9/25, clip size
  difference real-first vs real-second 1.75 %, no metadata leaks.
- Eyes: P03, P11, P16 frames at 0, 5, 10, 11.5, 12, 21 s and waveforms extracted (`mismatch/spot/`); P03 and P16 looked at.

Deviations: (1) limits check uses the retarget gate tolerance 1.25 x LIMITS (worst speed 1.12, worst accel 1.21 of the limit), the
tolerance A's windows were gated at; the rules note said "no limit breached". (2) Gap "digital silence" is exact in the pre-encode wav
(AAC decode is not bit-exact). (3) The page's score clock ("Score 5.00s") is visible in every frame; it does not reveal the side.
(4) The two halves are one encoded video segment, so the size check of halves is 0 % by construction.
