# Builder prompt: work order 13B, the M3e toy with the new body and the movement changes (2026-11-06)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo13-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable (`systemctl --user freeze/thaw`), stoppable (`systemctl --user stop`, checkpoint, clean exit), restartable with one command without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` before launching.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated and pushed after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- Never say something looks better; no claims beyond a passed check. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
- One arm, always: never a hexagon, ring or ensemble as a target (the v47 hexagon files are only a reference).
- Worktree: new `.claude/worktrees/body-m3f`, branch `body-m3f` from `origin/body` (9acbf19 or later). **Your share: 8 threads, 14 GB.**
  Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3f/`.
- Keep every existing result reproducible: the old body and the M3e/K5 code paths must stay bit-identical by default (new behaviour behind
  new files or off-by-default options; test that M3e try 1's first epoch is unchanged). New code goes in new files (e.g. `m3f.py`,
  `m3f_jax.py`, `make_arm_v2.py`) importing the old ones where possible.

## Read first

`docs/BRAIN_SPEC.md` §7.24 (binding: the whole section, including the overseer's defaults), §7.23, §7.19 (toy bar, argmax, WO7 observer
procedure), §7.20, §7.21; `docs/NIGHT_LOG_body-m3e.md` (M3e try 1, controls, ablations, WO11 seed 2: the recipe, chain scripts, bar);
`docs/NIGHT_LOG_body-k5video.md` (the try 1 floor and speed breaches); `scripts/body/make_arm.py`, `arm_sim.py` (`floor_margin`, the
check-csv floor rule: points 1-4 clear z = 0 by 0.05 m, the hand by 0.11 m), `m3e.py`, `m3e_jax.py`, `cpg.py`, `bdesc.py`, `run_m3e.py`,
`chain_wo11.py`; `crates/hyst-compile/src/body.rs` (`HAND_MPS`, `JOLT_MPS2`, `LIMITS`, joint ranges) and `score_csv.rs` (the check).

## The work

1. **New body (§7.24 Body).** Table plane at z = 0 with contact; self-collision on (all links, base column, mirror ball, with the
   geometry the rig and check-csv use); joint ranges as in the rig; a small cost for time within 10 deg of any joint limit; check-csv's
   hand-speed and jolt limits as soft penalties (hinge on the excess), each normalised by its value for the untrained policy on the
   calibration episodes and weighted like the energy term (same lambda). Tests: a pose through the table is pushed out by contact; a
   self-intersecting pose collides; the penalties are 0 inside the limits. **Measure first** the cost per M3e epoch with contact (MJX) and
   project K5-pass2's one pass (K5 try 1: 61.1 s per round, 977 rounds, 13.15 h); write it in the night log and report it to the overseer
   before the grid if the projection is above 22 h (the 24 h box).
2. **Movement changes (§7.24 Movement 1-4)**, each behind its own switch so it can be ablated: (1) minimum-jerk cost, mean squared joint
   jerk, normalised by the untrained policy's value; (2) observers read descriptors from joint trajectories low-passed at 10 Hz, jerk-based
   descriptors removed from both observers' inputs (list which ones); (3) the L3 phase estimate low-passed (tau 0.2 s) and coupling strength
   multiplied by the L3 order parameter, kappa still learned; (4) program crossfade over 0.75 s between the old and new programs' generator
   settings, plus a cost per switch.
3. **Grid on the tune episodes** (M3e recipe otherwise: lambda 0.03, lr 1e-3, 40 epochs, seed 0): jerk weight {0.01, 0.03, 0.1} x switch
   cost {0.01, 0.05} (both in the energy term's normalised units). Bar (e) uses `scripts/body/hf_share.py` (written by work order 13A,
   branch `body-hf`; merge it from origin when it lands) and the reference `docs/hf_v47_reference.json`: mean (e) over the episodes <=
   1.25 x the mean of v47's three per-song values. Selection: the §7.24 rule (passes the toy bar and (e) on tune, highest external (a),
   ties to the smaller weights). State the selected point before the held-out run.
4. **Try 1 on the held-out episodes** with the selected point: the toy bar exactly as M3e (external and internal (a), (b), (c), argmax for
   the bar, sampled reported) plus (e). WO7 controls reported: untrained policy and kappa = 0 (paired intervals, 10,000 resamples). Report
   check-csv-style breaches (floor margin, hand speed, jolt, joint range) on the held-out rollouts with the same thresholds.
   Try 2 only if try 1 fails, changing only what the failure names; then the same report.
5. **Report only:** per-change ablation of movement changes 1-4 on (e) (each switched off alone, selected weights otherwise), with (a) too.

## Done when

Tests committed and passing (new body, penalties, each movement switch, old-path bit-identity); the contact cost and pass2 projection in
the log; grid table, selected point, try 1 (and try 2 if run) with bar verdict per component, controls, breaches, and the ablation table
in `/secondary/hyst-data/body/m3f/summary.json` and the night log MORNING SUMMARY. Branch pushed. Then report to the overseer.
