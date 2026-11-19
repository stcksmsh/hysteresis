# Builder prompt: H1, the hippocampus, toy only (2026-11-03)

You are a builder for Hysteresis. Work alone, without waiting for input. This order is a toy test only: no long run, no corpus training.

## Where

- Repo: `/secondary/Programming/Github/Hysteresis`. Make your own worktree on a new branch `body-h1` from origin `body`:
  `git -C /secondary/Programming/Github/Hysteresis worktree add .claude/worktrees/body-h1 -b body-h1 origin/body`. Work only there.
  Never touch the main checkout, `keys-decide`, `master`, or another builder's branch (`body-z` may be in use in parallel: do not edit
  `train.py`, `core.py` or anything under `scripts/compute/` or `scripts/body/`).
- Commit messages: plain prose, **no co-author or attribution lines of any kind**.
- Frozen `src/` and `tools/` read-only. Environment `/secondary/hyst-env/brain`, unchanged; install nothing. Data under `/secondary/hyst-data/brain/h1/`.
- Any run longer than 10 min: detached and memory-capped,
  `systemd-run --user --unit=hyst-h1-<fresh-name> -p MemoryMax=12G -p MemorySwapMax=0 <script>`, `python -u`, 8 threads at most
  (another builder may be using the machine). Mains power for runs: check `cat /sys/class/power_supply/AC*/online`.

## Read first

1. `docs/BODY_BRAIN_PLAN.md` §1 (rules) and §5 (H1). §12 is the unattended template.
2. `docs/BRAIN_SPEC.md` §7.1, §7.3, §7.10 (R1 hippocampus design, R3 = the T1a + T1b bar), §7.11.
3. `scripts/brain/toy_b7.py`, `scripts/brain/core_b7.py` (the hippocampus behind the `hippocampus` flag, the `oracle` hook),
   `scripts/brain/test_core_b7.py`, `scripts/brain/B7_NOTES.md` and the toy part of `docs/NIGHT_LOG.md` (previous T1 results: trained T1b best
   ratio 0.61, oracle 0.348).

## The work (plan §5)

Two fixes, both in the toy:
- (a) **Hindsight retrieval loss.** Per read, find with no gradient the stored entry whose replay would have given the lowest prediction error,
  and train the query with cross-entropy toward it, weight 0.1.
- (b) **Scheduled sampling.** Start with the oracle pointer and hand over linearly to retrieval over the first 50 % of toy training.

Plus the **novelty lane**: every 0.5 s, 1 − max cosine against the store, no gradient, independent of the 2 s read. Report it on the toy
(during the repeat against outside it), no pass rule.

Keep changes behind flags so that with the flags off, `core_b7` and every existing test are unchanged (`cd scripts/brain &&
/secondary/hyst-env/brain/bin/python -m unittest` passes, about 150 tests).

## Bar and budget (fixed; do not change them)

- Bar: T1a and T1b of BRAIN_SPEC §7.10 R3, unchanged. T1a: during the repeat, ≥ 50 % of top-1 sources point into the first S and recognition
  is above the 95th percentile of non-repeat frames. T1b: error ratio (repeat / first) ≤ 0.5 on the iid-noise design and ≤ 0.5 on at least
  one of the two other designs.
- Two tries, 3 h time box each, wall time including runs. Try 2 may change only what try 1's failure names; write that down before try 2.
  State any number you choose (steps, learning rate, seeds) in the log before the run it governs.
- Report the oracle on the same toy for reference.
- If both tries fail: stop. The hippocampus stays off and the monitor never shows recall. Report why, with numbers.

## Log and finish

`docs/NIGHT_LOG.md`: a new dated H1 section with a MORNING SUMMARY on top, filled at the end. Report in a few lines: T1a and T1b numbers per
design and per try, oracle numbers, novelty-lane numbers, unittest count, what failed and why if it failed, branch and last commit. Push
`body-h1`. Do not edit `docs/BODY_BRAIN_PLAN.md`, `docs/BRAIN_SPEC.md` or `docs/NEXT_DECODER_THEN_BRAIN.md`. Never say something looks better;
no claims beyond the test.
