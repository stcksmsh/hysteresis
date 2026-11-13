# Night log, branch body-mnet (work order 29A)

## MORNING SUMMARY (re-run under BRAIN_SPEC 7.45, 2026-11-13)
- Steps (7.45.10 order), all gain 1 silent: (i) input scale s = 0.04278085684427462 (5 fixed-point steps; drive-std ratio 0.2504; input 0.0370 vs
  recurrent 0.1477). (ii) calibrated at +-60 %. (iii) command-limiter share (output p5-p95 / target p5-p95): base yaw 0.985, shoulder 0.997,
  elbow 0.977, wrist bend 0.995, wrist roll 0.988: neither base nor shoulder below half, so the spinal spring-damper stays at 3 Hz. (iv) gain-1 hand
  extent at +-60 % = 0.182 m (>= 0.10 m): +-60 % and the 0.10 m gate kept.
- Redraw (seed 29011): 41 draws, 10 kept (draws 6, 7, 9, 14, 18, 23, 27, 29, 38, 41), 31 discarded. Discards per gate (a draw can fail several):
  motion 20, limits 11, contact 9, clearance 1, end stop 1. S11 (all low) failed motion, S12 (all high) failed contact and limits: neither shown,
  neither replaced.
- Rendered: Part 1 **10** lamp clips (S01-S10), Part 2 **2** ball clips (S01, S02), Part 4 unchanged (4 round-1 clips referenced). Part 3 NOT run.
  Old clips kept in `/secondary/hyst-data/body/motornet_toy/clips_v1/` (with `work_v1/`, `settings_v1.json`, `measurements_v1.json`, `diag_v1.json`).
- Threads: cores 6-11 pinned, simulations single-threaded, renders 3 recorder workers. Compute: fit about 1 min, sampling 41 draws about 8 s,
  rendering 12 clips about 15 min wall; no GPU.
- Files: `/secondary/hyst-data/body/motornet_toy/` (clips/, settings.json, measurements.json, stoprule_numbers.json, motornet_fit.json).
  Manifest: `clips/manifest.json`. Params: `docs/MOTORNET_PARAMS.md`.

## 7.45.5 stop-rule numbers (numbers only; the stop rule is NOT judged here)
Per shown setting: position-spectrum peak of each joint (base yaw, shoulder, elbow, wrist bend, wrist roll; Hann, 12 s, DC excluded, bins > 0.1 Hz,
bin width 0.083 Hz), "at beat" = within one bin of 100/60 = 1.667 Hz, and the activity participation ratio (PR). Script `motornet_stoprule.py`.

| setting | peak Hz per joint | joints at the beat | PR |
|---|---|---|---|
| S01 | 0.416, 0.416, 1.664, 0.416, 0.416 | elbow | 2.213 |
| S02 | 0.416 x5 | none | 2.179 |
| S03 | 0.416 x5 | none | 2.016 |
| S04 | 0.416 x5 | none | 2.637 |
| S05 | 0.499 x5 | none | 2.172 |
| S06 | 0.416 x5 | none | 2.185 |
| S07 | 0.499 x5 | none | 2.208 |
| S08 | 0.416 x5 | none | 2.377 |
| S09 | 0.250 x5 | none | 1.968 |
| S10 | 0.499, 0.499, 1.664, 0.499, 0.499 | elbow | 2.177 |

Note: in S01 and S10 the third joint (elbow) is the one at 1.664 Hz; no other joint of any setting peaks within a bin of the beat. PR range 1.97-2.64.
Other numbers (29B's script): all ten "cycles"; dominant hand frequency 0.25-0.50 Hz; mean hand speed 0.25-0.86 m/s; mean hand height 0.28-0.52 m;
straightness 0.71-0.96. Hand extents (p5-p95, max axis): 0.16-0.67 m.

## Log
- 2026-11-12: branch body-mnet from origin/body. Rules written and pushed before any clip (v1). v1 clips rendered, then held at the overseer's request
  (all joints peaked at the 1.664 Hz input; PR 2.0-2.2): the diagnosis (v1) is in `/secondary/hyst-data/body/motornet_toy/diag_v1.json`; v1 cause
  restated by the overseer: the round-1 command limiter cut the beat-rate command, then servo lag: base yaw 47.5 -> 41.7 -> 13.4 -> 5.4 deg.
- 2026-11-13: merged origin/body; re-run per 7.45 as above. Rules and params pushed (`361b49b`) before sampling and rendering.
- FOR USER: Part 3 (music) still waits for the audio files and excerpt start times; the path is tested on a synthetic click track only.
- FOR USER: S11 and S12 are not shown (they fail gates); Part 1 has 10 clips, not 12.

CLIPS READY (commit hash below)
