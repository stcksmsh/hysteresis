# Builder prompt: work order 7, camera framing for all one-arm renders (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing unless the prompt says so. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo7-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: reuse `.claude/worktrees/body-fallback-tmp` (branch `body-tuning`, last commit d09d8bf); first `git merge origin/body`. Push `body-tuning`.
- **Version 47 stays byte-identical in `Off`.** After any change to `crates/` or anything the dance path reads, build `ensemble_preview` from
  your worktree and cmp the three songs against `$D/hexagon-47.html`, `$D/five-years-hexagon.html`, `$D/presence-hexagon.html` (export lines
  in `$D/tracker-scratch/newsong/three.sh`, which builds from another worktree: copy them into your own script;
  `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`; a shell guard refuses commands mixing
  `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file). For Rust: cargo test, clippy -D warnings and fmt --check on
  hyst-compile, hyst-output, hyst-previz and hyst-cli, with your own `CARGO_TARGET_DIR`.
- **Your share: 6 threads, 6 GB.** The installation is ONE arm; never multiple arms.

## Read first

`docs/BRAIN_SPEC.md` §7.18 point 4 (binding); `docs/NIGHT_LOG_body-tuning.md`; `scripts/author/README.md`, `record_ensemble.cjs`, `retune.sh`;
`crates/hyst-previz/README.md` and the preview's camera code.

## The work

In Presence at 110 s the hand leaves the top edge of the view. Widen or re-aim the camera so the whole arm, hand and its disc stay inside the
frame for all one-arm renders (the retune loop's windows and whole songs). Default: compute the arm's full reach envelope (base to fully
extended hand in every direction, plus the disc) and frame that with a margin; keep the camera angle otherwise. Check by computing, for the three
songs with `example-sketch.json`, the projected hand and disc positions for every frame (or every 0.1 s) and report the share of frames with any
part outside the view (must be 0) and the minimum margin; look at the frame at Presence 110 s. If the camera lives in a file the v47 hexagon
export reads, keep v47 `Off` byte-identical (the one-arm camera must not change the hexagon reference output). Re-render the three whole songs at
720p under 30 MiB. Tests as before.

When finished, message the overseer: branch, last commit, what changed, the outside-share and margin per song, the 110 s frame path, the 720p
paths with sizes, v47 cmp, tests run.
