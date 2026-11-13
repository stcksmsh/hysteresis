# Night log body-v3 (WO35, report only)

## STEP A READY (see the commit that carries this line)

`docs/V3_REPORT.md` section A; per-clip numbers `/secondary/hyst-data/body/retarget_look/v3/numbers.json` (key `stepA`). Medians over the 20 clips (acceleration sign changes per second, mean over axes for positions / share of speed power above 3 Hz):

| signal | sign changes /s | power > 3 Hz | power > 6 Hz |
|---|---|---|---|
| (0w) human end point, world | 6.52 | 0.031 | 0.003 |
| (0r) human end point relative to its origin | 6.28 | 0.048 | 0.004 |
| (1e) robot lamp position, FK of the stage-1 angles | 8.75 | 0.150 | 0.029 |
| (1) stage-1 joint angles, mean over the 5 joints | 8.93 | 0.129 | 0.037 |

Facts: the human end point has about 6.3-6.5 acceleration sign changes per second at the 30 fps sampling (so it is not free of direction changes by that count), but its speed power above 3 Hz is 0.03-0.05, a third to a fifth of the lamp-FK position (0.150) and of the angles (0.129 mean, wrist bend 0.199, roll 0.249). V1 clips (wrist) are smoother than V2 clips (head) in (0w); per-variant tables are in the report. Position deadband 0.01 m/s^2 (FOR USER: default; 1 deg/s^2 at a 0.57 m radius).
