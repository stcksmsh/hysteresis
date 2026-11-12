# Builder prompt: work order 29B, motor-network toy test: labelling tool, measurement script, report script (2026-11-12)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing from it ships:
- no learning or training;
- no pass bars;
- no verdict from you. Kosta (the user) labels the clips blind.

One arm only (permanent rule). A second builder (work order 29A) builds the network and renders the clips in parallel, and writes the
manifest and per-clip files you read.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing.
  - **No network** in the tool: no CDN, no fonts, no fetches outside 127.0.0.1.
  - Data, audio and videos stay outside git. Copyrighted audio is never committed or uploaded.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-mnettool origin/body`, then push `body-mnettool`.
- **Jobs:** tests run detached and memory-capped:
  `systemd-run --user --unit=hyst-wo29b-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  Cores **12-17** (`taskset -c 12-17`), never 6-11 (29A's). Mains only: poll `/sys/class/power_supply/ADP1/online` and wait while it reads 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnettool.md` (new; MORNING SUMMARY on top).
- **Environment:** body `/secondary/hyst-env/body` (numpy, scipy). **Output root:** `/secondary/hyst-data/body/motornet_toy/`.

## Read first

- `docs/BRAIN_SPEC.md` **§7.44** (binding: the toy test, the labels, the report) and §7.43.
- Round 1's tool and report, which you extend (do not break round 1; its tests must still pass):
  `scripts/body/dialstudy_session.py`, `scripts/body/dialstudy_report.py`, `scripts/body/test_dialstudy.py`,
  `scripts/body/dialstudy_straight.py`, `docs/DIALSTUDY_REPORT.md`.
- Round-1 session (for Part 4's "round 1" labels): `/secondary/hyst-data/body/dialstudy/session_2026-11-12/` (`key/key.json`,
  `answers.csv`). Read it only from the report script; the page never reads it.
- `scripts/body/m3f_report.py` (`fk_points`), `scripts/body/arm_sim.py` (`csv_text` format).
- 29A's prompt, `docs/BUILDER_PROMPT_WO29A_MOTORNET_CLIPS.md`, sections 6 and 7 (manifest and files), and 29A's rules file
  `docs/MOTORNET_RULES.md` on branch `body-mnet` once pushed (its section (f) defines the measurements; follow it).

## The work

### 1. Session tool for round 2

Extend `dialstudy_session.py` (or a thin wrapper `motornet_session.py`; your choice) to build a session from
`/secondary/hyst-data/body/motornet_toy/clips/manifest.json` into `/secondary/hyst-data/body/motornet_toy/session_<date>/`:
- one seeded random order (seed recorded) mixing Parts 1, 2 and 4 single clips, and Part 3 pairs when present; coded names; key in
  `session_<date>/key/key.json` (code -> id, part, setting, effector, round1_id, song); the page and server never read the key;
- labels for single clips (Parts 1, 2, 4): **calm / sad / tense / energetic / light / nothing, glitching / something, can't name it**;
  optional note. Round 1's label set stays the default for round-1 manifests;
- Part 3 pairs: the two renders in random order, "which fits the music?" with first / second / neither (round 1's pair mode);
- Part 4 clips are the round-1 video files, copied or hardlinked under a fresh code name; nothing in the page may reveal they are old;
- answers appended immediately to `answers.csv`; reload resumes; progress n of N only; session under 25 minutes (18 single clips + up to 5
  pairs).
- Tests (each module in its own process): seeded stable order; key and `answers.csv` return 404 over HTTP; new label set shown for the
  round-2 manifest and the old one for a round-1 manifest; Part 4 code names are fresh; no external URL in the page; a fake manifest with
  dummy clips of every part.

### 2. Measurement script

`scripts/body/motornet_measure.py --manifest <path> --out <dir>/measurements.json`: per setting (from its Part 1 clip's CSV and
`activity.npy`), exactly the definitions of 29A's rules file (f): participation ratio; regime decays / cycles / wanders; dominant movement
frequency; mean hand speed; mean hand height; hand-path straightness (chord/arc per stroke, reusing `dialstudy_straight.py`'s stroke
definition). Hand path from `m3f_report.fk_points` on the CSV. Numbers only. Tests on synthetic inputs with known answers (a pure
sinusoid activity -> cycles with the right frequency; an exponentially decaying one -> decays; a straight-line hand path -> 1.0; PR of
k equal independent components -> k).

### 3. Report script

`scripts/body/motornet_report.py --session <dir> --measurements <path>` writes `docs/MOTORNET_REPORT.md`:
- table per setting S01-S12: setting values -> Kosta's label -> note -> measurements;
- ball vs lamp for S01 and S02;
- Part 3 picks per song (setting ids, which was picked, or neither), if present;
- Part 4: round-1 label vs now per repeated clip (round-1 labels from the round-1 session's key + answers);
- network and body parameters used, by reference to `docs/MOTORNET_PARAMS.md`.
**No verdict and no score:** no "worth building on", no counts of "correct". Test it on a fake session.

### 4. Done when

- Tool, measurement script and report script are pushed with tests; round 1's tests still pass.
- A short "how Kosta runs it" block (one command + URL, port 8765) is in the night log.
- MORNING SUMMARY on top; "TOOL READY <commit>" in the night log.

Do not run a real session with the user yourself: the overseer starts it once 29A's clips are checked.

**Out of scope (stop and ask; log FOR USER):** training of any kind, DEAM, limbic part, pyribs, brain monitor, cortex changes, hardware,
new labels beyond the list above, any real audio file.
