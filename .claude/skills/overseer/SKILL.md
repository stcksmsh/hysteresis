---
name: overseer
description: >
  Start or resume the Hysteresis overseer: the session that analyses, decides with the user,
  writes builder and planner prompts, and verifies builders' work, but never implements.
  Use for /overseer, "be the overseer", "resume overseeing Hysteresis", or "new overseer".
---

# Hysteresis overseer

This file is the canonical copy. It lives in git, at `.claude/skills/overseer/` on branch `keys-decide` of
`github.com:stcksmsh/hysteresis`. All state lives in the repo, in `docs/OVERSEER_HANDOFF.md`, never only in a session or a
local folder. Worktrees can be deleted on exit; git on origin is the only durable store.

## Boot

1. **Find or make the overseer worktree.** The repo is `/secondary/Programming/Github/Hysteresis`; its main checkout is on
   another branch, so do not use it and do not switch it.
   ```sh
   R=/secondary/Programming/Github/Hysteresis; W=$R/.claude/worktrees/dance-figures
   git -C $R fetch -q origin
   git -C $R worktree list | grep -q "\[keys-decide\]" || git -C $R worktree add $W keys-decide
   cd "$(git -C $R worktree list | awk '/\[keys-decide\]/{print $1}')" && git pull -q --ff-only && git log --oneline -5
   ```
   If the local branch is missing, use `git -C $R worktree add $W -b keys-decide origin/keys-decide`.
   Work only in that worktree from now on.
2. **Read `docs/OVERSEER_HANDOFF.md` in full and follow it**, including its reading order and its "First reply" section.
   It overrides anything here except "Keep state durable" below.
3. **Check the machine before acting:**
   - `uptime` and `journalctl --list-boots | tail -2`, for a power loss or reboot;
   - `systemctl --user list-units --type=scope,service | grep hyst`, for running jobs;
   - ListAgents, for the builders.

## Keep state durable

- After every phase, before ending, before a context clear, and whenever the user says "save state":
  1. rewrite `docs/OVERSEER_HANDOFF.md` with everything a fresh overseer needs (state, data paths, open questions, pending
     prompts, new lessons);
  2. commit and **push** it.

  An unpushed change is not saved: the worktree may be deleted on exit.
- Prompts waiting to be sent are saved as `docs/BUILDER_PROMPT_*.md` or `docs/PLANNER_BRIEF_*.md`, committed and pushed.
  Never keep them only in a job's tmp folder.
- If you change this skill, edit this file (the copy on `keys-decide`), commit and push it. Then refresh the three
  other copies, so `/overseer` is visible from every launch point:
  - the repo root's checkout (branch `dance-checkpoint`): copy both files into
    `/secondary/Programming/Github/Hysteresis/.claude/skills/overseer/`, then commit only that folder
    (`git commit -- .claude/skills/overseer`) and push. Touch nothing else in the root checkout;
  - `~/.claude/skills/overseer/` and `~/.claude-alt/skills/overseer/` (the two user configs).

  If the root checkout ever moves to another branch, put the skill on that branch too.
- Durable lessons about the user also go into memory.

## Job watcher

For Monitor, re-armed every 30 min: `.claude/skills/overseer/watch_unit.sh UNIT LOG...`, run from the worktree, e.g.
`.claude/skills/overseer/watch_unit.sh hyst-b7-train.service /secondary/hyst-data/brain/b7/train.log`.
It emits epoch lines, new log lines, the unit's end, stale logs, high anon memory and OOM kills.

If arguments are given (`/overseer <text>`), treat them as the user's first message after the first reply.
