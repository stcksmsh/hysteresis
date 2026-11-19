# Builder prompt: work order 33, jitter diagnosis on the retarget look-test clips, report only (2026-11-13)

You are a builder for Hysteresis. Work alone and unattended. Where this prompt leaves a choice open, take the named default and log "FOR USER"
instead of waiting. If you start fresh, everything is named below.

**Binding:** `docs/BRAIN_SPEC.md` **§7.53** (Kosta's ruling on `docs/PLANNER_BRIEF_RETARGET_RESULTS.md`, with the overseer notes 7.53.8), then
§7.52 and §7.51. **Report only: adopt nothing, change no shown clip, no verdict.**

**Header rules:**
- In your current worktree: `git fetch origin && git checkout -b body-jitter origin/body`. Absolute paths; no new worktrees.
- Cores 6-11 (`taskset -c 6-11`). Any job longer than 2 minutes runs as a detached, memory-capped unit:
  `systemd-run --user --unit=hyst-wo33-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 ...`.
- Run on battery; never wait for mains.
- Commit and push the code before every run; push at least every 30 minutes.
- Plain commit messages with **no co-author or attribution lines**.
- No training, no downloads, nothing uploaded. Frozen `src/` and `tools/` untouched; round-1 files (`motornet.py`, `dialstudy.py`,
  `arm_sim.py`) unchanged.

## Read first

- `docs/BRAIN_SPEC.md` §7.51-7.53.
- `docs/RETARGET_RULES.md` (notes (h)-(l)) and `docs/RETARGET_REPORT.md`, especially the overseer table at its end.
- The code: `scripts/body/retarget.py` (`to_commands`, `to_100hz` = cubic spline), `retarget_run.py` (`sim_variant`, gates),
  `retarget_limiter.py` (the fixed limiter), `make_arm_v2p.py` (`guard`), `motornet.py` (`spinal`).
- The data: `/secondary/hyst-data/body/retarget_look/` (`manifest.json`, `numbers.json`, `work/*.csv`).

## The work

1. **Script `scripts/body/jitter_diag.py`, with a unit test** (`test_jitter_diag.py`). On a synthetic signal with a known jerk and known
   sign-change rate, the measures must return the known values.
2. **The 20 shown clips** (C01-C10 x V1, V2; the same windows as in `manifest.json`), rebuilt from FineDance exactly as `retarget_run.py`
   builds them. First confirm that the stage-4 rows of the baseline reproduce `work/<id>.csv` (max abs difference reported).
3. **Stages:**
   1. retargeted command at 30 fps;
   2. after the 30 -> 100 Hz cubic spline (and the guard; report the guard separately if it changes anything);
   3. limiter output;
   4. realised (servo/body).
4. **Per stage and per joint:**
   - acceleration sign changes per second;
   - jerk RMS (deg/s^3);
   - share of joint-speed power above 3 Hz and above 6 Hz (mean removed, over 0.2 Hz).

   Compute each at the stage's own rate, and also for stages 2-4 sampled at the 30 fps instants (7.53.8).
5. **Hypotheses, each separately (7.53.6 and 7.53.8):**
   - **H1:** the round-1 `motornet.spinal` (3 Hz, zeta 0.7, unchanged) inserted before the fixed limiter. Re-run stages 3-4.
   - **H2:** on the baseline, the share of frames where |limiter output acceleration| >= 0.98 x the limit (100 Hz frames, and the gate's
     50 Hz measure), and the sign flips per second of the limiter output acceleration, per joint.
   - **H3:** stage 2 vs stage 1 (what the cubic spline adds), plus a control with linear interpolation instead of the cubic spline, run
     through stages 2-4.
   - **H1 + H3 combined:** H1 with the cubic spline as used.

   For every variant run, also report the 7.52 gate pass/fail at 1.25. It is not used to select.
6. **Control:** the 2 round-1 S03 reference clips (`work/C01_R1S03.csv`, `C09_R1S03.csv`), measured at stage 4 as they are.
7. **Output:**
   - `docs/JITTER_DIAGNOSIS.md` (tables: per stage x joint, medians over the 20 clips plus per-clip in an appendix; one table per hypothesis
     plus the combination; no verdict);
   - `/secondary/hyst-data/body/retarget_look/jitter/numbers.json`;
   - for each of C04_V2 and C10_V1 under baseline, H1 and H3-linear, one plot of the shoulder and wrist-bend angle over 4 s (PNG in
     `jitter/`, not in git).

   Render no video.
8. **Done when:** "JITTER READY <commit>" in your night log with a short MORNING SUMMARY, pushed. Then **STOP**. The overseer checks, and
   Kosta rules on a fix.

**Out of scope (stop and ask; log FOR USER):** any fix adopted or tuned (cutoffs, filters, new interpolants, limiter changes); re-rendering
clips; training; music conditioning; gain modulation; hardware; brain monitor; uploads.
