# Builder prompt: work order 3, builder 2, the fallback arm, self-surprisal, mindState v2 (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; if GitHub returns a server error,
  retry). `git fetch -q origin`, then make your worktree:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-fallback -b body-fallback origin/body`. Work only there.
  Push `body-fallback` after every phase. Never touch `body`, `keys-decide`, `master` or the main checkout. Builder 1 works in parallel on
  `body-m3b` (`scripts/body/tm3*`, new M3b files): do not edit those.
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. **Version 47 stays byte-identical in `Off`.** After any change to `crates/` or to
  anything the dance path reads, run the check: build `ensemble_preview` from your worktree and cmp the three songs against `$D/hexagon-47.html`,
  `$D/five-years-hexagon.html`, `$D/presence-hexagon.html` (commands in `$D/tracker-scratch/newsong/three.sh`, which builds from another
  worktree, so copy its export lines into your own script; `D=/home/stcksmsh/Documents/Codex/2026-09-23-can-you-check-the-programming-github/output/music-arm`;
  a shell guard refuses commands mixing `$D` with pipes, `&&`, loops or heredocs, so put such steps in a script file). For Rust: cargo test,
  clippy -D warnings and fmt --check on hyst-compile, hyst-output, hyst-previz and hyst-cli; use your own `CARGO_TARGET_DIR` (a shared one gave
  stale errors).
- Environment `/secondary/hyst-env/brain`. Install nothing. Data outside git under `/secondary/hyst-data/`.
- **Your share: 6 threads, 6 GB.** Runs longer than 10 min through `scripts/compute/run_job.py`, memory-capped
  (`systemd-run --user --unit=hyst-wo3b2-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 <script>`), mains power only.
- Log: `docs/NIGHT_LOG_body-fallback.md`, MORNING SUMMARY on top, updated after every phase.
- Usage limits may stop you mid-task; the overseer will resume you. Commit and push often.

## Read first

1. `docs/BRAIN_SPEC.md` §7.14 (binding), then `docs/BODY_BRAIN_PLAN.md` (version 2) §8 and §9 (truth words).
2. `docs/NEXT_DECODER_THEN_BRAIN.md` §2 and its 2026-11-01 note (authoring tool on brain lanes; names).
3. `scripts/author/README.md` and its code; `scripts/brain/brain_mindstate.py`; `crates/hyst-compile/src/mind_state.rs`;
   `docs/NIGHT_LOG_body-h2show.md` (B7 lanes, brainDump); `docs/NIGHT_LOG_body-m1m3.md` (K1, the v47 replay set);
   `scripts/body/cerebellum.py`, `build_v47.py`.

## Phases

**Phase 1, the fallback arm, minimal (≤ 3 h).** The authoring tool reads B7 lanes (from `mindState.brain`, built in work order 2) instead of
B2's, for the three danced songs (Instant Crush, Five Years, Presence). Mechanism names only. Build the page, then export a bodyTrack per song
with `export_cli.cjs` and compile the arm preview with `attach.py --preview`, using `mappings/example-sketch.json` as the mapping (a
starting sketch, not a claim; the user tunes it by eye later). Deliver the three preview files outside git and list their paths. No design
choices beyond that: the mapping is the user's. Tests in `scripts/author/` pass. v47 check passes (Off is untouched).

**Phase 2, the self-surprisal lane (≤ 1.5 h).** From the K1 round-2 bundle `/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt`: the cerebellum's
NLL of the actual body state, per arm, for the three danced songs (each arm replaying v47 in physics, as in `build_v47.py`), at 30 Hz, to
`/secondary/hyst-data/body/selfsurprisal/<song>.npz` plus a JSON schema. Name: "cerebellum: prediction error of its own arm". No claim (K1
failed). Report the size per song.

**Phase 3, `mindState` version 2 (≤ 3 h).** The reserved `bands` / `surprise` / `neuromod` arrays carry B7 lanes (mechanism names), with a
version-2 reader in `mind_state.rs` that still reads version 1 unchanged. `mood.energy` stays from core-2b. Tests for both versions. v47 check
passes in `Off`.

**Phase 4 (≤ 20 min).** `scripts/compute/manifest.py` skips `dataset-metadata.json` in `build` and `verify` (Kaggle consumes it on upload). Test
added; `test_compute` passes.

**Also (≤ 30 min):** brainDump drops the crossing marks (§7.14 point 4): keep the four per-layer order-parameter traces as continuous data.
Regenerate the three danced songs' dumps.

## Finish

Fill the MORNING SUMMARY and report to the overseer in a few lines: the three preview paths; self-surprisal files and sizes; `mindState` v2
tests; the v47 check result (cmp output); test counts (Python, Node, Rust); FOR USER items; branch, last commit. Never say something looks
better; no claims. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
