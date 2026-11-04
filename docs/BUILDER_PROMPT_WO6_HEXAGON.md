# Builder prompt: work order 6, the fallback on six arms + self-surprisal lane (2026-11-05)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped (`systemd-run --user --unit=hyst-wo6-<you>-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1). Keep to your thread and memory cap.
- Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated after every phase. Usage limits or a power-off may stop you; the overseer resumes you. Commit and push after every phase.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- Worktree: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-hexagon -b body-hexagon origin/body`. Push
  `body-hexagon`. Never touch `body`, `keys-decide`, `master` or the main checkout.
- **Version 47 stays byte-identical in `Off`.** After any change to `crates/` or anything the dance path reads, build `ensemble_preview` from
  your worktree and cmp the three songs against `$D/hexagon-47.html`, `$D/five-years-hexagon.html`, `$D/presence-hexagon.html` (export lines
  in `$D/tracker-scratch/newsong/three.sh`, which builds from another worktree: copy them into your own script;
  `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`; a shell guard refuses commands mixing
  `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file). For Rust: cargo test, clippy -D warnings and fmt --check on
  hyst-compile, hyst-output, hyst-previz and hyst-cli, with your own `CARGO_TARGET_DIR`.
- **Your share: 6 threads, 6 GB.** Environment `/secondary/hyst-env/brain`. Install nothing. Data under `/secondary/hyst-data/brain/author/hexagon/`.

## Read first

1. `docs/BRAIN_SPEC.md` §7.17 points 4–6 (binding), §7.14.
2. `docs/NIGHT_LOG_body-fallback.md` (the one-arm fallback this extends), `docs/BUILDER_PROMPT_WO3_FALLBACK.md`.
3. `scripts/author/README.md` and code (`build.py`, `attach.py`, `author_core.cjs`, `record_ensemble.cjs`, `mappings/example-sketch.json`);
   `crates/hyst-compile/src/body_track.rs`, `mind_state.rs`; `crates/hyst-previz/README.md` (`ensemble_preview`, `--ring`, `--body layered`).
4. `scripts/body/selfsurprisal.py` and `/secondary/hyst-data/body/selfsurprisal/schema.json`.

## Phases

**Phase 1, six arms.** The fallback mapping (same B7 lanes, same `example-sketch.json`) drives the six-arm hexagon (as v47: `--ring 6,0.8`).
Each arm gets a per-arm offset or role (for example a phase delay around the ring, or a role per arm chosen from the lanes). Default: a
per-arm time offset around the ring plus mirrored left/right pairs; make it a field of the mapping so the user can change it by eye in the
authoring page, and log the default as "FOR USER". Arms reaching into each other's space is intended; report the minimum distance between any
two arms' links over each song (a number, no claim). Previews for Instant Crush, Five Years, Presence under the data folder.

**Phase 2, videos.** Whole-song previz videos of the three songs with `record_ensemble.cjs` (1080p, 30 fps, original AAC copied; Five Years uses
`HYST_TEMPO_MAP=five-years.tempomap.json` as before). Check per video: duration against the audio, the audio payload hash against the source,
and look at frames at 30, 100, 180, 260 s (all six arms drawn, nothing below the floor). Also make a 720p copy under 30 MiB of each, for
sending.

**Phase 3, self-surprisal lane.** Offer the self-surprisal data in the authoring tool as a lane named "cerebellum: prediction error of its own
arm" (no claim). Per arm where the mapping is per arm; otherwise the mean over arms. Tests for the new lane (Node author tests and Python).

The v47 check passes after every Rust change. When finished, message the overseer: branch, last commit, preview and video paths with sizes and
durations, the per-arm default, minimum inter-arm distances, v47 cmp result, tests run, FOR USER items.
