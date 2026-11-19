# Builder prompt: work order 55, re-timing after the sync audit (7.87): part A re-timed lamp analyses + token effect, part B arm-only re-timed mismatch round 2 material (2026-11-19)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".
Your launch message says which part is yours: **A** or **B**. Do only that part.

**Binding:** `docs/BRAIN_SPEC.md` **7.84-7.87** (read 7.86 and 7.87 in full). Background: `docs/SYNCAUDIT_REPORT_A.md`,
`docs/NIGHT_LOG_body-syncaudit-b.md`, `docs/PLANNER_BRIEF_SYNCAUDIT.md`. The realised arm (`controls/q50` and everything cut from it) trails its
music by a constant-ish lag; ruling: re-time at read time by **L(V1) = 0.35 s, L(V2) = 0.28 s** (one constant per variant). Residual
+-50 ms is recorded, not removed. Change no pipeline code that produces `controls/q50`; do not re-simulate. Do not touch the frozen
`src/` or `tools/`. One arm. Give no verdict beyond numbers and the stated rules.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b <branch> origin/body`; branch `body-retime-a` (part A) or
  `body-retime-b` (part B). Use absolute paths. Create no new worktrees.
- Cores: part A `taskset -c 14-19`, part B `taskset -c 6-13`. Units `hyst-wo55<a|b>-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`,
  `--working-directory=<worktree>`, `taskset` on the worker itself, `python -u`; make the log directory first; read logs 1 min after
  start; wait with the Monitor tool; catch errors per item. The machine may be loaded by other work: keep memory small.
- Commit and push before every run. Commits: plain messages, no co-author or attribution lines.
- No installs, downloads or uploads. Environment `/secondary/hyst-env/brain`. Data in `/secondary/hyst-data/`; out
  `/secondary/hyst-data/body/retime/<a|b>/`. Night log `docs/NIGHT_LOG_body-retime-<a|b>.md`.
- When done stop every Monitor and background task and send ONE final report.

## The shared helper (part A writes it first and pushes within 30 minutes; part B waits for it, polling `git fetch origin` with the Monitor every 5 minutes)

`scripts/body/retime.py` on branch `body-retime-a`: constants `L = {"V1": 0.35, "V2": 0.28}` and a function that shifts a lamp-derived array
**earlier** by L: `retime(x, rate_hz, variant)` returns `x[round(L * rate_hz):]` (the last L seconds are dropped, never padded) together with
the new valid length; plus `retime_rows_start(window_offset_s, variant)` = `window_offset_s + L` for cutting a joint CSV. Document the sign
(positive L = movement is later than its music, so the array is read L later). Test: a pulse at t in a 50 Hz array lands at t - L after the
retime. Part B copies the file's logic only after it appears on `origin/body-retime-a`; if it does not appear within 45 minutes, part B
writes its own two-line equivalent and logs FOR USER.

## Part A (branch `body-retime-a`)

1. **Rules note `docs/RETIME_RULES.md`, pushed before any result.** It states: L values and the sign; which arrays are shifted (every
   array cut from `controls/q50`: the lamp speed, lamp position, token controls of A) and which are not (raw-joint arrays, music
   features, pulse, cortex); the window handling (the last L seconds of a 20 s window are dropped); and that period-ratio results are
   unchanged by a constant shift (state it, and check it in step 2c).
2. **Re-timed analyses (report only), each as the original code path with the lamp shifted by L**, written next to the original results
   (never overwrite them), then a table original vs re-timed:
   - (a) **WO47 lamp BAS and V3** (`scripts/body/beatv_*.py`, `docs/BEATV_RULES.md`, `docs/BEATV_REPORT.md`): BAS of the lamp speed minima
     against librosa beats, with the same sigma, chance and bootstrap as WO47 (seed 47101), for V1 and V2, per dataset; V3 offsets
     (what V3 was: read the report) likewise.
   - (b) **WO52 event locks** (`scripts/body/rhythm_events.py`, `docs/RHYTHM_EVENTS_RULES.md`, `docs/RHYTHM_EVENTS_REPORT.md`): hold,
     change and burst responses against the music events (onset, dropout, novelty, cortex surprisal) at lags -1..+1 s: peak excess and
     its lag, original vs re-timed, same circular shifts (seed 52102) and bootstrap by song.
   - (c) **WO53 B lamp column** (`scripts/body/rawrhythm.py`): the lamp's rhythm bin shares and clustering measure, re-timed (expected
     identical; report any difference) and the raw vs lamp same-bin share per window.
   - Also report the single headline per analysis: whether the re-timed value differs from the original by more than the original's 95 %
     interval, as a number. No verdict.
3. **Token-level effect (7.87 Q4, report only).** A's controls (`scripts/body/grammar_data.py`, `docs/A_RULES.md`): state the token length
   and what L is in tokens (L / token length). Then measure how the alignment of controls to music changes: for each music event type
   used in WO52 and for the ear energy features, the event-locked control rate (vigour, height, sharpness, pause onset) at lag 0 on the
   original alignment and on the re-timed alignment; and the correlation of each control with the music's low-band energy and onset
   strength at lags -1..+1 s, original vs re-timed (bootstrap by song). Report whether the peak lag of control vs music moves by L.
   Do not rebuild A's data and do not train.
4. **Tests** for `retime.py` and the shifted-analysis wrappers on synthetic data. **Report:** commits, paths, the original vs re-timed
   tables (headline), the token numbers, anything skipped, every FOR USER item.

## Part B (branch `body-retime-b`): arm-only, re-timed mismatch round 2 material

Read first: `docs/MISMATCH_RULES.md`, `docs/PLANNER_BRIEF_MISMATCH.md`, `scripts/body/mismatch_build.py`, `mismatch_order.py`,
`mismatch_score.py`, `dialstudy_session.py`, `retarget_render.sh`, `retarget_page.py`, `docs/SYNCAUDIT_REPORT_A.md` (clip pipeline and the
hint/trail drawing code at `crates/hyst-previz/src/ensemble.html` lines about 258-290). Round 1 session
`/secondary/hyst-data/body/mismatch/session_2026-11-19` stays as it is; this is round 2 (the second and last round of this check).

1. **Rules note `docs/MISMATCH2_RULES.md`, pushed before any clip is made.** It repeats `MISMATCH_RULES.md` (same decision rule, verbatim
   from 7.84 item 1; same pair counts: 20 pairs + 5 repeats; same presentation: one clip per pair, 10 s + 1.5 s black + 10 s, same RMS
   match, same order balance and checks, same key schema so `mismatch_score.py` works unchanged) and changes only:
   - **Re-timed movement:** the joint CSV of every clip is cut from `window_offset + L(variant)` instead of `window_offset` (L = 0.35 s V1,
     0.28 s V2). Excerpts must still lie inside the kept 20 s window including the extra L; where `window_offset + 10 + L` exceeds the
     window's 20 s, redraw the offset (state it) or, if the neighbouring window is contiguous, read the continuation; do not pad. The
     music excerpt is unchanged (same start as the movement's *unshifted* excerpt, so the movement now precedes its old position by L).
     Log the resulting sync in the key (`retime_L_s`).
   - **Arm only (7.87):** remove the hand-path look-ahead hint and the trail from the page at render time, by patching the page in the
     render step (`retarget_page.py` style; do NOT edit `crates/hyst-previz/src/ensemble.html` or anything under `crates/`). Verify by
     rendering one frame and checking by pixels/by the page's draw calls that neither is drawn; keep a record of the patch in the report.
   - **Shifted pairs:** |offset| uniform in [4, 6] s (not 2-6). Foil inside the song and the Q3 window as in round 1.
   - **Different-song foils from a different dataset** when a song within 5 % tempo exists there (the preferred rule); same dataset only
     when none exists (flag in the key and the report).
   - **Fresh excerpts:** no song and no excerpt window used in round 1 (`mismatch/material_key.json`) may be reused as movement; check
     and report the overlap (must be 0 songs, or state why not possible per dataset and use the least overlap).
   - **Instruction page:** the session's opening text explains, in plain words: each clip shows the SAME movement twice; the music differs;
     in some pairs the music is the same song at a different moment (so both halves can sound alike), in others a different song; "same" is
     a valid answer; answer after the first pass. Read `dialstudy_session.py` for how an intro/instruction text is set; add the smallest
     option if it cannot show one, with a test. Do not state which side is real or how many of each kind.
   - **Repeats:** 5, as round 1 (at least 2 of each kind, order reversed).
2. **Build** as round 1: pair building, render, checks (duration 21.5 s exactly, silence/black gap, real half sample-exact, RMS ratio,
   frame-identical halves, order checks, no metadata leaks, sizes within 2 %), 3 clips spot-checked by eye from frames and waveforms. Add a
   check that proves the re-timing: from the key and the clip's joint CSV, the first row equals the q50 row at `window_offset + L`
   (max error 1e-3 deg), and the hint and trail are absent. Build the session with
   `dialstudy_session.py --clips <manifest> --out /secondary/hyst-data/body/mismatch2/session_<date> --seed 53201`. **Do NOT serve it.**
3. **Scorer:** reuse `scripts/body/mismatch_score.py` unchanged against the new session; test it on synthetic answers for this session's key
   (all real gives "met", random gives "not met"). Do not open any answers file.
4. **Report:** commits, paths, session folder, clip and order checks, the retime check, hint/trail removal evidence, overlap with round 1,
   foil-dataset choices, scorer synthetic results, every FOR USER item.
