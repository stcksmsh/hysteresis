# Stage 3 side-car reports: rules (work order 27, BRAIN_SPEC 7.41.3), written before any job

One arm (permanent rule). Report only: nothing here changes the Stage 3 run (unit `hyst-wo26b-run-*`, output `/secondary/hyst-data/body/s3/run/`, cores 6-11). The watcher never writes into
the run folder, never signals its unit and never uses cores 6-11. Its jobs use cores 12-17 (`taskset -c 12-17`), run detached under `systemd-run --user` with `MemoryMax=6G`, only on mains.
Code: `scripts/body/s3_sidecar.py` (watcher, hinge activity, round-400 clip), `scripts/body/s3_sidecar_slow.py` (brain env: slow lanes of Instant Crush). Output: `/secondary/hyst-data/body/s3/run_report/`.
Amendments only as dated entries at the end. **FOR USER** marks a place where the work order left a detail open and the nearest default was taken.

## 1. Trigger and copies

- The watcher polls `run/train.log` every 60 s for lines matching `validation at round R:`. Each R is handled once (done marker `run_report/R/hinges.json`).
- Order of events in the trainer: round, `ckpt.pkl` saved (epoch = rounds done), then the validation, which writes `best.pkl` if the score improved and logs the line. So at the line, `ckpt.pkl` is the
  validated policy. If the watcher is late and `ckpt.pkl` has already advanced (its `epoch` is R + 1), `ckpt.prev.pkl` (epoch R) is used; if neither has epoch R the round is reported as **missed**
  (no reconstruction from a later checkpoint).
- `ckpt.pkl` (or `ckpt.prev.pkl`) and `best.pkl` are copied to `run_report/R/` first; only the copies are read. A copy that fails to unpickle is retried after 30 s (3 tries, then the round is reported failed).
- A watcher armed after round R's line already exists reports R as **missed** in `summary.txt` (it does not process lines older than its arming time).
- The watcher exits after the validation at the final round (R = 977 or the run's own end/stop) or when no unit matching `hyst-wo26b-run-*` is active and no new validation line has appeared for 10 minutes.

## 2. Hinge activity (per validation)

Policy = the copy's `trainer.P`, cfg = `k5p2_train.CFG` (as the trainer's `Stage3Run`). Rollout = the trainer's own `update_D` path: the first 16 windows of `k5_train.val_windows` (`dtoy` =
`s3_data.build_toy3(k5, s3, "val", wins, floor_sd)`, `floor_sd` from `run/corpus_sd.json`, read only), argmax, key `PRNGKey(4242)`, start poses seed 4242, chunk 8 blocks, via `m3f.rollout`.
Scored = blocks b >= `VALID_FROM` = 8 of each window (112 of 120), so 16 x 112 = 1,792 blocks, 89,600 control steps (100 Hz), 44,800 hand samples (50 Hz). Shares pool all windows (count / count).

An element is **active** when it is **on or over** its threshold (>=), thresholds exactly those of the trainer (`m3f_jax`, `s3_loss`, `thresholds.json` of the run's `<s3>`):

| hinge | element counted | active when |
|---|---|---|
| `hand_v` | 50 Hz hand-speed samples (hand = `J.hand_points`, every 2nd control step, odd indices 1, 3, ...; speed = distance between consecutive samples x 50) | >= 1.2 m/s |
| `jolt` | 50 Hz samples of |change of hand speed| x 50 | >= 9 m/s^2 |
| `acc` | 50 Hz samples of the hand acceleration (central second difference) | >= 4.8 m/s^2 |
| `floor` | control steps (100 Hz) | check-csv floor margin <= 0: `min(min(z of fk points 1..4) - 0.05, z of point 5 - 0.05 - 0.06)` |
| `lim` | (control step, bend) pairs, bends = joints 1, 2, 3 | \|q\| >= 100 deg |
| `energy` | blocks | block `energy` (J) >= `thresholds.json` energy (0.3747) |
| `jerk` | blocks | block `jerk` (deg^2/s^6) >= `thresholds.json` jerk (4.748e6) |

Each 50 Hz hand sample is attributed to the block of its newest control step; it is scored when that block is >= 8. The 50 Hz grid is the trainer's (`penalties`: `hand_points(full[-51:])[::2]`),
computed over the whole episode so that differences cross block boundaries exactly as the trainer's previous-block sample does.

Reported per validation (`run_report/R/hinges.json`): the seven shares; per hinge also the mean violation `g_k` of the trainer's own definition for the same windows where cheap (the block-mean hinge values
from the rollout outputs, same formulas as `s3_loss.limit_g`); the seven multipliers `mu` (names `energy, jerk, hand_v, jolt, acc, floor, lim`) and the two D multipliers `muD` (fast, slow) from the copy;
`D_fast`, `D_slow` from the log line `epoch {...}` that precedes the validation line (the round R - 1 record), with the copy's own `Dest` next to them; the validation numbers (the log line and the copy's
`extra.val[-1]`: `ext_a`, `int_a`, `b`, compute hours); the round, the copy's file times and the cores used. One line per validation is appended to `run_report/summary.txt`.

**FOR USER (a):** the work order says "floor ... check-csv floor margin <= 0", the trainer's hinge uses the raised-plane margin (`plane` 0.053: link capsule radius and disc above the plane). The share above is the
check-csv one as written; `floor_trained` (plane margin <= 0, the trainer's own hinge) is reported next to it.
**FOR USER (b):** `lim` is the share of (step, bend) pairs; `lim_any_bend` (share of steps with at least one bend >= 100 deg) is reported next to it.

## 3. Round-400 clip (only at the validation of R = 400)

1. Copy `best.pkl` (as of that validation: its `round` field is stored; if it is older than 400 because the 400 validation did not improve, the clip uses it and says so, the round is in the file name's report).
2. **Slow lanes of Instant Crush** (prepared ahead by `s3_sidecar_slow.py`, brain env, cores 12-17): `braindump.danced_inputs("instant-crush")` -> `s3_slow.l4_blocks` -> the 13 columns by `s3_slow` exactly as
   `raw_columns` + `load_norm` (PCA and column normalisation of the train corpus, `s3/slow/norm.json`), written to `run_report/work/instant-crush.slow.npz`. Block count must equal the danced lanes' (679).
3. **Rollout** of the whole song, argmax, one continuous episode: the pass2 song recipe (`k5p2_eval.episode_inputs` on `k5/danced/lanes/instant-crush.npz`, `pad_chunks`, `rollout_song`, start seed 4242, chunk 8)
   with the Stage 3 policy input: `x` gets the previous block's slow columns appended (clip +-8, zero for block 0), exactly `s3_data.Toy3.inputs`. The joint CSV is written with `arm_sim.csv_text` (50 Hz rows).
4. **Render** 60 s, from 60 s to 120 s of the song, with the one-arm camera of `k5p2_render.sh` (the same `ensemble_preview --joint-csv` page, label "Stage 3 policy", `record_ensemble.cjs` with START 60 DUR 60,
   the song's audio `author/audio/instant-crush.m4a`), 1280x720, H.264 + aac, **< 30 MiB** (the size loop of the script), to `run_report/400/instant-crush-r400-60s.mp4`. The page binary is the existing
   `cargo-target-wo12/release/examples/ensemble_preview` (no build).
5. **Numbers for that 60 s** (CSV rows 3000..6000 of the 50 Hz joint rows = 60 s..120 s): shoulder sd = `np.std(rows[:, 1])` (deg, joint column 1) and occupied 5 cm hand cells = `len(s0_measure.cell_dist(rows))`
   (`CELL` = 0.05 m, hand = `m3f_report.fk_points(...)[:, 5]`). The same two numbers for pass2 on the same 60 s from `k5p2/check/songs/instant-crush.pass2.csv` (same rows 3000..6000). Written to
   `run_report/400/clip_numbers.json` together with the clip's path, size, duration (ffprobe) and the policy's round.
6. The render path is tested first on the timed-round `best.pkl` (10 s of the same window), and that test video is deleted.

## 4. Safety

- No write under `s3/run/`. No signal to a unit. Only `systemctl --user is-active` / `list-units` (read-only) on the run unit.
- `taskset -c 12-17` for every Python/node/ffmpeg/chrome child of the watcher; `MemoryMax=6G`, `MemorySwapMax=0`; a poll on `/sys/class/power_supply/ADP1/online` before each heavy job (waits on battery).
- JAX on CPU (`JAX_PLATFORMS=cpu`), the process pinned by `taskset -c 12-17`.
- Tests of the code run on `s3/train_timed/` (never on `s3/run/` except the read-only log polling), one test module per process.

## 5. Dated notes

(none yet)
