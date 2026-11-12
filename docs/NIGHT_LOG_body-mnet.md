# Night log, branch body-mnet (work order 29A)

## MORNING SUMMARY
- Rendered: Part 1 **10** silent lamp clips (S01-S10), Part 2 **2** ball clips (S01, S02), Part 4 **4** round-1 clips referenced (A_lag_low,
  A_neutral, A_posture_high, A_vigour_high). Part 3 held, path tested on a synthetic click track only.
- Discards per gate: none (draws 1-10 all passed). S11 (all low) and S12 (all high) failed the minimum-motion gate; not shown, not replaced.
  So the 12-setting design is 10 clips shown, 2 reported.
- Numbers from 29B's script (numbers only): every setting "cycles" at 1.664 Hz (the beat-input rate), participation ratio 2.03-2.2, mean hand
  height 0.513-0.514 m; hand speed 0.30-0.39 m/s; straightness varies (0.06-0.97). The settings share the input-entrained rhythm.
- Threads: cores 6-11 pinned, simulations single-threaded, renders 3 recorder workers. Compute: ~25 s sampling, ~10 min rendering.
- Files: `/secondary/hyst-data/body/motornet_toy/` (clips/, settings.json, measurements.json, work/). Manifest: `clips/manifest.json`.
- FOR USER: two deviations from the defaults (feasibility, in the rules file): calibration +-100 % of round-1 neutral amplitudes (default +-60 %);
  minimum-motion extent 0.05 m (default 0.10 m). Reason: hand extent 0.084 m at gain 1 (cause: see DIAGNOSIS; first stated cause was wrong).
- FOR USER: Part 3 held for the audio files and excerpt times. The click-track test shows the cortex phase lanes of a click track barely move, so
  real songs are needed to see the music path matter.

Status: ON HOLD at the overseer's request. Manifest finished; clips exist but are not declared ready.

CORRECTION (overseer, 2026-11-12), cause restated: the round-1 command limiter (mainly base and shoulder acceleration) cuts the 1.66 Hz
beat-rate command's amplitude, then servo lag cuts it further; base yaw 47.5 -> 41.7 -> 13.4 -> 5.4 deg. The earlier line "the beat-rate drive
is speed-limited" was wrong as stated (realised speeds stay under 0.9 of their limits because the lag has already cut them). See DIAGNOSIS below. HOLD: nothing further
rendered, no "CLIPS READY" written. Network, settings and clips unchanged.

## DIAGNOSIS FOR OVERSEER
Script `scripts/body/motornet_diag.py` (read-only), raw output `/secondary/hyst-data/body/motornet_toy/diag.json`, cores 6-11, detached unit.
Ranges are p5-p95 in degrees over the shown 12 s, joints = (base yaw, shoulder, elbow, wrist bend, wrist roll).

**(1) Drive per unit** (std over the shown 12 s of Win u and of W r, mean over 200 units):

| | input drive | recurrent drive |
|---|---|---|
| gain 1 | 0.864 | 0.553 |
| S01-S10 | 0.864 (all) | 0.43-0.67 (S08 0.43, S01 0.53, S03 0.67, S05 0.67) |
| S11 low / S12 high | 0.864 | 0.28 / 0.78 |
| gain 1, zero input (x0 = 0.01 N(0,1), seed 29099) | 0 | 0.113 |

**(2) Per joint ranges, gain 1** (S01-S10 differ by about +-30 % on shoulder/wrist bend/elbow targets; base realised always 5.3-6.4, roll 42.7-43.1):

| stage | base | shoulder | elbow | wrist bend | roll |
|---|---|---|---|---|---|
| calibrated target | 47.5 | 18.6 | 21.4 | 21.6 | 59.3 |
| spring-damper output | 41.7 | 16.4 | 21.1 | 21.2 | 58.4 |
| realised (physics) | 5.4 | 3.2 | 13.9 | 15.4 | 43.1 |

Extra, to locate the loss (gain 1, replicating the round-1 limiter on the spring-damper output): `LIMITS` speed (120, 90, 150, 200, 250) deg/s,
accel (600, 300, 1000, 2000, 3000) deg/s^2. The spring-damper output peaks at (200, 80, 118, 114, 351) deg/s, so base (200 > 120) and roll
(351 > 250) ask for more than the speed limit; a 20 deg amplitude at 1.66 Hz needs about 2200 deg/s^2 against the base acceleration limit
600. Output of the limiter: p5-p95 (13.4, 6.7, 22.4, 21.2, 53.2), peak speed (91, 46, 150, 106, 250). So the command limiter, not the
realised-angle speed, takes base from 41.7 to 13.4 deg, and the servo/physics takes it on to 5.4 (shoulder 16.4 -> 6.7 -> 3.2, elbow
21.1 -> 22.4 -> 13.9). The overseer's 0.9 check is on realised angles, where the lag has already lowered the speed. Roll is the one joint
whose realised range (43) is close to its limiter output (53).

**(3) Autonomous activity and extremes:**

| | PR of r | joint peak frequency (target / realised) |
|---|---|---|
| S11 (all low) | 1.97 | 1.664 Hz all five joints |
| S12 (all high) | 2.41 | 1.664 Hz all five joints |
| gain 1, zero input | 1.99 | 0.499 Hz all five joints (spectral bin resolution 0.083 Hz) |

Zero-input gain 1 does not decay and does not cycle at the beat: the activity is slow (0.5 Hz peak), PR 1.99, p5-p95 of the targets 1.5-10 deg.
Every joint peaks at 1.664 Hz in S01-S12 and at gain 1 (input rate = 100 BPM / 60). S11 and S12 failed the motion gate (not shown).

No change made to anything. Design question left to the overseer and planner.

## Log
- 2026-11-12: branch body-mnet from origin/body. Rules written (`docs/MOTORNET_RULES.md`) and pushed before any clip.
- Overseer amendment applied: dominant frequency = summed power spectra of mean-removed hand x, y, z, DC excluded.
- Sampling, rendering, manifest, measurement run done; see `docs/MOTORNET_PARAMS.md`.
