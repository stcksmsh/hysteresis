# Builder prompt: work order 53, mismatch test material (7.84 item 1) and raw-joint rhythm rerun (7.84 item 3) (2026-11-18)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".

This work order has two independent parts. **Part A** is the mismatch-test material. **Part B** is the raw-joint rhythm rerun. Your
launch message says which part is yours. Do only that part, on its own branch.

**Binding:** `docs/BRAIN_SPEC.md` **§7.84** (items 1-3 and its overseer notes), then 7.81, 7.75 (Q3 excerpt rule) and `docs/A_RULES.md`.
This is report and test tooling only: do not change A or B, and train nothing. Give no verdict. One arm.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b <branch> origin/body`. The branch is `body-mismatch` for part A
  and `body-rawrhythm` for part B. Use absolute paths. Create no new worktrees.
- Cores: part A uses `taskset -c 14-16`, part B uses `taskset -c 17-19`. Cores 0-13 belong to other work.
- Units:
  - detached `hyst-wo53<a|b>-<fresh>` units, `MemoryMax=8G`, `MemorySwapMax=0`, `--working-directory=<worktree>`;
  - `taskset` on the worker process itself, `python -u`;
  - make sure the log directory exists before start; read logs 1 min after start; wait with the Monitor tool;
  - catch errors per item and log names; scan inputs first.
- Commit and push before every run.
- Commits: plain messages, with no co-author or attribution lines.
- No installs, downloads or uploads. Environment: `/secondary/hyst-env/brain`.
- Data:
  - In (read-only): `/secondary/hyst-data/body/{t0,t0_phantom,t0_motorica,grammar,grammar2,controls,beatv,pulse2,rhythm}/`,
    `/secondary/hyst-data/datasets/` and the datasets' audio;
  - Out: part A `/secondary/hyst-data/body/mismatch/`, part B `/secondary/hyst-data/body/rawrhythm/`.
- Night log `docs/NIGHT_LOG_body-mismatch.md` (A) or `docs/NIGHT_LOG_body-rawrhythm.md` (B). Keep messages short.
- When done, stop every Monitor and background task you started, and send your final report exactly ONCE.

## Read first (both parts)

- `docs/BRAIN_SPEC.md` 7.75, 7.79-7.81 and **7.84 in full**.
- `docs/A_RULES.md`.
- `docs/RHYTHM_EVENTS_RULES.md` and `docs/RHYTHM_EVENTS_REPORT.md` (WO52: movement rhythm vs beat on the retargeted lamp; its code
  in `scripts/body/`, its per-window values in `/secondary/hyst-data/body/rhythm/`).
- `docs/BEATV_RULES.md` and `docs/BEATV_REPORT.md`: librosa beats per song in `beatv/librosa/<key>.json`; raw FineDance access and the
  approximate FK in `scripts/body/beatv_raw.py` and `beatv_lib.py`.

## Part A: mismatch-test material (7.84 item 1)

Additional reading: `scripts/body/grammar_clips.py`, `scripts/body/retarget_render.sh` (lamp-head render of the realised stage),
`scripts/body/dialstudy_session.py` (sessions; per-item `questions` option from WO48), `docs/PULSE_FLASH2_RESULT.md` and the WO51 viewing
scorer `scripts/body/pulse2_score.py` (session and key pattern).

1. **Rules note `docs/MISMATCH_RULES.md`, pushed before any clip is made.** It fixes the following, with numbers.
   - **Movement:** retargeted human clips at the realised stage, lamp head, 10 s. Sources FineDance, PhantomDance and Motorica (not
     AIOZ). Version mix V1/V2: half each, drawn with a seed. Excerpts per 7.75 Q3: song RMS at or above its own median, not in the first
     or last 10 s of the song. 20 distinct movement excerpts, spread over the three datasets (default 7 / 7 / 6), at most one per song.
   - **Pairs:** each pair is the same movement shown twice, once with its own music (real) and once with a foil:
     - (a) shifted: the same song, shifted by a random 2-6 s (uniform, sign random; seed stated), still inside the song and inside the
       7.75 Q3 window where possible;
     - (b) different song: another song whose librosa tempo is within 5 % of the real one (any dataset; default the same dataset if one
       exists), its excerpt chosen by the same Q3 rule.
     - 10 pairs of each kind, kind assigned by seed.
   - **Presentation (default, FOR USER):** `dialstudy_session.py` shows one clip per item, so each pair is ONE clip: version 1 (10 s), a
     1.5 s black gap with silence, version 2 (10 s). Order (real first or second) randomised per pair and balanced (10 / 10 overall,
     5 / 5 within each kind). Audio levels matched between the two halves (state the method, default RMS match of the music).
   - **Repeats:** 5 hidden repeats (>= 20 % of 20): repeat a pair with its order reversed. Draw them by seed, at least 2 of each kind,
     marked in the key only.
   - **Questions per item:** "Which fits the music better?" with answers first / second / same, and "Confidence?" with low / medium /
     high. Use the per-item `questions` option. If the tool cannot show these, add the smallest option that does, with a test.
   - **Key:** per item the pair id, kind, real side, foil source (song, offset), dataset, version, excerpt times, repeat flag.
   - **Decision rule (copy verbatim from 7.84 item 1) and how it is computed:**
     - real-pick share = real picks / non-tie answers, over first presentations;
     - repeat-flip rate = share of the 5 repeat pairs whose choice (real / foil / same) differs between the two showings;
     - rule met when the real-pick share >= 0.70 AND the real-pick share is above the chance level plus the flip rate (state the exact
       comparison; default: the real-pick share's binomial lower 95 % bound > 0.5 + flip rate / 2, report both forms);
     - reported for all pairs, and separately for shifted and different-song pairs, with confidence split.
   - **Order checks:** after the build, verify that the real side is balanced and not predictable from item position, file name or
     size (sizes within 2 % across halves of each pair), and that no clip name or metadata reveals the real side.
2. **Build:** render all 20 pair clips plus 5 repeats. Check every clip yourself by numbers: duration 21.5 s exactly, each half's audio
   starts at the stated sample, the real half's audio matches the movement's own music sample for sample, and no limit is breached.
   Spot-check 3 clips by eye from extracted frames and audio waveforms. Build the session with
   `dialstudy_session.py --clips <manifest> --out /secondary/hyst-data/body/mismatch/session_<date> --seed 53101`. Do NOT serve it.
3. **Scorer, prepared now and run later:** `scripts/body/mismatch_score.py SESSION_DIR` reads `answers.csv`, `key/key.json` and the
   material key, and writes `mismatch_result.json` plus a short table: the rule outcome, real-pick shares with intervals (all, shifted,
   different song), the flip rate, ties, and confidence splits. Test it on synthetic answers (all real gives "met"; random gives "not met").
4. **Tests** for pair building (the tempo match within 5 %, shift range, order balance) and the scorer.

Report: commits, paths, the session folder, clip checks, order checks, the scorer's synthetic test results, and every FOR USER item.

## Part B: raw-joint rhythm rerun (7.84 item 3), report only

1. **Rules note `docs/RAWRHYTHM_RULES.md`, pushed before any result.** It reuses WO52's rhythm definitions unchanged (window 3 s,
   hop 1 s, autocorrelation peak 0.2-2.5 s, strength, ratio to librosa beat period and to pulse v2 period, bins 1/2 [0.4, 0.6],
   1 [0.8, 1.25], 2 [1.6, 2.5], other, none below strength 0.2, same chance models and seeds as WO52) and changes only the signal:
   - raw human joints before retargeting: left and right wrist, left and right foot, pelvis, head;
   - per joint the speed of its position (world frame, pelvis-relative variant reported too); also the mean of the six;
   - per dataset where raw joints exist locally. Scan `/secondary/hyst-data/datasets/` first: FineDance raw (see `beatv_raw.py`; its
     approximate FK is the default, generic bone lengths, marked as a deviation), AIOZ, Motorica, and PhantomDance if its raw source is
     local. A dataset without usable raw joints is skipped and named FOR USER;
   - the same songs and windows as WO52 wherever possible, so raw and lamp values pair per window.
2. **Run** and write `docs/RAWRHYTHM_REPORT.md`:
   - per dataset, per joint (and the mean), per beat source: bin shares against both chance models, the clustering measure and the
     circular concentration, with bootstrap intervals by song (2,000, seed 53201);
   - side by side with WO52's retargeted lamp values on the same windows: period distributions (quantiles) and bin-share excess;
   - a paired per-window comparison of raw vs lamp period ratio (share of windows in the same bin);
   - state plainly whether 7.84 item 3's condition holds as numbers ("raw joints cluster at 1/2, 1, 2" = bin-share excess over chance
     with a lower interval bound > 0, for at least one joint or the mean; "the arm does not" = the lamp's interval includes 0). No
     verdict beyond that.
   - Save all per-window and per-song values under `rawrhythm/`.
3. **Tests** on synthetic joints: a joint oscillating at the beat period gives r = 1, at twice the period gives 2, noise gives "none".

Report: commits, paths, the headline table (raw vs lamp bin-share excess per dataset), anything skipped, and every FOR USER item.
