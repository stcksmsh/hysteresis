# S1 rebuild check: report (BRAIN_SPEC 7.62; numbers only, no verdict)

Session `/secondary/hyst-data/body/s1/session_2026-11-15/` (seed 35021; tool archive `s1/tool_3f697b8`), Kosta, 2026-11-15 11:12-11:22.
6 pairs, original retarget vs Run B rebuild (both through guard, H1, limiter, servo, v2p), "Which looks more like a person dancing?",
first / second / same. Picks seed 35001 (overseer reproduced), rebuild first in 3 of 6 (seed 35011). Joined by the overseer from
`answers.csv` x `key/key.json`.

| order | pair | dataset, copy | first / second | answer | picked | replays | note (verbatim) |
|---|---|---|---|---|---|---|---|
| 1 | S05 | AIOZ, V2m | orig / rebuild | same | same | 0 | Both "wait" too much and have periods where they do nothing, dont match the music enough etc |
| 2 | S02 | FineDance, V1m | rebuild / orig | second | original | 2 | Second seems less flicky and more dancy? Idk |
| 3 | S01 | FineDance, V1 | orig / rebuild | first | original | 0 | First is better, more on-music maybe? Unsure, they are both decent? |
| 4 | S04 | FineDance, V2m | orig / rebuild | same | same | 0 | They are basically the same? |
| 5 | S06 | AIOZ, V2m | rebuild / orig | same | same | 0 | Too slow for the song in question, why is it so slow/small for the 1st, the 2nd is a tad bigger but still too small, there is literally a DROP in this section you gave me |
| 6 | S03 | FineDance, V2m | rebuild / orig | same | same | 0 | similar, perhaps 1st, idk |

Totals: same 4, original 2, rebuild 0. Copies picked by seed: V1 1, V1m 1, V2m 4.

## Overseer measures on the rendered joint data (50 Hz, `s1/work/<id>_<orig|rebuild>.csv`; base, shoulder, elbow, wrist bend, roll)

| pair | acceleration sign changes /s, orig | rebuild | mean speed deg/s, orig | rebuild |
|---|---|---|---|---|
| S01 | 2.2 2.0 2.7 3.0 2.8 | 2.2 2.6 2.5 3.2 3.0 | 8.1 21.3 58.1 87.3 123.4 | 7.4 21.8 56.6 78.6 110.7 |
| S02 | 2.2 2.6 2.4 2.9 3.2 | 1.8 2.2 2.2 3.0 3.0 | 15.5 22.4 60.1 61.4 58.4 | 14.3 23.1 57.0 59.7 60.1 |
| S03 | 2.4 2.5 3.2 3.6 3.8 | 1.8 2.3 2.8 2.8 3.0 | 8.7 11.9 14.5 29.3 57.1 | 8.7 11.3 14.1 27.2 51.2 |
| S04 | 2.7 3.0 3.4 3.2 5.6 | 2.5 2.6 3.0 2.8 3.8 | 10.9 11.4 12.1 45.1 34.9 | 10.7 10.4 11.2 42.6 31.1 |
| S05 | 1.6 2.1 2.6 2.8 2.9 | 1.8 2.1 2.9 2.6 3.4 | 8.2 10.5 13.4 17.4 23.0 | 8.1 9.9 13.2 17.2 20.9 |
| S06 | 2.6 3.8 3.4 4.7 4.6 | 1.8 2.8 2.8 3.4 3.6 | 8.6 6.9 14.3 25.7 28.5 | 8.4 6.6 14.3 20.6 23.6 |

The S02 rebuild (the "flicky" note) has no more acceleration sign changes than its original; 95th-percentile acceleration is similar (wrist
roll 1,055 vs 983 deg/s^2). The rebuild is up to about 10-20 % slower on the wrist joints in several pairs. The AIOZ originals (S05, S06)
move more slowly than the FineDance ones on shoulder and wrists.
