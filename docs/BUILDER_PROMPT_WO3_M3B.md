# Builder prompt: work order 3, builder 1, the M3b toy (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; if GitHub returns a server error,
  retry). `git fetch -q origin`, then make your worktree:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-m3b -b body-m3b origin/body`. Work only there. Push
  `body-m3b` after every phase. Never touch `body`, `keys-decide`, `master` or the main checkout. Builder 2 works in parallel on `body-fallback`
  (`scripts/author/`, `scripts/brain/brain_mindstate.py`, `crates/`, `scripts/compute/manifest.py`): do not edit those.
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Data under `/secondary/hyst-data/body/m3b/`, outside git.
- Environment `/secondary/hyst-env/brain` (torch + MuJoCo 3.17). Install nothing.
- **Your share: 12 threads, 14 GB.** Every run longer than 10 min through `scripts/compute/run_job.py`, as a detached memory-capped service:
  `systemd-run --user --unit=hyst-wo3b1-<fresh-name> -p MemoryMax=14G -p MemorySwapMax=0 <script>`; `python -u`; save the policy **before**
  evaluation (a run was lost to an OOM in evaluation last time). Mains power: `/sys/class/power_supply/ADP1/online` = 1; if 0, wait at most
  15 min, then skip and log FOR USER. No Kaggle in this order.
- Log: `docs/NIGHT_LOG_body-m3b.md`, MORNING SUMMARY on top, updated after every phase.
- Usage limits may stop you mid-task; the overseer will resume you. Commit and push often so nothing is lost.

## Read first

1. `docs/BRAIN_SPEC.md` §7.14 (the rulings that define M3b; binding), then `docs/BODY_BRAIN_PLAN.md` (version 2) §6 and §11.
2. `docs/NIGHT_LOG_body-m1m3.md` (T-M3: grid, try 1, try 2, the shifted-proprioception control, the collapse) and `docs/PLANNER_BRIEF_WO2_RESULTS.md`.
3. `scripts/body/tm3.py`, `tm3_world.py`, `run_tm3.py`, `test_tm3.py`, `cerebellum.py`, `m3_cortex.py`. Note: `tm3_world` patches `core.N = 16`
   and `core_b7.BLOCK = 50` on import, so run its tests in their own process.

## The work (BRAIN_SPEC §7.14 point 2, exactly)

Build M3b as new files or flags beside T-M3 (T-M3's code and results stay reproducible):
- **Reward** r = (S_shifted − S_moving) + β·LP − λ·E. S_shifted = the cortex fed the same episode's proprioception shifted by a random 2–8 s
  (fixed seeds; state the shift rule, e.g. circular within the episode, in the log before the first run). No S_still anywhere.
- **The wrist roll** is excluded from (b), from the dominant joint in (c), and from the proprioception into the cortex relay. It still costs energy
  and the cerebellum still sees it.
- **Selection:** an entropy bonus on the program choice (weight from the grid); report programs used, counts, switches per minute, entropy.
- **Toy cerebellum:** the K1 round-2 bundle `/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt` (the better one; T-M3 used round 1). Log it.
- **Unit tests:** S_shifted uses the same episode's proprioception with the stated shift; the roll is absent from the relay input and from (b)/(c);
  the entropy bonus enters the loss; identity at step 0; (d) is computed correctly on a synthetic choice sequence.

## Bar, grid and tries (fixed; do not change them)

- Pass = (a) mean S_shifted − S_moving > 0 with the interval over episodes above 0; (b) RMS joint speed ≥ 10 °/s over the four non-roll joints;
  (c) the dominant non-roll joint's velocity phase-locks to the pulse (PLV above 1,000 circular-shift surrogates, p < 0.01); (d) at least 4
  programs, each chosen in ≥ 5 % of decisions.
- Grid on the toy only: β ∈ {0, 0.1, 1}, λ ∈ {0.01, 0.1, 1}, c_sw ∈ {0, 0.1}, entropy weight ∈ {0.01, 0.05} (relative scales as in T-M3; state
  the entropy weight's scale before running). Pick the setting that maximises (a) subject to (b) and (d); if none meets (d), maximise (a) subject
  to (b) and log it. Freeze and record it before try 1.
- Try 1 with that setting. If it fails: diagnose in ≤ 30 min, then try 2 with one engineering change named in the log before the run (learning
  rate, entropy bonus weight, or episode length; **not** the reward definition or the bar). 4 h box per try, grid included in try 1's box.
- Also report the shifted-proprioception control's analogue: S_shifted − S_moving with a second, independent shift, so it is clear the reward is
  not a fixed artefact of one shift.
- **Stop after try 2 (or after a pass). Do not start a real M3b run.**
- Defaults: a unit test that cannot pass in 30 min, log it and skip what depends on it. If both tries fail, write it plainly: by §7.14, the
  self-driven body is closed for this plan.

## Finish

Fill the MORNING SUMMARY and report to the overseer in a few lines: the grid and the chosen setting; (a)–(d) per try with intervals and p;
programs used, counts, switches per minute, entropy; per-joint RMS speeds; the second-shift control; unit tests; FOR USER items; branch, last
commit, data paths. Provisional servo model stated. Never say something looks better. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`,
`docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
