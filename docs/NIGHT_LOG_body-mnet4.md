# Night log, body-mnet4 (WO30B, motor-network toy round 2)

## MORNING SUMMARY

All clips are gated, rendered (1280x720 h264, 30 s, lamp; Part B with the excerpt audio muxed), in the manifest; 3 frames per clip looked at (frames 60/450/840 at 30 fps: lamp and arm in frame, motion visible, no glitches).
Rules file `docs/MOTORNET2_RULES.md` was pushed first (94a57ae); nothing changed after. ENERGY READY 9d99a8e (30A) merged before any music input was computed.
Stop rule NOT hit (7.47.4.8): silent runs, base yaw p5-p95 between 27 and 74 deg; PR >= 3 in at least one population for S02, S04, S05, S08. Part B was rendered.
Cores 6-11, lanes 6 torch threads, simulations single-threaded, 3 recorder workers; mains only.

Network (see rules for all numbers): slow 100 units tau 300 ms, fast 100 units tau 75 ms; raw within-block radii 0.767 / 0.730 scaled to 1.05, full matrix radius 1.498; input scales s_slow 0.1947, s_fast 0.1804 (ratios 0.2503 / 0.2505); subsets (slow, fast) (39,41) (43,37) (41,39) (33,47); spinal stays 3 Hz (limiter shares 0.98-1.00); gain-1 silent extent 0.297 m.
One forced change from round 1: the reversal rate divides by the 30 s clip length (round 1's code divides by 12); thresholds unchanged. Calibration window 30 s (the shown length).

## Sampling (seed 30011)

17 draws, 8 kept (draws [2, 5, 6, 9, 11, 14, 15, 17]) as S01-S08, 9 discards. Per gate {'motion': 6, 'contact': 3, 'limits': 2}; per run {'silent': 6, 'blue-lagoon': 3}. Discards:

- draw 1: silent fails ['motion'] (extent 0.019 m)
- draw 3: blue-lagoon fails ['contact'] (extent 0.742 m)
- draw 4: silent fails ['motion'] (extent 0.018 m)
- draw 7: blue-lagoon fails ['contact', 'limits'] (extent 0.396 m)
- draw 8: blue-lagoon fails ['contact', 'limits'] (extent 0.674 m)
- draw 10: silent fails ['motion'] (extent 0.016 m)
- draw 12: silent fails ['motion'] (extent 0.094 m)
- draw 13: silent fails ['motion'] (extent 0.026 m)
- draw 16: silent fails ['motion'] (extent 0.015 m)

Round-1 S03 reference at 30 s per song: all 5 pass the gates (none dropped).

## Part A silent stats (PR slow/fast, base yaw p5-p95 deg, shoulder p5-p95 deg, facing drift deg, 3 s moving-mean range deg, hand m/s)

- S01: PR 2.32/3.12, yaw 30.8, shoulder 9.7, drift -1.8, mm range 16.9, hand 0.160
- S02: PR 3.41/3.75, yaw 66.5, shoulder 9.7, drift -35.9, mm range 61.0, hand 0.157
- S03: PR 1.87/2.69, yaw 51.2, shoulder 6.3, drift -5.9, mm range 46.8, hand 0.119
- S04: PR 3.03/3.36, yaw 73.8, shoulder 11.9, drift -38.1, mm range 56.7, hand 0.231
- S05: PR 2.21/3.66, yaw 31.4, shoulder 5.5, drift 11.3, mm range 30.8, hand 0.097
- S06: PR 2.07/2.34, yaw 61.5, shoulder 16.5, drift 2.2, mm range 59.2, hand 0.204
- S07: PR 1.96/2.78, yaw 41.0, shoulder 6.9, drift 12.9, mm range 38.7, hand 0.102
- S08: PR 3.82/4.68, yaw 27.2, shoulder 4.5, drift -0.3, mm range 22.7, hand 0.167

## Part B (seed 30031; new setting vs round-1 S03)

- B1 blue-lagoon: new S06 hand 0.172, yaw 46.1, shoulder 5.7; round-1 S03 hand 0.332, yaw 26.5; ear energy raw 1.34 (input 1.67), arousal raw 0.415 (input -0.29)
- B2 schizoid-man: new S07 hand 0.059, yaw 36.8, shoulder 4.9; round-1 S03 hand 0.232, yaw 33.4; ear energy raw 0.08 (input 0.10), arousal raw 0.757 (input 0.04)
- B3 epitaph: new S05 hand 0.073, yaw 20.7, shoulder 3.6; round-1 S03 hand 0.247, yaw 23.6; ear energy raw -0.05 (input -0.07), arousal raw 0.014 (input -0.68)
- B4 breathe: new S03 hand 0.117, yaw 70.6, shoulder 7.2; round-1 S03 hand 0.294, yaw 26.4; ear energy raw -0.39 (input -0.49), arousal raw 0.997 (input 0.27)
- B5 one-of-these-days: new S01 hand 0.071, yaw 22.4, shoulder 5.0; round-1 S03 hand 0.126, yaw 10.7; ear energy raw -0.30 (input -0.38), arousal raw -0.694 (input -1.36)

Files: scripts `motornet2.py`, `motornet2_fit.py`, `motornet2_lanes.py`, `motornet2_energy.py`, `motornet2_run.py`, `motornet2_job.sh`, `motornet2_render.sh`. Data `/secondary/hyst-data/body/motornet_toy2/` (clips/, manifest.json in clips/, settings.json, numbers.json, work/, lanes/, motornet2_fit.json). No audio in git. FOR USER: none.
