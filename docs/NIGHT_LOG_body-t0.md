# Night log body-t0 (WO37 Builder A, 2026-11-14)

- Rules `T0_RULES.md` pushed first (accepted by the overseer, addendum `token_lookahead_s`); 7.60 applied (calibrated AIOZ, weight per AIOZ clip).
- Checks: lanes reproduce the stored ones (arousal_b7 2.4e-7 / 4.8e-7, s10 5.7e-6, L4 mode groups 3.8e-6; limit 1e-4); look-test window C04 V2 pre-H1 target reproduced to 4.7e-12 deg, same gate verdict, realised vs csv 5e-7;
  `test_t0_lib.py` 8 tests (mirror twice = identity, mirrored wrist = reflected wrist, split grouping + seed, weights, windows, posture/gesture, token pooling, norm).
- AIOZ: restricted unpickler and adapter by Builder B (merged). Literal rule HOLD 2.8 %; calibrated keep list used on the overseer's ruling.
- Time estimate: 0.78 s per gated window; full run (2,055 dancers x 4 copies, 8 processes) took 728 s. Lanes: 1,007 songs/clips, about 1 h.
- Full run complete: 8,220 npz, none missing. Report `docs/T0_REPORT.md`, `t0/numbers.json`.

FOR USER: surprisal from `bd.surprisal` (not `b2.surprisal_lanes`); AIOZ fps taken as 30 (clip fps within 0.1 %); ear-energy lookahead 1.0 s (stored per column); 31 % of train tokens have at least one surprisal layer undefined (clip starts, deep layers),
mostly AIOZ (clips are short: 1,334 of 1,336 train dancers have a dropped tail and most have 0-3 windows); the beat phase uses the offline whole-song beat grid; the harness forced a worktree (branch `body-t0-w`, pushed to `origin/body-t0`); one FineDance song name was an int (cast to text).

MORNING SUMMARY (usable hours = kept 20 s windows, summed over the 4 copies; tokens counted once per dancer-copy set, i.e. one copy):
- Groups (songs / YouTube ids) per split: train 303, validation 40, test 60.
- FineDance usable h: train 14.13, validation 2.48, test 2.26. AIOZ usable h: train 37.14, validation 2.90, test 11.38.
- AIOZ survivors: 1,852 dancers (calibrated), 804 clips, 19.28 h of motion before windowing.
- Tokens per split (one copy): FineDance 41,520 / 7,266 / 6,166; AIOZ 99,959 / 8,340 / 30,221 (train / validation / test).

T0 READY
