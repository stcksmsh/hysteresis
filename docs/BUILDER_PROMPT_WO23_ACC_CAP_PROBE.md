# Builder prompt: work order 23, report-only probe of the generator's acceleration and speed caps on the M3f toy (2026-11-09)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **Report only: no claim, no change to any default.**

## Where and how

- **Repo:** `/secondary/Programming/Github/Hysteresis`. The remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub
  server error.
- **Commit messages:** plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- **Frozen and forbidden:** `src/` and `tools/` are read-only. Never drive hardware. Install nothing. Data stays outside git, under
  `/secondary/hyst-data/`.
- **Long runs** (over 10 min): detached and memory-capped with
  `systemd-run --user --unit=hyst-wo23-<fresh-name> -p MemoryMax=12G -p MemorySwapMax=0 --working-directory=<abs dir> <abs script>`,
  `python -u`, mains power only (wait for `/sys/class/power_supply/ADP1/online` = 1 with an armed poll).
  - 6 threads, `taskset -c 12-17`. Work order 22 (another builder) uses cores 6-11 at the same time.
- **Push** within 30 minutes, before the runs, and after every phase. Log: `docs/NIGHT_LOG_body-acc.md` (MORNING SUMMARY on top).
- **Worktree: none new.** Stay in the worktree your session is pinned to, with absolute paths:
  `git fetch origin && git checkout -b body-acc origin/body`, then push `body-acc`.
- **Environment:** `/secondary/hyst-env/body`.
- **Data:** `/secondary/hyst-data/body/acc/`.

## Read first

- `docs/BRAIN_SPEC.md` **§7.37 point 3** (binding: this order), then §7.27-7.32 (the M3f toy's terms) and §7.36.2 (occupied cells).
- `docs/PLANNER_BRIEF_STAGE1_RESULTS.md`, section "the 0.741 m/s ceiling" (the WO21 finding this probe follows up).
- Code: `scripts/body/cpg.py` (ACC_SHARE line 21; the 0.8 speed share in line 65), `scripts/body/m3d_jax.py` line 63 (the same caps in
  the differentiable rollout), `scripts/body/make_arm.py` line 22 (LIMITS), `run_m3f.py`, `m3f.py`, `m3f_gate17.py`, `m3f_report.py`
  (hand metrics), `m3f_endstop.py`, `s0_ceiling.py` (WO21's cap-share measure), `s0_measure.py` (5 cm grid JS, occupied cells, entropy).
- `docs/NIGHT_LOG_body-m3f.md` (WO17 section) and `/secondary/hyst-data/body/m3f/rerun4/` (the WO17 runs = the setting in force).

## The servo model's limits (state them in the report)

`make_arm.py` LIMITS, speed deg/s / acceleration deg/s^2: base 120 / 600, shoulder 90 / 300, elbow 150 / 1000, wrist bend 200 / 2000,
roll 250 / 3000. Note `cpg.py:21`: ACC_SHARE 0.7 once let the shoulder reach 1.2x its acceleration limit at 50 Hz.

## Steps

1. **Options, additive, default = today.** Add `--acc-share` (default 0.25) and `--speed-share` (default 0.8) to `run_m3f.py`, reaching
   both `cpg.py` and `m3d_jax.py` (a module constant `SPEED_SHARE = 0.8` in `cpg.py` replacing the two literals is fine). Test: with
   defaults, a rollout and the first epoch's loss are **bit-identical** to the current code (compare against origin/body). Push.
2. **Settings, seed 0, the exact WO17 options** (`--body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane --w-floor 1.0
   --smooth-u`, jerk 0.03, switch 0.01, lam 0.03, 40 epochs, held eval; copy the command from `rerun4/chain.log`'s cfg line and the
   chain script):
   - B: baseline = `/secondary/hyst-data/body/m3f/rerun4/seed0` (reuse; do not retrain; first confirm its cfg equals the defaults);
   - A1: `--acc-share 0.4`;
   - S1: `--speed-share 0.95`;
   - AS: both.
   Time one epoch per new setting first (WO17 ~65 s/epoch at 8 threads); report the projection; run A1, S1, AS as one detached unit.
   Untrained and kappa0 controls are not needed.
3. **Measure, per setting B, A1, S1, AS** (one script `scripts/body/acc_probe_report.py`, new file, applied identically to all four, from
   the held-out rollouts):
   - share of control steps on each cap, per joint: acceleration cap and speed cap separately (as `s0_ceiling.py` defines it);
   - **realised** joint speed and acceleration (from the simulated q, at 100 Hz and 50 Hz), p99 and max per joint, each as a share of the
     joint's limit above; flag any setting with any joint > 1.0x;
   - occupied cells (5 cm grid, equal durations) and cell entropy;
   - between-episode JS and the half-episode JS control (the held-out episodes stand in for songs; log FOR USER what an episode's source
     is in `toy.npz`, and whether two episodes can share a source);
   - decoding: argmax ext and int (a), as in `m3f_gate17.py`;
   - hand metrics: e'1 (hand acc p99), e'2 (share hand speed > 1 m/s), hand speed p99/max, floor breaches, end-stop events, contact share.
4. **Report** `/secondary/hyst-data/body/acc/report.json` + `.txt` (one table, four columns), night log, push, and tell the overseer: the
   table, which settings break a joint limit, wall time. No recommendation beyond "within / outside the limits".

## Done when

`body-acc` pushed (options + bit-identity test + report script + night log); runs in `/secondary/hyst-data/body/acc/{A1,S1,AS}/`;
`report.json`.
