# Builder prompt: work order 14A, toy try 1 rerun with the floor-margin and hand-acceleration hinges and the hard joint clip (2026-11-07)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo14-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable (`systemctl --user freeze/thaw`), stoppable (`systemctl --user stop`, checkpoint, clean exit), restartable with one command without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` before launching.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated and pushed after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- **Worktree: none new.** Stay in the worktree your session is pinned to (`/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f`), absolute paths. `git fetch origin && git merge origin/body` into `body-m3f` first (body f44a196 or later). Push `body-m3f`.
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3f/rerun1/`.
- The M3e/K5 paths and M3f's current defaults (the WO13B try 1 result) must stay reproducible: new behaviour behind new options; test it.

## Read first

`docs/BRAIN_SPEC.md` §7.27 (binding), §7.26, §7.25, §7.24; your own `docs/NIGHT_LOG_body-m3f.md` (WO13B); `scripts/body/m3f.py`,
`m3f_jax.py` (`penalties`), `m3f_report.py` (check-csv thresholds), `arm_sim.py` (`limit_target`: today only two bends are clipped).

## The work

1. **Floor-margin hinge** (§7.27 point 1): penalty on the amount by which check-csv's floor margin is negative (points 1-4 above z = 0 by
   0.05 m, the hand by 0.11 m; same geometry as `m3f_report.py`), mean hinge per block. **Hand-acceleration hinge:** penalty on hand
   acceleration magnitude above 4.8 m/s2 (hand = last FK point, 50 Hz as in (e'1)), mean hinge per block. Both normalised exactly like the
   hand-speed hinge (by the untrained policy's value on the OLD body, with the same floor rule your FLOORS use if that value is 0; state the
   values), inside LAMBDA x (...), **weight 1 each, fixed**. Name the weights in code as the §7.26 round-2 knobs.
2. **Hard clip** (§7.27 point 2): the commanded target is clipped to the rig range for every ranged joint (not only the two bends), in the
   new body path only. Test: a target beyond a limit never yields a joint position beyond it (state the max excess over a test episode).
3. **Rerun toy try 1** with the WO13B selected point (jerk 0.03, switch 0.01), seed 0, same recipe, held-out 16 episodes: the toy bar
   (ext/int (a), (b), (c)) plus (e'1), (e'2), argmax for the verdict, sampled reported; (e), table-contact share, the check-csv-style
   breaches, and **per joint the share of time within 2 deg of a limit**. WO7 controls again (untrained, kappa = 0; paired, 10,000
   resamples). This is an engineering rerun under the same bar, not a new try (§7.27 point 1).
4. Write `/secondary/hyst-data/body/m3f/rerun1/summary.json` and the night log; push. If the rerun fails any bar component, stop and report.

## Done when

Tests for both hinges, the hard clip and old-path bit-identity pass and are committed; the rerun result, controls, breaches and
near-limit shares are in the summary and the night log MORNING SUMMARY; branch pushed. Then report to the overseer.
