# Builder prompt: work order 4, builder 3, the H3 toy (blend memory) (2026-11-04)

You are a builder for Hysteresis. Work alone and unattended. Never wait for input: take the named default and log "FOR USER".

## Where and how

- Repo `/secondary/Programming/Github/Hysteresis` (remote is HTTPS with the gh login; plain `git push` works; retry on a GitHub server error).
  `git fetch -q origin`, then: `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-h3 -b body-h3 origin/body`.
  Work only there; push `body-h3` after every phase. Never touch `body`, `keys-decide`, `master` or the main checkout. Other builders work on
  `body-m3c` (`scripts/body/`) and `body-fallback` (`scripts/author/`, `crates/`, `scripts/brain/brain_mindstate.py`, `braindump.py`): do not
  edit those. Changes to `core_b7.py` go behind default-off flags; every existing test passes unchanged.
- Commit messages: plain prose, **no co-author or attribution lines of any kind**.
- Frozen `src/` and `tools/` read-only. Never drive hardware. Environment `/secondary/hyst-env/brain`; install nothing. Data under
  `/secondary/hyst-data/brain/h3/`.
- **Your share: 4 threads, 5 GB.** Runs longer than 10 min through `scripts/compute/run_job.py`, detached and memory-capped
  (`systemd-run --user --unit=hyst-wo4b3-<fresh-name> -p MemoryMax=5G -p MemorySwapMax=0 <script>`), `python -u`, mains power only.
- Log: `docs/NIGHT_LOG_body-h3.md`, MORNING SUMMARY on top, updated after every phase. Usage limits may stop you; the overseer resumes you.

## Read first

1. `docs/BRAIN_SPEC.md` §7.15 (defines H3; binding), §7.10 (R1 pointer replay, R3 = the T1a + T1b bar), §7.14.
2. `docs/NIGHT_LOG_body-h2show.md` (H2: the code, tries, baselines: untrained H2 passes T1a on all three designs; the oracle passes T1b) and the H1
   section of `docs/NIGHT_LOG.md`.
3. `scripts/brain/hippo_h2.py`, `toy_h2.py`, `test_h2.py`, `core_b7.py`, `toy_b7.py`.

## The work (§7.15, exactly)

- H2's fixed sparse random code and one-shot store, unchanged and untrained.
- The hippocampus's own prediction per layer: the replayed horizon targets from the top-k sources (B7's pointer replay, the oracle's path).
- Final prediction per layer: w = sigmoid(a·(recognition − b)); mean = (1 − w)·cortex + w·replay; variance blended the same way (state the exact
  variance formula before the first run). **Only a and b, per layer, are trained.** The cortex is unchanged (on the toy: the toy cortex is first
  trained exactly as in H2's toy with the hippocampus off, then frozen; state this in the log).
- Unit tests: no gradient reaches the code, the cortex or anything but a and b; w → 0 recovers the cortex prediction exactly; storage one-shot;
  17 s eligibility.
- Citation: kNN-LM (Khandelwal et al. 2020). Record the full reference, and check it against the paper if you can reach it offline; otherwise
  log "not verified".

## Bar and tries (fixed)

- T1a + T1b of §7.10 R3 on designs A, B and C, same toy settings and evaluation as H2. Also report the oracle and the cortex-only baseline.
- Two tries, 3 h box each. Try 2 may change only the toy's training of a and b (learning rate, steps, initial b) and H2's k / temperature, named
  before the run.
- If it passes: stop and report (C1–C3 on held-out songs is a separate order). If both tries fail: log it; the hippocampus stays off.

## Finish

Fill the MORNING SUMMARY and report to the overseer in a few lines: T1a and T1b per design and try; learned a and b per layer; oracle and
cortex-only baselines; unit tests; the citation status; FOR USER items; branch, last commit. Never say something looks better. Do not edit
`docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md`, `docs/WORK_ORDER_*.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`.
