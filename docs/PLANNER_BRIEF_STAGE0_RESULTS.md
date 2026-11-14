# Planner brief: Stage 0 results (2026-11-09)

Rules in force: BRAIN_SPEC 7.34 (Stage 0 and the overseer operationalisation) and 7.35 (Stage 1 toy). Builder: agent 1, WO19, branch
body-s0. Data: `/secondary/hyst-data/body/s0/` (summary.json, measures.json). Nothing was trained.

## What ran

- **Pass2** (best.pkl, round 600): a continuous argmax rollout of all 357 held-out songs, 50 Hz, 25 min in total.
- **v47 one arm on held-out songs:** the headless chain runs in 3.2 min per song (mp3 -> analysis -> Demucs -> notes sidecar ->
  ensemble_preview --score -> score-csv). But v47's automatic beat grid failed the builder's pre-set quality gate (fitReliable, and >= 50 %
  of onsets within 60 ms) on 0 of 10 songs (16-33 % within 60 ms); one export also aborted. So v47 was measured on the three danced songs
  only: 3 pairs, not tempo-matched.

## Results

Builder numbers, recomputed by the overseer from the saved rollouts with independent code (own FK, own features, sklearn): they match.

| Measure (5 cm cells; 30 s clips) | Pass2, 357 held-out songs | v47 one arm, 3 danced songs | Pass2, same 3 songs |
|---|---|---|---|
| **Machine 2AFC**, 128 tempo-matched pairs (\|dBPM\| <= 5, different artists) | **49.1 % [45.4, 52.7]** (overseer: 48.4 % [44.7, 52.0]); shuffled 50.1 % | 33 % (3 pairs, 2-8 test clips each: uninterpretable) | 58 % (same 3 pairs) |
| JS distance between songs (median) | 0.321 all pairs / 0.298 tempo pairs | 0.733 | 0.252 |
| JS between the halves of one song (median) | 0.463 | 0.832 | 0.364 |
| Ratio between / half | 0.69 | 0.88 | 0.69 |
| Distinct postures (>= 0.5 % dwell) | 59.7 | **7** | 61.7 |
| Occupied cells (any dwell) | 412 | 1,507 | 458 |
| Shoulder sd | 3.87 deg | 14.9 deg | 3.20 deg |
| Peak hand speed | 0.742 m/s, across-song sd 0.007 | 1.44 m/s, sd 0.23 | 0.741, sd 0.0001 |
| Program entropy | 0.0 bits on all 357 songs | n/a | 0.0 |

**The pre-registered expectations:**
- pass2 2AFC <= 60 %: **met**. The stop rule did not fire, and the diagnosis is not contradicted.
- "v47 clearly higher": **not testable** (no held-out v47 songs).

**Other findings:**
- **The hand-speed bound is not the ceiling.** The bound is 1.2 m/s (`m3f_jax.py:32`), and pass2 peaks 0.46 m/s below it. The 0.741 m/s
  ceiling comes from elsewhere (probably the movement mapping's amplitude). Cause not checked.
- **Tempo deviation, recorded:** the B7 `omega` lane is the L3 phase rate, not the beat (its median is 4.6 "BPM"). It disagreed with
  librosa on 20 of 20 songs, so tempo is from librosa for every song.
- **2AFC design, recorded:** equal clip counts per song were needed. With unequal counts, the shuffled control was 55.9 %, because a
  majority guess wins. Only 285 of the 357 songs have >= 2 whole clips in each half.

## Problems with two measures (overseer's findings)

1. **"Distinct postures (>= 0.5 % dwell)" runs backwards.** It gives v47 7 and pass2 60. A wide-moving arm spreads its dwell so thinly
   that few cells reach 0.5 %; a small repeated loop concentrates dwell into many cells above 0.5 %. "Occupied cells (any dwell)" orders
   them correctly (v47 1,507 vs pass2 412-458). **The Stage 1 collapse precondition (7.35.2) uses "distinct postures <= 1/3 of untrained",
   so it may mis-fire.**
2. **The first-half -> second-half split hurts arms whose sections differ.** v47's own halves differ more than two v47 songs do (0.83 vs
   0.73). A classifier trained on first halves then fails on second halves. The between/half ratio is below 1 for both v47 (0.88) and
   pass2 (0.69), so that ratio does not separate them either.

## Questions

**Q1. Close Stage 0 without a held-out v47 comparison?**
Options:
- (a) accept: pass2 at chance, plus the collapse indicators, is enough to proceed;
- (b) hand-regrid 12 tempo-matched pairs for v47 (the same manual tempo-map work the three danced songs needed; hours, partly the user's);
- (c) accept, and name v47 on the three danced songs as a weak reference only.

Recommend (c).

**Q2. Fix the posture measure before Stage 1 runs?**
Options:
- (a) replace "distinct postures (>= 0.5 % dwell)" by "occupied cells (any dwell)" in the Stage 1 collapse precondition and in every later
  bar;
- (b) use the entropy of the cell distribution (bits) instead;
- (c) keep it.

Recommend (a), with (b) reported alongside. The toy's grid is already fixed (24 x 24, 5 cm).

**Q3. Fix the 2AFC split for Stage 3 (ruled before Stage 3, not now)?**
Options:
- (a) interleaved clips: train on odd 30 s clips, test on even ones, with a 30 s gap rule;
- (b) keep the first/second half.

Recommend (a) for Stage 3; Stage 1 keeps its rules (the toy songs have no sections).

**Q4. Run Stage 1 now?**
Recommend: yes, as soon as Q2 is ruled (about 1-1.5 h of compute). The built toy is verified: 17 tests rerun by the overseer, and arm (i)'s
surviving between-song sd is 0.20 vs 0.99.
