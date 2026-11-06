# Night log: body-k5video (work order 12)

Provisional servo model (Feetech STS3215 12 V assumed). One arm. Branch `body-k5video` from `origin/body` 6e65bdf. Data outside git: `/secondary/hyst-data/body/k5/danced/`.

## MORNING SUMMARY

Status: steps 1, 2 and 4 done and tested; step 3 (render) running or finished, see "Render status" at the bottom of this section.

**Paths** (all under `/secondary/hyst-data/body/k5/danced/`)
- Lanes: `lanes/<song>.npz` (K5 keys: frames, y, phi_end, omega, s10, arousal_b7, power10), 3 songs.
- Rollouts: `<song>.k5.csv` (50 Hz joint CSV, `arm_sim.csv_text`) and `<song>.k5.npz` (per block: yz, desc, idesc, logits, pi, kappa, ms, energy, xin, feat, cb_sq, cb_nll; `q` (blocks, 50, 5) joint degrees at 100 Hz; `q0` start pose; `rows50` the CSV rows).
- Report: `segments.json` (copy `docs/k5video_segments.json`), `breaches.json` (copy `docs/k5video_breaches.json`), `rust.log` (checks), `roll.log`.
- Video: `video/<song>-k5.mp4` (1080p), `video/<song>-k5-720p.mp4`, `video/<song>-side-by-side-720p.mp4`.

**Code** (new files only; `k5_train.py`, `k5_eval.py`, `m3e*.py` imported, not touched): `scripts/body/k5_video_lanes.py`, `k5_video_roll.py`, `k5_video_seg.py`, `k5_video_breaches.py`, `test_k5_video.py`, `k5_render.sh`, `v47_regression.sh`. One Rust file changed: `crates/hyst-previz/examples/ensemble_preview.rs` gained `--joint-csv FILE` (off by default; the old page template moved unchanged into a helper `page()`).

**Tests passed**
- Step 1: the check-split song 009900 re-derived through the export path equals its stored `lanes/check/009900.npz`: same keys, max abs difference 0, bit-identical (`python k5_video_lanes.py check`).
- Step 2: the continuous full-song rollout (324 blocks) over its first 120 blocks (60 s) equals the K5 eval's own single-window rollout (`T.rollout_batched`, same start seed 4242, same chunk size 8): all 11 output arrays bit-identical, max difference 0.0 (`test_k5_video`, 4 tests OK). Continuous means: one carry (arm, MJX physics, CPG, cerebellum, closed-loop features, proprioception buffers), never reset, passed from chunk to chunk; the 30 s causal z-score (`m3e.running_z`) is run once over the whole song from its start.
- Rust (fresh `CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-wo12`): `cargo test` hyst-compile 102 passed (1 ignored, as before), hyst-output, hyst-previz, hyst-cli all ok; `cargo clippy -D warnings --all-targets` and `cargo fmt --check` clean on the four crates. **v47 regression: the three hexagon exports (`--ring 6,0.8`) are byte-identical (`cmp`) to `hexagon-47.html`, `five-years-hexagon.html`, `presence-hexagon.html`** (my `scripts/body/v47_regression.sh`, run after the final Rust edit).

**Numbers**
| song | blocks | CSV rows | CSV s | audio s | difference s |
|---|---|---|---|---|---|
| instant-crush | 679 | 16976 | 339.50 | 339.824 | 0.324 |
| five-years | 567 | 14176 | 283.50 | 283.753 | 0.253 |
| presence | 541 | 13526 | 270.50 | 270.733 | 0.233 |
The difference is the dropped partial last block (lanes keep whole 0.5 s blocks) plus the 100 Hz frame count; the video holds the last pose to the audio end. Rollouts took 27 s, 5 s, 11 s for the three songs (after a ~40 s compile).

`hyst check-csv`: **all three REFUSED** (this policy was never trained against the hand/floor rules; the K5 energy term is the only cost). Breaches by kind, in rows (check-csv's total equals my count: instant-crush 17,658):
| song | rows | rows with any breach | floor margin | hand speed (1.2 m/s) | hand jolt (9) | base_yaw speed | shoulder accel | joint position | wrist_roll speed |
|---|---|---|---|---|---|---|---|---|---|
| instant-crush | 16976 | 16038 | 15795 | 1510 | 24 | 52 | 38 | 238 | 1 |
| five-years | 14176 | 13012 | 12911 | 955 | 32 | 74 | 19 | 0 | 0 |
| presence | 13526 | 13134 | 13075 | 988 | 46 | 78 | 35 | 0 | 28 |
Worst floor margin -0.72 / -0.67 / -0.72 m; max hand speed 2.40 / 1.99 / 2.29 m/s; max hand jolt 10.9 / 10.7 / 11.6 m/s2. The floor rule (points 1-4 clear the floor by 5 cm, the hand by 11 cm) is broken in 91-97 % of rows (rows with a floor breach: 93 %, 91 %, 97 %): in the CSV rig the policy's pose is below the rule almost all the time. The MuJoCo arm model has no floor contact, so nothing stopped it.

**Step 4, readability per 60 s (report only; no pass/fail, no wording)**. ARGMAX, observers refit once as the K5 check (`m3e.fresh_observers` on the cached `trained_argmax_{0..3}_b0.npz` observer-training rollouts, which are the trained argmax ones, so reused, not regenerated). (a) = gap over 20 seeded circular shifts >= 4 s (same definition and seed as `m3d.time_shuffled_gap`); targets = the song's own causal z-score, not restarted per segment; the first segment of a song scores blocks >= 8 (the K5 check's EVAL_FROM), later ones all blocks. Interval = bootstrap 95 % of the mean over the 20 shifts (the 2.5-97.5 percentile range of the 20 per-shift gaps is also in `segments.json`). K5 check values for comparison: ext 0.625, int 0.636 (per-song means over 3 windows of 60 s, 357 held-out songs).

| song | segment (s) | ext gap [95 %] | int gap [95 %] |
|---|---|---|---|
| instant-crush | 0-60 | 0.135 [0.117, 0.153] | 0.261 [0.228, 0.291] |
| | 60-120 | 0.497 [0.451, 0.540] | 0.427 [0.379, 0.476] |
| | 120-180 | 1.253 [0.949, 1.542] | 1.287 [0.969, 1.591] |
| | 180-240 | 0.698 [0.596, 0.799] | 0.816 [0.715, 0.914] |
| | 240-300 | 0.516 [0.413, 0.617] | 0.508 [0.405, 0.606] |
| | 300-340 (40 s, partial) | 0.463 [0.390, 0.525] | 0.780 [0.653, 0.904] |
| five-years | 0-60 | 0.396 [0.312, 0.478] | 0.389 [0.292, 0.482] |
| | 60-120 | 0.365 [0.292, 0.433] | 0.389 [0.296, 0.480] |
| | 120-180 | 0.781 [0.629, 0.925] | 0.757 [0.612, 0.891] |
| | 180-240 | 0.692 [0.552, 0.823] | 0.677 [0.540, 0.805] |
| | 240-284 (44 s, partial) | 1.505 [1.157, 1.823] | 1.406 [1.144, 1.653] |
| presence | 0-60 | 0.250 [0.178, 0.320] | 0.258 [0.207, 0.307] |
| | 60-120 | 0.787 [0.688, 0.869] | 0.785 [0.693, 0.869] |
| | 120-180 | 0.634 [0.520, 0.752] | 0.409 [0.331, 0.487] |
| | 180-240 | 1.116 [0.936, 1.275] | 1.010 [0.844, 1.156]|
| | 240-270 (30 s, partial) | 1.200 [1.058, 1.335] | 1.015 [0.931, 1.095] |
All 16 segments are above 0 in both decoders (lowest: instant-crush 0-60, ext 0.135). The interval is over 20 shifts of one segment, not over songs: it does not say how the figures would vary across songs. These are three songs, not the 357 of the check.

**Deviations from the order**
1. `three.sh` is tied to another worktree (`dance-figures`) and to measuring scripts of another job; I did not run it. `scripts/body/v47_regression.sh` runs its three `ensemble_preview` commands from this tree and `cmp`s the outputs with the three stored hexagon files: identical.
2. The 720p copy of the side-by-side is 2560x720 (each panel at native 720p side by side), not a 1280x720 frame.
3. The page text for a CSV render says `1 arm · joint CSV · K5 policy` and shows one placeholder cue (no cues exist for a policy rollout); everything else in the page is the same template, camera and rig geometry (from the CSV header), implement `Rig::illustrative_five_axis().implement` (the default the fallback pages use).
4. Start pose of the rollout: `m3d.start_poses(1, 4242)`, the check's held-out start seed (the order did not name one).
5. The trajectory is not an output of `m3e_jax.block_fn`; `chunk_q` calls it unchanged and reads the block's 50 joint rows from the new carry's `buf` (no copy of K5 code, no change to a K5 file).

**FOR USER**
- Look at the videos beside the fallback; the check-csv floor/hand-speed refusals above mean this policy's pose is not yet something a real arm may play: the K5 training has no floor or hand-speed term. A K5-pass2 would need one (spec 7.22 point 3); not my decision.
- Joint trajectories and per-block state are saved for the three songs if anyone wants to plot them.

**Render status**: see the end of the log.

## Phase log

- 2026-11-06 phase 1 (lanes): export + check. Committed.
- 2026-11-06 phase 2 (rollout, tests): committed.
- 2026-11-06 phase 3 (Rust `--joint-csv`, v47 cmp, tests): committed. A 20 s test render (instant-crush 60-80 s, 1280x720) works; its frames show the page with the arm on its pedestal, a trail ribbon and the mirror shards.
- 2026-11-06 phase 4 (segments): committed.
- Phase 5 (full renders, `k5_render.sh`, unit `hyst-wo12-render`): started; resume with `systemd-run --user --unit=hyst-wo12-render2 -p MemoryMax=6G -p MemorySwapMax=0 -p CPUQuota=600% bash scripts/body/k5_render.sh` (finished files are kept). Pause `systemctl --user freeze hyst-wo12-render`, stop `systemctl --user stop hyst-wo12-render`.
