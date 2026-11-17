# Builder prompt: work order 50, factorial "fits the music" viewing material: tempo x phase x events (7.79 Step 1) (2026-11-17)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".

**Binding:**
- `docs/BRAIN_SPEC.md` **§7.79** (Step 1 and its overseer notes), then 7.78, 7.75 (Q3 excerpt rule) and `docs/A_RULES.md`.
- This is test tooling only. Do not change A and do not build a motor clock or a lookahead selection (7.79 HOLD).
- Give no verdict. One arm.
- The overseer's subagents may run small jobs on cores 14-19, so stay on cores 6-13.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b body-factorial origin/body`. Use absolute paths. Create no new
  worktrees.
- Units:
  - detached units `hyst-wo50-<fresh>`, `MemoryMax=8G`, `MemorySwapMax=0`;
  - `taskset -c 6-13` on the actual worker process, `python -u`;
  - read logs 1 min after start; catch errors per item and log names.
- Runs: run on battery. Commit and push before every run.
- Commits: plain messages, with no co-author or attribution lines.
- No installs, downloads or uploads. Environment: `/secondary/hyst-env/brain`.
- Data:
  - In (read-only): `/secondary/hyst-data/body/{grammar2,pulse,grammar,controls,t0,t0_phantom,t0_motorica}/` and the datasets' audio;
  - Out: `/secondary/hyst-data/body/factorial/`.
- Night log `docs/NIGHT_LOG_body-factorial.md`. Keep messages short.

## Read first

- `docs/BRAIN_SPEC.md` 7.75 and 7.78-7.79.
- `docs/A2_REPORT.md`; A2 = seed 49102, `grammar2/runs/seed49102/best.pt`.
- `docs/PULSE_RULES.md`, `docs/PULSE_REPORT.md`, `docs/PULSE_FLASH_RESULT.md` (Kosta's notes on dropouts and pre-drop changes).
- The per-song pulse files `pulse/songs/<key>.{npz,json}`: 100 Hz rate, phase, amp, events.
- Code:
  - `scripts/body/grammar_{model,clips,checks}.py` and `scripts/body/retarget_render.sh` (lamp-head render);
  - `scripts/body/dialstudy_session.py`, whose per-item `questions` option was added in WO48;
  - `scripts/body/pulse_lib.py`, `scripts/brain/fast_features.py` (ear features).

## The work

1. **Rules note `docs/FACTORIAL_RULES.md`, pushed before any clip is made.** It fixes everything below, with the exact numbers.
   - **Excerpts:** 6 excerpts of 10 s each, by the 7.75 Q3 rule (RMS ≥ the song's median, not in the first or last 10 s). At least 2 must
     contain a drop or a dropout, found by the event detector below.
     - Songs from FineDance / AIOZ / PhantomDance, with no Motorica, so the material may be viewed anywhere.
     - None of them under 12 s of whole-song duration (7.79 Q4).
     - Choice is seeded (seed 50101); state the seed and the songs.
   - **Base movement:** for each excerpt, one A2 sample conditioned on the human controls of that excerpt, as in the WO45B checks. Use
     nucleus 0.9 and a fixed sample seed. All 8 versions of an excerpt are warps of this ONE realised movement. Generate a few seconds of
     extra lead-in and lead-out so warping never runs out of frames.
   - **Movement landings:** define them from the realised motion. Default: local minima of lamp speed that are at least 25 % below the
     surrounding 0.5 s maximum, with a minimum spacing of 0.25 s. State the rule and the number found per excerpt.
   - **Factor T (tempo):**
     - The movement's period is its median landing interval.
     - "Matched": time-scale the movement so that period equals the pulse's median IOI over the excerpt.
     - "Off": scale it to 15 % off that. Per the overseer note, 3 excerpts are slower and 3 faster; assign them with the seed before
       rendering.
   - **Factor P (phase):**
     - "Pulled": a smooth monotonic time warp moves each landing to the nearest pulse event within ±150 ms. Landings without one stay where
       they are.
     - "Random": the same warp machinery, with each landing shifted to a seeded random offset drawn from the same distribution of shift sizes
       that "pulled" produced, so both versions are warped by the same amount.
     - Warps never reverse time, never exceed the arm's speed and acceleration limits (`make_arm` LIMITS), and the local time-scale stays
       within [0.7, 1.4]. If a warp would break a limit, relax it and count the relaxations.
   - **Event detector** (causal, from the ear features, stated as rules):
     - drop: a low-band flux rise after at least 1 s of reduced low-band energy;
     - dropout: low-band (kick) energy below a stated fraction of the running median for at least 0.4 s, whether or not hats or vocals
       continue. Do NOT also require onset energy to fall: the cortex-events run (`docs/CORTEX_EVENTS_REPORT.md`) showed that this misses
       Kosta's beat dropouts. Onset and end are both events;
     - strong accent: an onset-strength peak above the song's p95 with a low-band share above a stated value;
     - a minimum spacing between events.
     - Report its hits on the 10 V4 songs against Kosta's notes (`docs/BEATV_V4_RESULT.md`, `docs/PULSE_FLASH_RESULT.md`), for information
       only.
   - **Factor E (events):**
     - "Respond": at each event inside the excerpt, the movement lands on the event (warp the nearest landing within ±300 ms onto it).
       Across a dropout, it holds: the local time-scale slows to at most 0.2× of normal for the dropout's length, within the limits, and
       resumes at its end.
     - "Ignore": no event handling.
     - When P is "pulled" and E is "respond", events take priority over pulse events within ±300 ms.
   - **Cells:** 2 × 2 × 2 = 8 versions per excerpt, 48 clips. All are rendered identically with the lamp head and the excerpt's music
     (no clicks or flashes), 10 s, from the same camera.
   - **Session:** 48 items plus 4 repeats, one per T × E cell, drawn with seed 50102 and marked in the key as repeats. Blind random order
     (seed 50103).
     - One question per item: "How well does it fit the music?" with labels 1, 2, 3, 4, 5, plus the optional note.
     - Use `dialstudy_session.py`'s per-item questions. If it cannot show the labels 1-5, add the smallest option that does, with a test.
   - **Report method:**
     - main effects of T, P and E, and the T × P, T × E, P × E and three-way interactions;
     - each effect is the mean rating difference;
     - 95 % intervals by bootstrap over excerpts (songs), 2,000 resamples, seed 50104;
     - repeat consistency: the absolute rating difference of the 4 repeat pairs;
     - every per-item value saved.
2. **Build:** render all 48 clips plus the 4 repeats.
   - Save per clip:
     - the warp function;
     - the landings before and after;
     - the events;
     - the pulse events;
     - the realised speed and acceleration maxima;
     - the number of relaxations.
   - Check every clip yourself by numbers: duration exactly 10 s, audio in sync (same start sample), and no limit breached.
   - Do NOT serve the session. Build it with `dialstudy_session.py --clips <manifest> --out /secondary/hyst-data/body/factorial/session_<date>
     --seed 50103`.
   - Night log "FACTORIAL READY <commit>", then STOP. All tests must pass.
3. **Scorer (prepare now, run later):** `scripts/body/factorial_score.py SESSION_DIR` reads `answers.csv` and `key/key.json` and writes the
   report table defined in the rules note. Test it on a synthetic answers file.

Report to the overseer:
- commits;
- paths;
- the songs and excerpts;
- events per excerpt;
- the warp sizes per factor;
- relaxations;
- anything that failed or was skipped;
- every FOR USER item.
