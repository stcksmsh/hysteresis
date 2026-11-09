# Builder prompt: work order 24, toy check of ii + iii with a D >= 0.7 hinge, seeds 4 and 5, report-only (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **Report only: no pass/fail claim.**

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo24-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll).
  - **Exactly 6 threads, `taskset -c 6-11`, for every run, and state it in the log** (BRAIN_SPEC 7.38.4: results depend on thread count).
    Work order 23 (another builder) uses cores 12-17.
- **Push** within 30 minutes, before the run, and after every phase. Log: `docs/NIGHT_LOG_body-s1.md` (append a WO24 section; MORNING
  SUMMARY on top).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s1d origin/body`, then push `body-s1d`.
- **Environment:** `/secondary/hyst-env/body`. **Data:** `/secondary/hyst-data/body/s1d/` (new).

## Read first

- `docs/BRAIN_SPEC.md` **§7.38** (binding: this order), then 7.34-7.37.
- `docs/STAGE1_RULES.md` (all sections) and `docs/PLANNER_BRIEF_STAGE1_RERUN.md` (the four-seed table).
- Code: `scripts/body/s1_toy.py` (`hinges`, `loss_fn`, `train`: the existing hinges are mean violations `g` with dual multipliers
  `mu <- max(0, mu + 0.02 g)`), `s1_chain.py`, `s1r_verdict.py`, tests.

## Steps

1. **Design the D hinge and write it down FIRST.** D is measured only at evaluation, so the hinge needs a training-time estimate of D.
   Default (take it unless it cannot work; then log FOR USER and pick the nearest):
   - every epoch, compute D exactly as the held-out evaluation does, but on a fixed **held-in** subset of train songs (e.g. 16 songs, never
     the held-out 32);
   - violation `g_D = max(0, 0.7 - D_est)`;
   - its dual multiplier `mu_D <- max(0, mu_D + eta_D * g_D)` (eta_D default 0.02 x a scale you justify) scales the decoding loss:
     `(1 + mu_D) * dec`, so a D shortfall raises the weight on decoding;
   - the other three hinges are unchanged.
   Write this as section 12 of `docs/STAGE1_RULES.md` (definition, held-in songs, eta_D, cost per epoch), commit and push, **before**
   any run.
2. **Code**, additive only: a new arm `iii+D` (arm iii plus the D hinge) selectable in `s1_toy.py`/a new `s1d_*.py`; every existing arm
   bit-identical (test: one epoch of arm iii, seed 0, same loss as origin/body). Unit test for the hinge update on a hand-made D sequence.
   Run each test module in its own process.
3. **Runs, seeds 4 and 5, 1000 epochs, 6 threads:** arms ii, iii, and iii+D (6 runs, one detached unit, expect about 30 min). The ii and
   iii runs give same-seed references.
4. **Report** `/secondary/hyst-data/body/s1d/report.json` + `.txt`, per arm and seed: between-song JS, half-song JS, ratio, D (with CI),
   occupied cells + entropy (equal durations), machine 2AFC, MMD; the trajectory of D_est and mu_D over epochs (every 10th) for iii+D.
   State plainly per seed whether iii+D reaches held-out D >= 0.7, and its occupied cells against ii and iii on the same seed. No pass
   claim. Push, append the night log, and report the table to the overseer.

## Done when

`body-s1d` pushed with rules section 12 (committed before the run), code + tests, night log; 6 runs in
`/secondary/hyst-data/body/s1d/run_*_s{4,5}/result.json`; `report.json`.
