# Night log: body-s0 (work order 19, Stage 0, analysis only)

## MORNING SUMMARY

STAGE 0 DONE, nothing trained. Pass2 machine 2AFC on 128 tempo-matched held-out pairs = 49.1 % [45.4, 52.7], shuffled control 50.1 %: at chance, at or under the 60 % line, so the diagnosis is NOT contradicted and the stop rule did not fire. "v47 clearly higher" could NOT be tested: v47 does not run unattended on corpus songs (0 of 10 passed the grid gate; one export aborted with the planner's "cannot fit tangents"), so v47 is measured on the three danced songs only (3 pairs, not tempo matched; 2AFC 33 %, uninterpretable). Data and summary in /secondary/hyst-data/body/s0/ (summary.json, measures.json).

## Phase 1: scripts and pass2 rollouts (2026-11-09)

- `scripts/body/s0_roll.py`: continuous full-song argmax rollout of k5p2 `best.pkl` (round 600) on each of the 357 held-out songs, reusing k5p2_eval's `episode_inputs`, `pad_chunks`, `rollout_song` (same body, options, chunk 8, start seed 4242; lanes from `k5/lanes/check`). No per-song report lines (not needed here). Saves `rows50` (50 Hz joint angles, deg), `pi`, `prog`. Data `/secondary/hyst-data/body/s0/pass2/`. Much faster than the ~2 h expected: after a 23 s compile a 300 s song takes 3-7 s; whole set about 30 min.
- `scripts/body/s0_tempo.py`: DEVIATION (the pre-registered fallback). The `omega` lane is the L3 mode's phase rate, not a beat rate: the median omega-BPM over the set is 4.6, and on the 20-song sanity check (seeded sample, librosa.beat.beat_track on the mp3) **20 of 20 disagree** (more than 4 allowed), so librosa tempo is used for all 357 songs.
- `scripts/body/s0_measure.py` + `test_s0_measure.py` (12 tests, brain env): JS distance (base 2, square root of the divergence; median over pairs; half-song control), postures (>= 0.5 % dwell, 5 cm cells), shoulder sd, peak hand speed (max 50 Hz central difference), program entropy, greedy tempo pairs, machine 2AFC (30 s clips, 10 cm ball-cell histogram + per-joint mean/sd of angle and speed, L2 logistic regression C=1 standardised, train first half / test second half, bootstrap 10,000 over pairs, label-shuffled control). Tests: a fixed shape at two speeds (JS small, 2AFC high through speed features), two postures (JS large, 2AFC high), same process (2AFC near chance), shuffled control near 50 %.
- Operational choices 7.34 does not fix: a pair is usable only if each song has >= 2 whole 30 s clips in each half (>= 2 min); clips lie wholly inside their half; JS "distance" is the square root of the base-2 divergence.
- Hand-speed bound in the pass2 loss: `HAND_MPS = 1.2` m/s at `scripts/body/m3f_jax.py:32`, used in `penalties()` (hinge `relu(hv - HAND_MPS)` on the 50 Hz forward-difference hand speed, line 272; also the acceleration hinge `ACC_MPS2 = 4.8`, line 45). The pass2 CFG/OPTS (`k5p2_train.py:33-34`) add `clip=True` and `pen2`, not another hand-speed bound. (e'2) in the check counts time above 1.0 m/s; `check-csv` limit is 1.2 m/s.

## Phase 2: measures, v47 feasibility, verdict (2026-11-09)

**Deviations:** (1) tempo from librosa for all songs (omega route failed the 20-song check, 20 of 20). (2) 2AFC uses equal clip counts per song in each half: with all clips the shuffled control was 55.9 % (majority-class effect from unequal song lengths), not about 50 %; with the fix it is 50.1 %. Test added. (3) Only songs with >= 2 whole 30 s clips per half (>= 2 min; 285 of 357) enter the 2AFC pairs; greedy pairs by |dBPM| gave 128 pairs.

**Pass2 on 357 held-out songs** (rows50 from a continuous argmax rollout, 3-7 s per song, ~25 min total):
| measure | pass2 |
|---|---|
| machine 2AFC (128 pairs) | 49.1 % [45.4, 52.7]; shuffled 50.1 % [48.8, 51.5] |
| JS between songs, all 63,546 pairs, median | 0.321 |
| JS between songs, 128 tempo pairs, median | 0.298 |
| JS half-song control, median | 0.463 (ratio between/half 0.69: halves of one song differ MORE than two songs) |
| distinct postures (>= 0.5 % dwell, 5 cm) | mean 59.7, sd 4.7 across songs (46-77); cells visited 412 |
| shoulder sd | 3.87 deg mean, sd 0.65 across songs |
| peak hand speed | mean 0.742 m/s, across-song sd 0.0073 (range 0.739-0.806): the same on every song |
| distance to the bound (1.2 m/s, m3f_jax.py:32, hinge line 272) | 0.46 m/s below it; the peak never approaches the bound |
| program entropy | 0.0 bits on all 357 songs (one program) |

**Three danced songs (not tempo matched, 3 pairs):**
| | v47 arm 0 | pass2 |
|---|---|---|
| postures >= 0.5 % | 7 (2, 7, 12) | 61.7 |
| cells visited | 1507 | 458 |
| shoulder sd | 14.9 deg | 3.2 deg |
| peak hand speed | 1.44 m/s (1.20, 1.45, 1.66), sd 0.23 | 0.741, sd 0.0001 |
| JS between / half control | 0.733 / 0.832 | 0.252 / 0.364 |
| 2AFC (3 pairs) | 33 % (50, 12.5, 37.5) | 58 % (75, 37.5, 62.5) |
v47 has far fewer dwell postures (it moves through many cells, dwelling little), 4.6x the shoulder spread and 2x the peak hand speed, and varies a lot between songs in peak speed (sd 0.23 vs 0.0001). Its JS and 2AFC do not show higher between-song separability on this protocol: v47's two halves of a song differ as much as two songs (ratio 0.88), so a first-half to second-half classifier fails for it. With 3 pairs and 2-8 test clips per pair this says nothing about v47 vs pass2; it is the weak case the order anticipated.

**v47 feasibility:** the headless chain (ffmpeg, analyze.py, dance_memory, Demucs htdemucs + 6s on CPU, stems, structure, notes, ensemble_preview --score, hyst score-csv --mode off --agent 0; `s0_v47_song.sh`) runs from an mp3 in 3.2 min per 3.5 min song, with no Rust change (`git diff --stat crates/` empty). What fails is the automatic beat grid: 0 of 10 songs passed the gate set before the run (fitReliable and >= 50 % of independent onsets within 60 ms; observed 16-33 %), and one export aborted ("cannot fit tangents segment 3180"). The danced songs needed manual regrid / tempo maps. Making 12 pairs would need that per song. Files of the 10 tried songs kept in `/secondary/hyst-data/body/s0/v47_gate_failed/` (exploratory, not used).

**Verdict against the pre-registration:** pass2 2AFC 49.1 % <= 60 %: the expectation holds, the diagnosis is not contradicted, continue. v47 "clearly higher" (>= +15 points and lower bound above the pass2 mean): NOT established, not testable here (see above). The pass2 measures that DO show the collapse: one program, peak hand speed identical across songs, ~60 dwell postures, small shoulder sd, and between-song JS below the half-song control.

## Work order 21: the 0.741 m/s peak (2026-11-09, branch body-s0b, report only)

**Answer: none of (a), (b), (c) produces it. The 0.741 m/s is a song-independent start-up transient at t = 2.74 s, from the fixed start pose, and it is not a ceiling.** Files: `scripts/body/s0_ceiling.py`, `s0_ceiling_run.sh`, `test_s0_ceiling.py` (6 tests), data `/secondary/hyst-data/body/s0/ceiling/` (`base_<id>.json` x 24, `amp_/c_/freq_<id>.json` x 3, `analytic.json`, `steady.json`).

1. **Where the peak sits.** On all 357 Stage 0 rollouts the hand-speed maximum lies in the first 8 s on 92.7 % of songs (331 of 357); the peak in the first 8 s is 0.7407 m/s, sd 0.0004 (0.7390-0.7416). On the 24 re-rolled songs (diagnostic path, same physics; peaks equal the Stage 0 values to 4 decimals) the peak is at 2.7 s on every song. After 8 s the per-song peak is 0.680 m/s, sd 0.036 (0.554-0.806), p99 0.615, median speed 0.365: it varies by song and is lower than 0.741 for most songs (the largest over all songs is 0.806, at a later moment). So "the same 0.741 on every song" in the Stage 0 table was the first-seconds transient, not a limit on the dance.
2. **Generator parameters at the peak (24 songs, identical to 3 digits on every song, sd ~0):** none at a bound. Base yaw centre 38.5 deg, amp 18 % of its 180 deg cap, frequency used 0.27 Hz (slewed 0.98 Hz); shoulder centre -76 deg, amp 10 % of its bound; elbow amp 16 %; wrist bend amp 16 %; wrist roll amp 38 % of 180 deg. Frequency never reaches F_MAX = 4 Hz (whole-song share at F_MAX is 0 for every joint); amplitude never reaches 98 % of its bound (whole-song share 0). Joint speeds at the peak are 19 / 25 / 35 / 30 / 25 % of the speed limits (base, shoulder, elbow, wrist bend, roll). The hand velocity comes from shoulder 0.24, elbow 0.33, wrist bend 0.20 m/s (base 0.01, roll 0.0): the start-up motion of the pitch joints, not base-yaw sweeping.
3. **Analytic check.** The largest hand speed with joint speeds at 0.64 / 0.8 / 1.0 x the speed limits (all 32 sign choices, best pose, joint-range limits only, floor ignored) is 2.03 / 2.54 / 3.17 m/s over all poses, and 1.88 / 2.34 / 2.93 m/s over the poses pass2 visits. Base yaw alone: 0.92 / 1.16 / 1.44 m/s (largest horizontal radius 0.69 m). 0.741 is far below all of them, so no combination of joint speed limits gives 0.741; the ceiling story is not supported analytically.
4. **What does bind in steady dance (whole-song shares, 24 songs):** the generator's own frequency caps (cpg.py). Shoulder, elbow and wrist bend sit on the acceleration cap (`ACC_SHARE = 0.25`, f <= sqrt(0.25 A / amp) / (2 pi 1.25)) 99.8-99.9 % of the steps; base yaw and wrist roll sit on the speed cap (f <= 0.8 V / amp / (2 pi 1.25)) 96 % and 98 % of the steps. The used frequency averages 0.10 / 0.57 / 0.50 / 0.85 / 0.27 Hz (base, shoulder, elbow, wrist, roll). The commanded frequency is mostly above these caps (slewed 1-3 Hz at the peak), so raising F_MAX cannot help. This is a (d)-type limit (cpg.py's rate caps), acting on frequency, not on amplitude.
5. **Perturbation (3 songs 113810, 125571, 149848; one bound relaxed at a time; module constants patched in the diagnostic process only, defaults untouched):** amp cap x1.5 (continuous joints 180 -> 270 deg): peak 0.7393 / 0.7411 / 0.7405, unchanged. Frequency max x1.5 (4 -> 6 Hz): 0.7403 / 0.7429 / 0.7419, unchanged. Smooth-u scale c = 0.35: 0.5435 / 0.5436 / 0.5603, with the peak moved to 5.5 / 5.6 / 6.0 s: c changes the start-up transient (it changes the first targets), and the new peak is lower. None of the three raises the peak; the transient is set by the fixed start pose (seed 4242) and the identical first-block commands (zero inputs, one program), not by any bound.
6. **Not done:** a variant with the acceleration share (`ACC_SHARE`) or the 0.8 speed share raised, which is the real steady-state limiter in point 4; the start-up transient was not traced step by step; the later per-song peaks (0.55-0.81 m/s) were not attributed to a bound.
