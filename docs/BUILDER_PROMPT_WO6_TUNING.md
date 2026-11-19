# Builder prompt: work order 6, the one-arm tuning loop + self-surprisal lane (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo6-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-tuning -b body-tuning origin/body`. Push
  `body-tuning`. Never touch `body`, `keys-decide`, `master` or the main checkout.
- **Version 47 stays byte-identical in `Off`.** After any change to `crates/` or anything the dance path reads, build `ensemble_preview` from
  your worktree and cmp the three songs against `$D/hexagon-47.html`, `$D/five-years-hexagon.html`, `$D/presence-hexagon.html` (export lines
  in `$D/tracker-scratch/newsong/three.sh`, which builds from another worktree: copy them into your own script;
  `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`; a shell guard refuses commands mixing
  `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file). For Rust: cargo test, clippy -D warnings and fmt --check on
  hyst-compile, hyst-output, hyst-previz and hyst-cli, with your own `CARGO_TARGET_DIR`.
- **Your share: 6 threads, 6 GB.** Environment `/secondary/hyst-env/brain`. Data under `/secondary/hyst-data/brain/author/tuning/`.

## Read first

1. `docs/BRAIN_SPEC.md` §7.17 points 4–6 (binding; point 4 as corrected by the user: **the installation is ONE arm**; no hexagon, no six-arm
   wiring, no ensemble work of any kind), §7.14.
2. `docs/NIGHT_LOG_body-fallback.md` (the one-arm fallback this builds on) and `docs/BUILDER_PROMPT_WO3_FALLBACK.md`.
3. `scripts/author/README.md` and code (`build.py`, `attach.py`, `export_cli.cjs`, `author_core.cjs`, `author_template.html`, `serve.py`,
   `record_ensemble.cjs`, `mappings/example-sketch.json`); `crates/hyst-compile/src/body_track.rs`, `mind_state.rs`;
   `crates/hyst-previz/README.md`.
4. `scripts/body/selfsurprisal.py` and `/secondary/hyst-data/body/selfsurprisal/schema.json`.

## Goal

The user judges the one-arm videos (`/secondary/hyst-data/brain/author/fallback/<song>-fallback.mp4`) and tunes the mapping by eye in the
authoring tool. Make that loop fast: change the mapping, see the arm move to the music again, within seconds for a short window.

## Phases

**Phase 1, the re-render loop.** One command (default: `scripts/author/retune.sh SONG MAPPING.json [START_S DURATION_S]`, plus a button in the
authoring page via `serve.py` if it is simple) that takes the current mapping (the file the authoring page saves or exports), rebuilds the
bodyTrack, attaches it, compiles the one-arm preview, and renders either the whole song or a window (default 20 s) to an mp4 with the song's
audio for that window. Songs: Instant Crush, Five Years (with its tempo map, as in the fallback), Presence. Measure and report the wall time for
a 20 s window and for a whole song. If a 20 s window takes longer than about 60 s, find where the time goes (cargo build, page load, frame
capture, encoding) and cut it (e.g. build once and reuse the binary, lower resolution option, faster encoder preset); log what you changed.
Keep the full-quality whole-song render available. Document the loop in `scripts/author/README.md` in plain steps the user can follow.

**Phase 2, self-surprisal lane.** Offer the self-surprisal data in the authoring tool as a lane named "cerebellum: prediction error of its own
arm" (no claim; mechanism name only). One arm: use the arm the fallback drives, or the mean over the six replayed v47 arms if no single arm
matches; state which. Tests for the new lane (Node author tests and Python).

**Phase 3, check.** Render one 20 s window per song with the loop from `example-sketch.json`; check duration against the audio window, that the
audio is the song's audio at that window, and look at the middle frame (arm, floor, nothing below the floor). Make a 720p copy under 30 MiB of
each whole-song fallback video for sending.

The v47 check passes after every Rust change. When finished, message the overseer: branch, last commit, the loop command and its measured
times, paths of the test windows and 720p copies with sizes and durations, the self-surprisal lane choice, v47 cmp result, tests run, FOR USER
items.
