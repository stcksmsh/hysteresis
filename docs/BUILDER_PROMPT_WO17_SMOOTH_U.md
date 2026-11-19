# Builder prompt: work order 17, smooth u outputs (no zero-gradient clips), two-seed toy rerun with the parking gate, clips (2026-11-08)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo17-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable, stoppable, restartable without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` first.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_body-m3f.md` (append "Work order 17"; MORNING SUMMARY on top), pushed after every phase.
- **Worktree: none new.** Stay in `/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f`, absolute paths. `git fetch origin && git merge origin/body` into `body-m3f` first (body with BRAIN_SPEC 7.32 or later). Push `body-m3f`.
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3f/rerun4/seed{0,1}/`, clips under `rerun4/clips/`.
- Every earlier path (M3e/K5, WO13B-WO16b) stays bit-identical with the new option absent: new behaviour behind a new option; test it.

## Read first

`docs/BRAIN_SPEC.md` §7.27-7.32 (**7.32 = this order**; 7.30.3 gate, 7.31.2 parking gate), `docs/PLANNER_BRIEF_WO16_RESULTS.md` and
`_WO16B_RESULTS.md` (the saturation chain), `docs/NIGHT_LOG_body-m3f.md` (WO15A-WO16b). Code: `scripts/body/m3f_jax.py` `block_fn`
(`u = jnp.clip(pi @ sigmoid(theta) + J.MOD * tanh(amod), 0, 1)`), `scripts/body/m3d_jax.py` `to_command`/`cpg_*` (centre = CLO + u[2]
(CHI - CLO); bend amplitude cap CHI - |centre|), `m3f_park_diag.py`, `m3f_endstop.py`, `m3f_gate.py`, the WO15B clip script.

## Steps

1. **Option `--smooth-u`** (default off):
   - Every u output: replace the hard clip to [0, 1] by a smooth, strictly monotone map of the unclipped sum s into the open interval
     (0, 1) (e.g. 0.5 + 0.5 tanh((s - 0.5) / 0.5), slope 1 at 0.5; state your choice). Bounds unchanged, never reached exactly.
   - Centres of the three bend joints (shoulder, elbow, wrist bend): map into +-(110 - A_min), A_min = 10 deg (so centre in (-100, 100),
     amplitude cap >= 10 deg). Continuous joints keep their current centre range. No hard clip anywhere on the u -> centre/amp/freq/lag path.
   - Keep `--hard-clip` (target clip + end stop) as the physical backstop.
   - Tests: default off bit-identical (WO15A seed 0 first epoch); gradient of the loss (or of each u) w.r.t. the unclipped sum is non-zero at
     and beyond the old bounds (s = -0.2, 0, 1, 1.2); bend centres never reach +-100.
2. Push the code. Then **toy try 1 on seeds 0 and 1**, sequential, same recipe as WO15A plus `--smooth-u`: `--body v2f --hard-clip
   --floor-acc-hinges --contact-tc 0.006 --raised-plane --w-floor 1.0`, jerk 0.03, switch 0.01. WO7 controls per seed. ~1 h 20 min each.
3. **Gate per seed** (extend `m3f_gate.py`): 7.30.3 (bar (a) ext/int, (b), (c), (e'1) <= 6.001, (e'2) <= 0.01101, floor-margin breaches in
   <= 2 of 16 episodes) **plus 7.31.2**: no ranged joint on a stop (|q| within 0.05 deg of 110) for more than 10 % of the time, and no single
   stop-hold longer than 5 s. Report-only: share of time on a stop per joint, longest stop-hold, longest hold of ANY pose (hand speed
   < 2 cm/s), clip-boundary holds (as WO16b), program counts and top share, trained - kappa0 paired (argmax and sampled), end stops.
4. **Clips** of both seeds (60 s, held-out episodes 0 and 1, same as WO15B; argmax scored rollout; 1080p + 720p < 30 MiB + one 720p
   side-by-side per episode, seed 0 left, seed 1 right), into `rerun4/clips/`, **whatever the gate result**. Silent (toy input).
5. **Report to the overseer immediately when the gate verdict for both seeds is known** (PASS/FAIL per seed, the numbers), before or while
   rendering the clips: if both pass, pass2 launches at once (agent 1) while you render. Then report the clips. Then stop.

## Done when

Tests committed and passing; both seeds' results, gates, controls and report-only lines in `rerun4/summary.json` and the night log; clips
rendered; branch pushed; both reports sent. Nothing else launched.
