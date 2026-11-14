# Builder prompt: work order 22, Stage 1 rerun on fresh seeds 2 and 3 under the pre-registered precondition (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo22-<fresh-name> -p MemoryMax=8G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll, do not start on battery).
  - 6 threads, `taskset -c 6-11`. Work order 23 (another builder) uses cores 12-17 at the same time.
- **Push** within 30 minutes, before the run, and after every phase. Log: `docs/NIGHT_LOG_body-s1.md` (append a WO22 section; MORNING
  SUMMARY on top).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-s1r origin/body`, then push `body-s1r`.
- **Environment:** `/secondary/hyst-env/body`.
- **Data:** `/secondary/hyst-data/body/s1r/` (new; never write into `/secondary/hyst-data/body/s1/`, which holds seeds 0/1).

## Read first

- `docs/BRAIN_SPEC.md` **§7.37** (binding: this order), then §7.34-7.36.
- `docs/STAGE1_RULES.md` (the toy's rules, amendments in section 10).
- `docs/PLANNER_BRIEF_STAGE1_RESULTS.md` (the seeds 0/1 results this rerun follows up).
- Code: `scripts/body/s1_toy.py`, `s1_chain.py`, `s1_chain.sh`, `s1_summary.py`, `test_s1_toy.py`; night log `docs/NIGHT_LOG_body-s1.md`.

## Steps

1. **Options.** `s1_chain.py` hard-codes seeds `(0, 1)` (line 24). Add `--seeds` (default `0,1`, so the old call is unchanged); keep
   `--root`. Write a new launcher `scripts/body/s1r_chain.sh` (do not edit `s1_chain.sh`): cores 6-11, `--epochs 1000 --seeds 2,3
   --root /secondary/hyst-data/body/s1r`, log `/secondary/hyst-data/body/s1r/chain.log`, resume-safe like the old one. The untrained
   baselines per seed are produced as before.
2. **Verdict script** `scripts/body/s1r_verdict.py` (new file), implementing 7.37.1 exactly:
   - collapse precondition: arm 0 or arm i has between-song JS / half-song JS <= 1.5 on **both** seeds 2 and 3; print each ratio;
   - if not met: "no verdict", stop;
   - else: arm i's reference JS = mean over seeds 2 and 3; for ii, iii, iv(0.05), iv(0.5) report mean JS / reference and D per seed;
     an arm reaches a factor when its seed mean does and D >= 0.7 on each seed; report the smallest of ii, iii, iv reaching >= 2x, and
     whether iv reaches >= 3x;
   - report alongside, per arm and seed: occupied cells and cell entropy (equal durations), machine 2AFC, MMD;
   - also print the seeds 0/1 table from `/secondary/hyst-data/body/s1/` labelled "informational only (7.37.1)".
   - A unit test on a hand-made result set (precondition met / not met; a 2x arm with D 0.69 on one seed must not count).
3. **Rules.** Add a section 11 to `docs/STAGE1_RULES.md`: "7.37 rerun: seeds 2/3, precondition and pass rule as BRAIN_SPEC 7.37.1".
   Commit and push steps 1-3 **before** the run. Run all `test_s1_toy.py` + the new test, each module in its own process.
4. **Run** all 12 runs (6 arms x seeds 2, 3) as one detached unit on mains. Expect about 1 h (seeds 0/1 took 51 min).
5. **Report:** run `s1r_verdict.py`, save its output as `/secondary/hyst-data/body/s1r/verdict.json` and `.txt`, commit the night-log
   section, push, and report to the overseer: the precondition ratios, the verdict line, the full table, wall time. Do not interpret
   beyond the rule.

## Done when

`body-s1r` pushed with the option, the verdict script and test, the rules section 11 (committed before the run), the night log; 12 runs
in `/secondary/hyst-data/body/s1r/run_*_s{2,3}/result.json`; `verdict.json`.
