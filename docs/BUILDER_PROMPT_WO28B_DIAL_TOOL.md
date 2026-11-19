# Builder prompt: work order 28B, hand-set dial study: end-effector shapes, blind labelling tool, report script (2026-11-12)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing from it ships:
- no learning or training;
- no numeric pass bars;
- no verdict from you. Kosta (the user) labels the clips blind.

One arm only (permanent rule). A second builder (work order 28A) renders the clips in parallel and writes the manifest you read
(section 3).

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing.
  - **No network** in the tool: no CDN, no fonts, no fetches outside 127.0.0.1.
  - v47 exports must stay **byte-identical** in Off.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-dialtool origin/body`, then push `body-dialtool`.
- **Jobs:**
  - Builds and tests run detached and memory-capped:
    `systemd-run --user --unit=hyst-wo28b-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  - Cores **12-17** (`taskset -c 12-17`, `cargo -j 6`), never 6-11 (28A's).
  - Use your own `CARGO_TARGET_DIR=/secondary/hyst-data/cargo-target-wo28b`.
  - Mains only: poll `/sys/class/power_supply/ADP1/online` and wait while it reads 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-dialtool.md` (new; MORNING SUMMARY on top).
- **Environments:** body `/secondary/hyst-env/body`, brain `/secondary/hyst-env/brain` (node/Chrome recorder as used by
  `scripts/author/record_ensemble.cjs`). **Output root:** `/secondary/hyst-data/body/dialstudy/`.

## Read first

- `docs/BRAIN_SPEC.md` **§7.43** (binding: the study, the labelling tool, the out-of-scope list).
- `crates/hyst-previz/examples/ensemble_preview.rs` (`--implement ball|disc`, `--joint-csv`) and
  `hyst_compile::ensemble::Implement` (`ball()`, `disc()`).
- `scripts/body/k5p2_render.sh` (page + recorder), `scripts/body/make_arm.py` (`ball()`: mass and size).

## The work

### 1. Two end-effector shapes (visual only)

Add `--implement lamp` and `--implement gripper` to `ensemble_preview`. Simple geometry, about the ball's size, mounted where the ball is.
- **lamp:** a lamp-like head, i.e. a short cone or cylinder shade with a lit face, pointing along the last link.
- **gripper:** a simple hand or gripper, i.e. a palm block with two or three finger bars.

The sim keeps the ball's mass and inertia (same mass per 7.43.4; 28A does not change physics). Report the sizes and the stated mass.

**Regression:**
- The default (ball) output and every v47 export in Off must be byte-identical to before. Run the existing previz/compile tests that
  check this, and compare a v47 Off export's hash before and after.
- `cargo test` / `clippy -D warnings` for the touched crates.

Render one 3 s still clip of each shape on any test CSV, and look at frames.

Push, then write "EFFECTOR READY <commit>" in the night log. The overseer verifies it, merges it into `body` and tells 28A.

### 2. Blind labelling tool

A local page with a tiny stdlib Python server on 127.0.0.1 (default; anything equivalent with no network is fine).

- **Session build:** `dialstudy_session.py --clips /secondary/hyst-data/body/dialstudy/clips/manifest.json --out
  /secondary/hyst-data/body/dialstudy/session_<date>/`.
  - Copies or hardlinks each clip under a random code name (e.g. `c7f2.mp4`) into `session_<date>/clips/`, in a seeded random order
    (seed recorded).
  - Writes the key (code -> manifest id, set, intent, effector, dials) to `session_<date>/key/key.json`. Kosta never sees this folder.
  - The page and server never read the key.
- **Sets A-C:**
  - One clip at a time, replay allowed.
  - One click from: **tense / heavy / calm / angry / light / nothing, glitching / something, can't name it**.
  - Optional free-text note.
  - The clip's code name is not shown, and no set or intent is visible.
- **Set D** (only if the manifest has D pairs; 28A will skip D unless audio appears): the two renders of one excerpt, side by side or in
  sequence, order randomised. "Which one fits the music?" with the options first / second / neither.
- **Answers:** each click is appended immediately to `session_<date>/answers.csv` (code, answer, note, timestamp, replays). Closing the page
  loses nothing; a reload resumes at the first unanswered clip.
- **Session length:** with 22 clips of 12 s it must stay under 20 minutes. Show progress (n of N) only.
- **Test** with a fake manifest of 5 short dummy clips:
  - order is seeded and stable;
  - the key is never served (request it over HTTP and expect 404);
  - answers are written and resumed;
  - no external URL appears in the page (grep for `http`).
  Test modules run each in its own process.

### 3. Report script

`dialstudy_report.py --session <dir>` joins `answers.csv` with the key and writes `docs/DIALSTUDY_REPORT.md`. It contains:
- a table of every clip: intended setting / effector / Kosta's label / note;
- per dial: the low, neutral and high labels side by side;
- presets: intended vs label;
- end effectors: the same preset across ball / lamp / gripper;
- Set D picks, if any;
- it includes `docs/DIALSTUDY_DIALS.md` (28A's dial notes) by reference.

It gives **no verdict and no score**: no "viable", no percentages of correct. Kosta decides what it means. Test it on the fake session.

### 4. Done when

- The effector option is pushed, regression-checked and marked READY.
- The tool and the report script are pushed with tests.
- A short "how Kosta runs it" block (one command + URL) is in the night log.
- MORNING SUMMARY on top.

Do not run a real session with the user yourself: the overseer starts it once 28A's clips are checked.

**Out of scope (stop and ask; log FOR USER):** training of any kind, DEAM, limbic readout, pyribs, brain monitor, cortex changes,
hardware, new dials or feelings, any audio file.
