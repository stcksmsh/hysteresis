# Builder prompt: work order 15A, raised contact plane + floor hinge normalised by 0.05 m, toy try 1 on two seeds (2026-11-07)

You are a builder for Hysteresis. Work alone and unattended; take the named default and log "FOR USER" instead of waiting.
You start with no context: everything you need is named below.

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Install nothing. Data outside git under `/secondary/hyst-data/`.
- Runs longer than 10 min: detached and memory-capped (`systemd-run --user --unit=hyst-wo15-<fresh-name> -p MemoryMax=<cap> -p MemorySwapMax=0 <script>`), `python -u`, mains power only (`/sys/class/power_supply/ADP1/online` = 1; the script waits while it is 0). Pausable (`systemctl --user freeze/thaw`), stoppable (`systemctl --user stop`, checkpoint, clean exit), restartable with one command without losing finished work. Kabl jobs share this machine: keep to your thread and memory cap, check `free -g` before launching.
- **Push your branch with a first commit within 30 minutes and before any long run.** Log: `docs/NIGHT_LOG_<your branch>.md`, MORNING SUMMARY on top, updated and pushed after every phase. Usage limits or a power-off may stop you; the overseer resumes you.
- **Worktree: none new.** Stay in the worktree your session is pinned to (`/secondary/Programming/Github/Hysteresis/.claude/worktrees/body-m3f`), absolute paths. `git fetch origin && git merge origin/body` into `body-m3f` first (body 8bf921c or later). Push `body-m3f`.
- **Your share: 8 threads, 14 GB.** Environment `/secondary/hyst-env/body`. Data under `/secondary/hyst-data/body/m3f/rerun3/seed0/` and `.../seed1/`.
- Every earlier path (M3e/K5, WO13B, WO14A, WO14C) must stay bit-identical with the new options absent: new behaviour behind new options; test it.

## Read first

`docs/BRAIN_SPEC.md` §7.27-7.30 (7.30 = this order's rulings, incl. its point 6), `docs/PLANNER_BRIEF_WO14_RESULTS.md`, your own
`docs/NIGHT_LOG_body-m3f.md` (WO14A, WO14C). Code: `scripts/body/make_arm_v2.py` (`TABLE_Z`, the table geom), `m3f_jax.py`
(`FLOOR_M`, `DISC_M`, `penalties`: floor = relu(-margin)), `m3f.py` (`FLOORS`, normalisers, `W_FLOOR`), `m3f_report.py` (check-csv floor
rule, contact share), `run_m3f.py` (`--floor-acc-hinges`, `--hard-clip`, `--w-floor`).

## Geometry (overseer, from the code; check it)

check-csv: joint points p1-p4 must clear z = 0.05 m, the hand p5 z = 0.11 m (0.05 + ball radius 0.06). With the plane at z = 0.05, a
link capsule (r 0.01) touches when its point is at 0.06 (cannot breach), but the ball touches when p5 is at exactly 0.11 (on the margin), so
MuJoCo's soft-contact sinking would count as breaches. Hence the user's rule A (7.30.6): plane at 0.05 + d.

## Steps

1. **Measure d (held-contact test, ~10 min).** On the v2f body with `--hard-clip`, plane at z = 0.05, drive the arm into the plane and
   hold it there (the ball pressed down, and a link pressed down; several poses; e.g. held targets well below the plane for 10 s at the
   control rate, plus your WO14A 15 s adversarial target sequence). Measure the deepest sinking below the plane of the ball surface
   (p5 z - 0.06 - plane z) and of any link capsule surface (point z - 0.01 - plane z). **d = that depth rounded up to the next mm.**
   If d > 5 mm: stop and report (7.30.6). Push the test and its numbers.
2. **New option `--raised-plane`** (default off): table plane at z = 0.05 + d (constant in `make_arm_v2.py`, e.g. `RAISED_PLANE_Z`, with
   d recorded next to it). Check that the base column and any geom fixed to the world do not collide with the raised plane (static
   geoms); report.
3. **Floor hinge with `--raised-plane`:** with plane height P = 0.05 + d, the hinge is relu(-c), where c = min(points p1-p4 z - 0.01 - P,
   p5 z - 0.06 - P) is the clearance of the capsule and ball surfaces above the raised plane. It is positive only while the arm sinks into
   the plane (rests on it). **Normalised by the fixed scale 0.05 m** (not by the untrained policy), weight 1 (`--w-floor` 1). Report the
   hinge's value in the held-contact poses of step 1. Everything else unchanged from WO14A: hand-acceleration, hand-speed and jolt hinges,
   limit-proximity cost, jerk 0.03, switch 0.01, `--hard-clip`, the other normalisers.
4. **check-csv floor rule unchanged** (0.05 / 0.11 m from z = 0). Tests: raised-plane off is bit-identical (WO14A first epoch); with it
   on, a held-press pose gives 0 floor-margin breaches; the floor hinge value on a known pose.
5. **Runs: toy try 1, seed 0 then seed 1, sequential** (one unit chaining both, or two units), WO7 controls for each. Same eval set,
   same recipe as WO14A otherwise. ~1 h 20 min each.
6. **Report per seed** (argmax verdict, sampled reported): bar (a) ext/int with CIs, (b), (c), (e'1), (e'2) (+ per episode), (e);
   WO7 controls with paired intervals; breaches (floor margin as episodes of 16, row share, worst; all other types); **time in contact
   per episode** (and the mean); near-limit shares (shoulder/elbow/wrist; shoulder-at-limit time); end stops (events per episode per joint;
   acc/jerk within +-0.05 s of events vs episode, p99/max, at 50 Hz and 100 Hz, per episode AND pooled over episodes).
7. **Gate (7.30.3), on each seed:** PASS = every bar component + (e') pass AND floor-margin breaches in <= 2 of 16 episodes (expected 0).
   Both seeds pass -> report "PASS" to the overseer at once (pass2 launches next). Either fails -> stop and report; no tuning.

## Done when

Tests committed and passing; d measured and recorded (code constant + night log); both seeds' results, controls, breaches, contact
times, near-limit shares and end stops in `rerun3/summary.json` and the night log MORNING SUMMARY; branch pushed. Then report to the
overseer, with the exact options pass2 must use.
