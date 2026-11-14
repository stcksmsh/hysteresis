# Builder prompt: work order 25, toy check of a D multiplier that can fall, seeds 6 and 7 (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. The decision rule is fixed in BRAIN_SPEC 7.39.2; you apply it
mechanically and report. Do not change the rule.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo25-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll).
  - **Exactly 6 threads, `taskset -c 6-11`, for every run, and state it in the log** (BRAIN_SPEC 7.38.4: results depend on thread count).
- **Push** within 30 minutes, before the run, and after every phase. Log: `docs/NIGHT_LOG_body-s1.md` (append a WO25 section; update the
  MORNING SUMMARY on top).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s1f origin/body`, then push `body-s1f`.
- **Environment:** `/secondary/hyst-env/body`. **Data:** `/secondary/hyst-data/body/s1f/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.39** (binding; point 2 is this work order), then 7.37-7.38.
- `docs/STAGE1_RULES.md` section 12 (the WO24 D hinge) and `docs/PLANNER_BRIEF_WO23_WO24_RESULTS.md` (WO24 results, seeds 4/5).
- Code: `scripts/body/s1_toy.py` (`d_est`, `d_hinge_update`, arm `iii+D`, `loss_fn` with `dw`), `s1d_chain.py`, `s1d_chain.sh`,
  `s1d_report.py`, `test_s1d.py`.

## Steps

1. **Write section 13 of `docs/STAGE1_RULES.md` FIRST** (commit and push before any run):
   - new arm `iii+Df` = arm `iii+D` with only the multiplier update changed to
     `mu_D <- max(0, mu_D + eta_D * (0.7 - D_est))`, eta_D = 0.16, mu_D = 0 at start; everything else as section 12 (same held-in 16
     songs, same D_est, same `(1 + mu_D) * dec` scaling);
   - runs: arms `iii+D` (rising, unchanged) and `iii+Df` (falling), seeds 6 and 7, 1000 epochs, 6 threads, cores 6-11: 4 runs, one
     detached unit, resume-safe;
   - the 7.39.2 rule verbatim: the falling multiplier is used in Stage 3 if held-out D >= 0.7 on both seeds AND MMD >= the rising
     version's mean MMD on seeds 6 and 7; otherwise the rising version;
   - operationalisation (overseer default): "MMD" of the falling version = its mean over seeds 6 and 7, compared with the rising
     version's mean over seeds 6 and 7. Also print the per-seed comparison; if the per-seed reading and the mean reading disagree, say so
     plainly in the report (the planner rules then).
2. **Code**, additive only: arm `iii+Df` in `s1_toy.py` (a sign/clip change in a new update function or a flag on `d_hinge_update`,
   default = current behaviour); every existing arm bit-identical (test: one epoch of arm `iii+D` seed 4 gives the same loss and mu_D as
   origin/body). Unit test of the falling update on a hand-made D_est sequence (rises when D_est < 0.7, falls when > 0.7, never below 0).
   Chain/report scripts: new files (`s1f_chain.py`/`.sh`, `s1f_report.py`) or copies; reuse `s1d_report.py` metrics unchanged.
   Run each test module in its own process.
3. **Run** the 4 runs (expect about 25-35 min). State the thread count and cores in the log.
4. **Report** `/secondary/hyst-data/body/s1f/report.json` + `.txt`, per arm and seed: held-out D (with CI), MMD, between-song JS,
   half-song JS, ratio, occupied cells + entropy (equal durations), machine 2AFC; D_est and mu_D every 10th epoch for both arms. Then the
   rule's outcome: "falling" or "rising", with the numbers it used. Push, append the night log, and report the table and outcome to the
   overseer.

## Done when

`body-s1f` pushed with rules section 13 (committed before the run), code + tests, night log; 4 runs in
`/secondary/hyst-data/body/s1f/run_*_s{6,7}/result.json`; `report.json` with the rule outcome.
