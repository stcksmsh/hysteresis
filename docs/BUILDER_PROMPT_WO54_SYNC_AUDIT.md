# Builder prompt: work order 54, end-to-end sync audit of movement vs music (7.86 Q2, report only) (2026-11-19)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".

**Why:** in the mismatch test Kosta picked the music shifted by 2-6 s over the real music in 8 of 8 non-tie shifted pairs. The planner
(`docs/BRAIN_SPEC.md` **7.86**, read it in full) judged this a systematic effect and ruled that all coupling conclusions of 7.74-7.85
(beat phase at chance, V3 offsets spread +-1 s, weak events/structure) are on hold until we know whether the pipeline puts movement and
music out of sync. This is that audit. **Report only: change no pipeline code and fix nothing.** If you find an offset, measure it and
report it; the overseer orders any fix and the reruns. Do not touch the frozen `src/` or `tools/`. One arm. Give no verdict beyond the
numbers and the 7.86 outcome rule (a stage offset above 50 ms, or a loader that misaligns motion and audio, is a "finding").

**Roles (your launch message says which is yours):**
- **Agent 1:** A1 (synthetic probe) and A4 (time-origin code review). Cores `taskset -c 6-13`. Branch `body-syncaudit-a`.
- **Agent 2:** A2 (AIST++ known-aligned reference) and A3 (per-song lag diagnostic). Cores `taskset -c 14-19`. Branch `body-syncaudit-b`.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b <branch> origin/body`. Use absolute paths. Create no new worktrees.
- Units: detached `hyst-wo54<a|b>-<fresh>`, `MemoryMax=10G`, `MemorySwapMax=0`, `--working-directory=<worktree>`, `taskset` on the worker
  itself, `python -u`; make the log directory first; read logs 1 min after start; wait with the Monitor tool; catch errors per item.
- Commit and push before every run. Commits: plain messages, no co-author or attribution lines.
- No installs, downloads or uploads. Environment `/secondary/hyst-env/brain`. Data in `/secondary/hyst-data/` (read-only except your out folder);
  out `/secondary/hyst-data/body/syncaudit/<a|b>/`. Night log `docs/NIGHT_LOG_body-syncaudit-<a|b>.md`.
- Another load may be on the machine; keep memory small. When done stop every Monitor and background task and send ONE final report.

## Read first (both)

- `docs/BRAIN_SPEC.md` 7.84-7.86, and `docs/PLANNER_BRIEF_MISMATCH.md` (the result; shifted foils picked 8/8).
- `docs/MISMATCH_RULES.md` and `scripts/body/mismatch_build.py` (how the clips were cut and muxed).
- `docs/RETARGET_RULES.md`, `scripts/body/retarget*.py`, `retarget_render.sh`, `scripts/body/grammar_data.py`, `controls_*.py`,
  `beatv_*.py` (WO47 measures), `rhythm_events.py` (WO52), `rawrhythm.py` (WO53 B), `aist_load.py`, `aist_bas.py`, `aist_music.py`.
- `docs/BEATV_REPORT.md`, `docs/RHYTHM_EVENTS_REPORT.md`, `docs/RAWRHYTHM_REPORT.md`.
- The stages the human clips go through, in order: dataset loading -> retarget (V1/V2) -> low-pass -> resample/spline (30 Hz to 50 Hz)
  -> warm-up -> command limiter -> servo (and any spinal layer when used) -> v2p body -> `--joint-csv` export -> `ensemble_preview` render
  -> `record_ensemble.cjs` -> ffmpeg audio mux -> `dialstudy` clip. Trace the real order from the code; correct this list in your report.

## Rules note first (both, short)

Each agent writes and pushes `docs/SYNCAUDIT_RULES_<A|B>.md` before any result: the exact definitions below, with the default numbers.
- **Offset sign:** positive = movement LATER than its music (movement event time minus music event time). State it once and use it everywhere.
- **Finding threshold:** |offset| > 50 ms at any stage, any dataset loader whose motion and audio starts differ, or any inconsistency
  between two code paths that should agree.
- **Resolution:** timing is measured on the arrays at 100 Hz or finer (sub-frame by parabolic interpolation of the cross-correlation
  peak or by the peak time of the impulse); the final video is measured at frame resolution (30 fps) and, for audio, at sample resolution.

## A1 (agent 1): synthetic probe

1. Build synthetic input: a 30 s mono audio file (44.1 kHz) of clicks at known times (a fixed list, e.g. every 0.5 s plus a few irregular
   ones, first click not at t = 0, 3 s onwards), and synthetic human motion in the **FineDance input format** (read `grammar_data.py` /
   the FineDance loader for the real file layout) at the dataset fps, with a sharp joint impulse (a fast, large-amplitude rotation of
   the wrists/feet/pelvis, one joint family at a time and a mixed variant) at the same times. Do the same for the other dataset
   formats the mismatch clips used (PhantomDance, Motorica); AIOZ only if cheap. Put the synthetic songs through the same entry point
   as a real song (the audio file in the same container/codec/sample rate the dataset uses, including mp3/wav as real).
2. Run it through the full pipeline **exactly as used for the mismatch clips** (same code, same defaults, same 20 s window selection and
   10 s excerpt cutting, same render and mux). Do not use a shortcut that skips a stage.
3. Measure, at every stage's output, the offset between the clicks and the motion impulses, and report a table: stage, array or file, rate,
   click-vs-impulse offset in ms (mean, spread, per impulse list in the data folder). Stages to include at least: loaded motion and
   loaded audio; after retarget; after low-pass; after resample/spline; after warm-up trimming; after limiter and servo; the joint
   CSV; the lamp/hand arrays the measures (WO47, WO52, WO53) read; the rendered frames (impulse frame index vs click time); the muxed
   audio track of the final clip (sample position of the click vs the video's frame of the impulse, 30 fps, by decoding the mp4, not by
   trusting container metadata); and the shifted-foil construction (confirm the foil's music offset is exactly the stated shift).
4. State for each stage whether the delay is constant (a latency) or varies, and its sign.

## A4 (agent 1): code review of every time origin

List, with file and line, **every place a time origin or time offset is set or assumed** from audio file to final clip. At least:
dataset loaders (motion start vs audio start, trimming, fps, frame vs sample conventions, mp3/AAC encoder delay and decoder
priming such as ffmpeg's start time, container start offsets), the beat grids of `beatv/librosa` (librosa frame to time convention
and hop), the 10 s warm-up, window extraction (`window_offset_s`, kept 20 s windows, q50 sampling), clip excerpt start times in
`mismatch_build.py`, the `record_ensemble.cjs` capture clock, and the ffmpeg mux. For each entry state: what offset it handles
(or does not), whether A1 measured it, and any doubt. Mark each "checked by A1", "checked by A2", or "reading only".

## A2 (agent 2): known-aligned reference (AIST++)

AIST++ sequences have motion and music aligned by construction (the dataset provides keypoints and music with known sync; the
registration is in `aist_load.py`, `aist_music.py`, WO47's BAS work). Take the same sequence set WO47 used (or a stated subset of at
least 60 sequences across genres, drawn by seed 54201):
1. On the **raw keypoints** (before any of our stages): beat alignment (BAS at the sigma used in WO47, and at a finer 0.05 s) and the
   onset-motion cross-correlation: motion speed (or the joints' kinematic-minima) against the music's onset envelope, the lag of the
   peak and the lag distribution over sequences. Chance: music from another sequence of the same genre.
2. Push the same sequences through **each stage** of our pipeline that can be run on AIST++ (retarget, low-pass, resample/spline,
   limiter, servo, v2p; use the same code as the mismatch clips where the stage accepts AIST++ input; if a stage cannot be run on
   AIST++ because of a format limit, say so and use the closest available stage output) and repeat the two measures after every
   stage. Report lag and BAS per stage, per sequence, with a bootstrap by sequence (2,000, seed 54202).
3. Report which stage, if any, moves the peak lag by more than 20 ms relative to the raw keypoints.

## A3 (agent 2): per-song lag diagnostic

On the existing material, for every dataset (FineDance, AIOZ, PhantomDance, Motorica):
1. Signals: the **lamp speed** (the arrays WO52 read, `controls/q50/...` and the rhythm tables), the **raw joint speeds** of WO53 part B
   (wrists, ankles, pelvis, head, and their mean), and for each song the music's **onset envelope** (ear column 40 as used in WO52, or
   librosa onset strength: use both, state which is main, default ear col 40) and **energy envelope** (low-passed RMS).
2. Per song, the normalised cross-correlation of motion signal vs music envelope over lags -3 s to +3 s (100 ms resolution or finer), after
   removing a 2 s moving mean from both; the peak lag within +-1.5 s and its height. Chance: the same motion against music of another
   song of similar tempo (20 draws per song, seed 54203) and against the song's music circularly shifted by random 2-6 s.
3. Report per dataset and signal: the distribution of peak lags (quantiles, histogram table), the share of songs whose peak is within +-100 ms
   of 0, the median peak height against chance, the lag of the pooled (average) cross-correlation, with bootstrap by song (2,000, seed 54204).
   Report V1 and V2 lamp separately.
4. Also report the lag **of the shifted foil comparison** in a form that lets us read the mismatch result: for the 13 shifted clips of the
   mismatch session (`/secondary/hyst-data/body/mismatch/material_key.json`), the cross-correlation at the stated foil offset vs at zero for the movement's own lamp
   speed against each half's music envelope (use the source songs and the real/foil start times from the key). No scoring of Kosta's answers
   (do not open his `answers.csv`).

## Tests

Add small tests on synthetic signals for your measuring code (a known lag is recovered within the stated resolution; the sign
convention is as defined).

## Report (both)

ONE final report: commits; paths; the headline tables (A1: offset per stage; A2: lag and BAS per stage; A3: lag distributions per
dataset and signal); every finding as a numbered list `FINDING n: stage / file / offset in ms / sign / evidence`; "no finding" stated for
the stages you cleared; the corrected stage list (A1/A4); anything you could not measure and why; every FOR USER item.
