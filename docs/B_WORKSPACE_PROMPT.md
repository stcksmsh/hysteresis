# Prompt: build B, the workspace (paste this to an agent in the repo)

Repo `stcksmsh/hysteresis`, branch `keys-decide` (never push to `master`).
Frozen `src/` and `tools/` are read-only. Never drive hardware.

The user has chosen this piece of work: **B, the workspace**, a recurrent state
that gives the dancing arms anticipation, payoff, afterglow, recognition and
composure. The restart prompt's rule against starting a big piece without the
user's choice is answered for B only. Melody-following and the braking work
stay untouched.

## Read, in this order

1. `docs/DANCE_RESTART_PROMPT.md`, in full: the current state (version 47), the
   user's settled wishes, how they review.
2. `docs/B_WORKSPACE.md`, in full: **the spec for this work.** Where it gives
   numbers, they are starting points; where it gives rules, they bind.
3. The last two entries of `docs/DANCE_HANDOFF.md` (versions 46 and 47).
4. `crates/hyst-compile/src/director.rs` (`Evidence`, `character`, `transitions`,
   `fixture`) and `crates/hyst-compile/src/director/figures.rs`
   (`compile_ensemble`: `intensity`, `classify`, runs, `ranks`/`swell`, `sized`,
   motif instances, moments, formations and `accents`, the figure clock, `hand`).

Ignore most of `AGENTS.md`; only its top section and last few entries are current.

## What you can and cannot verify

You can change the planner and run the tests. You **cannot** plan a real song,
measure one or make a video: the audio, sidecars, previews and measuring
scripts live only on the user's machine. Never say a change improved the dance.
Every result is unverified until the user exports, measures and judges it.

## Order of work. Stop and report at each ★.

1. **Golden first.** Before changing anything, add a test that records a digest
   of `compile_ensemble` output for the existing fixtures (one arm and six arms).
   `WorkspaceMode::Off` must reproduce it exactly from now on. Commit.
2. **Refactor without behaviour change.** Lift the known-future logic (arrival
   lift sign, cuts, repeats) out of the moments code into `Foresight`. The golden
   test must still pass. Commit.
3. **The workspace alone**, in `director/workspace.rs`: `BeatObs`, levels L1 to
   L4, surprise, the five field values, basins, `step()` as a pure per-beat
   function, and the modes `Off`, `Rehearsed`, `Schematic`. Not wired in yet.
   Tests 2 to 8 from the spec, on synthetic evidence (extend `fixture` or add a
   builder). Commit. ★ Report the field shapes from the tests in numbers.
4. **Wire the field into the existing knobs**, exactly as the spec's table says.
   Basins act only through formations, `accents`, `recall_from` and the `way`
   flip. No new moves, no new formations, no change to the follower, the caps
   or the collision check. Tests 9 and 10. Commit.
5. **Debug lane and summary**: the optional `workspace` lane on `EnsembleScore`,
   and the summary printed by `ensemble_preview` (basins with clock times, tension
   peaks, the largest surprises). Add a `--workspace off|rehearsed|schematic`
   flag to the example. Commit. ★ Stop.

Do not build `Learning`, per-arm temperament, the v2 latent workspace,
melody-following or braking.

## The loop guard

Read "Acceptance", "Rounds and stop rules" and "The v2 gate" in the spec
before writing code. They are fixed in advance:
- This prompt covers **round 1 only**. After step 5 you stop. Round 2 (tuning)
  starts only when the user sends a verdict with clock times, and it may change
  constants only.
- Never touch the frozen list (follower, braking, collision check, caps,
  motifs, formations, `character()`, moments' timing), even if you find a bug
  there. Write it into the handoff instead.
- Never propose a new mechanism, field or basin in this work. If you believe one
  is needed, say so in one line in the handoff and stop.

## When you stop

- Run the checks from the restart prompt, before and after:
  ```
  cargo test --workspace --exclude hyst-render
  cargo clippy -p hyst-compile -p hyst-output -p hyst-previz -p hyst-cli --all-targets -- -D warnings
  cargo fmt --all --check
  node crates/hyst-previz/tests/ensemble.cjs
  cd scripts && python3 -m unittest discover -p "test_dance_*.py"
  ```
- Append an honest entry to `docs/DANCE_HANDOFF.md`: what changed, the test
  numbers, every constant and where it came from, and **"not verified on any
  song"**.
- Give the user the exact commands for their machine: for each of the three
  songs, an export with `--workspace off`, `rehearsed` and `schematic`, then
  `jolts.py`/`spans.py`, then the blind A | B | C clips listed under
  "Acceptance" in the spec. Tell them what to look for and at which clock times
  (the held breath before 1:32 in "Presence"; the chorus return in "Instant
  Crush").
- Update the "Where we are" and "Known weak points" sections of
  `docs/DANCE_RESTART_PROMPT.md` and add a short entry to `AGENTS.md`.
- Commit and push to `keys-decide`.

Write to the user in plain, short sentences with numbers. Ask before any
artistic choice the spec does not settle.
