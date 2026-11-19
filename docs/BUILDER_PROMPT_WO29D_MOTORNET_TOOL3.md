# Builder prompt: work order 29D, motor-network toy test Part 3: session and report additions (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER" instead of
waiting. You start with no context: everything you need is named below.

**This is a disposable study.** Nothing ships. No verdict text anywhere. One arm only. A second builder (29C) renders the Part 3 music pairs in
parallel and writes the manifest items you read.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works. Retry on a GitHub server
  error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:**
  - `src/` and `tools/` are read-only. Never drive hardware. Install nothing.
  - **No network** in the tool: no CDN, no fonts, no fetches outside 127.0.0.1.
  - Data, audio and videos stay outside git. Copyrighted audio is never committed or uploaded.
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-mnettool3 origin/body`, then push `body-mnettool3`.
- **Jobs:** tests run detached and memory-capped:
  `systemd-run --user --unit=hyst-wo29d-<fresh-name> -p MemoryMax=6G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`.
  Cores **12-17** (`taskset -c 12-17`), never 6-11 (29C's). Mains only: poll `/sys/class/power_supply/ADP1/online` and wait while it reads 0.
- **Push** within 30 minutes and after every phase. Log: `docs/NIGHT_LOG_body-mnettool3.md` (new; MORNING SUMMARY on top).
- **Environment:** body `/secondary/hyst-env/body` (numpy, scipy). **Output root:** `/secondary/hyst-data/body/motornet_toy/`.


## Read first

- `docs/BRAIN_SPEC.md` **§7.46** (binding: the Part 3 report additions).
- `scripts/body/dialstudy_session.py`, `motornet_report.py`, `test_motornet.py`, `test_dialstudy.py` (on body), and `docs/MOTORNET_REPORT.md`.
- `docs/BUILDER_PROMPT_WO29C_MOTORNET_MUSIC.md` step 4 (the Part 3 manifest fields).

## The work

1. **Session option:** `dialstudy_session.py --parts 3` (or equivalent) builds a session from the manifest with **only** the Part 3 pairs.
   Parts 1, 2 and 4 were labelled already. Everything else stays as it is:
   - coded names;
   - seeded order;
   - key not served;
   - the two renders in random order, "first / second / neither".
2. **Report:** in `motornet_report.py`, the Part 3 table gives, per song:
   - the two settings as shown (first / second);
   - Kosta's pick;
   - the mean hand speed of each render;
   - the cortex arousal over the excerpt, raw and standardised.

   Read them from the manifest's Part 3 items (`hand_speed`, `arousal_raw`, `arousal_std`; if 29C's night log on branch `body-mnet3` names
   them differently, follow it). The report must be able to combine the Parts 1/2/4 session (`session_2026-11-13`) and a Part 3 session into
   one `docs/MOTORNET_REPORT.md`, e.g. by a repeatable `--session`.
3. **Tests:** with a fake Part 3 manifest and session:
   - only pairs appear with `--parts 3`;
   - the key returns 404;
   - the report columns are filled.

   Round 1's tests and `test_motornet.py` must still pass. Run each test module in its own process.
4. **Done when:** pushed, night log with MORNING SUMMARY, "TOOL3 READY <commit>". Then stop.

**Out of scope:** training, cortex, hardware, any real audio file, new labels.
