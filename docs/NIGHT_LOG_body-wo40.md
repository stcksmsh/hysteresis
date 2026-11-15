# Night log, builder (body-wo40), work order 40: S1 rebuild-check clips (2026-11-15)

Branch `body-wo40` (the name `body-s1` was taken by an older branch). Scripts `scripts/body/s1_clips.py`, `s1_render.sh`. Data `/secondary/hyst-data/body/s1/` (`picks.json`, `clips/`, `work/`, `gates_runB.npz`).

Run B rebuild gate pass share 0.9833 (same as 7.62). Pool sizes (test windows whose rebuild passes the gates at 1.25): FineDance 385, AIOZ 2029 (total 2414). Seed 35001, one window per song group.

| id | dataset | dancer | copy | window | group | pair order (shown) |
|---|---|---|---|---|---|---|
| S01 | finedance | fd_176 | V1 | 2 | fd_176 | orig then rebuild |
| S02 | finedance | fd_089 | V1m | 2 | fd_089 | rebuild then orig |
| S03 | finedance | fd_128 | V2m | 1 | fd_128 | rebuild then orig |
| S04 | finedance | fd_137 | V2m | 2 | fd_136 | orig then rebuild |
| S05 | aioz | aioz_3tHLWW--wh8_03_0_900_p3 | V2m | 0 | aioz_3tHLWW--wh8_01_0_697_p1 | orig then rebuild |
| S06 | aioz | aioz_66CzFi5hLKI_07_0_1830_p3 | V2m | 1 | aioz_66CzFi5hLKI_02_0_1406_p1 | rebuild then orig |

Rebuild first in 3 of 6 (`default_rng(35011)`). All 12 clips: h264 1280x720 + aac, 20.000 s each; audio = the window's music at offset 0. Original and rebuild both ran the same chain (guard, H1, limiter, servo, v2p); all 6 originals passed the gates. Looked at frames of S01_orig and S05_rebuild only (arm visible, lamp, trail; not used to select). Throwaway session built (6 pair items, order kept) and deleted.

Genre is not recorded for these windows; the manifest `genre` field holds the dataset name.

S1 CLIPS READY
