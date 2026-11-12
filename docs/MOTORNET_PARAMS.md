# Motor-network toy test: parameters actually used (work order 29A)

Definitions and rationale: `docs/MOTORNET_RULES.md`. Code: `scripts/body/motornet.py`, `motornet_run.py`, `motornet_render.sh`, `motornet_music.py`.

| Item | Value |
|---|---|
| Units N | 200 |
| Time constant tau | 75 ms |
| Nonlinearity | `r = tanh(g_i x_i)` |
| Integration | Euler 5 ms (200 Hz), read at 100 Hz; x = 0 at start |
| Recurrent W | iid Gaussian / sqrt(N), seed 29001 stream 0, rescaled to spectral radius exactly 1.05 |
| Input weights Win (200 x 3) | iid normal, seed 29001 stream 1 |
| Control units | 4; subsets of 80 neurons each (stream 2, overlap allowed); `g_i = prod_k c_k^m_ki`; no global gain |
| Control range | c in [0.5, 2.0], log-uniform |
| Readout Wout (5 x 200) | iid normal / sqrt(N), seed 29001 stream 3 |
| Silent input | cos, sin of `2 pi t 100/60`; arousal 0 |
| Music input | `l3_cos`, `l3_sin` (y cols 2, 3; 0.5 s blocks, linear interpolation), `arousal_b7` standardised by the pooled mean/sd of the three danced songs, clipped +-3 |
| Calibration | at c = 1, silent, 10 s warm-up + 12 s: per-joint mean m and sd s of y; target = centre + 1.0 * AMP * (y - m) / (2 s); centre (0, -60, 30, -15, 0), AMP (30, 12, 16, 16, 45) deg |
| Spinal spring-damper | 3 Hz, zeta 0.7, 1 ms semi-implicit Euler, start at rest on first target |
| Servo | kp = `make_arm.KP` (scale 1.0), zeta 1.5, `kv = 2 zeta sqrt(kp I)`; limiter, 0.5 deg margin, hard stops as round 1 |
| Stepping | plain MuJoCo CPU, 100 Hz control, 5 x 2 ms substeps |
| Warm-up / shown | 10 s / 12 s; contacts counted from 1.5 s before the shown part |
| Gates | round 1's (hf <= 0.01, reversals <= 6 /s, clearance, contact, end stops, limits) + extent >= 0.05 m, no 3 s stretch under 0.01 m/s |
| Draw seed | 29011 (settings), 29041 (Part 4 pick), 29031 (Part 3 pick, held) |
| Video | 1280x720 h264, 12 s, round 1's recorder and camera, lamp (Part 1) or ball (Part 2) |

## Run record

- Settings: draws 1-10 all passed (0 discards, 0 per gate). S11 (all low) and S12 (all high) both failed the **motion** gate, were not shown and
  not replaced. So Part 1 has **10** clips, Part 2 has 2 (S01, S02 ball), Part 4 has 4 (A_lag_low, A_neutral, A_posture_high, A_vigour_high,
  referenced from round 1, not re-rendered). Part 3 held; path tested on a synthetic click track only.
- Gain-1 calibration: output sd per joint (raw) 0.81 / 0.89 / 0.80 / 0.53 / 0.48; means ~0.
- Threads: all jobs pinned with `taskset -c 6-11`; the simulations are single-threaded (OMP_NUM_THREADS=1), one process; renders ran 3 recorder
  workers at a time (`dialstudy_render.sh`). Mains only (wrapper polls `/sys/class/power_supply/ADP1/online`).
- Compute: sampling 10 draws + 2 extremes + calibration about 25 s wall; rendering 12 clips about 10 min wall; no GPU.
- Launch: `systemd-run --user --unit=hyst-wo29a-<name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<scripts/body> motornet_job.sh python -u motornet_run.py sample`
  then `motornet_job.sh motornet_render.sh`, then `motornet_run.py manifest`.
- Measurements (29B's `motornet_measure.py`, run on these files): all ten settings show regime "cycles", dominant frequency 1.664 Hz (the beat
  input rate), participation ratio 2.03-2.2, mean hand height 0.513-0.514 m. Spot-check of S01 and S05 by an independent computation:
  agreement (hand speed within 0.5 %, PR and frequency identical). Numbers only, no reading.
- Music-path test (synthetic 100 BPM click, 40 s): cortex lanes computed through `k5_video_lanes.lanes_of`; network driven from them with a 10 s
  warm-up and a 12 s excerpt from 20 s; the lane spread is small (l3 std 0.06-0.10 against ~0.6 on a real song) and arousal sits near +4
  (clipped to +3), so the clip is almost static and fails the motion gate. This shows the path runs; it is not a result.
