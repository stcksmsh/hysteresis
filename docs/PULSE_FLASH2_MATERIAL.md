# Second pulse flash check: material (BRAIN_SPEC 7.79 pulse Q1 (d))

Rules: `docs/PULSE_FLASH2_RULES.md` (pushed before the material). Builder `scripts/body/pulse_flash2.py` (seeds 49301 songs, 49302 item order,
49303 session); check `scripts/body/pulse_flash2_check.py`. Material, key and session (built, NOT served):
`/secondary/hyst-data/body/pulse/flash2/` (`manifest.json`, `key.json`, `selection.json`, `Q00..Q19.mp4`, `session_2026-11-17/`).
Two items per song (flashes at pulse events / at librosa beats), 20 items, two questions each, same rendering as the first check.
Two motorica songs, so four items are local-only (`key.json` `local_only`).

| song | role | dataset | whole-song ratio (level) | excerpt start s | excerpt ratio (level) | pulse flashes | librosa flashes |
|---|---|---|---|---|---|---|---|
| fd_034 | new 2/3 | finedance | 0.626 (2/3) | 47 | 0.631 (2/3) | 45 | 80 |
| aioz_iOoW_Y_lto8_05_0_1680 | new 2/3 | aioz | 0.629 (2/3) | 11 | 0.625 (2/3) | 41 | 63 |
| ph_224 | new 2/3 | phantom | 0.764 (2/3) | 39 | 0.764 (2/3) | 63 | 85 |
| mo_kthstreet_gLH_sFM_cAll_d01_mLH6_ch06 | new 2/3 | motorica | 0.701 (2/3) | 84 | 0.701 (2/3) | 46 | 70 |
| fd_100 | new 3/2 | finedance | 1.230 (3/2) | 80 | 1.230 (3/2) | 64 | 51 |
| aioz_ULrcDcQabdA_07_0_1950 | new 3/2 | aioz | 1.517 (3/2) | 13 | 1.516 (3/2) | 66 | 49 |
| ph_157 | new 3/2 | phantom | 1.249 (3/2) | 126 | 1.249 (3/2) | 56 | 46 |
| mo_kthstreet_gPO_sFM_cAll_d02_mPO_ch01_funk_002 | new 3/2 | motorica | 1.229 (3/2) | 30 | 1.229 (3/2) | 62 | 51 |
| aioz_8JQ0zHmZBIg_05_0_1950 | failure | aioz | 0.976 (1) | 10 | 0.936 (1) | 69 | 70 |
| aioz_SZhU9XTCUiM_13_0_1950 | failure | aioz | 0.504 (1/2) | 21 | 0.502 (1/2) | 40 | 75 |

The excerpt ratio is the pulse tempo over librosa's tempo from the events inside the 30 s window; it stayed at the song's level for all ten.

## Checks (by numbers)

All 20 clips: video 30 s (within 0.05 s), an audio stream of 30 s (within 0.1 s), and the flash count in `key.json` equals the number of events
(pulse or librosa) inside the window `[start, start + 30)`. 0 of 20 failed.

## Deviations from the brief (all stated in the rules note as amendments)

- ph_187 was drawn first for phantom 2/3 and skipped: a 55 s song whose only window (starts 10 s) is below the song's median RMS. The next
  song of the shuffled pool was taken.
- The two failures are 65 s songs, so with the 10 s margins only starts 10-25 s exist. A different excerpt is possible only with a start
  difference of 10 s; the new excerpts overlap the first check's by 16-20 s (8JQ0: 24 s -> 10 s; SZhU: 10 s -> 21 s).
- Whole-song levels of the two failures are "1" (8JQ0) and "1/2" (SZhU); they are in as the brief asks, not as 2/3 or 3/2 songs.
- Songs under 50 s were excluded from the pool (a 30 s excerpt with 10 s margins needs 50 s).
