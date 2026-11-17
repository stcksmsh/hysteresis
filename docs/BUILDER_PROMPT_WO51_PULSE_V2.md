# Builder prompt: work order 51, pulse v2 (harmonic readout, stability, confidence) + numeric check + 40-item viewing material (7.80 Q1) (2026-11-17)

You are a builder for Hysteresis. Work alone and unattended. Where a choice is open, take the named default and log "FOR USER".

**Binding:** `docs/BRAIN_SPEC.md` **§7.80** (Q1 and its overseer notes), then 7.79, 7.78 2.1, and `docs/PULSE_RULES.md`. The pulse is the
TEMPO source only. Do not build a motor clock or an event detector. Give no verdict. One arm. Another builder (WO50) uses cores 6-13, so stay
on cores 14-19.

**Header rules:**
- Setup: in your current worktree run `git fetch origin && git checkout -b body-pulse2 origin/body`. Use absolute paths. Create no new
  worktrees.
- Units:
  - detached `hyst-wo51-<fresh>` units, `MemoryMax=8G`, `MemorySwapMax=0`, `--working-directory=<worktree>`;
  - `taskset -c 14-19` on the worker, `python -u`;
  - read logs 1 min after start; wait with the Monitor tool; catch errors per item and log names.
- Runs: run on battery. Commit and push before every run.
- Commits: plain messages, with no co-author or attribution lines.
- No installs, downloads or uploads. Environment: `/secondary/hyst-env/brain`.
- Data:
  - In (read-only): `/secondary/hyst-data/body/{pulse,t0,t0_phantom,t0_motorica,metric,beatv,cortexev}/` and the datasets' audio;
  - Out: `/secondary/hyst-data/body/pulse2/`. Leave v1's `pulse/` untouched.
- Night log `docs/NIGHT_LOG_body-pulse2.md`.

## Read first

- `docs/BRAIN_SPEC.md` 7.78-7.80.
- `docs/PULSE_RULES.md`, `docs/PULSE_REPORT.md`, `docs/PULSE_TABLES.md`.
- `docs/PULSE_FLASH_RESULT.md`, `docs/PULSE_FLASH2_RESULT.md`: Kosta's answers and notes, the target to beat.
- `docs/PULSE_FLASH2_MATERIAL.md`, `docs/CORTEX_EVENTS_REPORT.md`, which has novelty/section detectors you may reuse.
- Code:
  - `scripts/body/pulse_lib.py`, `pulse_run.py`, `pulse_flash.py`, `pulse_flash2.py`, `test_pulse.py`;
  - `scripts/brain/grfnn.py`;
  - `scripts/body/dialstudy_session.py`, which takes per-item `questions`;
  - `scripts/body/cortexev.py`.
- The published model: Velasco & Large 2011 (ISMIR, PS2-3) Eq. 3, which the overseer checked. Large's metrical readout = harmonic
  support across related frequencies. Cite only what you can state exactly from local copies or memory; mark anything reconstructed.

## The work

1. **Rules note `docs/PULSE2_RULES.md`, pushed before any song result.** Keep v1's oscillator bank, drive and integrator unless a change is
   needed for the items below; state each change. Fix:
   - **(b) Harmonic-support readout:**
     - each candidate f is scored by its own amplitude plus weighted amplitudes at 2f and f/2 (state the weights; default 0.5 each). Taken
       from neighbouring oscillators by interpolation on the log grid; outside the bank, 0;
     - times the existing prior and the arm cap.
     - State how this favours binary levels over 3:2.
   - **(s) Stability:** a level change needs sustained evidence: hold H s and margin M, longer and higher than v1's 2 s / 20 %. Defaults
     4 s and 35 %.
     - Preferably at a large novelty or phrase boundary: a causal novelty detector (state it; you may reuse `cortexev.py`'s ear change
       detector made causal) lowers H to 1.5 s within ±1 s of a boundary.
     - Local following (±2 oscillators) stays free.
   - **(c) Confidence:**
     - confidence in [0, 1] = the selected candidate's harmonic-support score relative to the bank (state the normalisation; default: score
       over the bank's 95th-percentile score over the last 8 s, clipped);
     - the pulse always runs; phase keeps integrating through low confidence;
     - output per song at 100 Hz: period, phase, confidence, selected frequency;
     - pulse events (phase zero crossings), each carrying its confidence.
   - **Numeric check:** everything v1's check had, plus:
     - level switches per minute (v1 vs v2);
     - median confidence in silence / beatless / dropout passages vs beat passages, with the passage rules stated (reuse v1's quiet and
       dropout definitions, add "beatless" from the low-band periodicity strength);
     - for the 20 viewing excerpts, the v2/librosa tempo ratio next to v1's;
     - all songs; songs under 12 s excluded from summaries (7.79 Q4).
   - **Tests** (synthetic):
     - v1's tests still pass where they apply;
     - a 3:2 trap (strong 3-against-2 hats over a 2 Hz kick) picks the binary level;
     - a short 1 s fill does not switch the level;
     - silence lowers confidence below a stated value, and the phase resumes within ±50 ms of the true beat after 4 s of silence.
2. **Run** on all songs, causal, whole songs. Write `docs/PULSE2_REPORT.md` with v1 vs v2 tables, and save every per-song value. Night log
   "PULSE2 READY <commit>".
3. **Viewing material, prepare only, do not serve:**
   - The same 20 excerpts as the two flash checks, read from `pulse/flash/key.json` and `pulse/flash2/key.json` (same songs, same starts).
   - Each is shown with pulse v2 events and with librosa beats: 40 items, the same rendering as before.
   - Pulse v2 flash brightness = that event's confidence (librosa flashes at full brightness). State the brightness map, and keep a minimum
     visible brightness of 0.15.
   - Two questions per item: "Is it the right speed?" (right / too fast / too slow) and "Is it steady?" (yes / switches).
   - Seeded random order (seed 51101); the key records the source.
   - Folder `pulse2/view/` with manifest and key. Build the session with `dialstudy_session.py --clips <manifest> --out
     /secondary/hyst-data/body/pulse2/view/session_<date> --seed 51102`. Do NOT serve it.
   - Night log "PULSE2 VIEW READY".
4. **Scorer:** `scripts/body/pulse2_score.py SESSION_DIR` applies the 7.80 DECISION RULE as the overseer note in 7.80 states it:
   - counts of "right" and of "yes" (steady) per source over the 20 excerpts;
   - pulse v2 must be ≥ librosa on both;
   - a per-item table next to Kosta's earlier answers for the same excerpt.

   Test it on a synthetic answers file. Then STOP; all tests must pass.

Report to the overseer:
- commits;
- paths;
- the parameter values;
- the v1 vs v2 headline numbers (switches per minute, the 3:2 share, confidence by passage type, the 20 excerpt ratios);
- anything that failed or was skipped;
- every FOR USER item.
