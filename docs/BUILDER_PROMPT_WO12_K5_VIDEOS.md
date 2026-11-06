# Builder prompt: work order 12, the K5 video path (2026-11-06)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo12-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Keep to your thread and memory cap. Every long run must be pausable (`systemctl --user freeze/thaw <unit>`) and stoppable (`systemctl --user stop <unit>`), and restartable with one command without redoing finished songs.
- **Push your branch before any long run.** Log: `docs/NIGHT_LOG_body-k5video.md`, MORNING SUMMARY on top, updated after every phase. Commit and push after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: new `.claude/worktrees/body-k5video`, branch `body-k5video` from `origin/body` (9f66459 or later). Push `body-k5video`.
- **Your share: 6 threads, 6 GB** (other projects share this machine). Environments: brain `/secondary/hyst-env/brain` (torch, for B7 lanes), body `/secondary/hyst-env/body` (JAX/MuJoCo, for the policy). One arm, always: never a hexagon, ring or ensemble.
- Do not change the K5 training or check code paths (`k5_train.py`, `k5_eval.py`, `m3e*.py`): import them. New files are yours. If you must touch a shared file, keep its old behaviour bit-identical and test it.

## Read first

- `docs/BRAIN_SPEC.md` §7.22 (binding: point 1 is this order), §7.19 A and C (argmax for every claim, observer procedure, claims), §7.20.
- `docs/NIGHT_LOG_body-k5train.md` (the K5 trainer and check; its "Renders (step 5)" FOR OVERSEER note lists exactly what is missing).
- `scripts/body/K5_RUN.md`, `scripts/body/k5_data.py` (module docstring: the lane definitions), `scripts/body/k5_train.py` (`WindowToy`, `rollout_batched`, `score_modes`), `scripts/body/k5_eval.py` (observer procedure), `scripts/body/m3e.py` (causal 30 s normalisation), `scripts/body/arm_sim.py` (`csv_text`, the 50 Hz joint CSV).
- `scripts/author/retune.sh`, `scripts/author/wo7_renders.sh`, `scripts/author/README.md` (the one-arm camera render of the authoring tool), `crates/hyst-previz/README.md`.

## Inputs

- Policy: `/secondary/hyst-data/body/k5/run1/best.pkl` (round 977, K5 try 1, passed). Check results and cached rollouts: `/secondary/hyst-data/body/k5/run1/eval/` (trained.json, rollouts/).
- The three danced songs: `instant-crush`, `five-years`, `presence`. B7 input: `scripts/brain/braindump.py` `danced_inputs(name)` (x, T x 46); B7 epoch 6 checkpoint as in `k5_data.cmd_lanes` (`train_b7.load_model7(braindump.CKPT)`). Audio: `/secondary/hyst-data/brain/author/audio/<song>.m4a`.
- The fallback videos to sit next to: `/secondary/hyst-data/brain/author/tuning/720p-cam/<song>-720p.mp4` (authoring tool, example-sketch mapping, WO7 camera).

## The work

1. **Lanes.** Export each danced song's B7 lanes in exactly the K5 format (`k5_data.song_lanes`, same npz keys as `/secondary/hyst-data/body/k5/lanes/check/*.npz`) to `/secondary/hyst-data/body/k5/danced/lanes/<song>.npz`. Test: for one check-split song, your export path gives the same arrays as the stored file (bit-identical, or state the max difference).
2. **Full-song rollout.** Roll `best.pkl` over each whole song, ARGMAX mode, as one continuous episode: the carry (arm, physics, cerebellum, cortex and observer state) is never reset, and the 30 s causal normalisation runs over the whole song from its start (as in the training windows' own warm-up, extended). Use chunks if memory needs it, with the state carried exactly across chunk edges. Test: the full-song rollout over the first 60 s equals a single-window rollout of the same 60 s (bit-identical, or state the max difference and why). Write the 50 Hz joint CSV with `arm_sim.csv_text` to `/secondary/hyst-data/body/k5/danced/<song>.k5.csv`; check it with `hyst check-csv` (crates/hyst-cli) and report any breaches. Save the per-block brain state and joint trajectory (npz) beside it.
3. **Render.** There is no renderer for a joint CSV yet. Build the smallest path that renders a joint CSV with the same one-arm camera, rig, implement and page style as the fallback videos (`ensemble_preview --body layered --clock music` as called by `retune.sh`), with the song's audio, 1080p, plus a 720p copy under 30 MiB (the size loop in `wo7_renders.sh`). Default: a new additive input (a new example or an off-by-default flag) that replaces the body pose with the CSV's joint angles; nothing else in the page changes. If you touch any Rust crate: `cargo test`, `cargo clippy -D warnings` and `cargo fmt --check` on hyst-compile, hyst-output, hyst-previz and hyst-cli (fresh `CARGO_TARGET_DIR` under `/secondary/hyst-data/`), and the v47 regression must stay byte-identical: `bash $D/tracker-scratch/newsong/three.sh TAG` then `cmp` against `$D/hexagon-47.html`, `$D/five-years-hexagon.html`, `$D/presence-hexagon.html`, with `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm` (a shell guard refuses commands mixing that path with pipes, `&&`, loops or heredocs: put such steps in a script file). Output: `/secondary/hyst-data/body/k5/danced/video/<song>-k5.mp4` and `<song>-k5-720p.mp4`. Also one side-by-side 720p file per song (fallback left, K5 right, same audio), under 30 MiB.
4. **Report only: readability per 60 s.** External and internal (a), ARGMAX, per consecutive 60 s segment of each song's continuous rollout (last partial segment reported separately with its length). Observers: exactly the K5 check's for the trained policy (fit on the same 4 observer-training rollouts; reuse `eval/rollouts/` if they are the cached trained argmax ones, else regenerate with the same keys and seeds), not refit per song. Same (a) definition (20 seeded circular shifts >= 4 s). Per segment: the gap and its 95 % interval over the shifts, plus the K5 check value (0.625 ext, 0.636 int) for comparison. Write `/secondary/hyst-data/body/k5/danced/segments.json` and a table in the night log. This is report-only: no pass/fail, no wording claims.

## Done when

- Lanes, CSVs, npz, the six mp4s and the three side-by-sides exist; CSV durations equal the song durations (state the difference in seconds); video durations equal the audio durations; `check-csv` result per song.
- You looked at frames from each video (start, middle, end, and one where the arm moves most) and state what is in them, without judging quality.
- Tests for steps 1-3 pass and are committed; any Rust checks and the v47 cmp pass.
- segments.json and the table are written. Night log MORNING SUMMARY lists paths, numbers, deviations and FOR USER items. Branch pushed. Then report to the overseer.
