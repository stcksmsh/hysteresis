# Night log: body-s3r (work order 27, Stage 3 side-car reports)

## MORNING SUMMARY

- 2026-11-12 09:42: watcher armed, unit `hyst-wo27-watcher-s3` (cores 12-17, `MemoryMax=6G`, started by `scripts/body/s3_sidecar_watch.sh`), output `/secondary/hyst-data/body/s3/run_report/`
  (`summary.txt`, `<R>/hinges.json`, `watch.log`). Run at that time: round 61 of 977, no validation line yet, so nothing is missed. Round 200 expected ~12:50.
- Test on `s3/train_timed/` (validation at round 2): hinges written in 62 s of rollout, 7 unit tests green. Details below.
- Round-400 clip: render path tested on the timed best.pkl (10 s of the 60-120 s window; 1280x720 h264 + aac, 15 MB; test video deleted). The watcher runs the clip as a fresh subprocess at the 400 validation, so it uses the code on disk at that time. Waiting for round 400 (~17:30).

## Log

### 09:36 hinge test on train_timed (unit `hyst-wo27-test-hinges-a`, output `run_report/_test_timed/`)
`s3_sidecar.py watch --test` on `s3/train_timed/` (round-2 checkpoint, same trainer code): checkpoint copied first, rolled out the 16 fixed validation windows (argmax, key and start poses 4242),
shares over 1,792 blocks / 89,600 control steps / 44,800 hand samples / 268,800 (step, bend) pairs:
hand_v 4.03 %, jolt 0.17 %, acc 1.87 %, floor (check-csv) 0.00 %, floor_trained 17.35 %, lim 1.78 % (any bend 5.24 %), energy 85.49 %, jerk 23.72 %; mu energy 3.98, jerk 108.5, hand_v 1.008,
jolt 1.008, acc 1.046, floor 1.001, lim 1.0; muD fast 0.237 slow 0.223; D_fast -0.043, D_slow -0.009 (from the log record of round 1, equal to the checkpoint's own `Dest`).
Remark: `floor_trained` (raised-plane margin <= 0) is 17 % while its mean violation is ~1e-5 m: the arm resting in contact on the plane sits at margin ~0. The check-csv margin (the work order's definition) is 0 %.
Unit tests `test_s3_sidecar.py` (synthetic known trajectories: still arm, on-threshold counts as active, bend pairs, hand speed 1.5 vs 0.8 m/s from a base rotation, floor sign, log parsing, checkpoint-epoch
selection / missed rule): 7 tests OK, own process, cores 12-17.

### Notes
- Worktree: the harness forced an isolated worktree before any edit (`.claude/worktrees/wo27-s3r`, branch `body-s3r` from `origin/body`), so this session did not stay in the checkout it started in.
- Commits carry no co-author or attribution lines (the work order's rule).

### 09:44-09:49 clip test (units `hyst-wo27-cliptest-a`, `-b`)
Slow lanes of Instant Crush built (brain env, `s3_sidecar_slow.py`, 679 blocks x 13, corpus-normalised; `run_report/work/instant-crush.slow.npz`). Rollout of 144 blocks on the timed best.pkl (round 2), joint CSV, ensemble_preview page,
`record_ensemble.cjs` window 60 s + 10 s, mp4 720p. First try failed at the numbers step (`s0_measure` imports sklearn, absent in the body env): `shoulder_cells` now repeats the cell definition
(`fk_points` hand, floor(p / 0.05), unique) instead of importing it. Second try: ok, numbers produced (round-2 policy: shoulder sd 23.0 deg, 162 cells in the 10 s; pass2 same 10 s: 1.5 deg, 112 cells).
