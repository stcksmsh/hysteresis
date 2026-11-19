# WO53 part A: split between two builders (2026-11-19)

Read `docs/BUILDER_PROMPT_WO53_MISMATCH.md` in full first (header rules, reading list, Part A items 1-4). This file only splits Part A and
overrides its cores and branches. Binding ruling: `docs/BRAIN_SPEC.md` 7.84 item 1 and 7.85. Part B is done; ignore it.

## Agent 1: material (Part A items 1 and 2, and the order checks of item 1)
- Branch `body-mismatch` from `origin/body` (current worktree, absolute paths, no new worktrees).
- Cores `taskset -c 6-13`. Units `hyst-wo53a-<fresh>`, MemoryMax 8G.
- Write and PUSH `docs/MISMATCH_RULES.md` first, within about 30 minutes, including the exact key.json schema and the answers.csv layout
  (agent 2 codes the scorer against them). Then build pairs, render the 20 + 5 clips, run the clip and order checks, build the session
  (do not serve it). Push before every run.
- Item 4's pair-building tests are yours.

## Agent 2: scorer (Part A item 3 and the scorer tests of item 4)
- Wait until `docs/MISMATCH_RULES.md` is on `origin/body-mismatch` (poll `git fetch origin` every 5 minutes with the Monitor tool; do
  nothing else meanwhile). Then branch `body-mismatch-score` from `origin/body-mismatch`, in your current worktree, absolute paths.
- Cores `taskset -c 14-15`; light work. Write `scripts/body/mismatch_score.py` and its tests exactly as item 3 says, against agent 1's
  schema. If the schema is ambiguous, write the ambiguity into your report as FOR USER and take the most literal reading; do not message
  agent 1.
- Push `body-mismatch-score`; agent 1 does not touch the scorer files, you do not touch the rules note or the clips.

Both: plain commit messages, no attribution lines. No serving, no installs. When done stop every Monitor and send ONE final report.
The overseer merges both branches into `body`.
