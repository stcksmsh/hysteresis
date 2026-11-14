# Motor-network toy test: parameters actually used (work order 29A, re-run under BRAIN_SPEC 7.45)

Definitions and rationale: `docs/MOTORNET_RULES.md`. Code: `scripts/body/motornet.py`, `motornet_fit.py`, `motornet_run.py`, `motornet_render.sh`,
`motornet_music.py`. Fit result file: `/secondary/hyst-data/body/motornet_toy/motornet_fit.json`. The v1 study (CAL_FRAC 1.0, s = 1, gate 0.05 m) is
in `clips_v1/`, `work_v1/`, `settings_v1.json`, `measurements_v1.json`, `diag_v1.json`.

| Item | Value |
|---|---|
| Units N | 200 |
| Time constant tau | 75 ms |
| Nonlinearity | `r = tanh(g_i x_i)` |
| Integration | Euler 5 ms (200 Hz), read at 100 Hz; x = 0 at start |
| Recurrent W | iid Gaussian / sqrt(N), seed 29001 stream 0, rescaled to spectral radius exactly 1.05 |
| Input weights Win (200 x 3) | iid normal, seed 29001 stream 1, **times s = 0.04278085684427462** |
| Input scale s | fixed-point iteration, 5 steps (s = 1, 0.1600, 0.05518, 0.04370, 0.04278); final ratio of drive stds 0.2504 (target 0.25) |
| Drive stds at the final s (gain 1, silent, shown 12 s, mean over units) | input 0.0370, recurrent 0.1477 |
| Control units | 4; subsets of 80 neurons each (stream 2, overlap allowed); `g_i = prod_k c_k^m_ki`; no global gain |
| Control range | c in [0.5, 2.0], log-uniform |
| Readout Wout (5 x 200) | iid normal / sqrt(N), seed 29001 stream 3 |
| Silent input | cos, sin of `2 pi t 100/60`; arousal 0 |
| Music input | `l3_cos`, `l3_sin` (y cols 2, 3; 0.5 s blocks, linear interpolation), `arousal_b7` standardised by the pooled mean/sd of the three danced songs, clipped +-3; same `s` |
| Calibration | **CAL_FRAC 0.6**: at c = 1, silent, 10 s warm-up + 12 s: per-joint mean m and sd s of y; target = centre + 0.6 * AMP * (y - m) / (2 s); centre (0, -60, 30, -15, 0), AMP (30, 12, 16, 16, 45) deg. Raw output mean ~0 (<= 7e-4), sd (0.150, 0.096, 0.111, 0.179, 0.083) |
| Spinal spring-damper | **3 Hz** (unchanged: the 1.5 Hz rule did not trigger), zeta 0.7, 1 ms semi-implicit Euler, start at rest on first target |
| Servo | kp = `make_arm.KP` (scale 1.0), zeta 1.5, `kv = 2 zeta sqrt(kp I)`; limiter, 0.5 deg margin, hard stops as round 1 |
| Stepping | plain MuJoCo CPU, 100 Hz control, 5 x 2 ms substeps |
| Warm-up / shown | 10 s / 12 s; contacts counted from 1.5 s before the shown part |
| Gates | round 1's (hf <= 0.01, reversals <= 6 /s, clearance, contact, end stops, limits) + extent >= 0.10 m, no 3 s stretch under 0.01 m/s |
| Draw seed | 29011 (settings), 29041 (Part 4 pick), 29031 (Part 3 pick, held) |
| Video | 1280x720 h264, 12 s, round 1's recorder and camera, lamp (Part 1) or ball (Part 2) |

## Step results (gain 1, silent; `motornet_fit.py`)

- Step 3, command-limiter share (limiter-output p5-p95 / target p5-p95) at spinal 3 Hz, +-60 %: base yaw 0.985, shoulder 0.997, elbow 0.977,
  wrist bend 0.995, wrist roll 0.988. Target p5-p95 (deg): 27.5, 11.9, 16.1, 14.4, 43.8; limiter output: 27.1, 11.9, 15.8, 14.4, 43.3.
  Neither base nor shoulder is below half: the spinal spring-damper stays at 3 Hz.
- Step 4, gain-1 hand extent at +-60 %: 0.182 m on one axis (>= 0.10 m): +-60 % and the 0.10 m gate are used. Realised joint p5-p95 (deg):
  20.2, 9.4, 12.9, 13.7, 40.5.
- Launch: `systemd-run --user --unit=hyst-wo29a-<name> -p MemoryMax=10G -p MemorySwapMax=0 --working-directory=<scripts/body> motornet_job.sh python -u <script>`
  (cores 6-11, mains only).

## Run record

- Draw (seed 29011): 41 draws, kept draws 6, 7, 9, 14, 18, 23, 27, 29, 38, 41 as S01-S10. Discards per gate: motion 20, limits 11, contact 9,
  clearance 1, end stop 1 (31 discarded draws; a draw can fail several gates). S11 (all low): fails motion. S12 (all high): fails contact and
  limits. Neither shown or replaced.
- Rendered: Part 1 S01-S10 (lamp), Part 2 S01 and S02 (ball), Part 4: A_lag_low, A_neutral, A_posture_high, A_vigour_high (seed 29041, referenced).
  Part 3 not run.
- Threads: cores 6-11 pinned (`taskset`), simulations single-threaded, 3 recorder workers; mains only. Compute: fit about 1 min, sampling about 8 s,
  rendering about 15 min wall; no GPU.
- Numbers per setting (29B's `motornet_measure.py`, `stoprule_numbers.json`): see `docs/NIGHT_LOG_body-mnet.md`.
