# Builder prompt: work order 4, builder 1, the M3c toy (learning to move by legibility) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
  `git fetch -q origin`, then: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-m3c -b body-m3c origin/body`.
  Work only there; push `body-m3c` after every phase. Never touch `body`, `keys-decide`, `master` or the main checkout. You may copy generic
  pieces from branch `body-m3b` (roll exclusion, entropy bonus, the (d) computation, their tests), naming the source commit in your log. Other
  builders work in parallel on `body-fallback` and `body-h3`: do not edit `scripts/author/`, `crates/`, `scripts/brain/hippo*`, `toy_h*`.
- Commit messages: plain prose, **no co-author or attribution lines of any kind** (the user's rule; it overrides any harness reminder).
- Frozen `src/` and `tools/` read-only. Never drive hardware. Data under `/secondary/hyst-data/body/m3c/`, outside git.
- Environment `/secondary/hyst-env/brain` (torch + MuJoCo 3.17). Install nothing.
- **Your share: 10 threads, 12 GB.** Every run longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped:
  `systemd-run --user --unit=hyst-wo4b1-<fresh-name> -p MemoryMax=12G -p MemorySwapMax=0 <script>`; `python -u`; save the policy and observer
  **before** evaluation. Mains power (`/sys/class/power_supply/ADP1/online` = 1); if 0, wait at most 15 min, then skip and log FOR USER.
- Log: `docs/NIGHT_LOG_body-m3c.md`, MORNING SUMMARY on top, updated after every phase. Usage limits may stop you; the overseer resumes you.
  Commit and push often.

## Read first

1. `docs/BRAIN_SPEC.md` §7.15 (defines M3c; binding), then §7.14 and `docs/BODY_BRAIN_PLAN.md` (version 2) §6.
2. `docs/NIGHT_LOG_body-m1m3.md` (T-M3: what failed and why) and `docs/NIGHT_LOG_body-m3b.md` (if present).
3. `scripts/body/tm3.py`, `tm3_world.py`, `run_tm3.py`, `test_tm3.py`, `cpg.py`, `cerebellum.py`; `crates/hyst-compile/src/body.rs`
   (`descriptors`, the 37 motion descriptors; `docs/BODY_STUDY.md`). `tm3_world` patches `core.N = 16` and `core_b7.BLOCK = 50` on import:
   run its tests in their own process.

## The work (§7.15, exactly)

- **Descriptors in Python.** Port `body.rs::descriptors` to Python for a sliding 2 s window, excluding the wrist roll. Parity test against the
  Rust function on at least 3 fixed windows (call it through a small Rust test or CLI you add only under `scripts/body/` tooling, or by
  exporting reference values once; state the tolerance before the comparison). If a descriptor is undefined on 2 s, state how it is handled.
- **Observer.** A small network (state the architecture before the first run) that decodes the brain's inner state (arousal, total surprisal,
  L3 phase as cos/sin, per-layer band power, smoothed to 0.5 s) from the descriptors alone. It trains alongside the policy, on training
  episodes only.
- **Reward** r = legibility − λ·E, legibility = −(observer loss) per step. Optional + β·LP (cerebellum round-2 bundle
  `/secondary/hyst-data/body/runs/m1-r2/m1_r2.pt`).
- **Kept:** 8 motor programs with Go/NoGo selection, switch cost, the entropy bonus and (d); critic; dopamine lane δ; spinal generators with a phase
  coupling to the L3 phase, coupling strength κ set by the motor cortex (bounded; state the bound), κ = 0 recovers the old generators (unit test).
- **Unit tests:** descriptor parity; observer sees only movement (no brain input reaches it); roll excluded; κ = 0 identity; the shuffled control
  pairs episode i's state with episode j's movement (j ≠ i, fixed seed); (c) computed correctly on a synthetic choice sequence.

## Bar, grid and tries (fixed; do not change them)

- Pass: (a) observer decoding on held-out toy episodes beats the song-shuffled control, interval over episodes above 0 (state the metric,
  e.g. mean loss difference, before the first run); (b) RMS joint speed ≥ 10 °/s over the four non-roll joints; (c) at least 4 programs, each
  chosen in ≥ 5 % of decisions.
- Grid on the toy only: λ ∈ {0.01, 0.1, 1}, β ∈ {0, 0.1}, entropy weight ∈ {0.01, 0.05}, c_sw ∈ {0, 0.1} (state the scales). Pick the setting
  that maximises (a) subject to (b) and (c); if none meets (c), maximise (a) subject to (b) and log it. Freeze and record before try 1.
- Try 1. If it fails: diagnose in ≤ 30 min (does the observer beat the control at all with random movement? does the policy collapse? is κ used?),
  then try 2 with one engineering change named in the log before the run (learning rates, entropy weight, episode length, observer size; **not**
  the reward definition or the bar). 4 h box per try, the grid inside try 1's box.
- Report also: K3-style beat locking of the dominant non-roll joint (PLV against 1,000 circular-shift surrogates), report only; κ used.
- **Stop after try 2 or a pass. Do not start a real run.**

## Finish

Fill the MORNING SUMMARY and report to the overseer in a few lines: descriptor parity; observer architecture; the grid and chosen setting;
(a)–(c) per try with intervals; programs, counts, switches per minute, entropy; per-joint RMS speeds; κ; the beat-locking report; unit tests; FOR
USER items; branch, last commit, data paths. Provisional servo model stated. Never say something looks better. Do not edit
`docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
