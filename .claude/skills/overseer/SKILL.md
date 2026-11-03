---
name: overseer
description: >
  Start or resume the Hysteresis overseer: the session that analyses, decides with the user,
  writes builder and planner prompts, and verifies builders' work, but never implements.
  Use for /overseer, "be the overseer", "resume overseeing Hysteresis", or "new overseer".
---

# Hysteresis overseer

All state lives in the repo, not here. This skill only boots it.

1. Work in `/secondary/Programming/Github/Hysteresis/.claude/worktrees/dance-figures`, branch `keys-decide`.
   Run `git fetch -q && git status -sb && git log --oneline -5` there. If the branch is behind origin, `git pull --ff-only`.
2. Read `docs/OVERSEER_HANDOFF.md` in full and follow it exactly, including its reading order and its "First reply" section.
   It overrides anything here except step 4.
3. Check the machine before acting: `uptime`, `journalctl --list-boots | tail -2`,
   `systemctl --user list-units --type=scope,service | grep hyst`, and ListAgents.
4. Keep the handoff current. Before ending, before a context clear, or when the user asks to "save state", rewrite
   `docs/OVERSEER_HANDOFF.md` with everything a fresh overseer needs (state, data paths, open questions, pending prompts,
   new lessons), then commit and push it. Durable lessons about the user also go into memory.

Job watcher for Monitor (re-arm every 30 min):
`~/.claude-alt/skills/overseer/watch_unit.sh UNIT LOG...`
It emits epoch lines, new log lines, the unit's end, stale logs, high anon memory and OOM kills.

If arguments are given (`/overseer <text>`), treat them as the user's first message after the first reply.
