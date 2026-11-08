# Night log: body-s0 (work order 19, Stage 0, analysis only)

## MORNING SUMMARY

(in progress) Stage 0 measurement of the one-shape collapse. Nothing trained.

## Phase 1: scripts and pass2 rollouts (2026-11-09)

- `scripts/body/s0_roll.py`: continuous full-song argmax rollout of k5p2 `best.pkl` (round 600) on each of the 357 held-out songs, reusing k5p2_eval's `episode_inputs`, `pad_chunks`, `rollout_song` (same body, options, chunk 8, start seed 4242; lanes from `k5/lanes/check`). No per-song report lines (not needed here). Saves `rows50` (50 Hz joint angles, deg), `pi`, `prog`. Data `/secondary/hyst-data/body/s0/pass2/`. Much faster than the ~2 h expected: after a 23 s compile a 300 s song takes 3-7 s; whole set about 30 min.
- `scripts/body/s0_tempo.py`: DEVIATION (the pre-registered fallback). The `omega` lane is the L3 mode's phase rate, not a beat rate: the median omega-BPM over the set is 4.6, and on the 20-song sanity check (seeded sample, librosa.beat.beat_track on the mp3) **20 of 20 disagree** (more than 4 allowed), so librosa tempo is used for all 357 songs.
- `scripts/body/s0_measure.py` + `test_s0_measure.py` (12 tests, brain env): JS distance (base 2, square root of the divergence; median over pairs; half-song control), postures (>= 0.5 % dwell, 5 cm cells), shoulder sd, peak hand speed (max 50 Hz central difference), program entropy, greedy tempo pairs, machine 2AFC (30 s clips, 10 cm ball-cell histogram + per-joint mean/sd of angle and speed, L2 logistic regression C=1 standardised, train first half / test second half, bootstrap 10,000 over pairs, label-shuffled control). Tests: a fixed shape at two speeds (JS small, 2AFC high through speed features), two postures (JS large, 2AFC high), same process (2AFC near chance), shuffled control near 50 %.
- Operational choices 7.34 does not fix: a pair is usable only if each song has >= 2 whole 30 s clips in each half (>= 2 min); clips lie wholly inside their half; JS "distance" is the square root of the base-2 divergence.
- Hand-speed bound in the pass2 loss: `HAND_MPS = 1.2` m/s at `scripts/body/m3f_jax.py:32`, used in `penalties()` (hinge `relu(hv - HAND_MPS)` on the 50 Hz forward-difference hand speed, line 272; also the acceleration hinge `ACC_MPS2 = 4.8`, line 45). The pass2 CFG/OPTS (`k5p2_train.py:33-34`) add `clip=True` and `pen2`, not another hand-speed bound. (e'2) in the check counts time above 1.0 m/s; `check-csv` limit is 1.2 m/s.
