# Builder prompt: work order 16, diagnosis of the parked (elbow-stop slump) behaviour in the WO15A toy seeds (2026-11-07)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below. **Analysis only: no training, no new cost, no change to any training path.**

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo16-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` first.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_body-m3f.md` (append a "Work order 16" section; MORNING SUMMARY on top), pushed after every phase.
- **Worktree: none new.** Stay in the worktree your session is pinned to (`/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f`), absolute paths. `git fetch origin && git merge origin/body` into `body-m3f` first (body with BRAIN_SPEC 7.31 or later). Push `body-m3f`.
- **Your share: 6 threads, 10 GB.** Environment `/secondary/hyst-env/body`. Output under `/secondary/hyst-data/body/m3f/rerun3/diag/`.
- New files only (e.g. `scripts/body/m3f_park_diag.py`, a test). If you need extra logging inside the simulation, add it behind a new
  default-off flag and prove with a test that the default rollout is bit-identical.

## Read first

`docs/BRAIN_SPEC.md` §7.24 (body, movement changes), §7.27-7.31 (**7.31 = this order**), `docs/PLANNER_BRIEF_WO15_RESULTS.md` (results,
the user's verdict, hold stretches in 2.4), `docs/NIGHT_LOG_body-m3f.md` (WO14A-WO15B). Code: `scripts/body/m3f.py` (`rollout`,
`score_policy`), `m3f_jax.py` (`arm_step`: target clip CLIP_MARGIN_DEG inside the range + hard end stop after every substep; the
generators / CPG, kappa, programs, observers), `m3f_report.py`, `m3f_endstop.py`, `make_arm_v2.py` (geoms, contype/conaffinity, raised plane).

## Data

- Seeds: `/secondary/hyst-data/body/m3f/rerun3/seed{0,1}/try1/` (`ckpt.pkl` = trained policy, `result.json`, `rollouts/trained_argmax_4.npz`
  = the scored held-out argmax rollout: `q` (16 episodes, 120 blocks, 50 steps, 5 joints) deg at 100 Hz, plus `pi`, `logits`, `kappa`,
  `desc`, `idesc`, `feat`, `xin`, ...). Run options: `--body v2f --hard-clip --floor-acc-hinges --contact-tc 0.006 --raised-plane
  --w-floor 1.0`, jerk 0.03, switch 0.01.
- The saved rollouts lack pre-clip targets, generator state and contact forces. **Re-simulate the same held-out argmax rollouts
  deterministically with extra logging** (same checkpoint, options, seeds, chunking as the scoring run), and first prove the re-simulation
  reproduces the saved `q` (max abs difference; expect 0 or float noise, state it).

## Steps

1. **Holds.** For both seeds, all 16 held-out episodes: every stretch >= 2 s with a ranged joint (shoulder, elbow, wrist bend) on its stop
   (|q| within 0.05 deg of 110). List them (seed, episode, joint, side, start, end). Known ones: seed 0 ep 0 elbow 9.3-24.6, 29.0-32.1,
   40.7-45.1 s; ep 1 elbow 12.3-25.3, 31.2-44.1 s; seed 1 ep 1 elbow 44.6-56.6 s, shoulder ep 0 17-20 and 31-33 s, ep 1 14-19 s.
2. **Per hold stretch, report (7.31.1 points 1-6):**
   1. Clipping: pre-clip commanded target, generator centre and amplitude for the held joint (time series summary: mean, min, max); the
      share of hold time with the pre-clip target beyond the stop; whether the oscillator keeps swinging there (amplitude, phase advancing).
   2. Chosen stillness: share of hold time where the commanded target is inside the range with small amplitude (state your threshold).
   3. Contact: self-contacts (ball or links vs base column or other links) and table contacts during the hold, with normal forces (mean,
      max); whether the arm rests on something.
   4. End stop: end-stop events and velocity zeroing at onset and exit; number of stop hits during the hold (is the joint pinned by repeated
      hits?).
   5. Brain side: program chosen (argmax of `pi`) during holds vs outside (distribution), kappa during vs outside, and the inner-state
      targets (arousal, surprisal, L3 order parameter; name the fields you use) during vs outside.
   6. Observer: decoding (a) inside holds vs outside (per-block decoder error or gap, both decoders), i.e. is the parked pose an easy code.
3. **Verdicts:** one line per hypothesis, supported / not supported, with the number that decides it:
   (H1) clipping: the policy commands beyond the stop and is clipped; (H2) chosen stillness; (H3) resting on a contact; (H4) pinned by
   repeated stop hits; (H5) tied to a program or brain state; (H6) the parked pose is an easy code for the observer.
4. Write `/secondary/hyst-data/body/m3f/rerun3/diag/summary.json` (per stretch and pooled) and the night-log section; push; report to the
   overseer; stop.

## Done when

Re-simulation reproduces the saved rollouts (stated); every hold stretch has points 1-6; six verdict lines; tests for any new flag pass and
the default paths stay bit-identical; branch pushed; report sent. Nothing trained, nothing launched.

## Addendum WO16b (user, 2026-11-07; BRAIN_SPEC 7.31.5) — run after WO16, same rules (analysis only)

Reuse the WO16 re-simulation; extend the default-off diag logging if needed (default path bit-identical, test it).
1. **Clip-boundary holds:** also list every hold >= 2 s with a ranged joint within 1 deg of the target-clip boundary (110 -
   CLIP_MARGIN_DEG = 109.5 deg), separately from the holds on the stop itself. In point 1 (clipping), report "beyond the stop" as beyond the
   clip boundary (109.5).
2. **H7, torque saturation / gravity:** per hold, the actuator torque (or force) of the held joint and of the shoulder vs the provisional
   stall torque 2.94 N m: share of hold time at or above saturation (state how torque is read from MuJoCo: `actuator_force`, gear, limits),
   and whether the joint is pushed into the stop by gravity rather than commanded there (e.g. the commanded target vs the stop, the sign
   of the gravity torque `qfrc_bias` on that joint, and what the joint does if the command were held 5 deg inside: optional quick test).
3. **H1b, network saturation:** per hold, whether the motor cortex's centre and amplitude outputs for the held joint sit at their output
   bounds (share of hold time within 2 % of a bound; name the output and its bounds, e.g. u in [0, 1] before the prototype map).
4. Verdict lines become H1, H1b, H2-H7 (one line each, supported / not supported, with the deciding number). Update `diag/summary.json`
   and the night log; push; report; stop.
